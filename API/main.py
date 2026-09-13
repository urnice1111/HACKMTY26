import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from API.models import OptimizeRouteRequest, OptimizedRoute
from API.run_store import (
    DEFAULT_SHIFT_ID,
    RunListResponse,
    ShiftStats,
    get_run,
    list_runs,
    save_run,
    stats_from,
    to_summary,
)
from DecisionAgent.Models.structured_output import AgentRun
from DecisionAgent.runner import run_routing_agent

app = FastAPI(title="Courier Decision API")
logger = logging.getLogger("courier_api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
                    "shift_id": DEFAULT_SHIFT_ID,
                },
                on_update=save_run,
            )
            if agent_run.decision is None:
                raise HTTPException(status_code=502, detail="DecisionAgent terminó sin decisión")
            logger.info(
                "DecisionAgent returned route indexes: %s",
                agent_run.chosen.indexes,
            )
            description = agent_run.description
        except HTTPException:
            raise
        except ValueError as error:
            raise HTTPException(status_code=422, detail=f"Datos inválidos para el agente: {error}") from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=f"DecisionAgent no disponible: {error}") from error
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"DecisionAgent error: {error}") from error

        indexes = agent_run.chosen.indexes
        if not indexes or indexes[0] != 0:
            raise HTTPException(status_code=502, detail="DecisionAgent devolvió una ruta sin origen")

        visit_indexes = [index for index in indexes[1:] if 1 <= index <= len(points)]
        if len(visit_indexes) != len(indexes) - 1 or len(set(visit_indexes)) != len(visit_indexes):
            raise HTTPException(status_code=502, detail="DecisionAgent devolvió índices de ruta inválidos")

    return OptimizedRoute(
        puntosVisitar=[points[index - 1] for index in visit_indexes],
        description=description,
    )


@app.post("/v1/runs", response_model=AgentRun)
def ingest_run(run: AgentRun) -> AgentRun:
    """Accept a full AgentRun (tool steps + nested decision) for dashboard replay."""
    return save_run(run)


@app.get("/v1/shifts/{shift_id}/runs", response_model=RunListResponse)
def get_shift_runs(
    shift_id: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> RunListResponse:
    runs = list_runs(shift_id, limit=limit)
    return RunListResponse(runs=[to_summary(run) for run in runs])


@app.get("/v1/runs/{run_id}", response_model=AgentRun)
def get_run_detail(run_id: str) -> AgentRun:
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run no encontrado")
    return run


@app.get("/v1/shifts/{shift_id}/stats", response_model=ShiftStats)
def get_shift_stats(shift_id: str) -> ShiftStats:
    return stats_from(list_runs(shift_id, limit=200), shift_id)
