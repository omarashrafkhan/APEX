from __future__ import annotations

from langgraph.graph import StateGraph, END

from state import PenetrationTestingState
from nodes.orchestrator import orchestrator_node
from nodes.recon import recon_node
from nodes.end_node import end_node


def build_graph():
	graph = StateGraph(PenetrationTestingState)

	# Minimal deterministic flow:
	# 1) recon collects data from target
	# 2) orchestrator builds SQLi specialist agent from recon context
	# 3) end terminates the run
	graph.add_node("recon", recon_node)
	graph.add_node("orchestrator", orchestrator_node)
	graph.add_node("end", end_node)

	graph.add_edge("recon", "orchestrator")
	graph.add_edge("orchestrator", "end")
	graph.add_edge("end", END)

	graph.set_entry_point("recon")

	return graph.compile()


app = build_graph()

