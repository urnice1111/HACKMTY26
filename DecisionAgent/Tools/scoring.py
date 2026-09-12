from agents.decorators import tool


def combined_score(total_weight: float, predicted_demand: float) -> float:
    return predicted_demand / (1.0 + total_weight)


@tool
def score_path(total_weight: float, predicted_demand: float) -> dict:
    """Score a path. Higher is better. For now: demand / (1 + weight).

    Args:
        total_weight: Path cost from path_cost.
        predicted_demand: Demand from predict_future at the final destination.
    """
    if total_weight < 0:
        return {"ok": False, "error": "total_weight must be >= 0"}
    score = combined_score(total_weight, predicted_demand)
    return {
        "ok": True,
        "score": score,
        "formula": "predicted_demand / (1 + total_weight)",
        "total_weight": total_weight,
        "predicted_demand": predicted_demand,
    }
