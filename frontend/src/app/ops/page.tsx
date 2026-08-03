"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function OpsPage() {
  const [metrics, setMetrics] = useState<Record<string, unknown> | null>(null);
  const [events, setEvents] = useState<
    Array<{ event_id: string; type: string; timestamp: string; payload: Record<string, unknown> }>
  >([]);
  const [executions, setExecutions] = useState<
    Array<{
      record_id: string;
      tool: string;
      success: boolean;
      duration: number;
      error: string | null;
      created_at: string;
    }>
  >([]);
  const [error, setError] = useState("");

  async function refresh() {
    try {
      const [m, e, x] = await Promise.all([
        api.metrics(),
        api.events(),
        api.executions(),
      ]);
      setMetrics(m);
      setEvents(e.events);
      setExecutions(x.executions);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load ops data");
    }
  }

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => {
      void refresh();
    }, 4000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl text-steel-50">Ops</h1>
          <p className="mt-1 text-sm text-steel-300">
            Metrics, event bus, and execution recorder — auto-refreshing
          </p>
        </div>
        <button type="button" className="btn-ghost" onClick={() => void refresh()}>
          Refresh
        </button>
      </div>

      {error && <p className="text-sm text-red-300">{error}</p>}

      <section className="panel p-5">
        <h2 className="font-display text-lg text-steel-50">Metrics</h2>
        <pre className="mt-3 overflow-x-auto rounded-lg border border-steel-700 bg-steel-950/60 p-3 font-mono text-xs text-steel-200">
          {metrics ? JSON.stringify(metrics, null, 2) : "Loading…"}
        </pre>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="panel p-5">
          <h2 className="font-display text-lg text-steel-50">Events</h2>
          <div className="mt-3 max-h-[28rem] space-y-2 overflow-y-auto">
            {events
              .slice()
              .reverse()
              .map((event) => (
                <div
                  key={event.event_id}
                  className="rounded-lg border border-steel-700 bg-steel-950/50 p-3"
                >
                  <p className="text-sm text-ember-300">{event.type}</p>
                  <p className="mt-1 font-mono text-[11px] text-steel-500">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </p>
                </div>
              ))}
            {!events.length && (
              <p className="text-sm text-steel-400">No events yet — run a chat or tool.</p>
            )}
          </div>
        </section>

        <section className="panel p-5">
          <h2 className="font-display text-lg text-steel-50">Executions</h2>
          <div className="mt-3 max-h-[28rem] space-y-2 overflow-y-auto">
            {executions
              .slice()
              .reverse()
              .map((item) => (
                <div
                  key={item.record_id}
                  className="rounded-lg border border-steel-700 bg-steel-950/50 p-3"
                >
                  <p className="text-sm text-steel-100">
                    {item.tool}{" "}
                    <span
                      className={
                        item.success ? "text-emerald-400" : "text-red-300"
                      }
                    >
                      {item.success ? "ok" : "fail"}
                    </span>
                  </p>
                  <p className="mt-1 font-mono text-[11px] text-steel-500">
                    {item.duration.toFixed(4)}s ·{" "}
                    {new Date(item.created_at).toLocaleTimeString()}
                  </p>
                  {item.error && (
                    <p className="mt-1 text-xs text-red-300">{item.error}</p>
                  )}
                </div>
              ))}
            {!executions.length && (
              <p className="text-sm text-steel-400">No executions recorded yet.</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
