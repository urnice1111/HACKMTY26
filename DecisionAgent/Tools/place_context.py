from agents import RunContextWrapper
from agents.decorators import tool

from DecisionAgent.Context.context import RoutingContext

_NOTES = [
    "warehouse hub; staging area, not a customer drop",
    "dense residential; evening peak 18:00-21:00, street parking tight",
    "office corridor; weekday lunch demand, quiet after 19:00",
    "university zone; class-change spikes, limited truck access",
    "retail strip; weekend afternoon rush, loading bay available",
    "hospital / clinic area; steady all-day demand, time-window sensitive",
    "industrial park; sparse customers, easy access, long gaps",
    "nightlife district; late demand after 20:00, congestion on weekends",
]


@tool
def get_place_context(wrapper: RunContextWrapper[RoutingContext], node_index: int) -> str:
    """Text context for a node: neighborhood notes, events, access restrictions.

    Args:
        node_index: Index of the node in the adjacency matrix.
    """
    ctx = wrapper.context
    n = ctx.n()
    if not 0 <= node_index < n:
        return f"error: node {node_index} is out of range"
    node_id = ctx.node_ids[node_index]
    if node_index == ctx.origin:
        note = _NOTES[0]
        role = "origin"
    else:
        note = _NOTES[(node_index % (len(_NOTES) - 1)) + 1]
        role = "delivery"
    return f"node_index={node_index} node_id={node_id} role={role}. {note}"
