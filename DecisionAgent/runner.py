from datetime import datetime

from agents import Runner

from DecisionAgent.config import require_api_key
from DecisionAgent.Context.context import (
    AVG_SPEED_KMH,
    RoutingContext,
    build_matrix,
    parse_coordinates,
)
from DecisionAgent.Models.structured_output import RoutingDecision
from DecisionAgent.agent import routing_agent


def _parse_now(now: datetime | str | None) -> datetime:
    if now is None:
        return datetime.now()
    if isinstance(now, datetime):
        return now
    return datetime.fromisoformat(now.replace("Z", "+00:00"))


def build_routing_context(
    coordinates: list,
    matrix: list[list[float]] | None = None,
    origin: int = 0,
    now: datetime | str | None = None,
    extra: dict | None = None,
    speed_kmh: float = AVG_SPEED_KMH,
) -> RoutingContext:
    points = parse_coordinates(coordinates)
    return RoutingContext(
        coordinates=points,
        matrix=matrix if matrix is not None else build_matrix(points, speed_kmh),
        origin=origin,
        now=_parse_now(now),
        extra=extra or {},
    )


def _prompt(ctx: RoutingContext) -> str:
    origin = ctx.point(ctx.origin)
    return (
        f"Plan the best 3 delivery paths from origin {ctx.origin} "
        f"(lat={origin['lat']}, lon={origin['lon']}). "
        f"n={ctx.n()}, now={ctx.now.isoformat()}. "
        f"Points have coordinates only; no ids."
    )


def _decision(result) -> RoutingDecision:
    output = result.final_output
    if output is None:
        raise RuntimeError("routing agent finished without a RoutingDecision")
    if isinstance(output, RoutingDecision):
        return output
    return RoutingDecision.model_validate(output)


async def run_routing_agent(
    coordinates: list,
    matrix: list[list[float]] | None = None,
    origin: int = 0,
    now: datetime | str | None = None,
    extra: dict | None = None,
    speed_kmh: float = AVG_SPEED_KMH,
) -> RoutingDecision:
    """Entry point for the API: pass coordinates, get the top paths."""
    require_api_key()
    ctx = build_routing_context(
        coordinates,
        matrix=matrix,
        origin=origin,
        now=now,
        extra=extra,
        speed_kmh=speed_kmh,
    )
    result = await Runner.run(
        routing_agent,
        input=_prompt(ctx),
        context=ctx,
        max_turns=30,
    )
    return _decision(result)


def run_routing_agent_sync(
    coordinates: list,
    matrix: list[list[float]] | None = None,
    origin: int = 0,
    now: datetime | str | None = None,
    extra: dict | None = None,
    speed_kmh: float = AVG_SPEED_KMH,
) -> RoutingDecision:
    """Sync wrapper for Flask / non-async API handlers."""
    require_api_key()
    ctx = build_routing_context(
        coordinates,
        matrix=matrix,
        origin=origin,
        now=now,
        extra=extra,
        speed_kmh=speed_kmh,
    )
    result = Runner.run_sync(
        routing_agent,
        input=_prompt(ctx),
        context=ctx,
        max_turns=30,
    )
    return _decision(result)


def run_routing_payload(payload: dict) -> dict:
    """JSON in / JSON out helper for the API layer.

    Required: coordinates = [[lat, lon], ...]
    Optional: matrix, origin, now, extra, speed_kmh
    """
    if "coordinates" not in payload:
        raise ValueError("payload must include coordinates: [[lat, lon], ...]")
    decision = run_routing_agent_sync(
        coordinates=payload["coordinates"],
        matrix=payload.get("matrix"),
        origin=payload.get("origin", 0),
        now=payload.get("now"),
        extra=payload.get("extra"),
        speed_kmh=payload.get("speed_kmh", AVG_SPEED_KMH),
    )
    return decision.model_dump()
