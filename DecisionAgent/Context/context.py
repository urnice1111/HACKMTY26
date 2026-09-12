from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite


def _as_finite_float(value: object, i: int, j: int) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"matrix[{i}][{j}] must be a number") from exc
    if not isfinite(number):
        raise ValueError(f"matrix[{i}][{j}] must be finite")
    return number


@dataclass
class RoutingContext:
    matrix: list[list[float]]
    node_ids: list[str]
    origin: int
    now: datetime
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        n = len(self.matrix)
        if n == 0:
            raise ValueError("matrix must not be empty")
        if any(len(row) != n for row in self.matrix):
            raise ValueError("matrix must be square")
        if len(self.node_ids) != n:
            raise ValueError("node_ids length must match matrix size")
        if not 0 <= self.origin < n:
            raise ValueError("origin is out of range")
        self.matrix = [
            [_as_finite_float(value, i, j) for j, value in enumerate(row)]
            for i, row in enumerate(self.matrix)
        ]
        self.node_ids = [str(node_id) for node_id in self.node_ids]

    def n(self) -> int:
        return len(self.matrix)

    def cost(self, i: int, j: int) -> float:
        return self.matrix[i][j]

    def hop_is_valid(self, i: int, j: int) -> bool:
        if i == j:
            return False
        return self.matrix[i][j] >= 0
