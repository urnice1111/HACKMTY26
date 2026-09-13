from dataclasses import dataclass, field
from datetime import datetime
from math import asin, cos, isfinite, radians, sin, sqrt

AVG_SPEED_KMH = 30.0
_EARTH_RADIUS_KM = 6371.0


def _as_finite_float(value: object, label: str) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number") from exc
    if not isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def parse_coordinates(raw: list) -> list[tuple[float, float]]:
    if not raw:
        raise ValueError("coordinates must not be empty")
    points: list[tuple[float, float]] = []
    for i, point in enumerate(raw):
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError(f"coordinates[{i}] must be [lat, lon]")
        lat = _as_finite_float(point[0], f"coordinates[{i}].lat")
        lon = _as_finite_float(point[1], f"coordinates[{i}].lon")
        points.append((lat, lon))
    return points


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = radians(a[0]), radians(a[1])
    lat2, lon2 = radians(b[0]), radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    chord = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * asin(sqrt(min(1.0, chord)))


def minutes_between(
    a: tuple[float, float],
    b: tuple[float, float],
    speed_kmh: float = AVG_SPEED_KMH,
) -> float:
    if speed_kmh <= 0:
        raise ValueError("speed_kmh must be > 0")
    return round(haversine_km(a, b) / speed_kmh * 60.0, 4)


def build_matrix(
    coordinates: list[tuple[float, float]],
    speed_kmh: float = AVG_SPEED_KMH,
) -> list[list[float]]:
    n = len(coordinates)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            minutes = minutes_between(coordinates[i], coordinates[j], speed_kmh)
            matrix[i][j] = minutes
            matrix[j][i] = minutes
    return matrix


def parse_matrix(raw: list, n: int) -> list[list[float]]:
    if len(raw) != n or any(len(row) != n for row in raw):
        raise ValueError("matrix must be square and match coordinates length")
    return [
        [_as_finite_float(value, f"matrix[{i}][{j}]") for j, value in enumerate(row)]
        for i, row in enumerate(raw)
    ]


@dataclass
class RoutingContext:
    coordinates: list[tuple[float, float]]
    matrix: list[list[float]]
    origin: int
    now: datetime
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.coordinates = parse_coordinates(self.coordinates)
        n = len(self.coordinates)
        self.matrix = parse_matrix(self.matrix, n)
        if not 0 <= self.origin < n:
            raise ValueError("origin is out of range")

    def n(self) -> int:
        return len(self.coordinates)

    def cost(self, i: int, j: int) -> float:
        return self.matrix[i][j]

    def hop_is_valid(self, i: int, j: int) -> bool:
        if i == j:
            return False
        return self.matrix[i][j] >= 0

    def point(self, i: int) -> dict[str, float]:
        lat, lon = self.coordinates[i]
        return {"lat": lat, "lon": lon}

    def fmt(self, i: int) -> str:
        lat, lon = self.coordinates[i]
        return f"{i}@({lat:.6f}, {lon:.6f})"

    def matrix_unit(self) -> str:
        """Human-readable unit for the matrix without changing its values."""
        value = self.extra.get("matrix_unit")
        return str(value) if value else "travel minutes"

    def route_rules(self) -> dict:
        rules = self.extra.get("route_constraints")
        return rules if isinstance(rules, dict) else {}

    def max_route_stops(self, requested: int) -> int:
        """Keep candidate generation within the simulator's capacity bound."""
        maximum = self.route_rules().get("max_route_stops")
        if isinstance(maximum, int) and maximum >= 0:
            return min(requested, maximum)
        return requested

    def route_constraint_error(self, nodes: list[int], *, complete: bool) -> str | None:
        """Return a constraint violation for a route prefix or complete plan.

        The constraints are optional so the DecisionAgent remains usable by its
        standalone CLI.  When called by the simulator, they force candidate
        paths to include mandatory stops, pair new pickups with their drops,
        respect precedence, and stay under the available capacity.
        """
        rules = self.route_rules()
        if not rules:
            return None
        positions = {index: offset for offset, index in enumerate(nodes)}
        required = {
            index
            for index in rules.get("required_stop_indexes", [])
            if isinstance(index, int)
        }
        if complete and not required.issubset(positions):
            return "path omits a mandatory stop"

        new_orders = 0
        for raw_order in rules.get("orders", []):
            if not isinstance(raw_order, dict):
                continue
            order_id = str(raw_order.get("pedido_id", "unknown"))
            pick = raw_order.get("pick_index")
            drop = raw_order.get("drop_index")
            pick = pick if isinstance(pick, int) else None
            drop = drop if isinstance(drop, int) else None
            has_pick = pick is not None and pick in positions
            has_drop = drop is not None and drop in positions

            if has_drop and pick is not None and not has_pick:
                return f"order {order_id} drops before its pickup"
            if has_pick and has_drop and positions[pick] > positions[drop]:
                return f"order {order_id} drops before its pickup"
            if not raw_order.get("is_active", False) and (has_pick or has_drop):
                new_orders += 1
                if complete and not (has_pick and has_drop):
                    return f"new order {order_id} must include pickup and drop"

        maximum_new = rules.get("max_new_orders")
        if isinstance(maximum_new, int) and new_orders > maximum_new:
            return "path exceeds the available order capacity"
        return None

    def route_constraints_summary(self) -> str:
        rules = self.route_rules()
        if not rules:
            return "No pickup/drop constraints were provided."
        required = rules.get("required_stop_indexes", [])
        maximum_new = rules.get("max_new_orders", 0)
        return (
            "This is a constrained pickup/drop plan. "
            f"Mandatory stop indexes: {required}. "
            f"At most {maximum_new} new orders may be accepted. "
            "A new order must include pickup and drop, in that order."
        )
