import type { RankedPath } from "../types";

type Props = {
  chosen?: RankedPath;
  alternatives: RankedPath[];
  revealed: boolean;
};

function Column({ title, path, winner }: { title: string; path: RankedPath; winner?: boolean }) {
  const hops = path.indexes.map((i) => `point ${i}`).join(" → ");
  return (
    <article className={winner ? "compare-col is-winner" : "compare-col"}>
      <h3>{title}</h3>
      <dl>
        <div>
          <dt>Drive</dt>
          <dd>~{Math.round(path.total_weight)} min</dd>
        </div>
        <div>
          <dt>How busy it looks</dt>
          <dd>{path.demand_forecast.toFixed(1)}</dd>
        </div>
        <div>
          <dt>Stops</dt>
          <dd>{path.delivery_count === 1 ? "1 delivery" : `${path.delivery_count} deliveries`}</dd>
        </div>
      </dl>
      <p className="hops">{hops}</p>
      <p className="why">{path.why}</p>
    </article>
  );
}

export function ComparePanel({ chosen, alternatives, revealed }: Props) {
  if (!revealed || !chosen) {
    return <p className="muted">Compare unlocks after the agent picks a run.</p>;
  }

  const rest = alternatives.slice(0, 2);
  return (
    <section className="panel compare">
      <h2>Compare</h2>
      <div className="compare-grid">
        <Column title="Chosen" path={chosen} winner />
        {rest.map((path, i) => (
          <Column key={path.indexes.join("-")} title={`Option ${i + 2}`} path={path} />
        ))}
      </div>
    </section>
  );
}
