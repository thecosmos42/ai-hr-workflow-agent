"""Graph assembly. `build_graph` is the only place the graph is wired."""
import sqlite3
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from config.settings import get_settings
from onboard_pilot.graph import nodes
from onboard_pilot.graph.routing import route_after_validation
from onboard_pilot.schemas import OnboardingState


def make_checkpointer() -> SqliteSaver:
    """SqliteSaver on data/checkpoints.db."""
    path = get_settings().checkpoints_db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver(sqlite3.connect(str(path), check_same_thread=False))


def route_after_escalation(state: OnboardingState) -> str:
    """After a human decision: approved cases finalize, anything else ends."""
    return "finalize" if state.status == "approved_by_human" else END


def build_graph(checkpointer: Any = None):
    """Compile the onboarding graph.

    START -> intake -> plan -> execute_tools -> validate -> {finalize | revise | escalate}
    revise -> execute_tools; escalate -> finalize (if approved) or END.
    """
    g = StateGraph(OnboardingState)
    g.add_node("intake", nodes.intake)
    g.add_node("plan", nodes.plan)
    g.add_node("execute_tools", nodes.execute_tools)
    g.add_node("validate", nodes.validate)
    g.add_node("revise", nodes.revise)
    g.add_node("escalate", nodes.escalate)
    g.add_node("finalize", nodes.finalize)

    g.add_edge(START, "intake")
    g.add_edge("intake", "plan")
    g.add_edge("plan", "execute_tools")
    g.add_edge("execute_tools", "validate")
    g.add_conditional_edges(
        "validate",
        route_after_validation,
        {"finalize": "finalize", "revise": "revise", "escalate": "escalate"},
    )
    g.add_edge("revise", "execute_tools")
    g.add_conditional_edges(
        "escalate", route_after_escalation, {"finalize": "finalize", END: END}
    )
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer)
