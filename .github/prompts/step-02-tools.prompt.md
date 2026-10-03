---
description: "Build step 2 — the five tools + tests/test_tools.py"
agent: agent
---
Execute **build step 2** of [plan.md](../../plan.md) §13. Read first: plan.md §3.4, §5 and DEVIATIONS.md (P3). Follow `.github/instructions/tools.instructions.md`. Step 1 must be ticked in [PROGRESS.md](../../PROGRESS.md).

Build in `src/onboard_pilot/tools/`:
- `hr_db.py`: `lookup_manager`, `check_duplicate`, `create_employee` (called only from finalize — docstring says so).
- `it_provisioner.py`: `request_account` with the FIXED check order (UNKNOWN_SYSTEM → ROLE_NOT_PERMITTED → adobe_cc always LICENSE_POOL_EXHAUSTED → success + `access_requests` row `proposed`). Use `random.seed(42)` only if you add randomness; adobe_cc must be deterministic.
- `equipment_catalog.py`: `search_catalog(query, category)`, `get_item(catalog_id)`. No budget logic.
- `policy_rag.py`: **stub for now** with the `query_policy(question, k=4)` signature and a `build_index()` placeholder that raises `NotImplementedError` (implemented in step 4).
- `scheduler.py`: `commit_events(plan)` → inserts `calendar_events` + one summary `outbox` row.
- Expose LLM-callable ones (`lookup_manager`, `request_account`, `search_catalog`, `get_item`, `query_policy`) as LangChain `@tool` wrappers that delegate to the plain functions.

`tests/test_tools.py` (temp DB fixture per test, no network): manager found/not found, duplicate detection, create_employee inserts, unknown system, role-not-permitted, adobe_cc fails for **every** role, success inserts a `proposed` row, catalog search/get_item (incl. out-of-stock item and unknown id), commit_events writes calendar rows and one outbox row, tools never raise on business failure.

Acceptance: `pytest tests/test_tools.py -q` is green.
Finish: tick step 2, set current step to 3, commit `step 2: tools and tool tests`.
