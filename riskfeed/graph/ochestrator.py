from __future__ import annotations

from langgraph.graph import StateGraph, END

from riskfeed.graph.state import GraphState
from riskfeed.graph.nodes import (
    session_load_node,
    intent_router_node,
    planner_node,
    tool_executor_node,
    retrieval_node,
    response_composer_node,
    verifier_node,
    repair_node,
    session_save_node,
)


def build_graph():
    g = StateGraph(GraphState)

    # Core nodes
    g.add_node("session_load", session_load_node)
    g.add_node("intent_router", intent_router_node)
    g.add_node("planner", planner_node)
    g.add_node("tool_executor", tool_executor_node)
    g.add_node("retrieval", retrieval_node)
    g.add_node("response_composer", response_composer_node)
    g.add_node("verifier", verifier_node)
    g.add_node("repair", repair_node)
    g.add_node("session_save", session_save_node)

    # Entry point: load session first
    g.set_entry_point("session_load")

    # Intent router
    g.add_edge("session_load", "intent_router")
    g.add_edge("intent_router", "planner")
    g.add_edge("planner", "tool_executor")
    g.add_edge("tool_executor", "retrieval")
    g.add_edge("retrieval", "response_composer")
    g.add_edge("response_composer", "verifier")

    # Conditional routing: if verification_ok then END else repair
    def route_after_verify(state: GraphState) -> str:
        return "end" if state.get("verification_ok") else "repair"

    g.add_conditional_edges(
        "verifier",
        route_after_verify,
        {
            "end": END,
            "repair": "repair",
        },
    )

    g.add_edge("repair", END)

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