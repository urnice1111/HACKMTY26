"""python -m DecisionAgent          -> live OpenAI run
python -m DecisionAgent --dry-run -> tools only, no LLM
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime

from DecisionAgent.Context.context import RoutingContext, build_matrix, parse_coordinates
from DecisionAgent.Tools.graph_helpers import compute_path_cost, enumerate_candidate_paths
from DecisionAgent.Tools.predict_future import forecast_demand
from DecisionAgent.Tools.scoring import combined_score

# Monterrey-ish sample points: origin plus three drops. No ids.
_SAMPLE_COORDINATES = [
    [25.6514, -100.2895],
    [25.6690, -100.3090],
    [25.6782, -100.3184],
    [25.6401, -100.2702],
]
_SAMPLE_NOW = datetime(2026, 9, 12, 18, 0)


def dry_run() -> None:
    points = parse_coordinates(_SAMPLE_COORDINATES)
    ctx = RoutingContext(
        coordinates=points,
        matrix=build_matrix(points),
        origin=0,
        now=_SAMPLE_NOW,
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
            f"{rank}. {path['coordinates']} weight={path['total_weight']} "
            f"demand={demand['predicted_demand']} score={round(score, 4)}"
        )
        print("   ", compute_path_cost(ctx, path["indexes"]))


def live_run() -> None:
    from DecisionAgent.runner import run_routing_agent_sync

    decision = run_routing_agent_sync(
        coordinates=_SAMPLE_COORDINATES,
        origin=0,
        now=_SAMPLE_NOW,
    )
    print(json.dumps(decision.model_dump(), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Skip the LLM and score paths locally")
    args = parser.parse_args()
    if args.dry_run:
        dry_run()
        return
    live_run()


if __name__ == "__main__":
    main()
