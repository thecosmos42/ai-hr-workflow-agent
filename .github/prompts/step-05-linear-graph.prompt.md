---
description: "Build step 5 — linear graph (happy path) with audit logging"
agent: agent
---
Execute **build step 5** of [plan.md](../../plan.md) §13. Read first: plan.md §3.2, §4, §6.3, §8 and DEVIATIONS.md (P1, P2, P3, P9, P12, P13). Follow `.github/instructions/graph.instructions.md`. Step 4 must be ticked in [PROGRESS.md](../../PROGRESS.md).

Build the graph with nodes `intake → plan → execute_tools → validate → finalize` and the **conditional edge already wired for revise/escalate** (their node bodies can be stubs that raise `NotImplementedError` until steps 6–7; the routing function is real).
- `llm.py`: `get_llm()` returning `ChatAnthropic` Haiku 4.5 (P13) and `COST_TABLE` (P12). Token counts come from `usage_metadata` (use `include_raw=True` with structured output).
- `audit/logger.py`: `@log_node` decorator + `audit_log` writer (latency, tokens, cost, summary, payload_json) + `state.audit_events`.
- `graph/nodes.py`: named UPPER_SNAKE prompt constants at the top. `plan` node is **literal-first** (P9): baseline access from the role's matrix, honour `requested_extras`, cite handbook sections by id, generate a day-1 schedule (it_setup, manager_1on1, hr_intro on start_date), compliance + security trainings where required, a right-to-work HR task when `visa_required`. Structured output with one retry → `plan=None` on failure.
- `graph/build.py`: `build_graph(checkpointer)`; `SqliteSaver` on `data/checkpoints.db`.
- `finalize`: writes all business tables in one transaction (P3), `cases.finalized_at`, and keeps the outcome status.
- `scripts/run_case.py`: runs a scenario JSON through the graph with `thread_id = case_id`, prints status, retries, violations, cost; supports `--auto-approve-escalations` (P10).
- Create `evals/scenarios/scenario_01.json` (happy path junior software engineer at eindhoven_office, start_date ≥ 2026-10-11, manager `anna.visser@corp.example`) and set `TODAY_OVERRIDE` for it via `.env` or CLI so min-notice passes.

Acceptance (run, show output):
- `python scripts/run_case.py evals/scenarios/scenario_01.json` → status `auto_approved`.
- SQLite shows rows in employees, access_requests (submitted), equipment_orders, calendar_events, onboarding_tasks, outbox, and `audit_log` has one row per node executed.

Finish: tick step 5, set current step to 6, commit `step 5: linear graph happy path`.
