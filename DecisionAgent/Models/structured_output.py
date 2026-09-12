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
    why: str


class RoutingDecision(BaseModel):
    paths: list[RankedPath] = Field(min_length=1, max_length=3)
    notes: str
