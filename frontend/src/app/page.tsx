"use client";

import { FormEvent, useEffect, useState } from "react";
import { API_URL, api } from "@/lib/api";

type Message = {
  role: "user" | "assistant" | "system";
  content: string;
};

function pretty(value: unknown): string {
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export default function ChatPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("calculate 12 * (5 + 8)");
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "system",
      content: "Connected to ForgeAI API. Create a session, then send a request.",
    },
  ]);
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState<string>("checking...");

  useEffect(() => {
    api
      .health()
      .then((data) => setHealth(`${data.status}${data.version ? ` · v${data.version}` : ""}`))
      .catch(() => setHealth("offline"));
  }, []);

  async function ensureSession() {
    if (sessionId) return sessionId;
    const created = await api.createSession();
    setSessionId(created.session_id);
    setMessages((prev) => [
      ...prev,
      {
        role: "system",
        content: `Session ${created.session_id.slice(0, 8)}… ready`,
      },
    ]);
    return created.session_id;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const text = input.trim();
    if (!text || busy) return;

    setBusy(true);
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");

    try {
      const sid = await ensureSession();
      const result = await api.chat(text, sid);
      const content = result.success
        ? pretty(result.output)
        : `Error: ${result.error || "unknown failure"}`;
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `${content}\n\n(task ${result.task_id.slice(0, 8)} · ${result.execution_time?.toFixed?.(4) ?? "?"}s)`,
        },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: error instanceof Error ? error.message : "Request failed",
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1.4fr_0.8fr]">
      <section className="panel flex min-h-[70vh] flex-col p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl text-steel-50">Chat</h1>
            <p className="text-sm text-steel-300">
              Routes through planner → kernel → tools
            </p>
          </div>
          <span className="rounded-md border border-steel-700 px-2 py-1 font-mono text-xs text-steel-300">
            API {health}
          </span>
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto rounded-lg border border-steel-800 bg-steel-950/50 p-4">
          {messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={`max-w-[90%] rounded-lg px-3 py-2 text-sm ${
                message.role === "user"
                  ? "ml-auto bg-ember-500/20 text-ember-300"
                  : message.role === "system"
                    ? "border border-steel-700 text-steel-300"
                    : "bg-steel-800 text-steel-100"
              }`}
            >
              <p className="mb-1 text-[11px] uppercase tracking-wide opacity-70">
                {message.role}
              </p>
              <pre className="whitespace-pre-wrap font-mono text-[13px] leading-relaxed">
                {message.content}
              </pre>
            </div>
          ))}
        </div>

        <form onSubmit={onSubmit} className="mt-4 flex gap-2">
          <input
            className="input-forge"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="calculate 2+2 · list files · search Python asyncio"
            disabled={busy}
          />
          <button className="btn-forge" type="submit" disabled={busy}>
            {busy ? "Running…" : "Send"}
          </button>
        </form>
      </section>

      <aside className="space-y-4">
        <div className="panel p-5">
          <h2 className="font-display text-lg text-steel-50">Session</h2>
          <p className="mt-2 break-all font-mono text-xs text-steel-300">
            {sessionId || "No session yet — created on first message"}
          </p>
          <button
            type="button"
            className="btn-ghost mt-4"
            onClick={async () => {
              try {
                await ensureSession();
              } catch (error) {
                setMessages((prev) => [
                  ...prev,
                  {
                    role: "system",
                    content:
                      error instanceof Error
                        ? error.message
                        : "Could not create session",
                  },
                ]);
              }
            }}
          >
            New session
          </button>
        </div>

        <div className="panel p-5">
          <h2 className="font-display text-lg text-steel-50">Try</h2>
          <ul className="mt-3 space-y-2 text-sm text-steel-300">
            <li>`calculate 15 / 3`</li>
            <li>`list files in .`</li>
            <li>`run python sum([1,2,3,4])`</li>
            <li>`search for FastAPI`</li>
          </ul>
          <p className="mt-4 text-xs text-steel-500">
            Backend: <span className="font-mono text-steel-300">{API_URL}</span>
          </p>
        </div>
      </aside>
    </div>
  );
}
