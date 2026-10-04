"""Case Trace page: audit log viewer with expandable steps."""
import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import get_settings
from onboard_pilot.db import get_connection


st.set_page_config(page_title="Case Trace", layout="wide")
st.title("Case Trace")

# Fetch all cases for dropdown
conn = get_connection()
cases = conn.execute(
    "SELECT case_id, case_id as name FROM cases ORDER BY created_at DESC"
).fetchall()
conn.close()

if not cases:
    st.info("No cases found. Run a scenario first.")
    st.stop()

# Case selector
case_ids = [c[0] for c in cases]
case_labels = [f"{c[0]} ({c[1]})" for c in cases]
selected_idx = st.selectbox("Select case", range(len(cases)), format_func=lambda i: case_labels[i])
selected_case_id = case_ids[selected_idx]

# Fetch audit log for selected case
conn = get_connection()
audit_entries = conn.execute(
    """
    SELECT node, attempt, latency_ms, tokens_in, tokens_out, cost_eur, summary, payload_json
    FROM audit_log
    WHERE case_id = ?
    ORDER BY rowid ASC
    """,
    (selected_case_id,)
).fetchall()
conn.close()

if not audit_entries:
    st.info(f"No audit log entries for {selected_case_id}")
    st.stop()

st.subheader(f"Trace for {selected_case_id}")

# Show each audit entry as an expander
for i, (node, attempt, latency_ms, in_tokens, out_tokens, cost, summary, payload_json) in enumerate(audit_entries):
    # Determine icon based on summary/status
    icon = "❌" if "BUDGET_EXCEEDED" in summary else "✅" if "clean" in summary.lower() else "ℹ️"
    
    # Build header: icon + node + attempt + summary
    tokens = (in_tokens or 0) + (out_tokens or 0)
    latency_ms = int(latency_ms or 0)
    cost_val = float(cost or 0)
    header = f"{icon} {node} (attempt {attempt}) | {latency_ms}ms, {tokens} tokens, €{cost_val:.4f} | {summary[:60]}..."
    
    with st.expander(header):
        # Show structured info
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Node", node)
        with col2:
            st.metric("Attempt", attempt)
        with col3:
            st.metric("Latency", f"{latency_ms}ms")
        with col4:
            st.metric("Tokens", tokens)
        with col5:
            st.metric("Cost", f"€{cost_val:.4f}")
        
        st.write("**Summary:**")
        st.write(summary)
        
        # Show payload if present
        if payload_json:
            try:
                payload = json.loads(payload_json)
                st.write("**Payload:**")
                
                # Violations
                if "violations" in payload and payload["violations"]:
                    st.write("*Violations:*")
                    for v in payload["violations"]:
                        st.write(f"  - [{v.get('severity')}] {v.get('code')}: {v.get('message')}")
                
                # Plan diff
                if "plan" in payload:
                    st.write("*Plan:*")
                    st.json(payload["plan"])
                
                # Tool results
                if "tool_results" in payload and payload["tool_results"]:
                    st.write("*Tool Results:*")
                    for tool_name, results in payload["tool_results"].items():
                        st.write(f"  **{tool_name}:**")
                        for result in results:
                            status = "✓" if result.get("ok") else "✗"
                            st.write(f"    {status} {result.get('error_code', 'ok')}: {result.get('error_message', result.get('data', ''))}")
            except Exception as e:
                st.error(f"Error parsing payload: {e}")
