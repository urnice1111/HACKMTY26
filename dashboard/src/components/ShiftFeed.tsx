import type { RunSummary } from "../types";

type Props = {
  runs: RunSummary[];
  selectedId: string | null;
  onSelect: (runId: string) => void;
};

function deliveries(count: number): string {
  if (count === 1) return "1 delivery";
  return `${count} deliveries`;
}

export function ShiftFeed({ runs, selectedId, onSelect }: Props) {
  if (runs.length === 0) {
    return <p className="empty">Waiting for the simulator…</p>;
  }

  return (
    <ul className="feed">
      {runs.map((run) => {
        const active = run.run_id === selectedId;
        return (
          <li key={run.run_id}>
            <button
              type="button"
              className={active ? "feed-card is-active" : "feed-card"}
              onClick={() => onSelect(run.run_id)}
            >
              <div className="feed-meta">
                <time dateTime={run.created_at}>
                  {new Date(run.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </time>
              {run.status === "running" ? <span className="badge">live</span> : null}
              {run.has_directions ? <span className="badge">directions</span> : null}
            </div>
            {run.status === "running" ? (
              <>
                <p className="feed-title">In progress…</p>
                <p className="feed-mins">
                  {run.event_count === 1 ? "1 tool" : `${run.event_count} tools`}
                </p>
              </>
            ) : (
              <>
                <p className="feed-title">
                  {deliveries(run.chosen.delivery_count)} to point {run.chosen.destination_index}
                </p>
                <p className="feed-mins">~{Math.round(run.chosen.total_weight)} min</p>
              </>
            )}
              <p className="feed-excerpt">{run.excerpt}</p>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
