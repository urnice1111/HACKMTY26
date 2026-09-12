from typing import Any

__all__ = [
    "PathStop",
    "RankedPath",
    "RoutingContext",
    "RoutingDecision",
    "run_routing_agent",
    "run_routing_agent_sync",
    "run_routing_payload",
]


def __getattr__(name: str) -> Any:
    if name == "RoutingContext":
        from DecisionAgent.Context.context import RoutingContext

        return RoutingContext
    if name in {"PathStop", "RankedPath", "RoutingDecision"}:
        from DecisionAgent.Models import structured_output

        return getattr(structured_output, name)
    if name in {"run_routing_agent", "run_routing_agent_sync", "run_routing_payload"}:
        from DecisionAgent import runner

        return getattr(runner, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
