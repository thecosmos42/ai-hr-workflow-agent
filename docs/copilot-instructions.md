# onboard-pilot — repository instructions for Copilot

You are the implementing agent for **onboard-pilot**, an HR new-hire onboarding agent built with LangGraph.

## Source of truth (precedence: top wins)
1. `DEVIATIONS.md` — pre-approved clarifications (`P1`, `P2`, …) plus any deviations logged during the build. Treat `P` entries as part of the spec.
2. `plan.md` (repo root) — the full spec. Read the sections relevant to your task **before** writing code.
3. `PROGRESS.md` — tells you which build step you are on.

## How to work
- Build **one step at a time** (plan.md §13). The user will run a `/step-NN-...` prompt. Never start step N+1 until step N's acceptance criteria pass — actually run the commands and show the output.
- Start each step with a 3–6 bullet plan of the files you will create or change, then build. Don't ask permission per file.
- Finish each step: run acceptance commands → tick the step in `PROGRESS.md` → `git commit -m "step N: <description>"`.
- If the spec is impossible or ambiguous: choose the simplest option consistent with every **FIXED** item, log it in `DEVIATIONS.md`, and continue. Stop and ask only when truly blocked (missing API key, destructive action, two FIXED items in conflict).
- If an acceptance criterion fails, fix the code, prompts or validators. **Never** edit tests, thresholds or `evals/expected.yaml` to make them pass.
- Do not add features, pages, files or dependencies that are not in plan.md or DEVIATIONS.md.

## Hard constraints (plan.md §1 — FIXED)
- Python 3.11+, src layout, package `onboard_pilot`, installed with `pip install -e .` (or `uv pip install -e .`).
- LangGraph agent; Pydantic v2 (`extra="forbid"`) for all schemas.
- **Validators and routing are pure Python. They MUST NOT call an LLM.**
- LLM: **Anthropic Claude Haiku 4.5** (`claude-haiku-4-5-20251001`) via `langchain-anthropic` `ChatAnthropic`, `temperature=0` (DEVIATIONS P13). Model name comes from `config/settings.py`, never hardcoded. All LLM construction goes through `llm.get_llm()`.
- SQLite only (`data/onboard.db`); LangGraph `SqliteSaver` on `data/checkpoints.db`; ChromaDB at `data/chroma/`.
- Email/calendar are MOCK: write to `outbox` / `calendar_events` tables only. Never call SMTP/Google/Microsoft APIs.
- Business tables are written **only** in the `finalize` node (see DEVIATIONS P3 for the exact exceptions).
- Secrets (`ANTHROPIC_API_KEY`) from env / `.env`; commit `.env.example`, never `.env`.
- Streamlit dashboard: exactly 3 pages, no auth.
- Out of scope: PDF/OCR, real email/calendar, multi-agent crews, auth, offboarding, Docker, LLM-as-judge.

## Code conventions
- Type hints everywhere; small functions; docstrings on every tool (they are shown to the LLM).
- Every LLM prompt is a **named UPPER_SNAKE constant at the top of its module**.
- Tools never raise on business failures: return `ToolResult(ok=False, error_code=...)`. Raise only on programmer errors.
- Library code uses `logging`, not `print`. Paths and thresholds come from `config/settings.py`.
- Tests must not need network or an API key, except tests marked `@pytest.mark.integration`.
- Dates are injected (`today` parameter / `settings.get_today()`); never call `date.today()` inside validators or routing.

## Commands
```bash
uv venv && source .venv/bin/activate        # or: python -m venv .venv
uv pip install -e ".[dev]"                  # or: pip install -e ".[dev]"
python scripts/init_all.py                  # idempotent
pytest -q
python scripts/run_case.py evals/scenarios/scenario_01.json
streamlit run dashboard/app.py
python evals/run_evals.py --auto-approve-escalations
```

## Scoped instructions
Path-specific rules live in `.github/instructions/*.instructions.md` and apply automatically.
