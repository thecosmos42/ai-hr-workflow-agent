---
applyTo: "src/onboard_pilot/tools/**,src/onboard_pilot/db.py,src/onboard_pilot/seed.py,tests/test_tools.py"
---
# Tool rules (plan.md §5)

- Every tool returns `ToolResult`. Business failures → `ok=False` with an `error_code`; never raise for them.
- Tools that the LLM may call are wrapped as LangChain `@tool` **and** remain plain callable functions for nodes and tests. Keep the plain function as the implementation; the `@tool` wrapper only delegates.
- `it_provisioner.request_account` order of checks is FIXED: `UNKNOWN_SYSTEM` → `ROLE_NOT_PERMITTED` → `adobe_cc` always `LICENSE_POOL_EXHAUSTED` (deterministic, not random) → success + INSERT `access_requests` row with `status='proposed'`.
- `equipment_catalog` never enforces budgets (validators do). Say so in the module docstring.
- `hr_db.create_employee` and `scheduler.commit_events` are called **only from `finalize`**.
- `policy_rag.query_policy` returns `{section_id, text, score}` with score in [0,1]. Embeddings are Chroma's default local function (P14). Use a cosine-space Chroma collection and `similarity = 1 - distance`, clipped to [0,1].
- SQLite: `row_factory = sqlite3.Row`, `PRAGMA foreign_keys=ON`, parameterized queries only. `init_db()` and `seed` must be idempotent.
- Tests: use a temp DB per test (fixture). Cover every error code, including that `adobe_cc` fails for every role.
