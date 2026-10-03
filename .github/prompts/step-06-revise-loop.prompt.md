---
description: "Build step 6 — revise/self-correction loop"
agent: agent
---
Execute **build step 6** of [plan.md](../../plan.md) §13. Read first: plan.md §6.3, §6.4 and DEVIATIONS.md (P1, P9). Follow `.github/instructions/graph.instructions.md`. Step 5 must be ticked in [PROGRESS.md](../../PROGRESS.md).

1. Implement the `revise` node: prompt constant at module top containing the current plan JSON, violations JSON, and the exact instruction *"Modify ONLY the parts of the plan needed to resolve these violations. Return the full corrected OnboardingPlan."* Increment `retry_count`; same structured-output + retry-once handling as `plan`; save old/new plan in the audit payload.
2. Edge `revise → execute_tools → validate`. Confirm `execute_tools` replaces `tool_results` and re-creates proposed access_requests rows each pass.
3. Make sure `validate` includes `violations_from_tool_results` (P1) so tool failures trigger revise.
4. Create `evals/scenarios/scenario_09.json` (budget trap: e.g. junior with `requested_extras: ["MacBook Pro", "two ultrawide monitors"]`) and `scenario_22.json` (`requested_extras: ["adobe_cc license"]`). Start dates ≥ 2026-10-11.
5. Run each scenario 3 times; if the model never produces a first-pass violation, adjust the **plan prompt** (stay literal-first), not the validators.

Acceptance (show the printed trace / audit_log rows):
- scenario_09: `BUDGET_EXCEEDED` on attempt 0, clean pass on a later attempt, `retry_count ≥ 1`, final status `auto_approved`.
- scenario_22: `TOOL_FAILURE` (adobe_cc) → revised plan substitutes an alternative and adds a follow-up task → `auto_approved`.
- `pytest -q` still green.

Finish: tick step 6, set current step to 7, commit `step 6: revise loop`.
