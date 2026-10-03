---
description: "Build step 10 — README business case, cleanup, fresh-clone check"
agent: agent
---
Execute **build step 10** of [plan.md](../../plan.md) §13. Read first: plan.md §12 and the real `evals/report.md`. Step 9 must be ticked in [PROGRESS.md](../../PROGRESS.md).

1. Write `README.md` with every §12 section: Problem, Solution + mermaid architecture diagram, Demo (D1=scenario_01, D2=scenario_09, D3=scenario_20, D4=scenario_16, D5=scenario_22 with the exact commands), Hours-saved math (150 hires/yr × 40 min ≈ 100 hrs), **Eval results table copied from the real `evals/report.md`** (never invent numbers), Failure modes & mitigations (prose-only rule gap / scenario 21, stale RAG, over-escalation tuning, cost table + assumed FX rate, the §3.2/§6.4 heuristic honestly described as a heuristic), Design decisions (deterministic validators vs LLM-judge; DB writes only in finalize; cheap model + governance; literal-first plan prompt P9; TOOL_FAILURE addition P1), Setup instructions (needs `ANTHROPIC_API_KEY`; embeddings run locally — mention the first-run model download).
2. Add a clearly marked placeholder for the demo GIF (`docs/demo.gif`) — you cannot record it; tell the user how (screen-record the dashboard running D2 and D3).
3. Cleanup: remove dead code and debug prints, ensure `.gitignore` covers `.env`, `data/*.db`, `data/chroma/`, `__pycache__`; make sure every deviation is in `DEVIATIONS.md`; `plan.md` is present at the repo root.
4. Fresh-clone check: clone the repo into a temp dir, create a venv, install, copy `.env.example` → `.env` (user's key), run `python scripts/init_all.py` and `python scripts/run_case.py evals/scenarios/scenario_01.json`. Fix the README until this works exactly as written.

Acceptance: the fresh-clone sequence works per README; `pytest -q` is green.
Finish: tick step 10 and commit `step 10: readme and cleanup`. Then print a short summary of deviations and anything the user must do manually (GIF, API key).
