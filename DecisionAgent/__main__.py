"""Local check without calling the LLM: python -m DecisionAgent --dry-run"""

from datetime import datetime

from DecisionAgent.Context.context import RoutingContext
from DecisionAgent.Tools.graph_helpers import compute_path_cost, enumerate_candidate_paths
from DecisionAgent.Tools.predict_future import forecast_demand
from DecisionAgent.Tools.scoring import combined_score

_SAMPLE_MATRIX = [
    [0, 8, 12, 20],
    [8, 0, 6, 10],
    [12, 6, 0, 7],
    [20, 10, 7, 0],
]
_SAMPLE_IDS = ["hub", "A", "B", "C"]


def dry_run() -> None:
    ctx = RoutingContext(
        matrix=_SAMPLE_MATRIX,
        node_ids=_SAMPLE_IDS,
        origin=0,
        now=datetime(2026, 9, 12, 18, 0),
    )
    pool = enumerate_candidate_paths(ctx, k=8, max_deliveries=3)
    ranked = []
    for path in pool["paths"]:
        demand = forecast_demand(ctx, path["destination_index"], path["arrival_offset_min"])
        score = combined_score(path["total_weight"], demand["predicted_demand"])
        ranked.append((score, path, demand))
    ranked.sort(key=lambda item: item[0], reverse=True)
    print("top paths (dry-run, no LLM):")
    for rank, (score, path, demand) in enumerate(ranked[:3], start=1):
        print(
            f"{rank}. {path['node_ids']} weight={path['total_weight']} "
            f"demand={demand['predicted_demand']} score={round(score, 4)}"
        )
        print("   ", compute_path_cost(ctx, path["nodes"]))


if __name__ == "__main__":
    dry_run()
