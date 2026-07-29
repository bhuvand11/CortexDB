"""
graph.py

Builds the CortexDB LangGraph: Planner -> (SQL agent | Investigator ->
Segment -> Confounders -> Context -> Narrator).
"""

from langgraph.graph import StateGraph, END
from agent.state import CortexState
from agent.nodes import (
    planner_node,
    route_decision,
    sql_agent_node,
    investigator_node,
    segment_node,
    confounder_node,
    context_node,
    narrator_node,
)


def build_graph():
    graph = StateGraph(CortexState)

    graph.add_node("planner", planner_node)
    graph.add_node("sql_agent", sql_agent_node)
    graph.add_node("investigator", investigator_node)
    graph.add_node("segment", segment_node)
    graph.add_node("confounders", confounder_node)
    graph.add_node("context", context_node)
    graph.add_node("narrator", narrator_node)

    graph.set_entry_point("planner")

    graph.add_conditional_edges(
        "planner",
        route_decision,
        {"lookup": "sql_agent", "investigate": "investigator"},
    )

    graph.add_edge("sql_agent", END)

    graph.add_edge("investigator", "segment")
    graph.add_edge("segment", "confounders")
    graph.add_edge("confounders", "context")
    graph.add_edge("context", "narrator")
    graph.add_edge("narrator", END)

    return graph.compile()