from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable
from datetime import datetime

from agents import Runner

from DecisionAgent.config import require_api_key
from DecisionAgent.Context.context import (
    AVG_SPEED_KMH,
    RoutingContext,
    build_matrix,
    parse_coordinates,
)
from DecisionAgent.Models.structured_output import AgentRun, GeoPoint, RoutingDecision, TokenUsage
from DecisionAgent.agent import routing_agent
from DecisionAgent.trace import extract_events

OnRunUpdate = Callable[[AgentRun], None]


def _parse_now(now: datetime | str | None) -> datetime:
    if now is None:
        return datetime.now()
    if isinstance(now, datetime):
        return now
    return datetime.fromisoformat(now.replace("Z", "+00:00"))


def resolve_shift_id(payload: dict | None = None, extra: dict | None = None) -> str | None:
    extra = extra or {}
    payload = payload or {}
    value = payload.get("shift_id") or extra.get("shift_id")
    if value is None or value == "":
        return None
    return str(value)


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


def _usage(result) -> TokenUsage:
    usage = getattr(getattr(result, "context_wrapper", None), "usage", None)
    return TokenUsage(
        input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
    )


def build_agent_run(
    ctx: RoutingContext,
    result,
    duration_ms: float,
    shift_id: str | None = None,
    run_id: str | None = None,
) -> AgentRun:
    origin = ctx.point(ctx.origin)
    extra_shift = ctx.extra.get("shift_id") if ctx.extra else None
    return AgentRun(
        run_id=run_id or str(uuid.uuid4()),
        shift_id=shift_id or (str(extra_shift) if extra_shift else None),
        created_at=datetime.now().isoformat(),
        duration_ms=round(duration_ms, 1),
        point_count=ctx.n(),
        origin=GeoPoint(lat=origin["lat"], lon=origin["lon"]),
        decision=_decision(result),
        events=extract_events(getattr(result, "new_items", None)),
        usage=_usage(result),
        status="complete",
    )


def _stub_run(ctx: RoutingContext, run_id: str, shift_id: str | None) -> AgentRun:
    origin = ctx.point(ctx.origin)
    extra_shift = ctx.extra.get("shift_id") if ctx.extra else None
    return AgentRun(
        run_id=run_id,
        shift_id=shift_id or (str(extra_shift) if extra_shift else None),
        created_at=datetime.now().isoformat(),
        duration_ms=0,
        point_count=ctx.n(),
        origin=GeoPoint(lat=origin["lat"], lon=origin["lon"]),
        decision=None,
        events=[],
        status="running",
    )


def _notify(on_update: OnRunUpdate | None, run: AgentRun) -> None:
    if on_update is not None:
        on_update(run)


def _run_kwargs(
    coordinates: list,
    matrix: list[list[float]] | None,
    origin: int,
    now: datetime | str | None,
    extra: dict | None,
    speed_kmh: float,
    shift_id: str | None,
) -> tuple[RoutingContext, str | None]:
    extra = dict(extra or {})
    resolved = shift_id or extra.get("shift_id")
    if resolved:
        extra["shift_id"] = resolved
    ctx = build_routing_context(
        coordinates,
        matrix=matrix,
        origin=origin,
        now=now,
        extra=extra,
        speed_kmh=speed_kmh,
    )
    return ctx, resolve_shift_id(extra=extra)


async def run_routing_agent(
    coordinates: list,
    matrix: list[list[float]] | None = None,
    origin: int = 0,
    now: datetime | str | None = None,
    extra: dict | None = None,
    speed_kmh: float = AVG_SPEED_KMH,
    shift_id: str | None = None,
    on_update: OnRunUpdate | None = None,
) -> AgentRun:
    """Entry point for the API: stream tool events via on_update, then return the finished run."""
    require_api_key()
    ctx, resolved_shift = _run_kwargs(
        coordinates, matrix, origin, now, extra, speed_kmh, shift_id
    )
    run_id = str(uuid.uuid4())
    started = time.perf_counter()
    run = _stub_run(ctx, run_id, resolved_shift)
    _notify(on_update, run)
    items: list = []
    streamed = None
    try:
        streamed = Runner.run_streamed(
            routing_agent,
            input=_prompt(ctx),
            context=ctx,
            max_turns=30,
        )
        async for event in streamed.stream_events():
            if getattr(event, "type", None) != "run_item_stream_event":
                continue
            if getattr(event, "name", None) not in {"tool_called", "tool_output"}:
                continue
            item = getattr(event, "item", None)
            if item is None:
                continue
            items.append(item)
            run = run.model_copy(
                update={
                    "events": extract_events(items),
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                }
            )
            _notify(on_update, run)
        finished = build_agent_run(
            ctx,
            streamed,
            (time.perf_counter() - started) * 1000,
            resolved_shift,
            run_id=run_id,
        )
        finished = finished.model_copy(update={"created_at": run.created_at})
        _notify(on_update, finished)
        return finished
    except (Exception, asyncio.CancelledError):
        if streamed is not None:
            streamed.cancel(mode="immediate")
        failed = run.model_copy(
            update={
                "status": "error",
                "events": extract_events(items),
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        )
        _notify(on_update, failed)
        raise


def run_routing_agent_sync(
    coordinates: list,
    matrix: list[list[float]] | None = None,
    origin: int = 0,
    now: datetime | str | None = None,
    extra: dict | None = None,
    speed_kmh: float = AVG_SPEED_KMH,
    shift_id: str | None = None,
) -> AgentRun:
    """Sync wrapper for Flask / non-async API handlers."""
    require_api_key()
    ctx, resolved_shift = _run_kwargs(
        coordinates, matrix, origin, now, extra, speed_kmh, shift_id
    )
    started = time.perf_counter()
    result = Runner.run_sync(
        routing_agent,
        input=_prompt(ctx),
        context=ctx,
        max_turns=30,
    )
    return build_agent_run(ctx, result, (time.perf_counter() - started) * 1000, resolved_shift)


def run_routing_payload(payload: dict) -> dict:
    """JSON in / JSON out helper for the API layer.

    Required: coordinates = [[lat, lon], ...]
    Optional: matrix, origin, now, extra, speed_kmh, shift_id

    Returns an AgentRun dict: decision nested under "decision", plus events[] for the dashboard.
    """
    if "coordinates" not in payload:
        raise ValueError("payload must include coordinates: [[lat, lon], ...]")
    extra = dict(payload.get("extra") or {})
    run = run_routing_agent_sync(
        coordinates=payload["coordinates"],
        matrix=payload.get("matrix"),
        origin=payload.get("origin", 0),
        now=payload.get("now"),
        extra=extra,
        speed_kmh=payload.get("speed_kmh", AVG_SPEED_KMH),
        shift_id=resolve_shift_id(payload, extra),
    )
    return run.model_dump()
