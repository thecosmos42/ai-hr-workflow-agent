---
applyTo: "dashboard/**"
---
# Dashboard rules (plan.md §11)

- Exactly 3 pages: `1_Cases.py`, `2_Case_Trace.py`, `3_Approval_Queue.py`. `app.py` is only a bootstrap (DEVIATIONS P11): it defines `get_graph()` decorated with `@st.cache_resource` (SqliteSaver, `check_same_thread=False`) and, under `if __name__ == "__main__":`, calls `st.switch_page("pages/1_Cases.py")`. Pages import it with `from app import get_graph`.
- Read data through `db.py` helpers; no business logic in the UI.
- Trace page ("the money page"): audit_log rows in chronological order as `st.expander`s showing node, attempt, latency, tokens, cost, summary; payload shows violations, plan diff (old vs new), tool results. A BUDGET_EXCEEDED → clean-pass sequence must be visually obvious (e.g. ❌ / ✅ on the summary line).
- Approval page: lists `cases.status = 'escalated'`; Approve/Reject + comment; resumes with `graph.invoke(Command(resume={"decision":..., "comment":...}), config={"configurable": {"thread_id": case_id}})`. Reject ends the case — no further revise.
- No auth, no extra pages, no custom CSS frameworks.
