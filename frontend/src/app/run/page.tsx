"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { API_URL, api } from "@/lib/api";

type RunEvent = {
  type: string;
  payload?: Record<string, unknown>;
};

export default function RunPage() {
  const [goal, setGoal] = useState("calculate 12 * (5 + 8)");
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState("idle");
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [snapshot, setSnapshot] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events, snapshot]);

  async function startRun(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setEvents([]);
    setSnapshot(null);
    try {
      const session = await api.createSession();
      const started = await api.startAutonomous(goal, session.session_id);
      setRunId(started.run_id);
      setStatus(started.status);
      setSnapshot(started);

      const source = new EventSource(
        `${API_URL}/agent/runs/${started.run_id}/stream`,
      );
      source.onmessage = (message) => {
        const data = JSON.parse(message.data) as RunEvent;
        if (data.type === "heartbeat") return;
        if (data.type === "snapshot") {
          setSnapshot(data.payload || null);
          return;
        }
        setEvents((prev) => [...prev, data]);
        if (data.type === "RunCompleted" || data.type === "RunFailed") {
          setStatus(data.type === "RunCompleted" ? "completed" : "failed");
          source.close();
          void api.getRun(started.run_id).then(setSnapshot);
        }
        if (data.type === "ApprovalRequired") {
          setStatus("awaiting_approval");
        }
      };
      source.onerror = () => {
        source.close();
      };
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start run");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
      <section className="panel flex min-h-[70vh] flex-col p-5">
        <div className="mb-4">
          <h1 className="font-display text-2xl text-steel-50">Autonomous Run</h1>
          <p className="mt-1 text-sm text-steel-300">
            Multi-step harness loop with live SSE events — Claude Code style control plane
          </p>
        </div>

        <form onSubmit={startRun} className="flex gap-2">
          <input
            className="input-forge"
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
            placeholder="Goal for the agent…"
            disabled={busy}
          />
          <button className="btn-forge" type="submit" disabled={busy}>
            {busy ? "Starting…" : "Run"}
          </button>
        </form>

        <div className="mt-4 flex items-center gap-3 text-sm text-steel-300">
          <span className="rounded-md border border-steel-700 px-2 py-1 font-mono text-xs">
            {status}
          </span>
          {runId && (
            <span className="font-mono text-xs text-steel-500">
              {runId.slice(0, 8)}…
            </span>
          )}
          {status === "awaiting_approval" && runId && (
            <button
              type="button"
              className="btn-ghost"
              onClick={async () => {
                await api.approveRun(runId);
                setStatus("running");
              }}
            >
              Approve
            </button>
          )}
        </div>

        <div className="mt-4 flex-1 space-y-2 overflow-y-auto rounded-lg border border-steel-800 bg-steel-950/50 p-4">
          {events.map((event, index) => (
            <div
              key={`${event.type}-${index}`}
              className="rounded-lg border border-steel-700 bg-steel-900/70 p-3"
            >
              <p className="text-sm text-ember-300">{event.type}</p>
              <pre className="mt-2 whitespace-pre-wrap font-mono text-[11px] text-steel-300">
                {JSON.stringify(event.payload ?? {}, null, 2)}
              </pre>
            </div>
          ))}
          {!events.length && (
            <p className="text-sm text-steel-400">
              Start a run to stream StepPlanned / ToolStarted / ToolFinished events.
            </p>
          )}
          <div ref={bottomRef} />
        </div>
        {error && <p className="mt-3 text-sm text-red-300">{error}</p>}
      </section>

      <aside className="panel p-5">
        <h2 className="font-display text-lg text-steel-50">Run snapshot</h2>
        <pre className="mt-3 max-h-[70vh] overflow-auto rounded-lg border border-steel-700 bg-steel-950/70 p-3 font-mono text-[11px] text-steel-200">
          {snapshot ? JSON.stringify(snapshot, null, 2) : "No run yet"}
        </pre>
      </aside>
    </div>
  );
}
