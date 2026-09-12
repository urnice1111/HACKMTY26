from agents import RunContextWrapper
from agents.decorators import tool

from DecisionAgent.Context.context import RoutingContext


@tool
def get_numeric_signals(wrapper: RunContextWrapper[RoutingContext], node_index: int) -> dict:
    """Numeric signals for a coordinate: open orders, wait time, congestion.

    Args:
        node_index: Index of the point in the coordinates list.
    """
    ctx = wrapper.context
    n = ctx.n()
    if not 0 <= node_index < n:
        return {"ok": False, "error": f"point {node_index} is out of range"}

    payload = {"ok": True, "index": node_index, **ctx.point(node_index)}
    if node_index == ctx.origin:
        payload.update({"open_orders": 0, "avg_wait_min": 0.0, "congestion": 0.1})
        return payload

    payload.update(
        {
            "open_orders": 2 + (node_index % 5),
            "avg_wait_min": 6.0 + (node_index % 4) * 3.5,
            "congestion": round(0.15 + (node_index % 6) * 0.1, 2),
        }
    )
    return payload
