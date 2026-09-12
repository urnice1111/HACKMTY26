import os

from agents import Agent, RunContextWrapper

from DecisionAgent.Context.context import RoutingContext
from DecisionAgent.Models.structured_output import RoutingDecision
from DecisionAgent.Tools import ROUTING_TOOLS


def build_instructions(
    wrapper: RunContextWrapper[RoutingContext],
    agent: Agent[RoutingContext],
) -> str:
    ctx = wrapper.context
    origin_id = ctx.node_ids[ctx.origin]
    labels = ", ".join(f"{i}:{name}" for i, name in enumerate(ctx.node_ids))
    return f"""
You plan delivery routes on a weighted graph.

Current request:
- origin index: {ctx.origin} ({origin_id})
- nodes: {labels}
- now: {ctx.now.isoformat()}
- matrix weights are travel minutes

Rules:
- Every path starts at origin {ctx.origin}.
- A path may include one delivery or several. Do not repeat nodes.
- Never invent distances. Call path_cost (or use candidate_paths) for weights.
- Workflow:
  1. Call get_graph_summary.
  2. Call candidate_paths to get a pool of single-stop and multi-stop routes.
  3. For promising nodes, call get_place_context and get_numeric_signals.
  4. For EACH serious candidate, call predict_future on the FINAL destination
     with that path's arrival_offset_min.
  5. Call score_path with total_weight and predicted_demand.
- Ranking for this iteration:
    score = predicted_demand / (1 + total_weight)
  Higher is better.
- Return the top 3 paths, ranked 1-3. If the graph has fewer valid paths, return all of them.
- Fill demand_forecast from predict_future and score from score_path.
- Keep why short and specific.
""".strip()


routing_agent = Agent[RoutingContext](
    name="DeliveryRouter",
    instructions=build_instructions,
    tools=ROUTING_TOOLS,
    output_type=RoutingDecision,
    model=os.getenv("OPENAI_MODEL", "gpt-4o"),
)
