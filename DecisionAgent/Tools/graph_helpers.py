from agents import RunContextWrapper
from agents.decorators import tool

from DecisionAgent.Context.context import RoutingContext

_MAX_PATHS_COLLECTED = 200


def _validate_path(ctx: RoutingContext, nodes: list[int]) -> dict | None:
    n = ctx.n()
    if not nodes:
        return {"ok": False, "error": "path must not be empty"}
    if nodes[0] != ctx.origin:
        return {"ok": False, "error": "path must start at origin"}
    if len(nodes) < 2:
        return {"ok": False, "error": "path must include at least one delivery"}
    seen: set[int] = set()
    for node in nodes:
        if not 0 <= node < n:
            return {"ok": False, "error": f"point {node} is out of range"}
        if node in seen:
            return {"ok": False, "error": "no repeated points"}
        seen.add(node)
    for a, b in zip(nodes, nodes[1:]):
        if not ctx.hop_is_valid(a, b):
            return {"ok": False, "error": f"no valid hop from {a} to {b}"}
    if error := ctx.route_constraint_error(nodes, complete=True):
        return {"ok": False, "error": error}
    return None


def compute_path_cost(ctx: RoutingContext, nodes: list[int]) -> dict:
    error = _validate_path(ctx, nodes)
    if error:
        return error

    total = 0.0
    arrival = 0.0
    stops = []
    for a, b in zip(nodes, nodes[1:]):
        hop = ctx.cost(a, b)
        total += hop
        arrival += hop
        stop = {"index": b, "arrival_offset_min": arrival, **ctx.point(b)}
        stops.append(stop)

    dest = nodes[-1]
    return {
        "ok": True,
        "indexes": nodes,
        "coordinates": [ctx.point(i) for i in nodes],
        "total_weight": total,
        "arrival_offset_min": arrival,
        "delivery_count": len(nodes) - 1,
        "destination_index": dest,
        "destination": ctx.point(dest),
        "stops": stops,
    }


def enumerate_candidate_paths(
    ctx: RoutingContext,
    k: int = 8,
    max_deliveries: int = 3,
) -> dict:
    k = max(1, min(k, 15))
    max_deliveries = max(1, min(max_deliveries, 4))
    max_deliveries = ctx.max_route_stops(max_deliveries)
    if max_deliveries < 1:
        return {"ok": True, "count": 0, "paths": []}
    origin = ctx.origin
    n = ctx.n()
    found: list[tuple[float, list[int]]] = []

    def dfs(path: list[int], cost: float, visited: set[int]) -> None:
        deliveries = len(path) - 1
        if 1 <= deliveries <= max_deliveries and not ctx.route_constraint_error(path, complete=True):
            found.append((cost, path[:]))
        if deliveries >= max_deliveries or len(found) >= _MAX_PATHS_COLLECTED:
            return
        last = path[-1]
        for nxt in range(n):
            if nxt in visited or not ctx.hop_is_valid(last, nxt):
                continue
            next_path = path + [nxt]
            if ctx.route_constraint_error(next_path, complete=False):
                continue
            dfs(next_path, cost + ctx.cost(last, nxt), visited | {nxt})
            if len(found) >= _MAX_PATHS_COLLECTED:
                return

    dfs([origin], 0.0, {origin})
    found.sort(key=lambda item: (item[0], len(item[1])))

    unique: list[tuple[float, list[int]]] = []
    rest: list[tuple[float, list[int]]] = []
    seen_destinations: set[int] = set()
    for cost, path in found:
        dest = path[-1]
        if dest not in seen_destinations:
            unique.append((cost, path))
            seen_destinations.add(dest)
        else:
            rest.append((cost, path))
    selected = (unique + rest)[:k]

    paths = []
    for cost, path in selected:
        dest = path[-1]
        paths.append(
            {
                "indexes": path,
                "coordinates": [ctx.point(i) for i in path],
                "total_weight": cost,
                "delivery_count": len(path) - 1,
                "destination_index": dest,
                "destination": ctx.point(dest),
                "arrival_offset_min": cost,
            }
        )
    return {"ok": True, "count": len(paths), "paths": paths}


def graph_summary(ctx: RoutingContext) -> str:
    rows = "\n".join(
        f"{ctx.fmt(i)} -> "
        + ", ".join(
            f"{ctx.fmt(j)}={w}min"
            for j, w in enumerate(row)
            if i != j and ctx.hop_is_valid(i, j)
        )
        for i, row in enumerate(ctx.matrix)
    )
    return (
        f"origin={ctx.fmt(ctx.origin)}\n"
        f"n={ctx.n()}\n"
        f"points use [lat, lon]; weights are {ctx.matrix_unit()}\n"
        f"{ctx.route_constraints_summary()}\n"
        f"{rows}"
    )


@tool
def get_graph_summary(wrapper: RunContextWrapper[RoutingContext]) -> str:
    """Return coordinates, origin, and travel-minute weights as text."""
    return graph_summary(wrapper.context)


@tool
def path_cost(wrapper: RunContextWrapper[RoutingContext], nodes: list[int]) -> dict:
    """Validate a complete feasible path and return its total matrix weight.

    Args:
        nodes: Point indexes in visit order. Must start at origin and include at least one delivery.
    """
    return compute_path_cost(wrapper.context, nodes)


@tool
def candidate_paths(
    wrapper: RunContextWrapper[RoutingContext],
    k: int = 8,
    max_deliveries: int = 3,
) -> dict:
    """Return cheap complete, feasible candidate paths from origin.

    Args:
        k: Maximum number of paths to return.
        max_deliveries: Maximum stops after origin in a path.
    """
    return enumerate_candidate_paths(wrapper.context, k=k, max_deliveries=max_deliveries)
