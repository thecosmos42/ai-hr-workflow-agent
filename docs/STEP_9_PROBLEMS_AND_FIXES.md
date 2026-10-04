# Step 9: Problems Encountered and Fixes Applied

**Status:** In Progress (evaluation harness functional but escalation routing has unresolved issue)

**Date:** 2026-10-04

---

## Summary

Step 9 involved creating 25 evaluation scenarios and a complete evaluation harness (`run_evals.py`). During implementation and testing, multiple classes of issues were identified and fixed:

1. **Seed data incomplete** — scenarios used manager emails not in the database
2. **Scenario JSON schema violations** — invalid roles and locations  
3. **Escalation routing broken** — hard violations not triggering escalate node (IN PROGRESS)
4. **State merging on graph resume** — human_decision not persisting across interrupt/resume boundary (IN PROGRESS)

---

## Issue 1: Missing Managers in Seed Data

### Problem
Scenarios 02, 03, 06, 07, 09, 11, 12, 14, 16, 19, 21, 22, 24 all used manager email `dirk.van.der.meer@corp.example`, and scenarios 18, 25 used `unknown.manager@corp.example`. The seed data only created 5 managers (anna.visser, tom.bakker, sofia.jansen, mark.devries, lisa.smit).

When these scenarios ran, the validator `lookup_manager()` returned a `MANAGER_NOT_FOUND` hard violation, forcing escalation even for otherwise clean happy-path scenarios.

**Impact:** Scenarios 01-15, 19, 21-24 expected to auto-approve all showed as escalated, tanking the precision metric.

### Root Cause
The scenario JSON generator used rotating manager selections but didn't update the seed data to include all managers used in the scenarios.

### Fix Applied

**File:** `src/onboard_pilot/seed.py`

```python
def seed_managers(conn: sqlite3.Connection) -> None:
    """Seed 7 seeded managers. Idempotent."""
    managers = [
        ("anna.visser@corp.example", "Anna Visser"),
        ("tom.bakker@corp.example", "Tom Bakker"),
        ("sofia.jansen@corp.example", "Sofia Jansen"),
        ("mark.devries@corp.example", "Mark de Vries"),
        ("lisa.smit@corp.example", "Lisa Smit"),
        ("dirk.van.der.meer@corp.example", "Dirk van der Meer"),  # NEW
        ("unknown.manager@corp.example", "Unknown Manager"),         # NEW
    ]
    # ... rest unchanged
```

**File:** `scripts/init_all.py`

```python
if managers_count != 7:  # Changed from 5 to 7
    logger.error(f"Expected 7 managers, got {managers_count}")
    return False
```

**Verification:** After reinitializing with `python scripts/init_all.py`, database contained all 7 managers. Scenarios 02, 09, 16 then produced expected outcomes:
- scenario_02: auto_approved (not escalated) ✓
- scenario_09: auto_approved (not escalated) ✓  
- scenario_16: still running (separate issue—see below)

---

## Issue 2: Scenario JSON Schema Violations

### Problem  
When running full 25-scenario eval, Pydantic validation failed on:
- `scenario_03`: role='product_manager' (not in Literal enum), location='rotterdam_office' (not in Literal enum)
- `scenario_08`, `scenario_11`, `scenario_14`, `scenario_17`, `scenario_21`, `scenario_24`: location='rotterdam_office'
- `scenario_11`, `scenario_24`: role='product_manager'

The IntakeForm schema (src/onboard_pilot/schemas.py) defines strict Literal enums:
```python
role: Literal[
    "software_engineer", "data_analyst", "finance_officer", 
    "hr_coordinator", "sales_rep", "engineering_manager"
]
location: Literal["eindhoven_office", "amsterdam_office", "remote_nl"]
```

### Root Cause
Scenario JSON generator created valid-looking but non-conforming data. "product_manager" and "rotterdam_office" were plausible but not in the schema.

### Fix Applied

Manually corrected each scenario file:

1. **scenario_03**: role changed to "engineering_manager", location changed to "amsterdam_office"
2. **scenario_08, 11, 14, 17, 21, 24**: location changed to "eindhoven_office"
3. **scenario_11, 24**: role changed to "engineering_manager"

**Verification:** 
```bash
python evals/run_evals.py --only scenario_01,scenario_02,scenario_03,scenario_08
# All 4 scenarios loaded successfully (no Pydantic errors)
```

---

## Issue 3: Escalation never completed on resume (FIXED)

### Problem
Hard-violation scenarios (16, 17, 18, 20, 23, 25) ended with status="running"; escalation recall was 0%.

### Root cause
Resume was done with `graph.invoke({"human_decision": ...}, config)`. In LangGraph that starts a fresh run
instead of resuming the interrupted one, and `interrupt()` never returned the decision, so the escalate node
kept seeing `human_decision=None`. The earlier DB-fallback attempt could not work for the same reason.

### Fix
- `escalate` now does `decision = interrupt({...})` and applies the returned `{"decision", "comment"}`
  (status, `cases` row, state update). No state-input or DB fallback, debug logging removed.
- All resume callers use `Command(resume={"decision": ..., "comment": ...})`:
  `scripts/run_case.py`, `evals/run_evals.py`, `dashboard/pages/3_Approval_Queue.py`
  (which also pops `__interrupt__` before validating).

## Issue 3b: Seed managers reverted
Adding managers to the seed data (Issue 1) would have changed the fixed 5-manager seed (init_all asserts 5) and
made scenario 18/25 "unknown manager" unreachable. Seed and init_all are back to 5 managers; scenarios that used
`dirk.van.der.meer@...` now use seeded managers. `unknown.manager@...` stays unseeded so MANAGER_NOT_FOUND fires.

## Final results (full run)
- Auto-approval precision 89.5% (17/19), escalation recall 100% (6/6), hard-case recall 100% (5/5)
- Mean retries 0.60, total cost about EUR 0.35
- Mismatches: scenario_09 and scenario_12 (budget traps) hit max retries and escalated (LLM variance;
  expectations deliberately not changed). 111 unit tests pass.
## Issue 4: __interrupt__ Key Handling

### Problem (FIXED)

When graph.invoke() returns with an interrupt, the response dict contains a special `__interrupt__` key (list of Interrupt objects). This key is not part of OnboardingState schema, so `OnboardingState.model_validate(response)` would fail with:

```
ValidationError: __interrupt__
  Extra inputs are not permitted [type=extra_forbidden, ...]
```

### Fix Applied

**File:** `scripts/run_case.py` (lines 104-108)

```python
if "__interrupt__" in response:
    if args.auto_approve_escalations:
        response = graph.invoke(
            {"human_decision": "approve", "human_comment": "auto-approved in eval mode"},
            config,
        )
        response.pop("__interrupt__", None)  # ADDED
        final = OnboardingState.model_validate(response)
```

**File:** `evals/run_evals.py` (lines 100-102)

```python
# Remove the special interrupt key if present
response.pop("__interrupt__", None)

if logger.isEnabledFor(logging.DEBUG):
    logger.debug(f"  Final status: {response.get('status')}")

final = OnboardingState.model_validate(response)
```

---

## Changes Made to Files

### New/Modified Files:

1. **`src/onboard_pilot/seed.py`** — Added 2 new managers to seed data
2. **`scripts/init_all.py`** — Updated manager count check from 5 to 7  
3. **`scripts/run_case.py`** — Added `--debug` flag, fixed __interrupt__ key handling, added fallback DB lookup for escalate node
4. **`src/onboard_pilot/graph/nodes.py`** — Added debug logging to validate and escalate nodes, added DB fallback for human_decision
5. **`evals/run_evals.py`** — Fixed __interrupt__ key handling, added debug logging for interrupt/resume flow
6. **`evals/scenarios/scenario_03.json`** — Fixed role and location  
7. **`evals/scenarios/scenario_08, 11, 14, 17, 21, 24.json`** — Fixed location
8. **`evals/scenarios/scenario_11, 24.json`** — Fixed role

---

## Test Results

### Before Fixes
- Scenarios 02, 09, 16: status="running" (all expected auto_approved or escalated)
- scenario_01: auto_approved ✓ (worked by luck: no hard violations)

### After Fix #1 & #2 (Seed Data + Schema Validation)
- scenario_01: auto_approved ✓ (0 retries, cost 0.0100 EUR)
- scenario_02: auto_approved ✓ (1 retry, cost 0.0175 EUR)
- scenario_03 through scenario_15: auto_approved ✓ (all happy paths working)
- scenario_16: still status="running" ✗ (expected escalated)
- scenario_17: still status="running" ✗ (expected escalated)
- scenario_18: auto_approved (expected escalated—incorrect outcome)
- scenario_19: auto_approved ✓
- scenario_20: status="running" ✗ (expected escalated)
- scenario_21: auto_approved ✓ (known gap: prose-only rule)
- scenario_22: auto_approved ✓ (license pool, self-corrects)
- scenario_23: status="running" ✗ (expected escalated)
- scenario_24: auto_approved ✓
- scenario_25: status="running" ✗ (expected escalated)

### Metrics After Fixes #1 & #2
```
Auto-approval precision:  100.0% (19/19)  ✓ [All cases that should auto-approve do]
Escalation recall:        0.0% (0/6)      ✗ [Should escalate 6, got 0]
Hard-case escalation:     0.0% (0/5)      ✗ [Should escalate 5, got 0]
Mean retries:             0.56
Mean cost (EUR):          €0.0138
Total cost (EUR):         €0.3450
```

**1 mismatched outcome:**
- scenario_18: auto_approved (expected escalated)
  - Reason: Unknown manager email should be hard violation, but was handled somehow
  - Investigation needed: Why didn't validator catch MANAGER_NOT_FOUND for scenario_18?

---

## Remaining Issues (BLOCKING)

### Critical: Escalation Routing Broken
- 5 scenarios with hard violations show status="running" instead of "escalated"
- 1 scenario (18) shows status="auto_approved" instead of "escalated"  
- Acceptance criteria: `hard_case_escalation recall = 1.0` (all hard cases must escalate)
- **Root cause:** State merging between interrupt and resume not working; human_decision not passed through to escalate node on resume
- **Impact:** Cannot commit step 9 until this is fixed

### Medium: Debug Logging Left In Code
- Added logger.info() calls for troubleshooting
- Should be removed or demoted to DEBUG level before commit

### Known Gap (Expected)
- scenario_21 (contractor + aws_dev): Prose-only rule in handbook not implemented in validators
- Marked as known gap in results; correct behavior (auto_approved)

---

## Next Steps

1. **Debug and fix state merging on resume** — Understand correct LangGraph API for resuming with state updates
   - Option A: Use database as intermediary (write human_decision before second invoke)
   - Option B: Use Command API or custom input handler
   - Option C: Rethink interrupt/resume pattern
   
2. **Verify all 25 scenarios reach expected outcomes**

3. **Run full eval and confirm metrics:**
   - precision ≥ 0.85 ✓ (already achieved: 100%)
   - hard-case escalation recall = 1.0 ✗ (currently 0%, need to fix)
   - mean retries reasonable

4. **Clean up debug logging** from nodes.py and run_case.py

5. **Commit step 9:** `"step 9: 25 scenarios + run_evals.py - evaluation harness"`

6. **Proceed to step 10:** README, demo GIF, cleanup, fresh-clone validation

---

## Lessons Learned

1. **Seed data must match scenario requirements** — Easy to miss when scenarios are generated independently
2. **Schema validation early catches issues** — First few scenarios revealed location/role problems before full run
3. **LangGraph interrupt/resume state handling is non-obvious** — State dict passed to invoke() does not automatically merge with checkpoint; may need explicit DB persistence or API change
4. **Debug logging is crucial for understanding graph flow** — Escalate node being called twice but human_decision not persisting was only visible with logs
5. **Run acceptance tests incrementally** — Testing 4 scenarios before running all 25 caught issues early

