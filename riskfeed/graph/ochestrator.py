from __future__ import annotations

from langgraph.graph import StateGraph, END

from riskfeed.graph.state import GraphState
from riskfeed.graph.nodes import (
    intent_router_node,
    planner_node,
    tool_executor_node,
    response_composer_node,
)


def build_graph():
    """
      intent_router -> planner -> tool_executor -> response_composer -> END
      Build the graph with the nodes and edges
    """
    g = StateGraph(GraphState)

    g.add_node("intent_router", intent_router_node)
    g.add_node("planner", planner_node)
    g.add_node("tool_executor", tool_executor_node)
    g.add_node("response_composer", response_composer_node)

    g.set_entry_point("intent_router")
    g.add_edge("intent_router", "planner")
    g.add_edge("planner", "tool_executor")
    g.add_edge("tool_executor", "response_composer")
    g.add_edge("response_composer", END)

    return g.compile()


GRAPH = build_graph()


def run_chat(
    *,
    role: str,
    message: str,
    session_id: str | None,
    confirm_action_id: str | None,
    debug_enabled: bool,
) -> GraphState:
    state: GraphState = {
        "role": role,
        "message": message,
        "session_id": session_id,
        "confirm_action_id": confirm_action_id,
        "debug_enabled": debug_enabled,
    }
    return GRAPH.invoke(state)