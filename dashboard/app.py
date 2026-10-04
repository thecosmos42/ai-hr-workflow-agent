"""Streamlit dashboard bootstrap. Builds and caches the LangGraph agent."""
import sqlite3

import streamlit as st
from config.settings import get_settings
from langgraph.checkpoint.sqlite import SqliteSaver
from onboard_pilot.graph.build import build_graph


@st.cache_resource
def get_graph():
    """Build and cache the onboarding graph with SqliteSaver checkpointer."""
    checkpointer = SqliteSaver(sqlite3.connect(
        str(get_settings().checkpoints_db_path),
        check_same_thread=False
    ))
    return build_graph(checkpointer=checkpointer)


if __name__ == "__main__":
    st.switch_page("pages/1_Cases.py")
