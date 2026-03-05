# agents/graph.py - LangGraph workflow definition
from langgraph.graph import StateGraph, END
from .state import ReconState
from .nodes import extractor_node, matcher_node, exception_handler_node


def build_graph():
    """Build and compile the multi-agent reconciliation graph.
    Flow: START -> extractor -> matcher -> exception_handler -> END
    """
    graph = StateGraph(ReconState)

    # register nodes
    graph.add_node("extractor", extractor_node)
    graph.add_node("matcher", matcher_node)
    graph.add_node("exception_handler", exception_handler_node)

    # wire edges
    graph.set_entry_point("extractor")
    graph.add_edge("extractor", "matcher")
    graph.add_edge("matcher", "exception_handler")
    graph.add_edge("exception_handler", END)

    return graph.compile()


# compiled graph instance (singleton)
recon_graph = build_graph()
