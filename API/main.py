import os
import logging
from enum import Enum

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from supabase import Client, create_client

from DecisionAgent.runner import run_routing_agent

load_dotenv()

app = FastAPI(title="Courier Decision API")
logger = logging.getLogger("courier_api")

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_KEY en .env")

supabase: Client = create_client(supabase_url, supabase_key)


class CourierState(str, Enum):
    DROP = "drop"
    PICK = "pick"
    WAIT = "wait"


class OrderState(str, Enum):
    DROP = "drop"
    PICK = "pick"


class Node(BaseModel):
    """A simulator point in [longitude, latitude] order."""

    state: OrderState
    order_pos: tuple[float, float]


class CourierStatus(BaseModel):
    status: CourierState
    current_pos: tuple[float, float]
    activeOrders: int
    points_to_visit: list[Node] | None = None


class MatrixRequest(BaseModel):
    """Matrix index 0 is the courier; indexes 1..n are visit points."""

    matrix: list[list[float]]


class OptimizedRoute(BaseModel):
    """Route selected for the simulator, plus the reason behind it."""

    points_to_visit: list[Node]
    description: str


def latest_courier_status() -> CourierStatus:
    """Read the single most recent courier snapshot from Supabase."""
    try:
        result = (
            supabase.table("courier_status")
            .select("status, current_pos, active_orders, points_to_visit")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Supabase error: {error}") from error

    if not result.data:
        raise HTTPException(status_code=404, detail="No hay CourierStatus guardado")

    row = result.data[0]
    return CourierStatus(
        status=row["status"],
        current_pos=row["current_pos"],
        activeOrders=row["active_orders"],
        points_to_visit=row["points_to_visit"],
    )



def as_agent_coordinate(position: tuple[float, float]) -> list[float]:
    """Convert API [longitude, latitude] positions to DecisionAgent [lat, lon]."""
    longitude, latitude = position
    return [latitude, longitude]


def validate_matrix(matrix: list[list[float]], point_count: int) -> None:
    expected_size = point_count + 1
    if len(matrix) != expected_size or any(len(row) != expected_size for row in matrix):
        raise HTTPException(
            status_code=422,
            detail=(
                f"matrix debe ser de {expected_size} x {expected_size}. "
                "El índice 0 es current_pos; los demás índices son points_to_visit."
            ),
        )


def mock_route_indexes(matrix: list[list[float]], point_count: int) -> list[int]:
    """Deterministic nearest-neighbour route for endpoint testing without an LLM."""
    current_index = 0
    remaining = set(range(1, point_count + 1))
    ordered: list[int] = []

    while remaining:
        next_index = min(
            remaining,
            key=lambda index: (matrix[current_index][index], index),
        )
        ordered.append(next_index)
        remaining.remove(next_index)
        current_index = next_index

    return ordered


@app.get("/")
def health_check() -> dict[str, str]:
    return {"message": "Courier Decision API funcionando"}


@app.get("/courier-status", response_model=CourierStatus)
def get_courier_status() -> CourierStatus:
    """Return only the latest CourierStatus stored in Supabase."""
    return latest_courier_status()


@app.post("/optimize-route", response_model=OptimizedRoute)
async def optimize_route(
    request: MatrixRequest,
    mock: bool = Query(default=False, description="Use local routing; do not call DecisionAgent"),
) -> OptimizedRoute:
    """Receive a simulator matrix and return only the agent's chosen visit points."""
    courier = latest_courier_status()
    points = courier.points_to_visit or []
    validate_matrix(request.matrix, len(points))

    if not points:
        return OptimizedRoute(
            points_to_visit=[],
            description="No hay puntos pendientes por visitar.",
        )

    # The API uses [longitude, latitude]; DecisionAgent explicitly uses [lat, lon].
    coordinates = [as_agent_coordinate(courier.current_pos)] + [
        as_agent_coordinate(point.order_pos) for point in points
    ]

    if mock:
        visit_indexes = mock_route_indexes(request.matrix, len(points))
        description = (
            "Ruta de prueba: se ordenaron los puntos eligiendo en cada paso "
            "el siguiente punto con menor tiempo en la matriz."
        )
    else:
        try:
            logger.info("Calling DecisionAgent with %s visit points", len(points))
            decision = await run_routing_agent(
                coordinates=coordinates,
                matrix=request.matrix,
                origin=0,
                extra={
                    "courier_status": courier.status.value,
                    "current_pos": list(courier.current_pos),
                    "points_to_visit": [point.model_dump(mode="json") for point in points],
                    "active_orders": courier.activeOrders,
                },
            )
            logger.info("DecisionAgent returned route indexes: %s", decision.chosen.indexes)
            description = decision.description
        except ValueError as error:
            raise HTTPException(status_code=422, detail=f"Datos inválidos para el agente: {error}") from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=f"DecisionAgent no disponible: {error}") from error
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"DecisionAgent error: {error}") from error

        # DecisionAgent returns matrix indexes. Index 0 is the courier, so index
        # k maps to points_to_visit[k - 1].
        indexes = decision.chosen.indexes
        if not indexes or indexes[0] != 0:
            raise HTTPException(status_code=502, detail="DecisionAgent devolvió una ruta sin origen")

        visit_indexes = [index for index in indexes[1:] if 1 <= index <= len(points)]
        if len(visit_indexes) != len(indexes) - 1 or len(set(visit_indexes)) != len(visit_indexes):
            raise HTTPException(status_code=502, detail="DecisionAgent devolvió índices de ruta inválidos")

    return OptimizedRoute(
        points_to_visit=[points[index - 1] for index in visit_indexes],
        description=description,
    )
