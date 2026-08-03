"use client";

import { useEffect, useState } from "react";
import { SessionDetail, api } from "@/lib/api";

export default function SessionsPage() {
  const [sessions, setSessions] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    setError("");
    try {
      const data = await api.sessions();
      setSessions(data.sessions);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sessions");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    if (!selected) {
      setDetail(null);
      return;
    }
    api
      .getSession(selected)
      .then(setDetail)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load session"),
      );
  }, [selected]);

  return (
    <div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
      <section className="panel p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl text-steel-50">Sessions</h1>
            <p className="mt-1 text-sm text-steel-300">
              Conversation history and summaries
            </p>
          </div>
          <button
            type="button"
            className="btn-ghost"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                const created = await api.createSession();
                await refresh();
                setSelected(created.session_id);
              } catch (err) {
                setError(
                  err instanceof Error ? err.message : "Could not create session",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            New
          </button>
        </div>

        <div className="mt-5 space-y-2">
          {sessions.map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => setSelected(id)}
              className={`w-full rounded-lg border px-3 py-2 text-left font-mono text-xs transition ${
                selected === id
                  ? "border-ember-500/50 bg-ember-500/10 text-ember-300"
                  : "border-steel-700 text-steel-300 hover:border-steel-500"
              }`}
            >
              {id}
            </button>
          ))}
          {!sessions.length && (
            <p className="text-sm text-steel-400">No sessions yet.</p>
          )}
        </div>
        {error && <p className="mt-4 text-sm text-red-300">{error}</p>}
      </section>

      <section className="panel p-5">
        <h2 className="font-display text-xl text-steel-50">Detail</h2>
        {!detail && (
          <p className="mt-3 text-sm text-steel-400">Select a session to inspect.</p>
        )}
        {detail && (
          <div className="mt-4 space-y-4">
            <div>
              <p className="text-xs uppercase tracking-wide text-steel-500">Summary</p>
              <p className="mt-1 text-sm text-steel-200">
                {detail.summary || "No summary yet"}
              </p>
            </div>
            <div className="space-y-2">
              {detail.messages.map((message, index) => (
                <div
                  key={`${message.timestamp}-${index}`}
                  className="rounded-lg border border-steel-700 bg-steel-950/50 p-3"
                >
                  <p className="text-[11px] uppercase tracking-wide text-steel-500">
                    {message.role} · {new Date(message.timestamp).toLocaleString()}
                  </p>
                  <pre className="mt-2 whitespace-pre-wrap font-mono text-xs text-steel-200">
                    {message.content}
                  </pre>
                </div>
              ))}
              {!detail.messages.length && (
                <p className="text-sm text-steel-400">No messages in this session.</p>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
