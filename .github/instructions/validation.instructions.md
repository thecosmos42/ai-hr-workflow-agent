---
applyTo: "src/onboard_pilot/validation/**,src/onboard_pilot/graph/routing.py,tests/test_validators.py,tests/test_routing.py"
---
# Validators & routing rules (plan.md §6)

- **Pure Python. No LLM calls, no network, no `date.today()`.** `today` is always a parameter.
- Validators may read reference data (managers, employees, catalog) through read-only `db.py` helpers; accept an optional `conn` argument so tests can pass an in-memory DB (DEVIATIONS P4).
- Policy numbers come from `config/policy_tables.yaml` via the loader in `config/settings.py`. Never hardcode budgets, deadlines or matrices in code.
- `run_all_validators(plan, form, today)` runs **every** check and returns **all** violations, not just the first. If `plan is None`, return a single `PLAN_PARSE_ERROR` violation.
- Violation codes and severities are the §6.2 table (plus `TOOL_FAILURE`, DEVIATIONS P1). Every `PolicyViolation.message` must include the offending value **and** the limit. `field_path` uses forms like `equipment[1].price_eur`.
- Interpretations that are pre-approved: budget uses catalog price when the item exists (P5); remote allowance = `min(350, monitor total)` for `remote_nl` (P6); security training required iff the role's matrix has `vpn` or any `aws_*` (P7).
- `route_after_validation(state)` must be a **pure function** that returns only `"finalize" | "revise" | "escalate"`. It never mutates state. Escalation reasons are built by a separate pure helper `build_escalation_reason(state) -> str` (P8).
- Hard violations never retry. Soft + `retry_count < MAX_RETRIES` → revise. Soft with retries exhausted → escalate. No violations → escalate on low RAG score or `conflicting_policy_detected`, else finalize.
- Tests: every violation code has ≥1 positive and ≥1 negative test; every routing branch has a test. Use `today = date(2026, 10, 1)` in tests.
