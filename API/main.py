import logging
from enum import Enum

from fastapi import FastAPI, HTTPException, Query
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from DecisionAgent.runner import run_routing_agent

app = FastAPI(title="Courier Decision API")
logger = logging.getLogger("courier_api")


class CourierState(str, Enum):
    DROP = "drop"
    PICK = "pick"
    WAIT = "wait"


class OrderState(str, Enum):
    DROP = "drop"
    PICK = "pick"


class Node(BaseModel):
    """A visit point in [longitude, latitude] order."""

    model_config = ConfigDict(populate_by_name=True)

    state: OrderState = Field(validation_alias=AliasChoices("state", "type"))
    order_pos: tuple[float, float] = Field(
        validation_alias=AliasChoices("order_pos", "orderPos")
    )


class OptimizeRouteRequest(BaseModel):
    """Everything the simulator sends for one routing decision."""

    model_config = ConfigDict(populate_by_name=True)

    estadoCourier: CourierState = Field(
        validation_alias=AliasChoices("estadoCourier", "status", "courier_state")
    )
    current_pos: tuple[float, float] = Field(
        validation_alias=AliasChoices("current_pos", "currentPos")
    )
    pedidosActivos: int = Field(
        ge=0,
        validation_alias=AliasChoices("pedidosActivos", "activeOrders", "active_orders"),
    )
    puntosVisitar: list[Node] | None = Field(
        default=None,
        validation_alias=AliasChoices("puntosVisitar", "points_to_visit"),
    )
    matrix: list[list[float]]


class OptimizedRoute(BaseModel):
    """The route answer sent immediately back to the simulator."""

    puntosVisitar: list[Node]
    description: str


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
                "El índice 0 es current_pos; los demás índices son puntosVisitar."
            ),
        )


def mock_route_indexes(matrix: list[list[float]], point_count: int) -> list[int]:
    """Nearest-neighbour route for HTTP testing without calling an LLM."""
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


@app.post("/optimize-route", response_model=OptimizedRoute)
async def optimize_route(
    request: OptimizeRouteRequest,
    mock: bool = Query(default=False, description="Orden local para pruebas; no llama DecisionAgent"),
) -> OptimizedRoute:
    """Order the simulator's points and return the selected points plus its reason."""
    points = request.puntosVisitar or []
    validate_matrix(request.matrix, len(points))

    if not points:
        return OptimizedRoute(
            puntosVisitar=[],
            description="No hay puntos pendientes por visitar.",
        )

    coordinates = [as_agent_coordinate(request.current_pos)] + [
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
            agent_run = await run_routing_agent(
                coordinates=coordinates,
                matrix=request.matrix,
                origin=0,
                extra={
                    "courier_status": request.estadoCourier.value,
                    "current_pos": list(request.current_pos),
                    "points_to_visit": [point.model_dump(mode="json") for point in points],
                    "active_orders": request.pedidosActivos,
                },
            )
            logger.info(
                "DecisionAgent returned route indexes: %s",
                agent_run.decision.chosen.indexes,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=f"Datos inválidos para el agente: {error}") from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=f"DecisionAgent no disponible: {error}") from error
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"DecisionAgent error: {error}") from error

        indexes = agent_run.decision.chosen.indexes
        if not indexes or indexes[0] != 0:
            raise HTTPException(status_code=502, detail="DecisionAgent devolvió una ruta sin origen")

        visit_indexes = [index for index in indexes[1:] if 1 <= index <= len(points)]
        if len(visit_indexes) != len(indexes) - 1 or len(set(visit_indexes)) != len(visit_indexes):
            raise HTTPException(status_code=502, detail="DecisionAgent devolvió índices de ruta inválidos")

        description = agent_run.decision.description

    return OptimizedRoute(
        puntosVisitar=[points[index - 1] for index in visit_indexes],
        description=description,
    )
