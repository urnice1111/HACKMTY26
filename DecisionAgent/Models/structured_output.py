from pydantic import BaseModel, Field


class PathStop(BaseModel):
    node_index: int
    node_id: str
    arrival_offset_min: float


class RankedPath(BaseModel):
    rank: int = Field(ge=1, le=3)
    nodes: list[int]
    stops: list[PathStop]
    total_weight: float
    delivery_count: int
    destination_index: int
    demand_forecast: float
    score: float
    why: str


class RoutingDecision(BaseModel):
    paths: list[RankedPath] = Field(min_length=1, max_length=3)
    notes: str
