"""Happy-path graph test with a fake LLM and a temp DB. No network, no API key."""
import sqlite3
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from config import settings as settings_module
from onboard_pilot.db import init_db
from onboard_pilot.graph import nodes
from onboard_pilot.graph.build import build_graph
from onboard_pilot.schemas import (
    AccessRequest,
    OnboardingState,
    EquipmentItem,
    IntakeForm,
    OnboardingPlan,
    OnboardingTask,
    ScheduledEvent,
)
from onboard_pilot.seed import seed_all

START = date(2026, 10, 19)


def good_plan(case_id="case-t1") -> OnboardingPlan:
    return OnboardingPlan(
        case_id=case_id,
        employee_summary="Junior engineer.",
        access_requests=[
            AccessRequest(system=s, justification="role baseline")
            for s in ("email", "slack", "gitlab", "vpn", "jira", "aws_dev")
        ],
        equipment=[
            EquipmentItem(catalog_id="EQ-001", name="ThinkPad T14", price_eur=1249),
            EquipmentItem(catalog_id="EQ-008", name="ASUS 24\" Monitor", price_eur=199),
            EquipmentItem(catalog_id="EQ-014", name="Keychron K8 Keyboard", price_eur=89),
        ],
        schedule=[
            ScheduledEvent(title=t, event_type=t, date=START, duration_minutes=30)
            for t in ("it_setup", "manager_1on1", "hr_intro")
        ]
        + [
            ScheduledEvent(title="Compliance", event_type="compliance_training",
                           date=START + timedelta(days=3), duration_minutes=60),
            ScheduledEvent(title="Security", event_type="security_training",
                           date=START + timedelta(days=5), duration_minutes=90),
        ],
        tasks=[OnboardingTask(title="Collect laptop", owner="it", due_date=START)],
        policy_citations=["§3.2", "§4.1"],
    )


class FakeStructuredLLM:
    def __init__(self, plan):
        self.plan = plan

    def invoke(self, messages):
        raw = SimpleNamespace(usage_metadata={"input_tokens": 1000, "output_tokens": 500})
        return {"raw": raw, "parsed": self.plan, "parsing_error": None}


class FakeLLM:
    def __init__(self, plan):
        self.plan = plan

    def with_structured_output(self, schema, include_raw=False):
        assert include_raw is True
        return FakeStructuredLLM(self.plan)


@pytest.fixture
def env(tmp_path, monkeypatch):
    s = settings_module.get_settings()
    monkeypatch.setattr(s, "db_path", tmp_path / "onboard.db")
    monkeypatch.setattr(s, "today_override", "2026-10-01")
    init_db(s.db_path)
    conn = sqlite3.connect(str(s.db_path))
    conn.row_factory = sqlite3.Row
    seed_all(conn)
    conn.close()
    monkeypatch.setattr(
        nodes, "_retrieve_policy", lambda form: ("§3.2 Budget caps ...", 0.7)
    )
    return s


def form(case_id="case-t1") -> IntakeForm:
    return IntakeForm(
        case_id=case_id, full_name="Eva de Boer", email="eva@example.com",
        role="software_engineer", level="junior", department="engineering",
        start_date=START, manager_email="anna.visser@corp.example",
        location="eindhoven_office", contract_type="permanent", visa_required=False,
    )


def run_graph(config=None):
    raw = build_graph().invoke({"case_id": "case-t1", "form": form()}, config or {})
    return OnboardingState.model_validate(raw)


def run_graph(config=None):
    raw = build_graph().invoke({"case_id": "case-t1", "form": form()}, config or {})
    return OnboardingState.model_validate(raw)


def count(db_path, table, case_id="case-t1"):
    conn = sqlite3.connect(str(db_path))
    n = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE case_id = ?", (case_id,)).fetchone()[0]
    conn.close()
    return n


def test_happy_path_auto_approved_and_writes_business_tables(env, monkeypatch):
    monkeypatch.setattr(nodes, "get_llm", lambda: FakeLLM(good_plan()))
    result = run_graph({"configurable": {"run_id": "run-test"}})
    assert result.status == "auto_approved"
    assert result.violations == []
    assert result.retry_count == 0

    db_path = env.db_path
    conn = sqlite3.connect(str(db_path))
    assert conn.execute("SELECT COUNT(*) FROM employees WHERE email='eva@example.com'").fetchone()[0] == 1
    conn.close()
    assert count(db_path, "equipment_orders") == 3
    assert count(db_path, "calendar_events") == 5
    assert count(db_path, "onboarding_tasks") == 1
    assert count(db_path, "outbox") == 1
    conn = sqlite3.connect(str(db_path))
    statuses = {r[0] for r in conn.execute(
        "SELECT status FROM access_requests WHERE case_id='case-t1'")}
    case = conn.execute("SELECT status, finalized_at FROM cases WHERE case_id='case-t1'").fetchone()
    conn.close()
    assert statuses == {"submitted"}
    assert case[0] == "auto_approved" and case[1] is not None


def test_audit_log_has_one_row_per_node(env, monkeypatch):
    monkeypatch.setattr(nodes, "get_llm", lambda: FakeLLM(good_plan()))
    result = run_graph({"configurable": {"run_id": "run-test"}})
    conn = sqlite3.connect(str(env.db_path))
    rows = conn.execute(
        "SELECT node, tokens_in, tokens_out, cost_eur, run_id FROM audit_log "
        "WHERE case_id='case-t1' ORDER BY id").fetchall()
    conn.close()
    assert [r[0] for r in rows] == ["intake", "plan", "execute_tools", "validate", "finalize"]
    plan_row = rows[1]
    assert plan_row[1] == 1000 and plan_row[2] == 500
    assert plan_row[3] == pytest.approx((1000 * 0.92 + 500 * 4.60) / 1_000_000)
    assert all(r[4] == "run-test" for r in rows)
    assert all(r[1] == 0 for i, r in enumerate(rows) if i != 1)
    assert [e["node"] for e in result.audit_events] == [r[0] for r in rows]


def test_parse_failure_yields_none_plan_after_one_retry(env, monkeypatch):
    calls = []

    class BadStructured:
        def invoke(self, messages):
            calls.append(1)
            raw = SimpleNamespace(usage_metadata={"input_tokens": 10, "output_tokens": 5})
            return {"raw": raw, "parsed": None, "parsing_error": ValueError("bad")}

    class BadLLM:
        def with_structured_output(self, schema, include_raw=False):
            return BadStructured()

    monkeypatch.setattr(nodes, "get_llm", lambda: BadLLM())
    plan, errors = nodes.generate_plan("sys", "user")
    assert plan is None and len(calls) == 2 and len(errors) == 2


def test_plan_node_forces_case_id_and_sets_rag_score(env, monkeypatch):
    monkeypatch.setattr(nodes, "get_llm", lambda: FakeLLM(good_plan(case_id="WRONG")))
    result = run_graph()
    assert result.plan.case_id == "case-t1"
    assert result.rag_min_score == 0.7


def test_execute_tools_replaces_proposed_rows(env, monkeypatch):
    monkeypatch.setattr(nodes, "get_llm", lambda: FakeLLM(good_plan()))
    f = form()
    conn = sqlite3.connect(str(env.db_path))
    conn.execute("INSERT INTO cases (case_id) VALUES ('case-t1')")
    conn.execute("INSERT INTO access_requests (case_id, system, justification, status) "
                 "VALUES ('case-t1','stale','x','proposed')")
    conn.commit()
    conn.close()
    state = OnboardingState(case_id="case-t1", form=f, plan=good_plan())
    out = nodes.execute_tools(state)
    assert len(out["tool_results"]) == 6 + 3
    conn = sqlite3.connect(str(env.db_path))
    systems = {r[0] for r in conn.execute("SELECT system FROM access_requests WHERE case_id='case-t1'")}
    conn.close()
    assert "stale" not in systems and "gitlab" in systems


def test_finalize_rolls_back_on_failure(env, monkeypatch):
    monkeypatch.setattr(nodes, "commit_events",
                        lambda *a, **k: SimpleNamespace(ok=False, error_message="boom"))
    conn = sqlite3.connect(str(env.db_path))
    conn.execute("INSERT INTO cases (case_id) VALUES ('case-t1')")
    conn.commit()
    conn.close()
    state = OnboardingState(case_id="case-t1", form=form(), plan=good_plan())
    with pytest.raises(RuntimeError):
        nodes.finalize(state)
    conn = sqlite3.connect(str(env.db_path))
    assert conn.execute("SELECT COUNT(*) FROM employees WHERE email='eva@example.com'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM equipment_orders").fetchone()[0] == 0
    conn.close()
