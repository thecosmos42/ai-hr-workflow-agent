"""Deterministic policy validators (plan.md §6). Pure Python: no LLM, no network.

Every check is a small function returning a list of violations. `today` is always
injected. Reference data (managers, employees, catalog) is read through `db.py`
helpers (DEVIATIONS P4). Policy numbers come from `config/policy_tables.yaml`.
"""
import sqlite3
from datetime import date, timedelta

from config.settings import get_settings, load_policy_tables
from onboard_pilot import db
from onboard_pilot.schemas import (
    IntakeForm,
    OnboardingPlan,
    PolicyViolation,
    ToolResult,
)
from onboard_pilot.validation.violations import SEVERITY, ViolationCode

# Tool errors already reported by validators (P1; UNKNOWN_CATALOG_ITEM added, see D4).
_TOOL_ERRORS_COVERED_BY_VALIDATORS = {
    "UNKNOWN_SYSTEM",
    "ROLE_NOT_PERMITTED",
    "UNKNOWN_CATALOG_ITEM",
}


def _violation(
    code: ViolationCode, message: str, field_path: str, policy_ref: str
) -> PolicyViolation:
    return PolicyViolation(
        code=code.value,
        severity=SEVERITY[code],
        message=message,
        field_path=field_path,
        policy_ref=policy_ref,
    )


def _fmt_eur(value: float) -> str:
    return f"€{value:,.2f}"


def check_start_date(form: IntakeForm, today: date) -> list[PolicyViolation]:
    """START_DATE_TOO_SOON: start_date must be >= today + min_notice_days."""
    min_notice = load_policy_tables()["min_notice_days"]
    earliest = today + timedelta(days=min_notice)
    if form.start_date < earliest:
        return [
            _violation(
                ViolationCode.START_DATE_TOO_SOON,
                f"Start date {form.start_date.isoformat()} is before the earliest allowed "
                f"{earliest.isoformat()} (today {today.isoformat()} + {min_notice} days notice).",
                "form.start_date",
                "policy_tables.yaml:min_notice_days",
            )
        ]
    return []


def check_manager(form: IntakeForm, conn: sqlite3.Connection) -> list[PolicyViolation]:
    """MANAGER_NOT_FOUND: manager_email must be a seeded manager."""
    if not db.manager_exists(form.manager_email, conn=conn):
        return [
            _violation(
                ViolationCode.MANAGER_NOT_FOUND,
                f"Manager '{form.manager_email}' is not a known manager (must exist in employees "
                f"with is_manager=1).",
                "form.manager_email",
                "§2",
            )
        ]
    return []


def check_duplicate(form: IntakeForm, conn: sqlite3.Connection) -> list[PolicyViolation]:
    """DUPLICATE_EMPLOYEE: email must not already be in employees."""
    if db.employee_exists_by_email(form.email, conn=conn):
        return [
            _violation(
                ViolationCode.DUPLICATE_EMPLOYEE,
                f"Employee with email '{form.email}' already exists (limit: one record per email).",
                "form.email",
                "§1",
            )
        ]
    return []


def check_access(plan: OnboardingPlan, form: IntakeForm) -> list[PolicyViolation]:
    """ACCESS_NOT_IN_MATRIX (soft) and PRIVILEGED_ACCESS_REQUEST (hard)."""
    tables = load_policy_tables()
    allowed = set(tables["access_matrix"].get(form.role, []))
    privileged = set(tables["privileged_systems"])
    out: list[PolicyViolation] = []
    for i, req in enumerate(plan.access_requests):
        if req.system in allowed:
            continue
        path = f"access_requests[{i}].system"
        if req.system in privileged:
            out.append(
                _violation(
                    ViolationCode.PRIVILEGED_ACCESS_REQUEST,
                    f"Privileged system '{req.system}' requested for role '{form.role}', "
                    f"which is not permitted by the access matrix (allowed: {sorted(allowed)}).",
                    path,
                    "§4.2",
                )
            )
        else:
            out.append(
                _violation(
                    ViolationCode.ACCESS_NOT_IN_MATRIX,
                    f"System '{req.system}' is not in the access matrix for role '{form.role}' "
                    f"(allowed: {sorted(allowed)}).",
                    path,
                    "§4.1",
                )
            )
    return out


def check_catalog_items(
    plan: OnboardingPlan, conn: sqlite3.Connection
) -> list[PolicyViolation]:
    """UNKNOWN_CATALOG_ITEM and ITEM_OUT_OF_STOCK for every equipment line."""
    out: list[PolicyViolation] = []
    for i, item in enumerate(plan.equipment):
        row = db.get_catalog_item(item.catalog_id, conn=conn)
        path = f"equipment[{i}].catalog_id"
        if row is None:
            out.append(
                _violation(
                    ViolationCode.UNKNOWN_CATALOG_ITEM,
                    f"Catalog id '{item.catalog_id}' ('{item.name}') does not exist in the "
                    f"equipment catalog.",
                    path,
                    "§3.3",
                )
            )
        elif not row["in_stock"]:
            out.append(
                _violation(
                    ViolationCode.ITEM_OUT_OF_STOCK,
                    f"Catalog item '{item.catalog_id}' ('{row['name']}') is out of stock "
                    f"(in_stock=0, required >= 1).",
                    path,
                    "§3.3",
                )
            )
    return out


def equipment_total_and_monitors(
    plan: OnboardingPlan, conn: sqlite3.Connection
) -> tuple[float, float]:
    """Return (total, monitor_total) using catalog prices when known (P5)."""
    total = 0.0
    monitors = 0.0
    for item in plan.equipment:
        row = db.get_catalog_item(item.catalog_id, conn=conn)
        price = float(row["price_eur"]) if row else float(item.price_eur)
        line = price * item.quantity
        total += line
        if row and row["category"] == "monitor":
            monitors += line
    return total, monitors


def check_budget(
    plan: OnboardingPlan, form: IntakeForm, conn: sqlite3.Connection
) -> list[PolicyViolation]:
    """BUDGET_EXCEEDED: total vs level budget (+ remote monitor allowance, P6)."""
    tables = load_policy_tables()
    base = float(tables["equipment_budget_eur"][form.level])
    total, monitors = equipment_total_and_monitors(plan, conn)
    limit = base
    ref = "§3.2"
    note = f"{form.level} budget {_fmt_eur(base)}"
    if form.location == "remote_nl":
        allowance = min(float(tables["remote_monitor_allowance_eur"]), monitors)
        limit += allowance
        ref = "§3.2, §6.4"
        note += f" + remote monitor allowance {_fmt_eur(allowance)}"
    if round(total, 2) > round(limit, 2):
        return [
            _violation(
                ViolationCode.BUDGET_EXCEEDED,
                f"Equipment total {_fmt_eur(total)} exceeds the limit of {_fmt_eur(limit)} "
                f"({note}).",
                "equipment",
                ref,
            )
        ]
    return []


def security_training_required(role: str) -> bool:
    """Security training is required iff the role has vpn or any aws_* access (P7)."""
    systems = load_policy_tables()["access_matrix"].get(role, [])
    return any(s == "vpn" or s.startswith("aws_") for s in systems)


def check_training(plan: OnboardingPlan, form: IntakeForm) -> list[PolicyViolation]:
    """TRAINING_MISSING / TRAINING_TOO_LATE for compliance and (if required) security."""
    deadlines = load_policy_tables()["training_deadlines_days"]
    required = ["compliance_training"]
    if security_training_required(form.role):
        required.append("security_training")
    out: list[PolicyViolation] = []
    for training in required:
        days = deadlines[training]
        deadline = form.start_date + timedelta(days=days)
        events = [(i, e) for i, e in enumerate(plan.schedule) if e.event_type == training]
        if not events:
            out.append(
                _violation(
                    ViolationCode.TRAINING_MISSING,
                    f"Required {training} is not scheduled (must be scheduled by "
                    f"{deadline.isoformat()}, start_date + {days} days).",
                    "schedule",
                    "§5.1",
                )
            )
            continue
        i, earliest = min(events, key=lambda pair: pair[1].date)
        if earliest.date > deadline:
            out.append(
                _violation(
                    ViolationCode.TRAINING_TOO_LATE,
                    f"{training} is scheduled on {earliest.date.isoformat()}, after the deadline "
                    f"{deadline.isoformat()} (start_date + {days} days).",
                    f"schedule[{i}].date",
                    "§5.1",
                )
            )
    return out


def check_day1_events(plan: OnboardingPlan, form: IntakeForm) -> list[PolicyViolation]:
    """MISSING_DAY1_EVENT: each mandatory event must occur on start_date."""
    out: list[PolicyViolation] = []
    for event_type in load_policy_tables()["mandatory_day1_events"]:
        if not any(
            e.event_type == event_type and e.date == form.start_date for e in plan.schedule
        ):
            out.append(
                _violation(
                    ViolationCode.MISSING_DAY1_EVENT,
                    f"Mandatory day-1 event '{event_type}' is not scheduled on the start date "
                    f"{form.start_date.isoformat()}.",
                    "schedule",
                    "§8.1",
                )
            )
    return out


def check_visa_task(plan: OnboardingPlan, form: IntakeForm) -> list[PolicyViolation]:
    """VISA_TASK_MISSING: visa_required needs an hr-owned 'right to work' task."""
    if not form.visa_required:
        return []
    if any("right to work" in t.title.lower() and t.owner == "hr" for t in plan.tasks):
        return []
    return [
        _violation(
            ViolationCode.VISA_TASK_MISSING,
            "visa_required=true but no task containing 'right to work' owned by 'hr' exists "
            f"({len(plan.tasks)} tasks found, 1 required).",
            "tasks",
            "§7.1",
        )
    ]


def run_all_validators(
    plan: OnboardingPlan | None,
    form: IntakeForm,
    today: date,
    conn: sqlite3.Connection | None = None,
) -> list[PolicyViolation]:
    """Run every check and return ALL violations. `plan=None` -> PLAN_PARSE_ERROR only."""
    if plan is None:
        return [
            _violation(
                ViolationCode.PLAN_PARSE_ERROR,
                "Structured output could not be parsed into an OnboardingPlan after 2 attempts "
                "(0 valid plans, 1 required).",
                "plan",
                "plan.md:§3.2",
            )
        ]

    own_conn = conn is None
    if conn is None:
        conn = db.get_connection(get_settings().db_path)
    try:
        violations: list[PolicyViolation] = []
        violations += check_start_date(form, today)
        violations += check_manager(form, conn)
        violations += check_duplicate(form, conn)
        violations += check_access(plan, form)
        violations += check_catalog_items(plan, conn)
        violations += check_budget(plan, form, conn)
        violations += check_training(plan, form)
        violations += check_day1_events(plan, form)
        violations += check_visa_task(plan, form)
        return violations
    finally:
        if own_conn:
            conn.close()


def violations_from_tool_results(tool_results: list[ToolResult]) -> list[PolicyViolation]:
    """Turn failed tool results into soft TOOL_FAILURE violations (DEVIATIONS P1).

    UNKNOWN_SYSTEM, ROLE_NOT_PERMITTED and UNKNOWN_CATALOG_ITEM are skipped: validators
    already report them.
    """
    out: list[PolicyViolation] = []
    for i, result in enumerate(tool_results):
        if result.ok or result.error_code in _TOOL_ERRORS_COVERED_BY_VALIDATORS:
            continue
        out.append(
            _violation(
                ViolationCode.TOOL_FAILURE,
                f"Tool '{result.tool}' failed with {result.error_code}: "
                f"{result.error_message or 'no details'}.",
                f"tool_results[{i}]",
                f"tool:{result.tool}",
            )
        )
    return out
