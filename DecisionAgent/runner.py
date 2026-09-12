from datetime import datetime

from dotenv import load_dotenv
from agents import Runner

from DecisionAgent.Context.context import RoutingContext
from DecisionAgent.Models.structured_output import RoutingDecision
from DecisionAgent.agent import routing_agent

load_dotenv()


def _parse_now(now: datetime | str | None) -> datetime:
    if now is None:
        return datetime.now()
    if isinstance(now, datetime):
        return now
    return datetime.fromisoformat(now.replace("Z", "+00:00"))


def build_routing_context(
    matrix: list[list[float]],
    node_ids: list[str] | None = None,
    origin: int = 0,
    now: datetime | str | None = None,
    extra: dict | None = None,
) -> RoutingContext:
    n = len(matrix)
    return RoutingContext(
        matrix=matrix,
        node_ids=node_ids or [str(i) for i in range(n)],
        origin=origin,
        now=_parse_now(now),
        extra=extra or {},
    )


def _prompt(ctx: RoutingContext) -> str:
    return (
        f"Plan the best 3 delivery paths. "
        f"n={ctx.n()}, origin={ctx.origin} ({ctx.node_ids[ctx.origin]}), "
        f"now={ctx.now.isoformat()}."
    )


def _decision(result) -> RoutingDecision:
    output = result.final_output
    if output is None:
        raise RuntimeError("routing agent finished without a RoutingDecision")
    if isinstance(output, RoutingDecision):
        return output
    return RoutingDecision.model_validate(output)


async def run_routing_agent(
    matrix: list[list[float]],
    node_ids: list[str] | None = None,
    origin: int = 0,
    now: datetime | str | None = None,
    extra: dict | None = None,
) -> RoutingDecision:
    """Entry point for the API: pass the adjacency matrix, get the top paths."""
    ctx = build_routing_context(matrix, node_ids=node_ids, origin=origin, now=now, extra=extra)
    result = await Runner.run(
        routing_agent,
        input=_prompt(ctx),
        context=ctx,
        max_turns=30,
    )
    return _decision(result)


def run_routing_agent_sync(
    matrix: list[list[float]],
    node_ids: list[str] | None = None,
    origin: int = 0,
    now: datetime | str | None = None,
    extra: dict | None = None,
) -> RoutingDecision:
    """Sync wrapper for Flask / non-async API handlers."""
    ctx = build_routing_context(matrix, node_ids=node_ids, origin=origin, now=now, extra=extra)
    result = Runner.run_sync(
        routing_agent,
        input=_prompt(ctx),
        context=ctx,
        max_turns=30,
    )
    return _decision(result)


def run_routing_payload(payload: dict) -> dict:
    """JSON in / JSON out helper for the API layer."""
    decision = run_routing_agent_sync(
        matrix=payload["matrix"],
        node_ids=payload.get("node_ids"),
        origin=payload.get("origin", 0),
        now=payload.get("now"),
        extra=payload.get("extra"),
    )
    return decision.model_dump()
