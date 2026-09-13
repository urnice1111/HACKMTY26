from enum import Enum

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


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
