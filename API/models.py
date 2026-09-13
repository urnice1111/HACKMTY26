from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import AliasChoices, BaseModel, BeforeValidator, ConfigDict, Field


def empty_if_none(value: Any) -> Any:
    """Go marshals empty slices as JSON null; treat that as an empty list."""
    return [] if value is None else value


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


class SimulatorStop(BaseModel):
    """One of the simulator's route points, in its native JSON shape."""

    id: str
    pedido_id: str | None = None
    type: Literal["courier", "pick", "drop"]
    latitud: float
    longitud: float
    obligatoria: bool = False


class SimulatorPrecedence(BaseModel):
    pedido_id: str
    pick: str
    drop: str


class SimulatorRestrictions(BaseModel):
    capacidad_maxima: int = Field(ge=0)
    pedidos_activos: Annotated[list[dict], BeforeValidator(empty_if_none)] = Field(
        default_factory=list
    )
    precedencias: Annotated[list[SimulatorPrecedence], BeforeValidator(empty_if_none)] = (
        Field(default_factory=list)
    )


class SimulatorDecisionRequest(BaseModel):
    """Contract sent by the Go simulator to ``POST /decision``.

    The matrix preserves ``null`` because it represents an unreachable or
    precedence-forbidden hop. The adapter converts it to the agent's negative
    sentinel before planning.
    """

    evento: str
    tiempo_simulado: str
    estado_courier: CourierState
    pedidos_activos: int = Field(ge=0)
    capacidad_maxima: int = Field(ge=0)
    puntos_ruta: list[SimulatorStop] = Field(min_length=1)
    matriz: list[list[float | None]]
    matriz_unidad: Literal["mxn_equivalente"]
    valor_minuto_mxn: float = Field(gt=0)
    restricciones: SimulatorRestrictions
    pedidos_disponibles: Annotated[list[dict], BeforeValidator(empty_if_none)] = Field(
        default_factory=list
    )


class SimulatorDecisionResponse(BaseModel):
    """Decision shape consumed by ``internal/sim.AgentClient``."""

    aceptar_pedidos: Annotated[list[str], BeforeValidator(empty_if_none)] = Field(
        default_factory=list
    )
    paradas_ordenadas: Annotated[list[SimulatorStop], BeforeValidator(empty_if_none)] = (
        Field(default_factory=list)
    )
    ruta_propuesta: Annotated[list[dict], BeforeValidator(empty_if_none)] = Field(
        default_factory=list
    )
    descripcion: str = ""
    direcciones: Annotated[list[str], BeforeValidator(empty_if_none)] = Field(
        default_factory=list
    )
