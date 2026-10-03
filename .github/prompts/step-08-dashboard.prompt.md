---
description: "Build step 8 — Streamlit dashboard (3 pages)"
agent: agent
---
Execute **build step 8** of [plan.md](../../plan.md) §13. Read first: plan.md §11 and DEVIATIONS.md (P11). Follow `.github/instructions/dashboard.instructions.md`. Step 7 must be ticked in [PROGRESS.md](../../PROGRESS.md).

Build `dashboard/app.py` (bootstrap + cached `get_graph()`), and the three pages exactly as specified:
- `1_Cases.py`: cases table (id, name, role, status, retries, cost, created), 4 metric tiles (total cases, % auto-approved, mean cost/case, mean retries), "Run scenario" with a file picker over `evals/scenarios/`.
- `2_Case_Trace.py`: case selector → chronological audit_log expanders (node, attempt, latency, tokens, cost, summary) with payload (violations, plan diff, tool results). Make the self-correction obvious.
- `3_Approval_Queue.py`: escalated cases with pretty plan, reason, citations, violations; Approve / Reject + comment → `Command(resume=...)`.
Add helper queries to `db.py` where needed. No extra pages, no auth.

Acceptance (run `streamlit run dashboard/app.py`, then verify and report what you checked; use the terminal/browser tools if available, otherwise list manual steps for the user):
- Run scenario_09 from page 1; page 2 shows BUDGET_EXCEEDED → clean pass.
- Run scenario_16; page 3 lists it; Approve resumes and finalizes; case leaves the queue.
- App starts without errors; `pytest -q` still green.

Finish: tick step 8, set current step to 9, commit `step 8: streamlit dashboard`.
