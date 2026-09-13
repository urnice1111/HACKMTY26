export type GeoPoint = {
  lat: number;
  lon: number;
};

export type PathStop = {
  index: number;
  lat: number;
  lon: number;
  arrival_offset_min: number;
};

export type RankedPath = {
  rank: number;
  indexes: number[];
  coordinates: GeoPoint[];
  stops: PathStop[];
  total_weight: number;
  delivery_count: number;
  destination_index: number;
  destination: GeoPoint;
  demand_forecast: number;
  score: number;
  why: string;
};

export type ToolEvent = {
  seq: number;
  tool: string;
  label: string;
  summary: string;
  args: Record<string, unknown>;
  ok: boolean;
};

export type RunStatus = "running" | "complete" | "error";

export type AgentRun = {
  run_id: string;
  shift_id: string | null;
  created_at: string;
  duration_ms: number;
  point_count: number;
  origin: GeoPoint;
  decision: {
    chosen: RankedPath;
    alternatives: RankedPath[];
    description: string;
    notes: string;
  } | null;
  events: ToolEvent[];
  usage: { input_tokens: number; output_tokens: number };
  directions?: { steps: string[]; reason: string } | null;
  status?: RunStatus;
};

export type RunSummary = {
  run_id: string;
  created_at: string;
  duration_ms: number;
  event_count: number;
  has_directions: boolean;
  excerpt: string;
  chosen: {
    delivery_count: number;
    total_weight: number;
    destination_index: number;
  };
  status?: RunStatus;
};

export type ShiftStats = {
  shift_id: string;
  decision_count: number;
  avg_total_weight_min: number;
  pct_single_stop: number;
  pct_multi_stop: number;
  picked_shorter_trip: number;
  picked_busier_stop: number;
};
