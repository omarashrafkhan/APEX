from __future__ import annotations

from typing import Dict, Any

from state import APEXState


def end_node(state: APEXState) -> Dict[str, Any]:
	"""
	End node: Gracefully terminate the graph execution.
	"""
	print("🏁 End node reached - Execution complete")
	
	return {
		"status": "finished"
	}
