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
