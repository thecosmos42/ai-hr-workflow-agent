---
description: "Build step 3 — validators, violations, routing + unit tests"
agent: agent
---
Execute **build step 3** of [plan.md](../../plan.md) §13. Read first: plan.md §3.3, §6 and DEVIATIONS.md (P1, P4–P8). Follow `.github/instructions/validation.instructions.md`. Step 2 must be ticked in [PROGRESS.md](../../PROGRESS.md).

Build:
- `validation/violations.py`: `PolicyViolation` is already in schemas — here define the `ViolationCode` enum (the 13 codes of §6.2 **plus `TOOL_FAILURE`**, P1) and a severity map.
- `validation/validators.py`: one small pure function per check, `run_all_validators(plan, form, today, conn=None)`, and `violations_from_tool_results(tool_results)` (P1). Every message contains the offending value and the limit.
- `graph/routing.py`: `route_after_validation(state)`, `conflicting_policy_detected(state)`, `build_escalation_reason(state)`. Pure functions (P8). `MAX_RETRIES` / `RAG_SCORE_THRESHOLD` come from settings.

Tests (no LLM, no network, `today = date(2026, 10, 1)`):
- `tests/test_validators.py`: every violation code has ≥1 positive and ≥1 negative case; budget cases cover each level, the remote allowance (P6), catalog-price authority (P5), training deadlines (P7), day-1 events, visa task, `plan=None`, and "returns ALL violations, not just the first".
- `tests/test_routing.py`: hard → escalate (even with retries left), soft & retries left → revise, soft & retries exhausted → escalate, clean + low RAG → escalate, clean + §3.2 & §6.4 cited + remote_nl → escalate, same citations but not remote → finalize, clean → finalize; `build_escalation_reason` names every trigger.

Acceptance: `pytest tests/test_validators.py tests/test_routing.py -q` is green and the full `pytest -q` still passes.
Finish: tick step 3, set current step to 4, commit `step 3: validators and routing`.
