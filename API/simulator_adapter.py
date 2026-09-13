"""Translation layer between the Go simulator and the routing agent.

The simulator owns order state and is the source of truth for feasibility.  The
agent only chooses among routes over numbered points, so this module preserves
the point/index mapping, gives the agent its route constraints, and validates
the selected indexes before they are returned to Go.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from API.models import (
    SimulatorDecisionRequest,
    SimulatorDecisionResponse,
    SimulatorStop,
)


class SimulatorContractError(ValueError):
    """The request or the agent's selected path violates the Go contract."""


def _assert_matrix_shape(request: SimulatorDecisionRequest) -> None:
    expected = len(request.puntos_ruta)
    if len(request.matriz) != expected or any(len(row) != expected for row in request.matriz):
        raise SimulatorContractError(
            f"matriz debe ser de {expected} x {expected}, igual que puntos_ruta"
        )


def agent_matrix(request: SimulatorDecisionRequest) -> list[list[float]]:
    """Replace Go's JSON ``null`` with the agent's unreachable-hop sentinel."""
    _assert_matrix_shape(request)
    normalized: list[list[float]] = []
    for row in request.matriz:
        normalized.append([-1.0 if value is None else float(value) for value in row])
    return normalized


def agent_coordinates(request: SimulatorDecisionRequest) -> list[list[float]]:
    """DecisionAgent expects [latitude, longitude], unlike the legacy endpoint."""
    return [[point.latitud, point.longitud] for point in request.puntos_ruta]


def _active_order_ids(request: SimulatorDecisionRequest) -> set[str]:
    return {
        str(order.get("pedido_id"))
        for order in request.restricciones.pedidos_activos
        if order.get("pedido_id")
    }


def agent_extra(request: SimulatorDecisionRequest) -> dict[str, Any]:
    """Build constraint metadata used by the agent's candidate-path tool."""
    _assert_matrix_shape(request)
    if request.puntos_ruta[0].type != "courier":
        raise SimulatorContractError("puntos_ruta[0] debe ser el courier")
    if request.restricciones.capacidad_maxima != request.capacidad_maxima:
        raise SimulatorContractError("capacidad_maxima no coincide con restricciones")

    active_ids = _active_order_ids(request)
    by_order: dict[str, dict[str, Any]] = {}
    for index, point in enumerate(request.puntos_ruta[1:], start=1):
        if not point.pedido_id:
            raise SimulatorContractError(f"la parada {point.id} no tiene pedido_id")
        rule = by_order.setdefault(
            point.pedido_id,
            {
                "pedido_id": point.pedido_id,
                "pick_index": None,
                "drop_index": None,
                "is_active": point.pedido_id in active_ids or point.obligatoria,
            },
        )
        key = f"{point.type}_index"
        if rule[key] is not None:
            raise SimulatorContractError(f"pedido {point.pedido_id} repite la parada {point.type}")
        rule[key] = index

    required = [
        index
        for index, point in enumerate(request.puntos_ruta)
        if index > 0 and point.obligatoria
    ]
    if any(request.puntos_ruta[index].pedido_id not in active_ids for index in required):
        raise SimulatorContractError("una parada obligatoria debe pertenecer a un pedido activo")

    max_new_orders = request.capacidad_maxima - request.pedidos_activos
    if max_new_orders < 0:
        raise SimulatorContractError("pedidos_activos excede capacidad_maxima")

    # At most two active orders exist in the simulator, so an exhaustive search
    # over this many stops remains bounded while producing complete plans.
    max_route_stops = len(required) + 2 * max_new_orders
    return {
        "shift_id": "shift-abc",
        "simulator_event": request.evento,
        "simulated_at": request.tiempo_simulado,
        "matrix_unit": request.matriz_unidad,
        "minute_value_mxn": request.valor_minuto_mxn,
        "route_constraints": {
            "required_stop_indexes": required,
            "max_new_orders": max_new_orders,
            "max_route_stops": max_route_stops,
            "orders": list(by_order.values()),
        },
    }


def _selected_stops(
    request: SimulatorDecisionRequest, indexes: list[int]
) -> tuple[list[SimulatorStop], list[int]]:
    _assert_matrix_shape(request)
    if not indexes or indexes[0] != 0:
        raise SimulatorContractError("la ruta del agente debe iniciar en el índice 0")
    if len(indexes) != len(set(indexes)):
        raise SimulatorContractError("la ruta del agente no puede repetir puntos")
    if any(index < 0 or index >= len(request.puntos_ruta) for index in indexes):
        raise SimulatorContractError("la ruta del agente contiene un índice inexistente")
    if any(index == 0 for index in indexes[1:]):
        raise SimulatorContractError("el courier sólo puede aparecer al inicio de la ruta")
    for source, destination in zip(indexes, indexes[1:]):
        if request.matriz[source][destination] is None:
            raise SimulatorContractError("la ruta del agente contiene un salto no permitido")
    route_indexes = indexes[1:]
    required = {
        index
        for index, point in enumerate(request.puntos_ruta)
        if index > 0 and point.obligatoria
    }
    if not required.issubset(route_indexes):
        raise SimulatorContractError("la ruta del agente omitió una parada obligatoria")
    return [request.puntos_ruta[index] for index in route_indexes], route_indexes


def decision_response(
    request: SimulatorDecisionRequest, indexes: list[int]
) -> SimulatorDecisionResponse:
    """Map a complete agent path back to the decision expected by Go.

    A non-mandatory order is accepted only if both its pickup and drop are in
    the returned route, in that order. Mandatory stops must all be present.
    This keeps invalid LLM output from entering the simulator.
    """
    stops, route_indexes = _selected_stops(request, indexes)
    position = {index: offset for offset, index in enumerate(route_indexes)}
    grouped: dict[str, list[tuple[int, SimulatorStop]]] = defaultdict(list)
    for index, stop in zip(route_indexes, stops):
        if not stop.pedido_id:
            raise SimulatorContractError(f"la parada {stop.id} no tiene pedido_id")
        grouped[stop.pedido_id].append((index, stop))

    all_points_by_order: dict[str, list[tuple[int, SimulatorStop]]] = defaultdict(list)
    for index, stop in enumerate(request.puntos_ruta[1:], start=1):
        if stop.pedido_id:
            all_points_by_order[stop.pedido_id].append((index, stop))

    accepted: list[str] = []
    for order_id, selected in grouped.items():
        all_order_stops = all_points_by_order[order_id]
        selected_types = {stop.type for _, stop in selected}
        all_types = {stop.type for _, stop in all_order_stops}
        mandatory = any(stop.obligatoria for _, stop in all_order_stops)
        pick_index = next((index for index, stop in all_order_stops if stop.type == "pick"), None)
        drop_index = next((index for index, stop in all_order_stops if stop.type == "drop"), None)

        if pick_index is not None and drop_index is not None:
            if selected_types != {"pick", "drop"}:
                raise SimulatorContractError(
                    f"pedido {order_id} debe incluir pick y drop completos"
                )
            if position[pick_index] > position[drop_index]:
                raise SimulatorContractError(f"pedido {order_id} entrega antes de recoger")
        elif selected_types != {"drop"} or all_types != {"drop"}:
            raise SimulatorContractError(f"paradas inválidas para pedido {order_id}")

        if not mandatory:
            accepted.append(order_id)

    available_capacity = request.capacidad_maxima - request.pedidos_activos
    if len(accepted) > available_capacity:
        raise SimulatorContractError("la ruta acepta más pedidos que la capacidad disponible")

    return SimulatorDecisionResponse(
        aceptar_pedidos=accepted,
        paradas_ordenadas=stops,
        ruta_propuesta=[],
    )
