"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Message, Session, api } from "@/lib/api";

function pretty(content: string) {
  try {
    const parsed = JSON.parse(content);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return content;
  }
}

export default function HomePage() {
  const [userId, setUserId] = useState("local");
  const [me, setMe] = useState<{ name: string; role: string; stats: Record<string, number> } | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [events, setEvents] = useState<string[]>([]);
  const [files, setFiles] = useState<{
    uploads: Array<{ name: string; size: number }>;
    artifacts: Array<{ name: string; size: number }>;
    workspace: Array<{ name: string; size: number }>;
  } | null>(null);
  const [sessionStats, setSessionStats] = useState<Record<string, number> | null>(null);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);

  const activeSession = useMemo(
    () => sessions.find((item) => item.session_id === activeId) || null,
    [sessions, activeId],
  );

  async function refreshSessions(uid = userId) {
    const data = await api.sessions(uid);
    setSessions(data.sessions);
    return data.sessions;
  }

  async function loadSession(sessionId: string, uid = userId) {
    setActiveId(sessionId);
    const [msgs, fl, st] = await Promise.all([
      api.messages(sessionId, uid),
      api.files(sessionId, uid),
      api.sessionStats(sessionId, uid),
    ]);
    setMessages(msgs.messages);
    setFiles(fl);
    setSessionStats(st);
  }

  useEffect(() => {
    void (async () => {
      try {
        const profile = await api.me(userId);
        setMe(profile);
        const list = await refreshSessions(userId);
        if (list[0]) await loadSession(list[0].session_id, userId);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to boot UI");
      }
    })();
  }, [userId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, events]);

  async function onNewChat() {
    const created = await api.createSession("New chat", userId);
    await refreshSessions();
    await loadSession(created.session_id);
    setEvents([]);
  }

  async function onSend(event: FormEvent) {
    event.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    let sessionId = activeId;
    if (!sessionId) {
      const created = await api.createSession(text.slice(0, 48), userId);
      sessionId = created.session_id;
      await refreshSessions();
      setActiveId(sessionId);
    }

    setBusy(true);
    setError("");
    setInput("");
    setEvents([]);
    setMessages((prev) => [
      ...prev,
      {
        message_id: `local-${Date.now()}`,
        role: "user",
        content: text,
        created_at: new Date().toISOString(),
      },
    ]);

    const source = new EventSource(api.streamUrl(sessionId));
    source.onmessage = (message) => {
      const data = JSON.parse(message.data) as { type: string; payload?: Record<string, unknown> };
      if (data.type === "heartbeat" || data.type === "subscribed") return;
      setEvents((prev) => [...prev, data.type]);
      if (data.type === "ChatCompleted") source.close();
    };
    source.onerror = () => source.close();

    try {
      const result = await api.chat(sessionId, text, userId);
      setMessages(result.messages);
      setSessionStats(result.stats);
      await refreshSessions();
      const fl = await api.files(sessionId, userId);
      setFiles(fl);
      const profile = await api.me(userId);
      setMe(profile);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat failed");
    } finally {
      setBusy(false);
      source.close();
    }
  }

  return (
    <div className="flex min-h-screen bg-[#0b0f14] text-slate-100">
      <aside className="flex w-72 flex-col border-r border-white/10 bg-[#0f141b]">
        <div className="border-b border-white/10 p-4">
          <p className="font-display text-2xl text-orange-300">ForgeAI</p>
          <p className="mt-1 text-xs text-slate-400">Portable agent workspace</p>
          <button type="button" className="btn-forge mt-4 w-full" onClick={() => void onNewChat()}>
            New chat
          </button>
        </div>
        <div className="flex-1 space-y-1 overflow-y-auto p-2">
          {sessions.map((session) => (
            <button
              key={session.session_id}
              type="button"
              onClick={() => void loadSession(session.session_id)}
              className={`w-full rounded-lg px-3 py-2 text-left text-sm ${
                activeId === session.session_id
                  ? "bg-orange-500/15 text-orange-200"
                  : "text-slate-300 hover:bg-white/5"
              }`}
            >
              {session.title}
            </button>
          ))}
        </div>
        <div className="border-t border-white/10 p-4 text-xs text-slate-400">
          <label className="mb-1 block">User id</label>
          <input
            className="input-forge"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
          />
          {me && (
            <p className="mt-2">
              {me.name} · {me.role}
              <br />
              tokens {me.stats?.total_tokens ?? 0}
            </p>
          )}
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-white/10 px-6 py-4">
          <div>
            <h1 className="font-display text-xl">{activeSession?.title || "Chat"}</h1>
            <p className="text-xs text-slate-400">
              LLM decides tools inline · events: {events.slice(-4).join(" → ") || "idle"}
            </p>
          </div>
          {sessionStats && (
            <div className="rounded-lg border border-white/10 px-3 py-2 font-mono text-xs text-slate-300">
              in {sessionStats.prompt_tokens} · out {sessionStats.completion_tokens} · total{" "}
              {sessionStats.total_tokens}
            </div>
          )}
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto px-6 py-6">
          {messages.map((message) => (
            <div
              key={message.message_id}
              className={`max-w-3xl rounded-2xl px-4 py-3 text-sm ${
                message.role === "user"
                  ? "ml-auto bg-orange-500/20 text-orange-50"
                  : message.role === "tool"
                    ? "border border-cyan-500/20 bg-cyan-500/10 text-cyan-100"
                    : "bg-white/5 text-slate-100"
              }`}
            >
              <p className="mb-1 text-[11px] uppercase tracking-wide opacity-60">{message.role}</p>
              <pre className="whitespace-pre-wrap font-mono text-[13px] leading-relaxed">
                {pretty(message.content)}
              </pre>
            </div>
          ))}
          {!messages.length && (
            <div className="mx-auto mt-24 max-w-xl text-center text-slate-400">
              <p className="font-display text-3xl text-slate-200">What are we building?</p>
              <p className="mt-3 text-sm">
                Chats, uploads, and tool steps persist under FORGE_HOME. Copy the data folder to resume elsewhere.
              </p>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <form onSubmit={onSend} className="border-t border-white/10 px-6 py-4">
          <div className="mx-auto flex max-w-3xl items-end gap-2">
            <button
              type="button"
              className="btn-ghost"
              onClick={() => fileRef.current?.click()}
              disabled={!activeId || busy}
            >
              Upload
            </button>
            <input
              ref={fileRef}
              type="file"
              className="hidden"
              onChange={async (event) => {
                const file = event.target.files?.[0];
                if (!file || !activeId) return;
                await api.upload(activeId, file, userId);
                setFiles(await api.files(activeId, userId));
                setMessages((await api.messages(activeId, userId)).messages);
              }}
            />
            <input
              className="input-forge"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Message ForgeAI…"
              disabled={busy}
            />
            <button className="btn-forge" type="submit" disabled={busy}>
              {busy ? "Running…" : "Send"}
            </button>
          </div>
          {error && <p className="mx-auto mt-2 max-w-3xl text-sm text-red-300">{error}</p>}
        </form>
      </main>

      <aside className="hidden w-72 flex-col border-l border-white/10 bg-[#0f141b] xl:flex">
        <div className="border-b border-white/10 p-4">
          <p className="text-sm font-medium">Session files</p>
        </div>
        <div className="flex-1 space-y-4 overflow-y-auto p-4 text-xs text-slate-300">
          {(["uploads", "workspace", "artifacts"] as const).map((kind) => (
            <div key={kind}>
              <p className="mb-2 uppercase tracking-wide text-slate-500">{kind}</p>
              <div className="space-y-1">
                {(files?.[kind] || []).map((item) => (
                  <p key={`${kind}-${item.name}`} className="truncate font-mono">
                    {item.name} ({item.size}b)
                  </p>
                ))}
                {!files?.[kind]?.length && <p className="text-slate-600">Empty</p>}
              </div>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}
