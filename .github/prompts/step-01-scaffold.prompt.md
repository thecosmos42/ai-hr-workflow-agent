---
description: "Build step 1 — scaffold, config, schemas, db, seed, init_all"
agent: agent
---
Execute **build step 1** of [plan.md](../../plan.md) §13. Read first: plan.md §1, §2, §3, §4, §6.1, §8, §9 and [DEVIATIONS.md](../../DEVIATIONS.md) (P2, P3, P12, P13). Check [PROGRESS.md](../../PROGRESS.md).

Do, in order:
1. Create the **exact** layout from §2. Later-step modules may be stubs containing only a module docstring. Empty `__init__.py` where needed.
2. `pyproject.toml` (setuptools, `src` layout, package `onboard_pilot`, `[dev]` extra with pytest). Pin top-level deps: langgraph, langgraph-checkpoint-sqlite, langchain-anthropic, langchain-core, chromadb, pydantic>=2, pydantic-settings, pyyaml, python-dotenv, email-validator, streamlit, pandas. Also `.env.example` (containing `ANTHROPIC_API_KEY=sk-ant-...`) and `.gitignore` per §2. Run `git init` if there is no repo.
3. `config/policy_tables.yaml` — **verbatim** content from §6.1.
4. `config/settings.py` (pydantic-settings): `llm_model="claude-haiku-4-5-20251001"`, `llm_max_tokens=4096` (P13), `MAX_RETRIES=3`, `RAG_SCORE_THRESHOLD=0.35`, DB/checkpoint/chroma paths, `TODAY_OVERRIDE`, `get_today()`, and a cached `load_policy_tables()`.
5. `schemas.py` — every model from §3 with the exact field names, `extra="forbid"`. `graph/state.py` — `OnboardingState` from §4.
6. `db.py` — `init_db()` creating ALL tables: `employees` (with `is_manager`), `equipment_catalog`, `access_matrix` (mirror of the yaml, reference only), `access_requests`, `equipment_orders`, `calendar_events`, `onboarding_tasks`, `outbox`, `cases`, `audit_log` (exact DDL from §8). Plus a connection helper and the CRUD helpers you can already foresee. Idempotent.
7. `seed.py` — 5 managers (§9.1), ~20 catalog items (§9.2, including EQ-001…EQ-005 and EQ-010 out of stock), access matrix rows from the yaml. Idempotent (upsert / `INSERT OR IGNORE`).
8. `scripts/init_all.py` — init_db + seed, then call `build_index()` from `tools/policy_rag.py` **only if it exists** (it will in step 4). Idempotent.

Acceptance (run them, show output):
- `python scripts/init_all.py` twice → still exactly 5 managers and the same catalog count (≥ 20).
- `python -c "from onboard_pilot.schemas import IntakeForm, OnboardingPlan"` works.

Finish: tick step 1 in PROGRESS.md, set "Current step" to 2, commit `step 1: scaffold, config, schemas, db, seed`.
