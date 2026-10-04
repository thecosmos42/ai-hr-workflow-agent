"""Validator tests: pure Python, no LLM, no network. today = 2026-10-01."""
import sqlite3
from datetime import date, timedelta

import pytest

from onboard_pilot.db import init_db
from onboard_pilot.schemas import (
    AccessRequest,
    EquipmentItem,
    IntakeForm,
    OnboardingPlan,
    OnboardingTask,
    ScheduledEvent,
    ToolResult,
)
from onboard_pilot.seed import seed_equipment_catalog, seed_managers
from onboard_pilot.validation.validators import (
    run_all_validators,
    violations_from_tool_results,
)
from onboard_pilot.validation.violations import SEVERITY, ViolationCode

TODAY = date(2026, 10, 1)
START = date(2026, 10, 20)
MANAGER = "anna.visser@corp.example"


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "t.db"
    init_db(db_path)
    c = sqlite3.connect(str(db_path))
    c.row_factory = sqlite3.Row
    seed_managers(c)
    seed_equipment_catalog(c)
    yield c
    c.close()


def make_form(**kw) -> IntakeForm:
    base = dict(
        case_id="case-1",
        full_name="Nina Test",
        email="nina@example.com",
        role="finance_officer",
        level="junior",
        department="finance",
        start_date=START,
        manager_email=MANAGER,
        location="amsterdam_office",
        contract_type="permanent",
        visa_required=False,
    )
    base.update(kw)
    return IntakeForm(**base)


def day1(start=START) -> list[ScheduledEvent]:
    return [
        ScheduledEvent(title=t, event_type=t, date=start, duration_minutes=30)
        for t in ("it_setup", "manager_1on1", "hr_intro")
    ]


def compliance(d=None) -> ScheduledEvent:
    return ScheduledEvent(
        title="Compliance", event_type="compliance_training",
        date=d or START + timedelta(days=5), duration_minutes=60,
    )


def security(d=None) -> ScheduledEvent:
    return ScheduledEvent(
        title="Security", event_type="security_training",
        date=d or START + timedelta(days=5), duration_minutes=60,
    )


def make_plan(form: IntakeForm | None = None, **kw) -> OnboardingPlan:
    """A clean plan for the default finance_officer form (no security training needed)."""
    base = dict(
        case_id="case-1",
        employee_summary="x",
        access_requests=[AccessRequest(system="email", justification="j")],
        equipment=[EquipmentItem(catalog_id="EQ-004", name="Dell XPS 13", price_eur=1199)],
        schedule=day1() + [compliance()],
        tasks=[],
        policy_citations=["§3.2"],
    )
    base.update(kw)
    return OnboardingPlan(**base)


def codes(violations) -> list[str]:
    return [v.code for v in violations]


def run(plan, form=None, conn=None):
    return run_all_validators(plan, form or make_form(), TODAY, conn=conn)


def test_clean_plan_has_no_violations(conn):
    assert run(make_plan(), conn=conn) == []


def test_severity_map_covers_every_code():
    assert set(SEVERITY) == set(ViolationCode)
    assert len(ViolationCode) == 14
    hard = {c for c, s in SEVERITY.items() if s == "hard"}
    assert hard == {
        ViolationCode.PRIVILEGED_ACCESS_REQUEST,
        ViolationCode.START_DATE_TOO_SOON,
        ViolationCode.MANAGER_NOT_FOUND,
        ViolationCode.DUPLICATE_EMPLOYEE,
    }


# ---- PLAN_PARSE_ERROR
def test_plan_none_returns_single_parse_error(conn):
    v = run(None, conn=conn)
    assert codes(v) == ["PLAN_PARSE_ERROR"]
    assert v[0].severity == "soft"


def test_plan_present_no_parse_error(conn):
    assert "PLAN_PARSE_ERROR" not in codes(run(make_plan(), conn=conn))


# ---- START_DATE_TOO_SOON
def test_start_date_too_soon(conn):
    form = make_form(start_date=TODAY + timedelta(days=9))
    v = run(make_plan(schedule=day1(form.start_date) + [compliance(form.start_date)]), form, conn)
    assert codes(v) == ["START_DATE_TOO_SOON"]
    assert v[0].severity == "hard"
    assert "2026-10-10" in v[0].message and "2026-10-11" in v[0].message


def test_start_date_exactly_min_notice_ok(conn):
    form = make_form(start_date=TODAY + timedelta(days=10))
    plan = make_plan(schedule=day1(form.start_date) + [compliance(form.start_date)])
    assert "START_DATE_TOO_SOON" not in codes(run(plan, form, conn))


# ---- MANAGER_NOT_FOUND
def test_manager_not_found(conn):
    v = run(make_plan(), make_form(manager_email="ghost@corp.example"), conn)
    assert codes(v) == ["MANAGER_NOT_FOUND"]
    assert v[0].severity == "hard"
    assert "ghost@corp.example" in v[0].message


def test_manager_found(conn):
    assert "MANAGER_NOT_FOUND" not in codes(run(make_plan(), conn=conn))


def test_non_manager_employee_is_not_a_manager(conn):
    conn.execute(
        "INSERT INTO employees (email, full_name, is_manager) VALUES ('reg@corp.example','Reg',0)"
    )
    conn.commit()
    v = run(make_plan(), make_form(manager_email="reg@corp.example"), conn)
    assert "MANAGER_NOT_FOUND" in codes(v)


# ---- DUPLICATE_EMPLOYEE
def test_duplicate_employee(conn):
    v = run(make_plan(), make_form(email=MANAGER), conn)
    assert codes(v) == ["DUPLICATE_EMPLOYEE"]
    assert v[0].severity == "hard"


def test_no_duplicate_employee(conn):
    assert "DUPLICATE_EMPLOYEE" not in codes(run(make_plan(), conn=conn))


# ---- ACCESS_NOT_IN_MATRIX / PRIVILEGED_ACCESS_REQUEST
def test_access_not_in_matrix(conn):
    plan = make_plan(
        access_requests=[
            AccessRequest(system="email", justification="j"),
            AccessRequest(system="gitlab", justification="j"),
        ]
    )
    v = run(plan, conn=conn)
    assert codes(v) == ["ACCESS_NOT_IN_MATRIX"]
    assert v[0].field_path == "access_requests[1].system"
    assert "gitlab" in v[0].message and "finance_officer" in v[0].message


def test_privileged_access_is_hard(conn):
    plan = make_plan(access_requests=[AccessRequest(system="aws_prod", justification="j")])
    v = run(plan, conn=conn)
    assert codes(v) == ["PRIVILEGED_ACCESS_REQUEST"]
    assert v[0].severity == "hard"


def test_privileged_system_permitted_by_matrix_is_ok(conn):
    form = make_form(role="hr_coordinator", department="hr")
    plan = make_plan(
        access_requests=[AccessRequest(system="hris", justification="j")],
        schedule=day1() + [compliance()],
    )
    assert run(plan, form, conn) == []


def test_privileged_system_for_other_role_is_hard(conn):
    plan = make_plan(access_requests=[AccessRequest(system="hris", justification="j")])
    assert codes(run(plan, conn=conn)) == ["PRIVILEGED_ACCESS_REQUEST"]


def test_access_allowed_systems_ok(conn):
    plan = make_plan(
        access_requests=[AccessRequest(system=s, justification="j") for s in
                         ("email", "slack", "erp_finance", "expense_tool")]
    )
    assert run(plan, conn=conn) == []


# ---- UNKNOWN_CATALOG_ITEM / ITEM_OUT_OF_STOCK
def test_unknown_catalog_item(conn):
    plan = make_plan(equipment=[EquipmentItem(catalog_id="EQ-999", name="Mystery", price_eur=10)])
    v = run(plan, conn=conn)
    assert codes(v) == ["UNKNOWN_CATALOG_ITEM"]
    assert v[0].field_path == "equipment[0].catalog_id"
    assert "EQ-999" in v[0].message


def test_known_catalog_item_ok(conn):
    assert "UNKNOWN_CATALOG_ITEM" not in codes(run(make_plan(), conn=conn))


def test_item_out_of_stock(conn):
    plan = make_plan(
        equipment=[EquipmentItem(catalog_id="EQ-009", name="Aeron", price_eur=1100)]
    )
    v = run(plan, conn=conn)
    assert codes(v) == ["ITEM_OUT_OF_STOCK"]
    assert "EQ-009" in v[0].message


def test_in_stock_item_ok(conn):
    assert "ITEM_OUT_OF_STOCK" not in codes(run(make_plan(), conn=conn))


# ---- BUDGET_EXCEEDED
@pytest.mark.parametrize(
    "level,limit", [("junior", 1800), ("medior", 2200), ("senior", 2600), ("lead", 3000)]
)
def test_budget_per_level_boundary(conn, level, limit):
    form = make_form(level=level)
    # EQ-001 1249 + EQ-002 3499 > every limit; one MacBook alone (3499) > lead too
    over = make_plan(equipment=[EquipmentItem(catalog_id="EQ-002", name="MBP", price_eur=3499)])
    v = run(over, form, conn)
    assert codes(v) == ["BUDGET_EXCEEDED"]
    assert f"{limit:,.2f}" in v[0].message
    # Exactly at the limit is allowed: fill with desk (250) quantity to hit the limit
    exact_qty = limit // 250
    at_limit = make_plan(
        equipment=[EquipmentItem(catalog_id="EQ-011", name="Desk", price_eur=250, quantity=exact_qty)]
    )
    assert "BUDGET_EXCEEDED" not in codes(run(at_limit, form, conn))
    just_over = make_plan(
        equipment=[EquipmentItem(catalog_id="EQ-011", name="Desk", price_eur=250,
                                 quantity=exact_qty + 1)]
    )
    if (exact_qty + 1) * 250 > limit:
        assert "BUDGET_EXCEEDED" in codes(run(just_over, form, conn))


def test_budget_quantity_multiplies(conn):
    plan = make_plan(
        equipment=[EquipmentItem(catalog_id="EQ-001", name="TP", price_eur=1249, quantity=2)]
    )
    assert codes(run(plan, conn=conn)) == ["BUDGET_EXCEEDED"]


def test_budget_uses_catalog_price_not_llm_price(conn):
    # LLM claims MacBook Pro costs 100 EUR; catalog says 3499 -> still over (P5)
    plan = make_plan(equipment=[EquipmentItem(catalog_id="EQ-002", name="MBP", price_eur=100)])
    assert codes(run(plan, conn=conn)) == ["BUDGET_EXCEEDED"]


def test_budget_inflated_llm_price_does_not_cause_violation(conn):
    plan = make_plan(equipment=[EquipmentItem(catalog_id="EQ-004", name="XPS", price_eur=9999)])
    assert "BUDGET_EXCEEDED" not in codes(run(plan, conn=conn))


def test_remote_allowance_covers_monitor_extra(conn):
    form = make_form(location="remote_nl")
    # 1249 laptop + 549 monitor = 1798... use junior 1800: laptop 1249 + two monitors 289+449 = 1987
    # 1987 <= 1800 + min(350, 738)=2150 -> ok
    plan = make_plan(
        equipment=[
            EquipmentItem(catalog_id="EQ-001", name="TP", price_eur=1249),
            EquipmentItem(catalog_id="EQ-005", name="Dell", price_eur=289),
            EquipmentItem(catalog_id="EQ-007", name="LG", price_eur=449),
        ]
    )
    assert "BUDGET_EXCEEDED" not in codes(run(plan, form, conn))


def test_remote_allowance_is_capped_at_350(conn):
    form = make_form(location="remote_nl")
    # 1249 + 549 + 449 = 2247 > 1800 + 350 = 2150
    plan = make_plan(
        equipment=[
            EquipmentItem(catalog_id="EQ-001", name="TP", price_eur=1249),
            EquipmentItem(catalog_id="EQ-006", name="LG34", price_eur=549),
            EquipmentItem(catalog_id="EQ-007", name="LG27", price_eur=449),
        ]
    )
    v = run(plan, form, conn)
    assert codes(v) == ["BUDGET_EXCEEDED"]
    assert "2,150.00" in v[0].message


def test_remote_allowance_limited_to_monitor_total(conn):
    form = make_form(location="remote_nl")
    # monitor total 199 -> allowance 199, limit 1999. Laptop 1249 + monitor 199 + desk 250 + 400 = over
    plan = make_plan(
        equipment=[
            EquipmentItem(catalog_id="EQ-001", name="TP", price_eur=1249),
            EquipmentItem(catalog_id="EQ-008", name="ASUS", price_eur=199),
            EquipmentItem(catalog_id="EQ-011", name="Desk", price_eur=250),
            EquipmentItem(catalog_id="EQ-017", name="Sony", price_eur=399),
        ]
    )  # total 2097 > 1800 + 199 = 1999
    v = run(plan, form, conn)
    assert codes(v) == ["BUDGET_EXCEEDED"]
    assert "1,999.00" in v[0].message


def test_non_remote_gets_no_allowance(conn):
    plan = make_plan(
        equipment=[
            EquipmentItem(catalog_id="EQ-001", name="TP", price_eur=1249),
            EquipmentItem(catalog_id="EQ-007", name="LG27", price_eur=449),
            EquipmentItem(catalog_id="EQ-005", name="Dell", price_eur=289),
        ]
    )  # 1987 > 1800
    assert codes(run(plan, conn=conn)) == ["BUDGET_EXCEEDED"]


# ---- TRAINING_MISSING / TRAINING_TOO_LATE
def test_compliance_training_missing(conn):
    plan = make_plan(schedule=day1())
    v = run(plan, conn=conn)
    assert codes(v) == ["TRAINING_MISSING"]
    assert "compliance_training" in v[0].message


def test_compliance_training_too_late(conn):
    late = START + timedelta(days=15)
    v = run(make_plan(schedule=day1() + [compliance(late)]), conn=conn)
    assert codes(v) == ["TRAINING_TOO_LATE"]
    assert late.isoformat() in v[0].message
    assert (START + timedelta(days=14)).isoformat() in v[0].message


def test_compliance_training_on_deadline_ok(conn):
    on_time = START + timedelta(days=14)
    assert run(make_plan(schedule=day1() + [compliance(on_time)]), conn=conn) == []


def test_security_training_required_for_vpn_role(conn):
    form = make_form(role="data_analyst", department="data")
    plan = make_plan(
        access_requests=[AccessRequest(system="email", justification="j")],
        schedule=day1() + [compliance()],
    )
    v = run(plan, form, conn)
    assert codes(v) == ["TRAINING_MISSING"]
    assert "security_training" in v[0].message


def test_security_training_required_for_aws_role(conn):
    form = make_form(role="engineering_manager", department="engineering")
    plan = make_plan(schedule=day1() + [compliance()])
    assert "security_training" in run(plan, form, conn)[0].message


def test_security_training_not_required_without_vpn_or_aws(conn):
    for role, dept in (("finance_officer", "finance"), ("hr_coordinator", "hr"),
                       ("sales_rep", "sales")):
        form = make_form(role=role, department=dept)
        assert run(make_plan(), form, conn) == [], role


def test_security_training_too_late_uses_30_days(conn):
    form = make_form(role="software_engineer", department="engineering")
    ok = make_plan(schedule=day1() + [compliance(), security(START + timedelta(days=30))])
    assert run(ok, form, conn) == []
    late = make_plan(schedule=day1() + [compliance(), security(START + timedelta(days=31))])
    assert codes(run(late, form, conn)) == ["TRAINING_TOO_LATE"]


# ---- MISSING_DAY1_EVENT
@pytest.mark.parametrize("missing", ["it_setup", "manager_1on1", "hr_intro"])
def test_missing_day1_event(conn, missing):
    events = [e for e in day1() if e.event_type != missing] + [compliance()]
    v = run(make_plan(schedule=events), conn=conn)
    assert codes(v) == ["MISSING_DAY1_EVENT"]
    assert missing in v[0].message


def test_day1_event_on_wrong_date_counts_as_missing(conn):
    events = day1()
    events[0] = events[0].model_copy(update={"date": START + timedelta(days=1)})
    v = run(make_plan(schedule=events + [compliance()]), conn=conn)
    assert codes(v) == ["MISSING_DAY1_EVENT"]


def test_all_day1_events_present_ok(conn):
    assert "MISSING_DAY1_EVENT" not in codes(run(make_plan(), conn=conn))


# ---- VISA_TASK_MISSING
def test_visa_task_missing(conn):
    v = run(make_plan(), make_form(visa_required=True), conn)
    assert codes(v) == ["VISA_TASK_MISSING"]


def test_visa_task_wrong_owner_is_missing(conn):
    plan = make_plan(tasks=[OnboardingTask(title="Right to work check", owner="it",
                                           due_date=START)])
    assert codes(run(plan, make_form(visa_required=True), conn)) == ["VISA_TASK_MISSING"]


def test_visa_task_present_case_insensitive(conn):
    plan = make_plan(tasks=[OnboardingTask(title="Verify Right To Work docs", owner="hr",
                                           due_date=START)])
    assert run(plan, make_form(visa_required=True), conn) == []


def test_visa_not_required_no_task_needed(conn):
    assert "VISA_TASK_MISSING" not in codes(run(make_plan(), conn=conn))


# ---- all violations returned
def test_returns_all_violations_not_just_first(conn):
    form = make_form(
        start_date=TODAY + timedelta(days=3),
        manager_email="ghost@corp.example",
        email=MANAGER,
        visa_required=True,
    )
    plan = make_plan(
        access_requests=[AccessRequest(system="aws_prod", justification="j"),
                         AccessRequest(system="gitlab", justification="j")],
        equipment=[EquipmentItem(catalog_id="EQ-002", name="MBP", price_eur=3499),
                   EquipmentItem(catalog_id="EQ-009", name="Aeron", price_eur=1100),
                   EquipmentItem(catalog_id="EQ-999", name="?", price_eur=1)],
        schedule=[],
    )
    got = set(codes(run(plan, form, conn)))
    assert got == {
        "START_DATE_TOO_SOON", "MANAGER_NOT_FOUND", "DUPLICATE_EMPLOYEE",
        "PRIVILEGED_ACCESS_REQUEST", "ACCESS_NOT_IN_MATRIX", "BUDGET_EXCEEDED",
        "ITEM_OUT_OF_STOCK", "UNKNOWN_CATALOG_ITEM", "TRAINING_MISSING",
        "MISSING_DAY1_EVENT", "VISA_TASK_MISSING",
    }


# ---- TOOL_FAILURE (P1)
def test_tool_failure_violation_for_license_pool():
    results = [ToolResult(tool="request_account", ok=False,
                          error_code="LICENSE_POOL_EXHAUSTED", error_message="pool empty")]
    v = violations_from_tool_results(results)
    assert codes(v) == ["TOOL_FAILURE"]
    assert v[0].severity == "soft"
    assert "LICENSE_POOL_EXHAUSTED" in v[0].message
    assert v[0].field_path == "tool_results[0]"


@pytest.mark.parametrize(
    "code", ["UNKNOWN_SYSTEM", "ROLE_NOT_PERMITTED", "UNKNOWN_CATALOG_ITEM"]
)
def test_tool_failure_skips_codes_covered_by_validators(code):
    results = [ToolResult(tool="request_account", ok=False, error_code=code)]
    assert violations_from_tool_results(results) == []


def test_tool_failure_ignores_successful_results():
    assert violations_from_tool_results([ToolResult(tool="get_item", ok=True)]) == []


# ---- purity
def test_validators_do_not_call_date_today():
    import inspect

    from onboard_pilot.validation import validators

    src = inspect.getsource(validators)
    assert "date.today" not in src and "get_today" not in src
