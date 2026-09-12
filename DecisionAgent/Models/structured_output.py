from pydantic import BaseModel, Field


class GeoPoint(BaseModel):
    lat: float
    lon: float


class PathStop(BaseModel):
    index: int
    lat: float
    lon: float
    arrival_offset_min: float


class RankedPath(BaseModel):
    rank: int = Field(ge=1, le=3)
    indexes: list[int]
    coordinates: list[GeoPoint]
    stops: list[PathStop]
    total_weight: float
    delivery_count: int
    destination_index: int
    destination: GeoPoint
    demand_forecast: float
    score: float
    why: str = Field(
        description=(
            "Everyday-language reason for this route: how long the drive is, "
            "how busy the last stop looks, and why it was kept or skipped."
        )
    )


class RoutingDecision(BaseModel):
    chosen: RankedPath
    alternatives: list[RankedPath] = Field(default_factory=list)
    description: str = Field(
        description=(
            "Dispatcher-style explanation in plain language. Copy take_decision's "
            "description, then add neighborhood details if useful. Do not talk about "
            "formulas, scores, or index lists."
        )
    )
    notes: str = Field(
        description="Optional extra color: parking, peak hour, congestion. Plain language."
    )
