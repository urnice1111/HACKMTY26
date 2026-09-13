import type { ShiftStats } from "../types";

type Props = {
  stats: ShiftStats | null;
};

export function ShiftStats({ stats }: Props) {
  if (!stats || stats.decision_count === 0) {
    return (
      <footer className="stats">
        <p>No shift stats yet.</p>
      </footer>
    );
  }

  const pct = (n: number) => `${Math.round(n * 100)}%`;
  return (
    <footer className="stats">
      <div>
        <span className="stat-label">Decisions</span>
        <strong>{stats.decision_count}</strong>
      </div>
      <div>
        <span className="stat-label">Avg minutes</span>
        <strong>{stats.avg_total_weight_min}</strong>
      </div>
      <div>
        <span className="stat-label">One stop</span>
        <strong>{pct(stats.pct_single_stop)}</strong>
      </div>
      <div>
        <span className="stat-label">Multi stop</span>
        <strong>{pct(stats.pct_multi_stop)}</strong>
      </div>
      <div>
        <span className="stat-label">Picked shorter trip</span>
        <strong>{stats.picked_shorter_trip}</strong>
      </div>
      <div>
        <span className="stat-label">Picked busier stop</span>
        <strong>{stats.picked_busier_stop}</strong>
      </div>
    </footer>
  );
}
