"""Graph nodes: intake, plan, execute_tools, validate, revise, escalate, finalize."""
import json
import logging
from datetime import timedelta

from config.settings import get_settings, get_today, load_policy_tables
from onboard_pilot import db
from onboard_pilot.audit.logger import log_node, record_usage, set_payload, set_summary
from onboard_pilot.llm import get_llm
from onboard_pilot.schemas import IntakeForm, OnboardingPlan, OnboardingState, ToolResult
from onboard_pilot.tools.equipment_catalog import get_item, search_catalog
from onboard_pilot.tools.hr_db import check_duplicate, create_employee, lookup_manager
from onboard_pilot.tools.it_provisioner import request_account
from onboard_pilot.tools.policy_rag import query_policy
from onboard_pilot.tools.scheduler import commit_events
from onboard_pilot.validation.validators import (
    run_all_validators,
    security_training_required,
    violations_from_tool_results,
)

logger = logging.getLogger(__name__)

PLAN_SYSTEM_PROMPT = """You are an HR onboarding planner. Produce a complete onboarding plan \
for one new hire as a structured OnboardingPlan.

Rules:
- Access: request every system in the role's baseline access list, plus any system the \
requester asked for in requested_extras. One AccessRequest per system, with a short justification.
- Equipment: choose a baseline kit (laptop, one monitor, keyboard, mouse, headset) using ONLY \
catalog items below, referenced by their exact catalog_id, name and price_eur. Keep the baseline \
kit within the level budget. Then add every item the requester asked for in requested_extras \
EXACTLY as asked, even if it would exceed the budget or conflict with a policy. Do not drop, \
substitute or refuse requested extras: automated policy checks run after you and decide.
- Schedule: on the start date schedule it_setup, manager_1on1 and hr_intro. Schedule \
compliance_training on or before its deadline. Schedule security_training on or before its \
deadline when the instructions below say it is required. Optionally add a buddy_lunch in week 1.
- Tasks: when visa_required is true add a task titled "Right to work verification" owned by "hr" \
due on or before the start date. Add any other follow-up tasks that are clearly needed.
- policy_citations: list the handbook section ids you relied on, for example ["§3.2", "§4.1"]. \
Only cite sections that appear in the policy excerpts.
- case_id must equal the case id given. employee_summary is 1-2 sentences.
- Dates are ISO format (YYYY-MM-DD)."""

PLAN_USER_TEMPLATE = """Case id: {case_id}

Intake form:
{form_json}

Baseline access for role '{role}': {baseline_access}
Level budget for '{level}': EUR {budget}
Compliance training deadline: {compliance_deadline}
Security training required: {security_required}{security_deadline_text}

Equipment catalog (catalog_id | name | category | price_eur | in_stock):
{catalog_text}

Policy excerpts:
{policy_text}
"""

PARSE_RETRY_PROMPT = (
    "Your previous answer could not be parsed into the required structure. "
    "Return the complete OnboardingPlan again, matching the schema exactly."
)


def _conn():
    return db.get_connection(get_settings().db_path)


@log_node("intake")
def intake(state: OnboardingState) -> dict:
    """Create or reset the cases row and run the duplicate and manager lookups."""
    conn = _conn()
    try:
        conn.execute(
            """
            INSERT INTO cases (case_id, status) VALUES (?, 'running')
            ON CONFLICT(case_id) DO UPDATE SET status='running', finalized_at=NULL,
                escalation_reason=NULL, human_decision=NULL, human_comment=NULL
            """,
            (state.case_id,),
        )
        conn.commit()
        results = [
            check_duplicate(state.form.email, conn=conn),
            lookup_manager(state.form.manager_email, conn=conn),
        ]
    finally:
        conn.close()
    set_summary(
        "intake checks: " + ", ".join(f"{r.tool}={'ok' if r.ok else r.error_code}" for r in results)
    )
    set_payload({"tool_results": [r.model_dump() for r in results]})
    return {"tool_results": results, "status": "running"}


def _policy_queries(form: IntakeForm) -> list[str]:
    queries = [
        f"equipment budget cap for a {form.level} hire",
        f"system access allowed for the {form.role.replace('_', ' ')} role",
        "when must compliance and security training be completed",
        "mandatory events on the first day",
    ]
    if form.location == "remote_nl":
        queries.append("remote employee monitor allowance and equipment")
    if form.visa_required:
        queries.append("right to work verification for visa hires")
    return queries


def _retrieve_policy(form: IntakeForm) -> tuple[str, float]:
    """Return (excerpt text, rag_min_score).

    The score is the minimum over queries of each query's best-match similarity. If the
    index is unavailable the score is 0.0 so the case escalates instead of passing silently.
    """
    sections: dict[str, str] = {}
    best_scores: list[float] = []
    for q in _policy_queries(form):
        result = query_policy(q, k=3)
        if not result.ok:
            logger.warning("Policy retrieval failed: %s", result.error_message)
            return "(policy handbook unavailable)", 0.0
        chunks = result.data["chunks"]
        if chunks:
            best_scores.append(chunks[0]["score"])
        for c in chunks:
            sections.setdefault(c["section_id"], c["text"])
    text = "\n\n".join(sections[k] for k in sorted(sections))
    return text, (min(best_scores) if best_scores else 0.0)


def _catalog_text(conn) -> str:
    items = search_catalog(conn=conn).data["items"]
    return "\n".join(
        f"{i['catalog_id']} | {i['name']} | {i['category']} | {i['price_eur']:.0f} | "
        f"{'in stock' if i['in_stock'] else 'OUT OF STOCK'}"
        for i in items
    )


def build_plan_prompt(form: IntakeForm, case_id: str, policy_text: str) -> str:
    """Fill PLAN_USER_TEMPLATE for a case."""
    tables = load_policy_tables()
    deadlines = tables["training_deadlines_days"]
    security = security_training_required(form.role)
    conn = _conn()
    try:
        catalog = _catalog_text(conn)
    finally:
        conn.close()
    return PLAN_USER_TEMPLATE.format(
        case_id=case_id,
        form_json=form.model_dump_json(indent=2),
        role=form.role,
        baseline_access=", ".join(tables["access_matrix"][form.role]),
        level=form.level,
        budget=tables["equipment_budget_eur"][form.level],
        compliance_deadline=(form.start_date + timedelta(days=deadlines["compliance_training"])).isoformat(),
        security_required="yes" if security else "no",
        security_deadline_text=(
            f" (deadline {(form.start_date + timedelta(days=deadlines['security_training'])).isoformat()})"
            if security
            else ""
        ),
        catalog_text=catalog,
        policy_text=policy_text,
    )


def generate_plan(system_prompt: str, user_prompt: str) -> tuple[OnboardingPlan | None, list[str]]:
    """Call the LLM with structured output; retry once on parse failure.

    Returns (plan or None, list of parse error strings). Token usage of every attempt is
    recorded on the current node.
    """
    structured = get_llm().with_structured_output(OnboardingPlan, include_raw=True)
    messages: list[tuple[str, str]] = [("system", system_prompt), ("human", user_prompt)]
    errors: list[str] = []
    for _ in range(2):
        out = structured.invoke(messages)
        record_usage(out.get("raw"))
        plan = out.get("parsed")
        if plan is not None and not out.get("parsing_error"):
            return plan, errors
        errors.append(str(out.get("parsing_error") or "no structured output returned"))
        messages = [*messages, ("human", PARSE_RETRY_PROMPT)]
    return None, errors


@log_node("plan")
def plan(state: OnboardingState) -> dict:
    """Retrieve policy context and ask the LLM for an OnboardingPlan."""
    policy_text, rag_min = _retrieve_policy(state.form)
    user_prompt = build_plan_prompt(state.form, state.case_id, policy_text)
    parsed, errors = generate_plan(PLAN_SYSTEM_PROMPT, user_prompt)
    if parsed is not None:
        parsed = parsed.model_copy(update={"case_id": state.case_id})
    set_summary(
        f"plan generated: {len(parsed.equipment)} equipment, {len(parsed.access_requests)} access, "
        f"{len(parsed.schedule)} events, rag_min={rag_min:.2f}"
        if parsed
        else f"plan parse failure after 2 attempts, rag_min={rag_min:.2f}"
    )
    set_payload(
        {
            "plan": parsed.model_dump(mode="json") if parsed else None,
            "parse_errors": errors,
            "rag_min_score": rag_min,
        }
    )
    return {"plan": parsed, "rag_min_score": rag_min}


@log_node("execute_tools")
def execute_tools(state: OnboardingState) -> dict:
    """Re-run provisioning and catalog lookups for the current plan (replaces tool_results)."""
    results: list[ToolResult] = []
    conn = _conn()
    try:
        conn.execute(
            "DELETE FROM access_requests WHERE case_id = ? AND status = 'proposed'",
            (state.case_id,),
        )
        conn.commit()
        if state.plan is not None:
            for req in state.plan.access_requests:
                results.append(request_account(req.system, state.form.role, state.case_id, conn=conn))
            for item in state.plan.equipment:
                results.append(get_item(item.catalog_id, conn=conn))
    finally:
        conn.close()
    failed = [r for r in results if not r.ok]
    set_summary(f"{len(results)} tool calls, {len(failed)} failed")
    set_payload({"tool_results": [r.model_dump() for r in results]})
    return {"tool_results": results}


@log_node("validate")
def validate(state: OnboardingState) -> dict:
    """Run all deterministic validators plus tool-failure violations."""
    violations = run_all_validators(state.plan, state.form, get_today())
    violations += violations_from_tool_results(state.tool_results)
    codes = sorted({v.code for v in violations})
    set_summary(f"{len(violations)} violations: {', '.join(codes)}" if violations else "0 violations")
    set_payload({"violations": [v.model_dump() for v in violations]})
    return {"violations": violations}


def revise(state: OnboardingState) -> dict:
    """Implemented in step 6."""
    raise NotImplementedError("revise node is implemented in build step 6")


def escalate(state: OnboardingState) -> dict:
    """Implemented in step 7."""
    raise NotImplementedError("escalate node is implemented in build step 7")


@log_node("finalize")
def finalize(state: OnboardingState) -> dict:
    """The only node that writes business tables, in a single transaction (DEVIATIONS P3)."""
    if state.plan is None:
        raise RuntimeError("finalize called without a plan")
    outcome = "auto_approved" if state.status == "running" else state.status
    conn = _conn()
    try:
        created = create_employee(state.form, conn=conn, commit=False)
        if not created.ok:
            raise RuntimeError(f"create_employee failed: {created.error_code}")
        conn.execute(
            "UPDATE access_requests SET status='submitted' WHERE case_id = ? AND status='proposed'",
            (state.case_id,),
        )
        for item in state.plan.equipment:
            row = db.get_catalog_item(item.catalog_id, conn=conn)
            price = float(row["price_eur"]) if row else item.price_eur
            conn.execute(
                "INSERT INTO equipment_orders (case_id, catalog_id, name, quantity, price_eur) "
                "VALUES (?, ?, ?, ?, ?)",
                (state.case_id, item.catalog_id, item.name, item.quantity, price),
            )
        for task in state.plan.tasks:
            conn.execute(
                "INSERT INTO onboarding_tasks (case_id, title, owner, due_date) VALUES (?, ?, ?, ?)",
                (state.case_id, task.title, task.owner, task.due_date.isoformat()),
            )
        scheduled = commit_events(state.plan, state.case_id, str(state.form.email), conn=conn, commit=False)
        if not scheduled.ok:
            raise RuntimeError(f"commit_events failed: {scheduled.error_message}")
        conn.execute(
            "UPDATE cases SET status = ?, finalized_at = CURRENT_TIMESTAMP WHERE case_id = ?",
            (outcome, state.case_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    set_summary(
        f"finalized as {outcome}: {len(state.plan.equipment)} equipment lines, "
        f"{len(state.plan.schedule)} events, {len(state.plan.tasks)} tasks"
    )
    set_payload({"outcome": outcome, "plan": state.plan.model_dump(mode="json")})
    return {"status": outcome}
