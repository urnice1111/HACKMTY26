from agents import RunContextWrapper
from agents.decorators import tool

from DecisionAgent.Context.context import RoutingContext


@tool
def get_numeric_signals(wrapper: RunContextWrapper[RoutingContext], node_index: int) -> dict:
    """Numeric signals for a node: open orders, wait time, congestion.

    Args:
        node_index: Index of the node in the adjacency matrix.
    """
    ctx = wrapper.context
    n = ctx.n()
    if not 0 <= node_index < n:
        return {"ok": False, "error": f"node {node_index} is out of range"}

    if node_index == ctx.origin:
        return {
            "ok": True,
            "node_index": node_index,
            "node_id": ctx.node_ids[node_index],
            "open_orders": 0,
            "avg_wait_min": 0.0,
            "congestion": 0.1,
        }

    return {
        "ok": True,
        "node_index": node_index,
        "node_id": ctx.node_ids[node_index],
        "open_orders": 2 + (node_index % 5),
        "avg_wait_min": 6.0 + (node_index % 4) * 3.5,
        "congestion": round(0.15 + (node_index % 6) * 0.1, 2),
    }
