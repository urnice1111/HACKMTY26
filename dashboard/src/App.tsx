import { useCallback, useEffect, useRef, useState } from "react";
import { getRun, getStats, isMock, listRuns } from "./api";
import { ComparePanel } from "./components/ComparePanel";
import { DecisionCopy } from "./components/DecisionCopy";
import { ShiftFeed } from "./components/ShiftFeed";
import { ShiftStats } from "./components/ShiftStats";
import { ToolReplay } from "./components/ToolReplay";
import type { AgentRun, RunSummary, ShiftStats as ShiftStatsData } from "./types";

const defaultShift = (import.meta.env.VITE_SHIFT_ID as string | undefined) ?? "shift-abc";

export default function App() {
  const [shiftId, setShiftId] = useState(defaultShift);
  const [draftShift, setDraftShift] = useState(defaultShift);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<AgentRun | null>(null);
  const [stats, setStats] = useState<ShiftStatsData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [replayDone, setReplayDone] = useState(false);
  const seen = useRef(new Set<string>());
  const autoPlayed = useRef(new Set<string>());
  const selectedIdRef = useRef<string | null>(null);
  selectedIdRef.current = selectedId;

  const refresh = useCallback(async () => {
    try {
      const list = await listRuns(shiftId);
      setError(null);
      setRuns(list);
      const nextStats = await getStats(shiftId);
      setStats(nextStats);

      const newest = list[0];
      if (newest) {
        const known = seen.current.has(newest.run_id);
        const firstWave = seen.current.size === 0;
        if (!known || firstWave) {
          if (!autoPlayed.current.has(newest.run_id)) {
            autoPlayed.current.add(newest.run_id);
            setSelectedId(newest.run_id);
          }
        }
      }
      for (const item of list) seen.current.add(item.run_id);

      const currentId = selectedIdRef.current ?? newest?.run_id ?? null;
      if (currentId) {
        const nextDetail = await getRun(currentId);
        setDetail(nextDetail);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reach the API");
    }
  }, [shiftId]);

  useEffect(() => {
    seen.current = new Set();
    autoPlayed.current = new Set();
    setSelectedId(null);
    setDetail(null);
    void refresh();
    const id = window.setInterval(() => void refresh(), 1500);
    return () => window.clearInterval(id);
  }, [refresh]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    setReplayDone(false);
    void getRun(selectedId)
      .then(setDetail)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Could not load run");
      });
  }, [selectedId]);

  const onReplayComplete = useCallback((done: boolean) => {
    setReplayDone(done);
  }, []);

  const decisionReady = Boolean(detail?.decision) && (replayDone || detail?.status === "complete");
  const live = detail?.status === "running";

  return (
    <div className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Decision observer</p>
          <h1>Shift console</h1>
        </div>
        <form
          className="shift-form"
          onSubmit={(e) => {
            e.preventDefault();
            setShiftId(draftShift.trim() || defaultShift);
          }}
        >
          <label>
            Shift
            <input
              value={draftShift}
              onChange={(e) => setDraftShift(e.target.value)}
              name="shift"
            />
          </label>
          <button type="submit">Watch</button>
        </form>
        <p className={isMock ? "live mock" : "live"}>
          <span className="dot" />
          {isMock ? "Mock data" : live ? "Live run" : "Live poll"}
        </p>
      </header>

      {error ? (
        <p className="banner" role="alert">
          {error} — retrying. Last data kept if any.
        </p>
      ) : null}

      <div className="layout">
        <aside>
          <h2>Decisions</h2>
          <ShiftFeed runs={runs} selectedId={selectedId} onSelect={setSelectedId} />
        </aside>
        <main>
          {detail ? (
            <>
              <ToolReplay
                events={detail.events}
                replayKey={detail.run_id}
                live={live}
                onComplete={onReplayComplete}
              />
              <DecisionCopy run={detail} revealed={decisionReady} />
              <ComparePanel
                chosen={detail.decision?.chosen}
                alternatives={detail.decision?.alternatives ?? []}
                revealed={decisionReady}
              />
            </>
          ) : (
            <p className="empty">Waiting for the simulator…</p>
          )}
        </main>
      </div>
      <ShiftStats stats={stats} />
    </div>
  );
}
