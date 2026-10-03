---
description: "Build step 7 — escalate node, interrupt(), resume across processes"
agent: agent
---
Execute **build step 7** of [plan.md](../../plan.md) §13. Read first: plan.md §6.3, §11 (last paragraph) and DEVIATIONS.md (P3, P8, P10). Follow `.github/instructions/graph.instructions.md`. Step 6 must be ticked in [PROGRESS.md](../../PROGRESS.md).

1. Implement the `escalate` node: idempotent pre-interrupt work (status `escalated`, `escalation_reason` via `build_escalation_reason`, update `cases`), then `interrupt({...plan, violations, reason})`. On resume with `{"decision", "comment"}`: approve → `approved_by_human` → `finalize`; reject → `rejected_by_human` → `END`. Store `human_decision` / `human_comment` on state and `cases`.
2. `scripts/run_case.py`: add `--resume <case_id> --decision approve|reject [--comment "..."]` using `graph.invoke(Command(resume=...), config={"configurable": {"thread_id": case_id}})`. Without `--auto-approve-escalations`, an escalated run prints the reason and exits cleanly.
3. Create `scenario_16.json` (`requested_extras: ["aws_prod access"]`), `scenario_17.json` (start 2026-10-04), `scenario_18.json` (unknown manager email).

Acceptance (run as **separate processes**, show output):
- `python scripts/run_case.py evals/scenarios/scenario_16.json` → `escalated`, reason names `PRIVILEGED_ACCESS_REQUEST`, no rows in employees.
- New process: `python scripts/run_case.py --resume <case_id> --decision approve` → finalized, rows written, `cases.status = approved_by_human`.
- Same for a reject on scenario_17 → `rejected_by_human`, still no employee row.
- `pytest -q` still green.

Finish: tick step 7, set current step to 8, commit `step 7: escalation and resume`.
