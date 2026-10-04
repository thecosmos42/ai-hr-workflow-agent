"""Approval Queue page: escalated cases awaiting human approval."""
import json
import sys
from pathlib import Path

import streamlit as st
from langgraph.types import Command

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import get_settings
from onboard_pilot.db import get_connection
from onboard_pilot.schemas import OnboardingState
from app import get_graph


st.set_page_config(page_title="Approval Queue", layout="wide")
st.title("Approval Queue")

graph = get_graph()

# Fetch escalated cases
conn = get_connection(get_settings().onboard_db_path)
escalated = conn.execute(
    """
    SELECT case_id, full_name, role, status, escalation_reason, created_at
    FROM cases
    WHERE status = 'escalated'
    ORDER BY created_at ASC
    """
).fetchall()
conn.close()

if not escalated:
    st.success("✓ No escalated cases. All hires approved!")
    st.stop()

st.warning(f"⏳ {len(escalated)} case(s) awaiting approval")

# Show each escalated case
for case_id, full_name, role, status, reason, created in escalated:
    with st.container(border=True):
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.subheader(f"📋 {case_id} — {full_name}")
            st.write(f"**Role:** {role}")
            st.write(f"**Status:** {status}")
            st.write(f"**Created:** {created}")
        
        # Show escalation reason
        st.write("**Escalation Reason:**")
        st.info(reason)
        
        # Fetch and show violations
        conn = get_connection(get_settings().onboard_db_path)
        audit_entry = conn.execute(
            "SELECT payload FROM audit_log WHERE case_id = ? AND node = 'escalate' LIMIT 1",
            (case_id,)
        ).fetchone()
        conn.close()
        
        if audit_entry and audit_entry[0]:
            try:
                payload = json.loads(audit_entry[0])
                if "violations" in payload:
                    st.write("**Violations:**")
                    for v in payload["violations"]:
                        st.write(
                            f"  **[{v.get('severity')}]** {v.get('code')}: {v.get('message')}"
                        )
            except Exception as e:
                st.error(f"Error loading violations: {e}")
        
        # Approval actions
        st.divider()
        col_approve, col_reject = st.columns(2)
        
        with col_approve:
            if st.button("✅ Approve", key=f"approve_{case_id}", use_container_width=True):
                with st.spinner("Processing..."):
                    try:
                        comment = st.text_input(
                            "Approval comment",
                            key=f"comment_approve_{case_id}",
                            label_visibility="collapsed"
                        )
                        response = graph.invoke(
                            Command(resume={"decision": "approve", "comment": comment or "Approved via dashboard"}),
                            {"configurable": {"thread_id": case_id}}
                        )
                        response.pop("__interrupt__", None)
                        final = OnboardingState.model_validate(response)
                        st.success(f"✓ Approved! Status: {final.status}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error approving: {e}")
        
        with col_reject:
            if st.button("❌ Reject", key=f"reject_{case_id}", use_container_width=True):
                with st.spinner("Processing..."):
                    try:
                        comment = st.text_input(
                            "Rejection reason",
                            key=f"comment_reject_{case_id}",
                            label_visibility="collapsed"
                        )
                        response = graph.invoke(
                            Command(resume={"decision": "reject", "comment": comment or "Rejected via dashboard"}),
                            {"configurable": {"thread_id": case_id}}
                        )
                        response.pop("__interrupt__", None)
                        final = OnboardingState.model_validate(response)
                        st.success(f"✓ Rejected. Status: {final.status}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error rejecting: {e}")
        
        st.divider()
