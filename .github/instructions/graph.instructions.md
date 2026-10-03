---
applyTo: "src/onboard_pilot/graph/**,src/onboard_pilot/audit/**,src/onboard_pilot/llm.py,scripts/run_case.py"
---
# Graph, LLM & audit rules (plan.md §4, §6.4, §8, §11)

## Topology (explicit edges)
`START → intake → plan → execute_tools → validate → (route_after_validation)`
- `finalize` → `END`
- `revise` → `execute_tools` (then `validate` again)
- `escalate` → `finalize` if human approved, `END` if rejected (conditional edge after resume)

## Nodes
- **intake**: creates/updates the `cases` row, runs `check_duplicate` and `lookup_manager` and stores results in `tool_results`. (Hard violations themselves come from the validators.)
- **plan**: calls `query_policy` (include a query about remote/monitor policy when `location == remote_nl`), then `llm.with_structured_output(OnboardingPlan)`. On parse failure retry once, then set `plan=None` so validators emit `PLAN_PARSE_ERROR`. Record the minimum retrieval score actually used in `state.rag_min_score`.
- **execute_tools**: **replace** (do not append to) `tool_results` each pass. Delete this case's `proposed` access_requests rows, then re-run `request_account` for each access request and `get_item` for each equipment line.
- **validate**: `run_all_validators(...)` + `violations_from_tool_results(...)` (DEVIATIONS P1). Writes `state.violations`.
- **revise**: prompt = current plan JSON + violations JSON + the exact instruction in plan.md §6.4. `retry_count += 1`. Store old/new plan in the audit payload so the trace page can show a diff.
- **escalate**: sets `status="escalated"`, `escalation_reason=build_escalation_reason(state)`, updates `cases`, then calls `interrupt(...)`. **Code before `interrupt()` re-runs on resume — keep it idempotent.** After resume, apply the decision: approve → `status="approved_by_human"`; reject → `status="rejected_by_human"`.
- **finalize**: the only node that writes business tables (employees, final access_requests status `submitted`, equipment_orders, onboarding_tasks, calendar_events, outbox). Wrap in one transaction. Do **not** overwrite the outcome in `cases.status`; set `finalized_at` instead (DEVIATIONS P3).

## Plan prompt design (DEVIATIONS P9)
The plan prompt is **literal-first**: honour `requested_extras` as asked and cite every handbook section relied on by id (e.g. `§3.2`). It must NOT pre-filter or refuse policy-violating requests — silently dropping them hides violations from the validators and makes scenarios 9–16, 20–25 untestable. The validators and the revise loop are the policy layer. Baseline access = the role's matrix systems from `policy_tables.yaml`.

## LLM & audit
- `llm.get_llm()` is the single factory: `ChatAnthropic` (`claude-haiku-4-5-20251001`, `temperature=0`, model + max_tokens from settings — P13). `COST_TABLE` lives in `llm.py` (P12).
- `@log_node` wraps every node: wall-clock latency, token usage from the response's `usage_metadata` (`input_tokens`/`output_tokens`; use `with_structured_output(..., include_raw=True)` to reach it, and sum across parse retries; zeros for pure-Python nodes; no OpenAI callbacks), one `audit_log` row per execution with `attempt = retry_count`, plus a compact dict appended to `state.audit_events`. `payload_json` must be rich enough for the trace page (violations, tool results, plan diff).
- Checkpointer: `SqliteSaver` on `data/checkpoints.db` using `sqlite3.connect(path, check_same_thread=False)`; `thread_id = case_id`. If Pydantic state fails to serialize, fall back to the TypedDict mirror allowed in plan.md §4.
- `build_graph(checkpointer)` is the only place the graph is assembled.
