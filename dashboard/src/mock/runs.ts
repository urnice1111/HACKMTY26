import type { AgentRun, RankedPath, ToolEvent } from "../types";

const origin = { lat: 25.6514, lon: -100.2895 };
const p1 = { lat: 25.669, lon: -100.309 };
const p2 = { lat: 25.6782, lon: -100.3184 };
const p3 = { lat: 25.6401, lon: -100.2702 };

function path(partial: Omit<RankedPath, "coordinates" | "stops" | "destination"> & { dest: { lat: number; lon: number } }): RankedPath {
  const coordinates = [origin, partial.dest];
  return {
    rank: partial.rank,
    indexes: partial.indexes,
    coordinates,
    stops: [
      {
        index: partial.destination_index,
        lat: partial.dest.lat,
        lon: partial.dest.lon,
        arrival_offset_min: partial.total_weight,
      },
    ],
    total_weight: partial.total_weight,
    delivery_count: partial.delivery_count,
    destination_index: partial.destination_index,
    destination: partial.dest,
    demand_forecast: partial.demand_forecast,
    score: partial.score,
    why: partial.why,
  };
}

const tools = (extras: ToolEvent[] = []): ToolEvent[] => [
  { seq: 1, tool: "get_graph_summary", label: "Reading the area", summary: "Looked over the area around the origin.", args: {}, ok: true },
  { seq: 2, tool: "candidate_paths", label: "Sketching possible routes", summary: "Sketched 8 possible routes from the origin.", args: { k: 8 }, ok: true },
  { seq: 3, tool: "get_place_context", label: "Checking the neighborhood", summary: "Checked what the neighborhood around a stop is like.", args: {}, ok: true },
  { seq: 4, tool: "get_numeric_signals", label: "Looking at live numbers", summary: "Looked at live numbers for a stop.", args: {}, ok: true },
  { seq: 5, tool: "predict_future", label: "Guessing how busy it will be", summary: "Guessed how busy the last stop will be when the vehicle arrives.", args: {}, ok: true },
  { seq: 6, tool: "path_cost", label: "Timing the trip", summary: "Timed a trip of about 5 minutes.", args: {}, ok: true },
  { seq: 7, tool: "score_path", label: "Weighing time vs demand", summary: "Weighed how long the drive is against how busy the stop looks.", args: {}, ok: true },
  { seq: 8, tool: "take_decision", label: "Picking the run", summary: "Picked the run that ends at point 3.", args: {}, ok: true },
  ...extras,
];

export const MOCK_RUN_A: AgentRun = {
  run_id: "run-alpha",
  shift_id: "shift-abc",
  created_at: "2026-09-12T18:01:00",
  duration_ms: 4100,
  point_count: 4,
  origin,
  decision: {
    chosen: path({
      rank: 1,
      indexes: [0, 3],
      dest: p3,
      total_weight: 4.6,
      delivery_count: 1,
      destination_index: 3,
      demand_forecast: 19.8,
      score: 3.52,
      why: "Go with one delivery at point 3. The drive is about 5 minutes and the last stop looks busy when you would arrive.",
    }),
    alternatives: [
      path({
        rank: 2,
        indexes: [0, 1],
        dest: p1,
        total_weight: 5.5,
        delivery_count: 1,
        destination_index: 1,
        demand_forecast: 16.2,
        score: 2.48,
        why: "Skipping one delivery at point 1: a bit longer, and fewer people waiting.",
      }),
      path({
        rank: 3,
        indexes: [0, 2],
        dest: p2,
        total_weight: 8.3,
        delivery_count: 1,
        destination_index: 2,
        demand_forecast: 18.0,
        score: 1.93,
        why: "Skipping one delivery at point 2: the extra driving does not pay off enough.",
      }),
    ],
    description:
      "Go with one delivery at point 3. The drive is about 4 minutes, and there is strong demand when the vehicle would arrive. Send the vehicle on the shorter, busier run first.",
    notes: "Evening window. Street parking may be tight later.",
  },
  events: tools(),
  usage: { input_tokens: 1200, output_tokens: 400 },
  status: "complete",
  directions: {
    steps: ["Leave the depot heading southeast.", "Continue about 4 minutes.", "Arrive at the drop."],
    reason: "Shortest busy run from the origin.",
  },
};

export const MOCK_RUN_B: AgentRun = {
  run_id: "run-bravo",
  shift_id: "shift-abc",
  created_at: "2026-09-12T18:08:00",
  duration_ms: 3800,
  point_count: 4,
  origin,
  decision: {
    chosen: path({
      rank: 1,
      indexes: [0, 1, 2],
      dest: p2,
      total_weight: 11.2,
      delivery_count: 2,
      destination_index: 2,
      demand_forecast: 18.0,
      score: 1.47,
      why: "Two deliveries, stopping at point 1 then point 2. Demand at the last stop still looks solid.",
    }),
    alternatives: [
      path({
        rank: 2,
        indexes: [0, 1],
        dest: p1,
        total_weight: 5.5,
        delivery_count: 1,
        destination_index: 1,
        demand_forecast: 12.0,
        score: 1.84,
        why: "A quicker single drop, but the last stop looks quieter.",
      }),
    ],
    description:
      "Go with two deliveries, stopping at point 1 then point 2. It takes longer than a one-stop run, but both drops are on the way and the last stop still looks busy enough to justify the extra minutes.",
    notes: "",
  },
  events: [
    { seq: 1, tool: "get_graph_summary", label: "Reading the area", summary: "Looked over the area around the origin.", args: {}, ok: true },
    { seq: 2, tool: "candidate_paths", label: "Sketching possible routes", summary: "Sketched 6 possible routes from the origin.", args: {}, ok: true },
    { seq: 3, tool: "path_cost", label: "Timing the trip", summary: "Timed a trip of about 11 minutes.", args: {}, ok: true },
    { seq: 4, tool: "predict_future", label: "Guessing how busy it will be", summary: "Guessed how busy the last stop will be when the vehicle arrives.", args: {}, ok: true },
    { seq: 5, tool: "score_path", label: "Weighing time vs demand", summary: "Weighed how long the drive is against how busy the stop looks.", args: {}, ok: true },
    { seq: 6, tool: "take_decision", label: "Picking the run", summary: "Picked the run that ends at point 2.", args: {}, ok: true },
  ],
  usage: { input_tokens: 900, output_tokens: 320 },
  status: "complete",
  directions: null,
};

export const MOCK_RUNS: AgentRun[] = [MOCK_RUN_A, MOCK_RUN_B];
