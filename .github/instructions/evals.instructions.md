---
applyTo: "evals/**,scripts/init_all.py"
---
# Eval rules (plan.md §10)

- Freeze `today = 2026-10-01` through `TODAY_OVERRIDE` (DEVIATIONS P2). Scenario `start_date`s must be ≥ 2026-10-11 (min notice 10 days) **except** scenario 17 (3 days out → 2026-10-04).
- Reset to a fresh DB file before each full run; case ids unique per run.
- Scenario distribution is FIXED (plan.md §10.1). Scenario 21 is a *known gap*: record the actual outcome and flag it in `report.md`.
- Metrics: auto-approval precision, escalation recall, mean retries, mean/total cost EUR. Measure outcomes **before** auto-resolving escalations (`--auto-approve-escalations` only exists so the run completes).
- Results (`results.csv`, `report.md`) must come from real runs. **Never fabricate or hand-edit numbers.** If targets are missed, fix prompts/validators, never `expected.yaml`.
- LLM runs cost money: support `--only scenario_09[,scenario_16]` for iteration (DEVIATIONS P10).
