"""In-memory AgentRun history for the dashboard. Restart wipes it."""

from __future__ import annotations

from threading import Lock

from pydantic import BaseModel, Field

from DecisionAgent.Models.structured_output import AgentRun

DEFAULT_SHIFT_ID = "shift-abc"

_lock = Lock()
_runs: dict[str, AgentRun] = {}
_order: list[str] = []


class ChosenSummary(BaseModel):
    delivery_count: int
    total_weight: float
    destination_index: int


class RunSummary(BaseModel):
    run_id: str
    created_at: str
    duration_ms: float
    event_count: int
    has_directions: bool
    excerpt: str
    chosen: ChosenSummary
    status: str = "complete"


class RunListResponse(BaseModel):
    runs: list[RunSummary] = Field(default_factory=list)


class ShiftStats(BaseModel):
    shift_id: str
    decision_count: int
    avg_total_weight_min: float
    pct_single_stop: float
    pct_multi_stop: float
    picked_shorter_trip: int
    picked_busier_stop: int


def _with_shift(run: AgentRun) -> AgentRun:
    if run.shift_id:
        return run
    return run.model_copy(update={"shift_id": DEFAULT_SHIFT_ID})


def save_run(run: AgentRun) -> AgentRun:
    stored = _with_shift(run)
    with _lock:
        if stored.run_id not in _runs:
            _order.insert(0, stored.run_id)
        _runs[stored.run_id] = stored
    return stored


def clear_runs() -> None:
    with _lock:
        _runs.clear()
        _order.clear()


def get_run(run_id: str) -> AgentRun | None:
    with _lock:
        return _runs.get(run_id)


def list_runs(shift_id: str, limit: int = 50) -> list[AgentRun]:
    with _lock:
        matched: list[AgentRun] = []
        for run_id in _order:
            run = _runs[run_id]
            if run.shift_id == shift_id:
                matched.append(run)
            if len(matched) >= limit:
                break
        return matched


def to_summary(run: AgentRun) -> RunSummary:
    decision = run.decision
    if decision is None:
        last = run.events[-1].label if run.events else "Thinking…"
        return RunSummary(
            run_id=run.run_id,
            created_at=run.created_at,
            duration_ms=run.duration_ms,
            event_count=len(run.events),
            has_directions=False,
            excerpt=last,
            chosen=ChosenSummary(delivery_count=0, total_weight=0, destination_index=0),
            status=run.status,
        )
    chosen = decision.chosen
    return RunSummary(
        run_id=run.run_id,
        created_at=run.created_at,
        duration_ms=run.duration_ms,
        event_count=len(run.events),
        has_directions=run.directions is not None,
        excerpt=decision.description[:140],
        chosen=ChosenSummary(
            delivery_count=chosen.delivery_count,
            total_weight=chosen.total_weight,
            destination_index=chosen.destination_index,
        ),
        status=run.status,
    )


def stats_from(runs: list[AgentRun], shift_id: str) -> ShiftStats:
    finished = [run for run in runs if run.status == "complete" and run.decision is not None]
    if not finished:
        return ShiftStats(
            shift_id=shift_id,
            decision_count=0,
            avg_total_weight_min=0,
            pct_single_stop=0,
            pct_multi_stop=0,
            picked_shorter_trip=0,
            picked_busier_stop=0,
        )

    single = sum(1 for run in finished if run.decision.chosen.delivery_count == 1)
    shorter = 0
    busier = 0
    for run in finished:
        pack = [run.decision.chosen, *run.decision.alternatives]
        min_weight = min(path.total_weight for path in pack)
        max_demand = max(path.demand_forecast for path in pack)
        if run.decision.chosen.total_weight == min_weight:
            shorter += 1
        if run.decision.chosen.demand_forecast == max_demand:
            busier += 1
    avg = sum(run.decision.chosen.total_weight for run in finished) / len(finished)
    return ShiftStats(
        shift_id=shift_id,
        decision_count=len(finished),
        avg_total_weight_min=round(avg, 1),
        pct_single_stop=single / len(finished),
        pct_multi_stop=1 - single / len(finished),
        picked_shorter_trip=shorter,
        picked_busier_stop=busier,
    )
