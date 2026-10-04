"""Cases page: list all cases, metrics, and run scenario button."""
import json
import sqlite3
import uuid
from pathlib import Path

import streamlit as st
from config.settings import get_settings
from onboard_pilot.db import get_connection
from onboard_pilot.schemas import IntakeForm

# Import from sibling app.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from app import get_graph


st.set_page_config(page_title="Cases", layout="wide")
st.title("Onboarding Cases")

# Get graph
graph = get_graph()

# Fetch all cases with retry count from audit log
conn = get_connection(get_settings().onboard_db_path)
cases_raw = conn.execute(
    "SELECT case_id, status, created_at FROM cases ORDER BY created_at DESC"
).fetchall()

# Enrich with retry count and role/name from intake form (stored in audit log)
cases = []
for case_id, status, created_at in cases_raw:
    # Get retry count (max attempt number in audit_log)
    retry_count = conn.execute(
        "SELECT COALESCE(MAX(attempt), 0) FROM audit_log WHERE case_id = ?",
        (case_id,)
    ).fetchone()[0]
    cases.append((case_id, case_id, "N/A", status, retry_count, created_at))

conn.close()

# Calculate metrics
total_cases = len(cases)
auto_approved = sum(1 for c in cases if c[3] == "auto_approved")
auto_approved_pct = (auto_approved / total_cases * 100) if total_cases else 0

# Calculate costs
conn = get_connection()
costs = {}
for case_id, _, _, _, _, _ in cases:
    cost = conn.execute(
        "SELECT COALESCE(SUM(cost_eur), 0) FROM audit_log WHERE case_id = ?",
        (case_id,)
    ).fetchone()[0]
    costs[case_id] = cost
conn.close()

mean_cost = sum(costs.values()) / total_cases if total_cases else 0
mean_retries = sum(c[4] for c in cases) / total_cases if total_cases else 0

# Show metrics
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Cases", total_cases)
with col2:
    st.metric("% Auto-Approved", f"{auto_approved_pct:.1f}%")
with col3:
    st.metric("Mean Cost (EUR)", f"{mean_cost:.4f}")
with col4:
    st.metric("Mean Retries", f"{mean_retries:.2f}")

st.divider()

# Run scenario button
st.subheader("Run Scenario")
scenario_dir = Path("evals/scenarios")
scenario_files = sorted(scenario_dir.glob("*.json"))

if scenario_files:
    selected_file = st.selectbox(
        "Choose a scenario",
        scenario_files,
        format_func=lambda p: p.name
    )
    if st.button("▶ Run", key="run_scenario"):
        st.info("Running scenario...")
        try:
            form = IntakeForm.model_validate(
                json.loads(selected_file.read_text(encoding="utf-8-sig"))
            )
            config = {
                "configurable": {
                    "thread_id": form.case_id,
                    "run_id": f"run-{uuid.uuid4().hex[:8]}"
                }
            }
            response = graph.invoke({"case_id": form.case_id, "form": form}, config)
            
            # Check for interrupt
            if "__interrupt__" in response:
                st.warning("⏸ Case escalated and awaiting approval")
            else:
                st.success("✓ Case completed")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")
else:
    st.warning("No scenarios found in evals/scenarios/")

st.divider()

# Cases table
st.subheader("All Cases")
if cases:
    table_data = []
    for case_id, full_name, role, status, retries, created in cases:
        cost = costs.get(case_id, 0)
        table_data.append({
            "Case ID": case_id,
            "Name": full_name,
            "Role": role,
            "Status": status,
            "Retries": retries,
            "Cost (EUR)": f"{cost:.4f}",
            "Created": created,
        })
    st.dataframe(table_data, use_container_width=True, hide_index=True)
else:
    st.info("No cases yet. Run a scenario to get started.")
