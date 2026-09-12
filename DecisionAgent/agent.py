from agents import Agent, RunContextWrapper

from DecisionAgent.config import model_name
from DecisionAgent.Context.context import RoutingContext
from DecisionAgent.Models.structured_output import RoutingDecision
from DecisionAgent.Tools import ROUTING_TOOLS


def build_instructions(
    wrapper: RunContextWrapper[RoutingContext],
    agent: Agent[RoutingContext],
) -> str:
    ctx = wrapper.context
    labels = ", ".join(ctx.fmt(i) for i in range(ctx.n()))
    origin = ctx.point(ctx.origin)
    return f"""
You plan delivery routes between geographic coordinates.

Current request:
- origin index: {ctx.origin} lat={origin["lat"]} lon={origin["lon"]}
- points: {labels}
- now: {ctx.now.isoformat()}
- points have no names or ids; identify them by index and (lat, lon)
- weights are travel minutes

Rules:
- Every path starts at origin index {ctx.origin}.
- A path may include one delivery or several. Do not repeat points.
- Never invent distances. Call path_cost (or use candidate_paths) for weights.
- Workflow:
  1. Call get_graph_summary.
  2. Call candidate_paths to get a pool of single-stop and multi-stop routes.
  3. For promising points, call get_place_context and get_numeric_signals.
  4. For EACH serious candidate, call predict_future on the FINAL destination
     with that path's arrival_offset_min.
  5. Call score_path with total_weight and predicted_demand.
  6. Call take_decision with the top 1-3 scored candidates.
- take_decision picks the path. Do not pick one yourself.
- Put that result in chosen. Put the rest in alternatives.
- Ranking for this iteration:
    score = predicted_demand / (1 + total_weight)
  Higher is better.
- Fill indexes and coordinates for every point in the chosen path and alternatives.
- Fill demand_forecast from predict_future and score from score_path.
- description must read like a person briefing a driver: several sentences, no jargon.
  Copy take_decision's description and add place details if they help. Do not mention
  scores, formulas, or raw index lists.
- why on chosen and each alternative should sound the same: plain language.
- notes can mention parking, peak hour, or congestion without changing the choice.
""".strip()


routing_agent = Agent[RoutingContext](
    name="DeliveryRouter",
    instructions=build_instructions,
    tools=ROUTING_TOOLS,
    output_type=RoutingDecision,
    model=model_name(),
)
