# PROGRESS

Current step: **8** (complete, proceeding to 9)
Rule: do not start step N+1 until step N is ticked. Tick only after the acceptance command was actually run and passed.

| # | Step | Done | Acceptance command(s) |
|---|------|------|-----------------------|
| 1 | Scaffold, config, schemas, db, seed, init_all | [x] | `python scripts/init_all.py` twice → 5 managers, ≥20 catalog rows, no duplicates |
| 2 | Tools (all 5) + tests | [x] | `pytest tests/test_tools.py -q` |
| 3 | Validators + routing + tests | [x] | `pytest tests/test_validators.py tests/test_routing.py -q` |
| 4 | Policy handbook + RAG index | [x] | `python -c "from onboard_pilot.tools.policy_rag import query_policy; print(query_policy('monitor allowance remote'))"` shows §6.4 |
| 5 | Linear graph, happy path | [x] | `python scripts/run_case.py evals/scenarios/scenario_01.json` → auto_approved |
| 6 | Revise loop | [x] | scenario_09 → BUDGET_EXCEEDED then clean pass, retries ≥ 1 |
| 7 | Escalation + interrupt + resume | [x] | scenario_16 → escalated; `--resume` approve → finalized; survives restart |
| 8 | Streamlit 3 pages | [x] | Cases page (metrics, table), Trace page (self-correction visibility), Approval Queue (escalation workflow) |
| 9 | 25 scenarios + run_evals | [ ] | `python evals/run_evals.py --auto-approve-escalations` → precision ≥ 0.85, hard-case recall = 1.0 |
| 10 | README + GIF + cleanup | [ ] | fresh clone → `.env` → init_all → run scenario_01 works per README |

## Notes / blockers
(agent: append short notes here)
