---
description: "Build step 9 — 25 scenarios, expected.yaml, run_evals.py"
agent: agent
---
Execute **build step 9** of [plan.md](../../plan.md) §13. Read first: plan.md §10 and DEVIATIONS.md (P2, P10). Follow `.github/instructions/evals.instructions.md`. Step 8 must be ticked in [PROGRESS.md](../../PROGRESS.md).

1. Create `evals/scenarios/scenario_01.json … scenario_25.json` with the **exact FIXED distribution** of §10.1 (1–8 happy paths covering all 6 roles, 4 levels and 3 locations; 9–12 budget traps; 13–15 access violations; 16 privileged, 17 start too soon, 18 unknown manager; 19 visa; 20 remote_nl monitor request; 21 contractor + aws_dev; 22 adobe_cc; 23 duplicate email (seed an existing employee or reuse a previously finalized email deterministically); 24 out-of-stock chair; 25 everything-wrong). Keep existing 01/09/16/17/18/22 consistent. Start dates ≥ 2026-10-11 except 17. Unique `case_id`s.
2. `evals/expected.yaml` in the §10.1 format for all 25 scenarios (scenario 21: `auto_approved` + note "known gap"; scenario 25: `escalated` with a note that resolving within retries is also acceptable).
3. `evals/run_evals.py`: fresh DB file, `TODAY_OVERRIDE=2026-10-01`, run every scenario (or `--only`), `--auto-approve-escalations`. Record per case: expected vs actual outcome, hard codes seen, retries, cost, latency, final-plan violation count (re-run `run_all_validators` on the final plan). Metrics: auto-approval precision, escalation recall (also report recall on hard-violation scenarios separately), mean retries, mean cost, total cost. Write `evals/results.csv` and `evals/report.md` (metrics table, per-scenario table, **Known gaps** section flagging scenario 21, mismatches listed honestly).
4. Run a few scenarios first with `--only`, fix problems, then the full run.

Acceptance: `python evals/run_evals.py --auto-approve-escalations` completes and writes both files; precision ≥ 0.85; escalation recall = 1.0 on the hard-violation scenarios (16, 17, 18, 23) and on scenario 20. If targets are missed, **fix prompts/validators — never expected.yaml or thresholds** — and re-run. Report the real numbers.

Finish: tick step 9, set current step to 10, commit `step 9: eval harness and results`.
