import type { AgentRun, RunSummary, ShiftStats } from "./types";
import { MOCK_RUN_A, MOCK_RUN_B } from "./mock/runs";

const apiBase = (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000/v1";
const useMock = import.meta.env.VITE_USE_MOCK === "1";

const mockStarted = Date.now();
const mockUnlockMs = 4000;

function toSummary(run: AgentRun): RunSummary {
  const excerpt =
    run.decision?.description.slice(0, 140) ??
    run.events.at(-1)?.label ??
    "Thinking…";
  return {
    run_id: run.run_id,
    created_at: run.created_at,
    duration_ms: run.duration_ms,
    event_count: run.events.length,
    has_directions: Boolean(run.directions),
    excerpt,
    chosen: run.decision
      ? {
          delivery_count: run.decision.chosen.delivery_count,
          total_weight: run.decision.chosen.total_weight,
          destination_index: run.decision.chosen.destination_index,
        }
      : { delivery_count: 0, total_weight: 0, destination_index: 0 },
    status: run.status ?? "complete",
  };
}

function visibleMockRuns(): AgentRun[] {
  const unlocked = Date.now() - mockStarted >= mockUnlockMs;
  const runs = unlocked ? [MOCK_RUN_B, MOCK_RUN_A] : [MOCK_RUN_A];
  return runs;
}

function statsFrom(runs: AgentRun[], shiftId: string): ShiftStats {
  const finished = runs.filter((r) => r.decision);
  if (finished.length === 0) {
    return {
      shift_id: shiftId,
      decision_count: 0,
      avg_total_weight_min: 0,
      pct_single_stop: 0,
      pct_multi_stop: 0,
      picked_shorter_trip: 0,
      picked_busier_stop: 0,
    };
  }
  const single = finished.filter((r) => r.decision!.chosen.delivery_count === 1).length;
  let shorter = 0;
  let busier = 0;
  for (const run of finished) {
    const pack = [run.decision!.chosen, ...run.decision!.alternatives];
    const minW = Math.min(...pack.map((p) => p.total_weight));
    const maxD = Math.max(...pack.map((p) => p.demand_forecast));
    if (run.decision!.chosen.total_weight === minW) shorter += 1;
    if (run.decision!.chosen.demand_forecast === maxD) busier += 1;
  }
  const avg = finished.reduce((s, r) => s + r.decision!.chosen.total_weight, 0) / finished.length;
  return {
    shift_id: shiftId,
    decision_count: finished.length,
    avg_total_weight_min: Math.round(avg * 10) / 10,
    pct_single_stop: single / finished.length,
    pct_multi_stop: 1 - single / finished.length,
    picked_shorter_trip: shorter,
    picked_busier_stop: busier,
  };
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${apiBase}${path}`);
  if (!res.ok) {
    throw new Error(`${res.status} ${path}`);
  }
  return (await res.json()) as T;
}

export async function listRuns(shiftId: string): Promise<RunSummary[]> {
  if (useMock) {
    return visibleMockRuns().map(toSummary);
  }
  const data = await getJson<{ runs: RunSummary[] }>(`/shifts/${encodeURIComponent(shiftId)}/runs?limit=50`);
  return data.runs ?? [];
}

export async function getRun(runId: string): Promise<AgentRun> {
  if (useMock) {
    const run = [MOCK_RUN_A, MOCK_RUN_B].find((r) => r.run_id === runId);
    if (!run) throw new Error("unknown mock run");
    return run;
  }
  return getJson<AgentRun>(`/runs/${encodeURIComponent(runId)}`);
}

export async function getStats(shiftId: string): Promise<ShiftStats> {
  if (useMock) {
    return statsFrom(visibleMockRuns(), shiftId);
  }
  return getJson<ShiftStats>(`/shifts/${encodeURIComponent(shiftId)}/stats`);
}

export const isMock = useMock;
