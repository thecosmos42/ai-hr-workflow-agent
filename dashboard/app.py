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


def get_case_values(graph, case_id: str) -> dict:
    """Read checkpointed state values without re-validating them against the schema.

    graph.get_state() coerces values into OnboardingState, which fails when Streamlit
    reloads onboard_pilot.schemas and the cached graph holds the older class objects.
    """
    tup = graph.checkpointer.get_tuple({"configurable": {"thread_id": case_id}})
    return dict(tup.checkpoint["channel_values"]) if tup else {}


if __name__ == "__main__":
    st.switch_page("pages/1_Cases.py")
