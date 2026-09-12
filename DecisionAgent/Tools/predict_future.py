from datetime import timedelta

from agents import RunContextWrapper
from agents.decorators import tool

from DecisionAgent.Context.context import RoutingContext


def forecast_demand(
    ctx: RoutingContext,
    destination_index: int,
    arrival_offset_min: float,
) -> dict:
    n = ctx.n()
    if not 0 <= destination_index < n:
        return {"ok": False, "error": f"point {destination_index} is out of range"}
    if arrival_offset_min < 0:
        return {"ok": False, "error": "arrival_offset_min must be >= 0"}

    arrival = ctx.now + timedelta(minutes=arrival_offset_min)
    hour = arrival.hour + arrival.minute / 60.0
    base = 6.0 if destination_index == ctx.origin else 8.0 + (destination_index % 5)
    peak = 1.8 if 17 <= hour < 22 else 1.0
    lunch = 1.3 if 12 <= hour < 14 else 1.0
    demand = round(base * peak * lunch, 2)
    confidence = 0.55 if peak > 1 else 0.7

    return {
        "ok": True,
        "destination_index": destination_index,
        "destination": ctx.point(destination_index),
        "arrival_offset_min": arrival_offset_min,
        "arrival_hour": round(hour, 2),
        "predicted_demand": demand,
        "confidence": confidence,
    }


@tool
def predict_future(
    wrapper: RunContextWrapper[RoutingContext],
    destination_index: int,
    arrival_offset_min: float,
) -> dict:
    """Predict demand at a destination coordinate at the time a path would arrive there.

    Args:
        destination_index: Final point index of a candidate path.
        arrival_offset_min: Minutes after departure when the path reaches that point.
    """
    return forecast_demand(wrapper.context, destination_index, arrival_offset_min)
