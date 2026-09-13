import type { AgentRun } from "../types";

type Props = {
  run: AgentRun;
  revealed: boolean;
};

export function DecisionCopy({ run, revealed }: Props) {
  if (!revealed || !run.decision) {
    return null;
  }

  const directions = run.directions;
  return (
    <section className="panel copy">
      <h2>Why this run</h2>
      <p className="hero-copy">{run.decision.description}</p>
      {run.decision.notes ? <p className="notes">{run.decision.notes}</p> : null}
      {directions ? (
        <div className="directions">
          <h3>Directions</h3>
          <p className="notes">{directions.reason}</p>
          <ol>
            {directions.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </div>
      ) : null}
    </section>
  );
}
