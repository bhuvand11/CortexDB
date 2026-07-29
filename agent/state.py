"""
state.py

Shared state passed between every node in the LangGraph.
"""

from typing import TypedDict, Optional, Any, List, Dict


class CortexState(TypedDict, total=False):
    question: str
    route: str                    # "lookup" or "investigate"
    metric: str                   # "sales" or "profit"

    lookup_sql: str
    lookup_result: str

    anomaly: Dict[str, Any]
    worst_segment: Dict[str, Any]
    confounders: Dict[str, Any]

    context_events: List[str]

    findings: List[str]
    final_answer: str