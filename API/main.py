import asyncio
import logging
import os

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from API.request_work import run_request_work

from API.models import (
    OptimizeRouteRequest,
    OptimizedRoute,
    SimulatorDecisionRequest,
    SimulatorDecisionResponse,
)
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
from API.simulator_adapter import (
    SimulatorContractError,
    agent_coordinates,
    agent_extra,
    agent_matrix,
    decision_response,
    fallback_decision,
)
from DecisionAgent.Models.structured_output import AgentRun
from DecisionAgent.runner import run_routing_agent

app = FastAPI(title="Courier Decision API")
logger = logging.getLogger("courier_api")

# The simulator parks the courier while /decision is in flight, so answering
# late looks the same as not answering at all. Give up on the LLM early and
# return the local plan instead of leaving the courier idle. Distinct from the
# simulator's own AGENT_TIMEOUT_SECONDS, which must stay larger than this.
AGENT_LLM_TIMEOUT_SECONDS = float(os.getenv("AGENT_LLM_TIMEOUT_SECONDS", "20"))
AGENT_USE_LLM = os.getenv("AGENT_USE_LLM", "1").strip().lower() not in {"0", "false", "no"}

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


@app.post("/decision", response_model=SimulatorDecisionResponse)
async def decide_for_simulator(request: SimulatorDecisionRequest, http_request: Request) -> SimulatorDecisionResponse:
    """Use the Go simulator's native contract to obtain a feasible route plan.

    If the LLM is slow, fails, or returns an invalid path, a local greedy plan
    accepts reachable offers so the courier is not left idle.
    """
    try:
        extra = agent_extra(request)
    except SimulatorContractError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    if not AGENT_USE_LLM:
        logger.info("AGENT_USE_LLM disabled; answering %s with the local plan", request.evento)
        return fallback_decision(
            request,
            "Se armó una ruta local porque el agente LLM está deshabilitado.",
        )

    try:
        logger.info(
            "Simulator event %s: planning across %s points",
            request.evento,
            len(request.puntos_ruta),
        )
        agent_run = await run_request_work(
            http_request,
            lambda: run_routing_agent(
                coordinates=agent_coordinates(request),
                matrix=agent_matrix(request),
                origin=0,
                now=request.tiempo_simulado,
                extra=extra,
                on_update=save_run,
            ),
            timeout=AGENT_LLM_TIMEOUT_SECONDS,
        )
        if agent_run.decision is None:
            raise RuntimeError("DecisionAgent terminó sin decisión")
        description = (agent_run.description or "").strip()
        return decision_response(
            request,
            agent_run.decision.chosen.indexes,
            description=description,
        )
    except SimulatorContractError as error:
        logger.warning("Invalid agent route; using a feasible local plan: %s", error)
        return fallback_decision(
            request,
            f"Se armó una ruta local porque la decisión no era válida: {error}",
        )
    except HTTPException:
        raise
    except asyncio.TimeoutError:
        logger.warning("DecisionAgent timed out; using a feasible local plan")
        return fallback_decision(
            request,
            "Se armó una ruta local porque el agente tardó demasiado.",
        )
    except (ValueError, RuntimeError) as error:
        logger.warning("DecisionAgent unavailable; using a feasible local plan: %s", error)
        return fallback_decision(
            request,
            f"Se armó una ruta local porque el agente no respondió: {error}",
        )
    except Exception as error:
        logger.exception("DecisionAgent error while handling simulator request")
        return fallback_decision(
            request,
            f"Se armó una ruta local porque el agente falló: {error}",
        )


@app.post("/optimize-route", response_model=OptimizedRoute)
async def optimize_route(
    request: OptimizeRouteRequest,
    http_request: Request,
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
            agent_run = await run_request_work(
                http_request,
                lambda: run_routing_agent(
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
                ),
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
        except asyncio.TimeoutError as error:
            raise HTTPException(status_code=504, detail="DecisionAgent timed out") from error
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
