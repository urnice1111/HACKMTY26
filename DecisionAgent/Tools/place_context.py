from agents import RunContextWrapper
from agents.decorators import tool

from DecisionAgent.Context.context import RoutingContext

_NOTES = [
    "depot / start; staging area, not a customer drop",
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
    """Text context for a coordinate: neighborhood notes, events, access restrictions.

    Args:
        node_index: Index of the point in the coordinates list.
    """
    ctx = wrapper.context
    n = ctx.n()
    if not 0 <= node_index < n:
        return f"error: point {node_index} is out of range"
    if node_index == ctx.origin:
        note = _NOTES[0]
        role = "origin"
    else:
        note = _NOTES[(node_index % (len(_NOTES) - 1)) + 1]
        role = "delivery"
    lat, lon = ctx.coordinates[node_index]
    return f"{ctx.fmt(node_index)} role={role} lat={lat} lon={lon}. {note}"
