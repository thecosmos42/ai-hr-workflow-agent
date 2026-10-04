"""Approval Queue page: escalated cases awaiting human approval."""
import sys
from pathlib import Path

import streamlit as st
from langgraph.types import Command

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import get_settings
from onboard_pilot.db import get_connection
from app import get_graph


def resume_case(graph, case_id: str, decision: str, comment: str) -> None:
    """Resume the interrupted escalate node with the human decision."""
    response = graph.invoke(
        Command(resume={"decision": decision, "comment": comment}),
        {"configurable": {"thread_id": case_id}},
    )
    response.pop("__interrupt__", None)
    st.session_state["last_result"] = f"{case_id}: {response.get('status')}"


st.set_page_config(page_title="Approval Queue", layout="wide")
st.title("Approval Queue")

graph = get_graph()

if "last_result" in st.session_state:
    st.success(f"Decision recorded - {st.session_state.pop('last_result')}")

conn = get_connection(get_settings().db_path)
escalated = conn.execute(
    """
    SELECT case_id, status, escalation_reason, created_at
    FROM cases
    WHERE status = 'escalated'
    ORDER BY created_at ASC
    """
).fetchall()
conn.close()

if not escalated:
    st.success("No escalated cases. Nothing awaiting approval.")
    st.stop()

st.warning(f"{len(escalated)} case(s) awaiting approval")

for case_id, status, reason, created in escalated:
    snap = graph.get_state({"configurable": {"thread_id": case_id}}).values
    form = snap.get("form")
    violations = snap.get("violations") or []

    with st.container(border=True):
        st.subheader(f"{case_id} - {getattr(form, 'full_name', 'unknown')}")
        st.write(f"**Role:** {getattr(form, 'role', 'N/A')}")
        st.write(f"**Status:** {status}")
        st.write(f"**Created:** {created}")

        st.write("**Escalation reason:**")
        st.info(reason or "No reason recorded")

        if violations:
            st.write("**Violations:**")
            for v in violations:
                st.write(f"- **[{v.severity}]** {v.code}: {v.message}")

        comment = st.text_input("Comment (optional)", key=f"comment_{case_id}")
        col_approve, col_reject = st.columns(2)
        with col_approve:
            if st.button("Approve", key=f"approve_{case_id}", use_container_width=True):
                try:
                    resume_case(graph, case_id, "approve", comment or "Approved via dashboard")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error approving: {e}")
        with col_reject:
            if st.button("Reject", key=f"reject_{case_id}", use_container_width=True):
                try:
                    resume_case(graph, case_id, "reject", comment or "Rejected via dashboard")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error rejecting: {e}")
