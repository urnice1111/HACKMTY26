import { useEffect, useRef, useState } from "react";
import type { ToolEvent } from "../types";

const ICONS: Record<string, string> = {
  get_graph_summary: "◎",
  candidate_paths: "⎇",
  path_cost: "⏱",
  get_place_context: "⌂",
  get_numeric_signals: "⌁",
  predict_future: "✧",
  score_path: "⚖",
  take_decision: "✓",
};

type Props = {
  events: ToolEvent[];
  replayKey: string;
  live?: boolean;
  onComplete: (done: boolean) => void;
};

export function ToolReplay({ events, replayKey, live = false, onComplete }: Props) {
  const ordered = [...events].sort((a, b) => a.seq - b.seq);
  const [visible, setVisible] = useState(0);
  const [playing, setPlaying] = useState(true);
  const completeRef = useRef(onComplete);
  completeRef.current = onComplete;
  const followedLive = useRef(false);

  useEffect(() => {
    setVisible(0);
    setPlaying(true);
    followedLive.current = false;
    completeRef.current(false);
  }, [replayKey]);

  useEffect(() => {
    if (live) {
      followedLive.current = true;
      setVisible(ordered.length);
      completeRef.current(false);
      return;
    }
    if (followedLive.current) {
      setVisible(ordered.length);
      completeRef.current(true);
      return;
    }
    if (ordered.length > 0 && visible >= ordered.length) {
      completeRef.current(true);
      return;
    }
    if (!playing || visible >= ordered.length) return;
    const id = window.setTimeout(() => setVisible((n) => n + 1), 700);
    return () => window.clearTimeout(id);
  }, [live, playing, visible, ordered.length]);

  const current = ordered[visible - 1];

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>{live ? "Agent live" : "Agent replay"}</h2>
        <div className="replay-controls">
          <button type="button" onClick={() => setPlaying((p) => !p)} disabled={live}>
            {playing ? "Pause" : "Play"}
          </button>
          <button
            type="button"
            onClick={() => {
              followedLive.current = false;
              setVisible(0);
              setPlaying(true);
              completeRef.current(false);
            }}
          >
            Replay
          </button>
          <button
            type="button"
            onClick={() => {
              setVisible(ordered.length);
              setPlaying(false);
              if (!live) completeRef.current(true);
            }}
          >
            Skip
          </button>
        </div>
      </header>
      <ol className="timeline">
        {ordered.map((event, i) => {
          const revealed = i < visible;
          const isCurrent = i === visible - 1;
          const finale = event.tool === "take_decision" && isCurrent;
          return (
            <li
              key={event.seq}
              className={`tick${revealed ? " is-on" : ""}${isCurrent ? " is-current" : ""}${finale ? " is-finale" : ""}${event.ok ? "" : " is-bad"}`}
            >
              <span className="tick-icon" aria-hidden="true">
                {ICONS[event.tool] ?? "•"}
              </span>
              <div>
                <p className="tick-label">{event.label}</p>
                <p className="tick-summary">{event.summary}</p>
              </div>
            </li>
          );
        })}
      </ol>
      {ordered.length === 0 && live ? <p className="muted">Waiting for the first tool…</p> : null}
      {current ? (
        <p className="sr-only" aria-live="polite">
          {current.label}. {current.summary}
        </p>
      ) : null}
    </section>
  );
}
