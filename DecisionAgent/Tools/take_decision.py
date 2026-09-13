from pydantic import BaseModel
from agents import RunContextWrapper
from agents.decorators import tool

from DecisionAgent.Context.context import RoutingContext
from DecisionAgent.Tools.scoring import combined_score


class PathCandidate(BaseModel):
    indexes: list[int]
    total_weight: float
    demand_forecast: float
    score: float | None = None


def _weight_phrase(weight: float) -> str:
    rounded = round(weight)
    if abs(weight - rounded) < 0.15:
        return f"{rounded} weighted route units"
    return f"{weight:.1f} weighted route units"


def _stops_phrase(indexes: list[int]) -> str:
    drops = indexes[1:]
    if not drops:
        return "no deliveries"
    if len(drops) == 1:
        return f"one delivery at point {drops[0]}"
    visit = ", then ".join(f"point {i}" for i in drops)
    return f"{len(drops)} deliveries, stopping at {visit}"


def _demand_phrase(value: float, peak: float) -> str:
    if peak <= 0:
        return f"expected demand around {value:.1f}"
    ratio = value / peak
    if ratio >= 0.9:
        return f"strong demand (about {value:.1f}) when the vehicle would arrive"
    if ratio >= 0.65:
        return f"decent demand (about {value:.1f}) when the vehicle would arrive"
    return f"weaker demand (about {value:.1f}) when the vehicle would arrive"


def describe_choice(chosen: dict, alternatives: list[dict]) -> str:
    peak = max(
        [chosen["demand_forecast"]] + [alt["demand_forecast"] for alt in alternatives],
        default=chosen["demand_forecast"],
    )
    chosen_stops = _stops_phrase(chosen["indexes"])
    opening = (
        f"Go with {chosen_stops}. Its route cost is about {_weight_phrase(chosen['total_weight'])}, "
        f"and there is {_demand_phrase(chosen['demand_forecast'], peak)}. "
        f"That combination is the best tradeoff right now: enough people waiting relative to how long the trip takes."
    )

    if not alternatives:
        rest = "There were no other serious options on the table, so this is the run to take."
    else:
        bits = []
        for alt in alternatives:
            alt_stops = _stops_phrase(alt["indexes"])
            slower = alt["total_weight"] > chosen["total_weight"] + 0.5
            weaker = alt["demand_forecast"] < chosen["demand_forecast"] * 0.9
            if slower and weaker:
                reason = "it takes longer and fewer people are expected to be waiting"
            elif slower:
                reason = "the extra driving does not pay off enough"
            elif weaker:
                reason = "demand there is softer even though the trip is comparable"
            else:
                reason = "it is simply a worse balance of time and demand"
            bits.append(
                f"Skipping {alt_stops}: that one costs about {_weight_phrase(alt['total_weight'])} "
                f"with {_demand_phrase(alt['demand_forecast'], peak)}, so {reason}."
            )
        rest = " ".join(bits)

    closing = (
        "In plain terms: send the vehicle on the shorter, busier run first. "
        "We are not folding in traffic, parking, or time windows yet—just how long the road is "
        "versus how busy the last stop looks at arrival."
    )
    return " ".join([opening, rest, closing])


def choose_path(candidates: list[PathCandidate]) -> dict:
    if not candidates:
        return {"ok": False, "error": "candidates must not be empty"}

    scored = []
    for raw in candidates:
        score = (
            raw.score
            if raw.score is not None
            else combined_score(raw.total_weight, raw.demand_forecast)
        )
        scored.append(
            {
                "indexes": raw.indexes,
                "total_weight": raw.total_weight,
                "demand_forecast": raw.demand_forecast,
                "score": score,
            }
        )

    scored.sort(key=lambda item: item["score"], reverse=True)
    chosen = scored[0]
    alternatives = scored[1:]
    description = describe_choice(chosen, alternatives)
    return {
        "ok": True,
        "chosen": chosen,
        "alternatives": alternatives,
        "why": description,
        "description": description,
        "rule": "max score = demand_forecast / (1 + total_weight)",
    }


@tool
def take_decision(
    wrapper: RunContextWrapper[RoutingContext],
    candidates: list[PathCandidate],
) -> dict:
    """Pick one delivery run from up to three options and explain it like a dispatcher would.

    Use this after you already know travel time and expected demand for each option.
    It always sends the vehicle on the option with the best balance of a short trip
    and busy destination, and it writes that choice in everyday language.

    Args:
        candidates: One to three scored paths. Do not pass more than three.
    """
    if len(candidates) > 3:
        return {"ok": False, "error": "pass at most 3 candidates"}
    return choose_path(candidates)
