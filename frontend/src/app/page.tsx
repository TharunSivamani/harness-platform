"use client";

import Link from "next/link";
import { FormEvent, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Message, ProjectTreeEntry, Session, api } from "@/lib/api";
import { formatBytes, formatTokens } from "@/lib/format";
import { ChatTranscript, ThinkingBlock } from "@/components/ChatTranscript";

type PendingAttachment = {
  id: string;
  file: File;
  previewUrl: string;
};

function ChatPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedSession = searchParams.get("session");

  const [userId, setUserId] = useState("local");
  const [me, setMe] = useState<{ name: string; role: string; stats: Record<string, number> } | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [liveThinking, setLiveThinking] = useState("");
  const [liveContent, setLiveContent] = useState("");
  const [streamingStarted, setStreamingStarted] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const streamRef = useRef<EventSource | null>(null);
  const [pending, setPending] = useState<PendingAttachment[]>([]);
  const [filesOpen, setFilesOpen] = useState(true);
  const [projectPathInput, setProjectPathInput] = useState("");
  const [projectRoot, setProjectRoot] = useState<string | null>(null);
  const [projectTree, setProjectTree] = useState<ProjectTreeEntry[]>([]);
  const [previewPath, setPreviewPath] = useState<string | null>(null);
  const [previewContent, setPreviewContent] = useState<string | null>(null);
  const [sandboxLabel, setSandboxLabel] = useState("");
  const [llmLabel, setLlmLabel] = useState("");
  const [llmProfiles, setLlmProfiles] = useState<Array<{ name: string }>>([]);
  const [activeProfile, setActiveProfile] = useState<string | null>(null);
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

  async function loadProjectTree(sessionId: string, uid = userId, root?: string | null) {
    const effectiveRoot = root ?? sessions.find((s) => s.session_id === sessionId)?.project_root;
    if (!effectiveRoot && !root) {
      // Still try — server knows session project_root
    }
    try {
      const tree = await api.projectTree(sessionId, ".", 2, uid);
      setProjectRoot(tree.project_root);
      setProjectPathInput(tree.project_root);
      setProjectTree(tree.entries);
    } catch {
      setProjectTree([]);
      if (!root) {
        setProjectRoot(null);
      }
    }
  }

  async function loadSession(sessionId: string, uid = userId) {
    setActiveId(sessionId);
    setLiveThinking("");
    setLiveContent("");
    setStreamingStarted(false);
    setPreviewPath(null);
    setPreviewContent(null);
    const [msgs, fl, st, list] = await Promise.all([
      api.messages(sessionId, uid),
      api.files(sessionId, uid),
      api.sessionStats(sessionId, uid),
      api.sessions(uid),
    ]);
    setSessions(list.sessions);
    setMessages(msgs.messages);
    setFiles(fl);
    setSessionStats(st);
    const session = list.sessions.find((item) => item.session_id === sessionId);
    const root = session?.project_root || null;
    setProjectRoot(root);
    setProjectPathInput(root || "");
    if (root) {
      await loadProjectTree(sessionId, uid, root);
    } else {
      setProjectTree([]);
    }
    router.replace(`/?session=${sessionId}`, { scroll: false });
  }

  useEffect(() => {
    void (async () => {
      try {
        const profile = await api.me(userId);
        setMe(profile);
        try {
          const sandbox = await api.sandboxStatus(userId);
          setSandboxLabel(`${sandbox.effective}${sandbox.docker_available ? "" : " (no docker)"}`);
        } catch {
          setSandboxLabel("");
        }
        try {
          const llm = await api.llmProfiles();
          setLlmProfiles(llm.profiles.map((item) => ({ name: item.name })));
          setActiveProfile(llm.active);
          setLlmLabel(
            `${llm.resolved.profile || "env"} · ${llm.resolved.provider}/${llm.resolved.model}`,
          );
        } catch {
          setLlmLabel("");
          setLlmProfiles([]);
          setActiveProfile(null);
        }
        const list = await refreshSessions(userId);
        const preferred =
          (requestedSession && list.find((item) => item.session_id === requestedSession)?.session_id) ||
          list[0]?.session_id;
        if (preferred) await loadSession(preferred, userId);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to boot UI");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, liveThinking, liveContent, streamingStarted]);

  useEffect(() => {
    return () => {
      pending.forEach((item) => URL.revokeObjectURL(item.previewUrl));
    };
  }, [pending]);

  async function onNewChat() {
    const created = await api.createSession(
      "New chat",
      userId,
      projectPathInput.trim() || undefined,
    );
    await refreshSessions();
    await loadSession(created.session_id);
    setPending([]);
  }

  async function onOpenProject() {
    const path = projectPathInput.trim();
    if (!path) {
      setError("Enter a folder path on this machine");
      return;
    }
    setError("");
    try {
      let sessionId = activeId;
      if (!sessionId) {
        const created = await api.createSession(
          path.split(/[/\\]/).filter(Boolean).pop() || "Project",
          userId,
          path,
        );
        sessionId = created.session_id;
      } else {
        await api.setProject(sessionId, path, userId);
      }
      await refreshSessions();
      await loadSession(sessionId);
      setFilesOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open project");
    }
  }

  async function onPreviewFile(path: string) {
    if (!activeId) return;
    try {
      const file = await api.projectFile(activeId, path, userId);
      setPreviewPath(file.path);
      setPreviewContent(file.content);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cannot preview file");
    }
  }

  async function onDeleteChat(sessionId: string) {
    if (!window.confirm("Delete this chat and its files?")) return;
    await api.deleteSession(sessionId, userId);
    const list = await refreshSessions();
    if (activeId === sessionId) {
      if (list[0]) {
        await loadSession(list[0].session_id);
      } else {
        setActiveId(null);
        setMessages([]);
        setFiles(null);
        setSessionStats(null);
        router.replace("/", { scroll: false });
      }
    }
  }

  function addAttachments(fileList: FileList | null) {
    if (!fileList?.length) return;
    const next: PendingAttachment[] = [];
    Array.from(fileList).forEach((file) => {
      next.push({
        id: `${file.name}-${file.size}-${Date.now()}-${Math.random()}`,
        file,
        previewUrl: URL.createObjectURL(file),
      });
    });
    setPending((prev) => [...prev, ...next]);
  }

  function removePending(id: string) {
    setPending((prev) => {
      const target = prev.find((item) => item.id === id);
      if (target) URL.revokeObjectURL(target.previewUrl);
      return prev.filter((item) => item.id !== id);
    });
  }

  async function onStop() {
    const sessionId = activeId;
    if (sessionId) {
      try {
        await api.cancelChat(sessionId, userId);
      } catch {
        // best-effort; UI still unlocks
      }
    }
    abortRef.current?.abort();
    streamRef.current?.close();
    if (sessionId) {
      try {
        const msgs = await api.messages(sessionId, userId);
        setMessages(msgs.messages);
      } catch {
        // ignore
      }
    }
    setBusy(false);
    setLiveThinking("");
    setLiveContent("");
    setStreamingStarted(false);
  }

  async function onSend(event: FormEvent) {
    event.preventDefault();
    const text = input.trim();
    if ((!text && !pending.length) || busy) return;

    let sessionId = activeId;
    if (!sessionId) {
      const created = await api.createSession(
        text.slice(0, 48) || pending[0]?.file.name || "New chat",
        userId,
      );
      sessionId = created.session_id;
      await refreshSessions();
      setActiveId(sessionId);
      router.replace(`/?session=${sessionId}`, { scroll: false });
    }

    const controller = new AbortController();
    abortRef.current?.abort();
    abortRef.current = controller;
    streamRef.current?.close();

    setBusy(true);
    setError("");
    setInput("");
    setLiveThinking("");
    setLiveContent("");
    setStreamingStarted(false);

    const localAttachments = pending.map((item) => ({
      name: item.file.name,
      kind: item.file.type.startsWith("image/") ? "image" : "file",
      previewUrl: item.previewUrl,
    }));

    setMessages((prev) => [
      ...prev,
      {
        message_id: `local-${Date.now()}`,
        role: "user",
        content: text || "(attachment)",
        created_at: new Date().toISOString(),
        metadata: {
          attachments: localAttachments.map((item) => ({
            name: item.name,
            kind: item.kind,
            previewUrl: item.previewUrl,
          })),
        },
      },
    ]);

    const source = new EventSource(api.streamUrl(sessionId));
    streamRef.current = source;
    const ready = new Promise<void>((resolve) => {
      const onReady = (message: MessageEvent) => {
        const data = JSON.parse(message.data) as { type: string };
        if (data.type === "subscribed") {
          source.removeEventListener("message", onReady);
          resolve();
        }
      };
      source.addEventListener("message", onReady);
    });

    source.onmessage = (message) => {
      const data = JSON.parse(message.data) as {
        type: string;
        payload?: Record<string, unknown>;
      };
      if (data.type === "heartbeat" || data.type === "subscribed") return;
      if (data.type === "ModelThinking") setStreamingStarted(true);
      if (data.type === "ThinkingDelta" && typeof data.payload?.delta === "string") {
        setStreamingStarted(true);
        setLiveThinking((prev) => prev + String(data.payload!.delta));
      }
      if (data.type === "ContentDelta" && typeof data.payload?.delta === "string") {
        setStreamingStarted(true);
        setLiveContent((prev) => prev + String(data.payload!.delta));
      }
      if (data.type === "AssistantThinking" && typeof data.payload?.thinking === "string") {
        setLiveThinking(String(data.payload.thinking));
      }
      if (data.type === "AssistantMessage" && typeof data.payload?.content === "string") {
        setLiveContent(String(data.payload.content));
        if (typeof data.payload.thinking === "string") {
          setLiveThinking(String(data.payload.thinking));
        }
      }
      if (data.type === "ChatCompleted" || data.type === "ChatCancelled") source.close();
    };
    source.onerror = () => source.close();

    try {
      await ready;
      if (controller.signal.aborted) return;
      const uploadedNames: string[] = [];
      for (const item of pending) {
        const uploaded = await api.upload(sessionId, item.file, userId, { attach: true });
        uploadedNames.push(uploaded.filename);
      }
      setPending((prev) => {
        prev.forEach((item) => URL.revokeObjectURL(item.previewUrl));
        return [];
      });

      const result = await api.chat(sessionId, text, userId, uploadedNames, controller.signal);
      setMessages(result.messages);
      setSessionStats(result.stats);
      await refreshSessions();
      const fl = await api.files(sessionId, userId);
      setFiles(fl);
      const profile = await api.me(userId);
      setMe(profile);
    } catch (err) {
      if (controller.signal.aborted || (err instanceof DOMException && err.name === "AbortError")) {
        try {
          const msgs = await api.messages(sessionId, userId);
          setMessages(msgs.messages);
        } catch {
          // ignore
        }
      } else {
        setError(err instanceof Error ? err.message : "Chat failed");
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      setBusy(false);
      setLiveThinking("");
      setLiveContent("");
      setStreamingStarted(false);
      source.close();
      if (streamRef.current === source) streamRef.current = null;
    }
  }

  const streaming = busy && (liveThinking.length > 0 || liveContent.length > 0 || streamingStarted);

  return (
    <div className="flex h-screen overflow-hidden bg-[#0b0f14] text-slate-100">
      <aside className="flex h-full w-72 shrink-0 flex-col overflow-hidden border-r border-white/10 bg-[#0f141b]">
        <div className="shrink-0 border-b border-white/10 p-4">
          <p className="font-display text-2xl text-orange-300">ForgeAI</p>
          <p className="mt-1 text-xs text-slate-400">Portable agent workspace</p>
          <button type="button" className="btn-forge mt-4 w-full" onClick={() => void onNewChat()}>
            New chat
          </button>
          <Link href="/profiles" className="btn-ghost mt-2 flex w-full">
            LLM profiles
          </Link>
          <Link href="/artifacts" className="btn-ghost mt-2 flex w-full">
            Artifacts
          </Link>
        </div>
        <div className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2">
          {sessions.map((session) => (
            <div
              key={session.session_id}
              className={`group flex items-center gap-1 rounded-lg ${activeId === session.session_id ? "bg-orange-500/15 text-orange-200" : "text-slate-300 hover:bg-white/5"
                }`}
            >
              <button
                type="button"
                onClick={() => void loadSession(session.session_id)}
                className="min-w-0 flex-1 truncate px-3 py-2 text-left text-sm"
              >
                {session.title}
              </button>
              <button
                type="button"
                title="Delete chat"
                className="mr-1 rounded px-2 py-1 text-xs text-slate-500 opacity-0 transition group-hover:opacity-100 hover:bg-red-500/20 hover:text-red-200"
                onClick={() => void onDeleteChat(session.session_id)}
              >
                ×
              </button>
            </div>
          ))}
        </div>
        <div className="shrink-0 border-t border-white/10 p-4 text-xs text-slate-400">
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
              tokens {formatTokens(me.stats?.total_tokens)}
            </p>
          )}
        </div>
      </aside>

      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <header className="flex shrink-0 items-center justify-between gap-4 border-b border-white/10 px-6 py-4">
          <div className="min-w-0 flex-1">
            <h1 className="font-display text-xl">{activeSession?.title || "Chat"}</h1>
            <p className="mt-1 truncate font-mono text-[11px] text-slate-500">
              {projectRoot ? `project ${projectRoot}` : "no project open — tools use session scratch"}
              {sandboxLabel ? ` · sandbox ${sandboxLabel}` : ""}
              {llmLabel ? ` · llm ${llmLabel}` : ""}
            </p>
            <div className="mt-2 flex max-w-3xl gap-2">
              <input
                className="input-forge font-mono text-xs"
                value={projectPathInput}
                onChange={(e) => setProjectPathInput(e.target.value)}
                placeholder="Open folder path (e.g. C:\Users\...\my-app)"
              />
              <button type="button" className="btn-ghost shrink-0" onClick={() => void onOpenProject()}>
                Open
              </button>
              {llmProfiles.length > 0 && (
                <select
                  className="input-forge max-w-[11rem] shrink-0 font-mono text-xs"
                  value={activeProfile || ""}
                  title="Active LLM profile"
                  onChange={(e) => {
                    const name = e.target.value;
                    void (async () => {
                      try {
                        const res = await api.activateLlmProfile(name);
                        setActiveProfile(res.active);
                        setLlmLabel(
                          `${res.resolved.profile || "env"} · ${res.resolved.provider}/${res.resolved.model}`,
                        );
                      } catch (err) {
                        setError(err instanceof Error ? err.message : "Failed to switch profile");
                      }
                    })();
                  }}
                >
                  {llmProfiles.map((item) => (
                    <option key={item.name} value={item.name}>
                      {item.name}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {sessionStats && (
              <div className="rounded-lg border border-white/10 px-3 py-2 font-mono text-xs text-slate-300">
                in {formatTokens(sessionStats.prompt_tokens)} · out{" "}
                {formatTokens(sessionStats.completion_tokens)} · total{" "}
                {formatTokens(sessionStats.total_tokens)}
              </div>
            )}
            <button
              type="button"
              className="btn-ghost hidden xl:inline-flex"
              onClick={() => setFilesOpen((value) => !value)}
              title={filesOpen ? "Collapse panel" : "Expand panel"}
            >
              {filesOpen ? "⟩ Files" : "⟨ Files"}
            </button>
          </div>
        </header>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-6 py-6">
          <ChatTranscript messages={messages} sessionId={activeId} />
          {streaming && (
            <div className="max-w-3xl rounded-2xl bg-white/5 px-4 py-3 text-sm text-slate-100">
              <div className="mb-2 flex items-center justify-between gap-3">
                <p className="text-[11px] uppercase tracking-wide opacity-60">assistant</p>
                <button type="button" className="btn-stop px-3 py-1.5 text-xs" onClick={() => void onStop()}>
                  <span className="inline-block h-2.5 w-2.5 rounded-[2px] bg-red-300" />
                  Stop generating
                </button>
              </div>
              {liveThinking ? <ThinkingBlock thinking={liveThinking} live /> : null}
              {liveContent ? (
                <pre className="whitespace-pre-wrap font-mono text-[13px] leading-relaxed">
                  {liveContent}
                </pre>
              ) : (
                !liveThinking && <p className="text-xs text-slate-400">Starting model…</p>
              )}
            </div>
          )}
          {busy && !streaming && (
            <div className="flex max-w-3xl items-center justify-between gap-3 rounded-2xl bg-white/5 px-4 py-3">
              <p className="text-xs text-slate-400">Starting model…</p>
              <button type="button" className="btn-stop px-3 py-1.5 text-xs" onClick={() => void onStop()}>
                <span className="inline-block h-2.5 w-2.5 rounded-[2px] bg-red-300" />
                Stop generating
              </button>
            </div>
          )}
          {!messages.length && !busy && (
            <div className="mx-auto mt-24 max-w-xl text-center text-slate-400">
              <p className="font-display text-3xl text-slate-200">Open a project</p>
              <p className="mt-3 text-sm">
                Paste a folder path above so the agent can read, edit, and run inside that tree
                (OpenCode / Hermes style). Chat history still lives under FORGE_HOME.
              </p>
            </div>
          )}
          {previewPath && previewContent !== null && (
            <div className="max-w-3xl rounded-2xl border border-white/10 bg-black/30 px-4 py-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <p className="truncate font-mono text-[11px] text-slate-400">{previewPath}</p>
                <button
                  type="button"
                  className="text-xs text-slate-500 hover:text-slate-200"
                  onClick={() => {
                    setPreviewPath(null);
                    setPreviewContent(null);
                  }}
                >
                  Close
                </button>
              </div>
              <pre className="max-h-80 overflow-auto whitespace-pre-wrap font-mono text-[12px] text-slate-200">
                {previewContent}
              </pre>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <form onSubmit={onSend} className="shrink-0 border-t border-white/10 px-6 py-4">
          {pending.length > 0 && (
            <div className="mx-auto mb-3 flex max-w-3xl flex-wrap gap-2">
              {pending.map((item) => (
                <div key={item.id} className="relative">
                  {item.file.type.startsWith("image/") ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={item.previewUrl}
                      alt={item.file.name}
                      className="h-20 w-20 rounded-lg border border-white/15 object-cover"
                    />
                  ) : (
                    <div className="flex h-20 w-28 items-center justify-center rounded-lg border border-white/15 bg-white/5 px-2 text-center font-mono text-[10px]">
                      {item.file.name}
                    </div>
                  )}
                  <button
                    type="button"
                    className="absolute -right-1 -top-1 rounded-full bg-black/80 px-1.5 text-[10px] text-white"
                    onClick={() => removePending(item.id)}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="mx-auto flex max-w-3xl items-end gap-2">
            <button
              type="button"
              className="btn-ghost"
              onClick={() => fileRef.current?.click()}
              disabled={busy}
            >
              Attach
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="image/*,.png,.jpg,.jpeg,.gif,.webp,.pdf,.txt,.md"
              multiple
              className="hidden"
              onChange={(event) => {
                addAttachments(event.target.files);
                event.target.value = "";
              }}
            />
            <input
              className="input-forge"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Message ForgeAI…"
              disabled={busy}
            />
            {busy ? (
              <button className="btn-stop" type="button" onClick={() => void onStop()}>
                <span className="inline-block h-2.5 w-2.5 rounded-[2px] bg-red-300" />
                Stop
              </button>
            ) : (
              <button className="btn-forge" type="submit" disabled={!input.trim() && !pending.length}>
                Send
              </button>
            )}
          </div>
          {error && <p className="mx-auto mt-2 max-w-3xl text-sm text-red-300">{error}</p>}
        </form>
      </main>

      <aside
        className={`hidden h-full shrink-0 flex-col overflow-hidden border-l border-white/10 bg-[#0f141b] transition-[width] duration-200 xl:flex ${filesOpen ? "w-72" : "w-10"
          }`}
      >
        {filesOpen ? (
          <>
            <div className="flex shrink-0 items-center justify-between border-b border-white/10 p-4">
              <p className="text-sm font-medium">Project</p>
              <button
                type="button"
                className="rounded px-2 py-1 text-xs text-slate-400 hover:bg-white/5"
                onClick={() => setFilesOpen(false)}
              >
                ⟩
              </button>
            </div>
            <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4 text-xs text-slate-300">
              {projectRoot ? (
                <div>
                  <p className="mb-2 truncate font-mono text-[10px] text-slate-500" title={projectRoot}>
                    {projectRoot}
                  </p>
                  <div className="space-y-0.5">
                    {projectTree.map((entry) => (
                      <button
                        key={entry.path}
                        type="button"
                        className={`flex w-full items-center gap-2 rounded px-1.5 py-1 text-left font-mono hover:bg-white/5 ${entry.type === "dir" ? "text-slate-400" : "text-slate-200"
                          }`}
                        onClick={() => {
                          if (entry.type === "file") void onPreviewFile(entry.path);
                        }}
                        title={entry.path}
                      >
                        <span className="w-3 shrink-0 text-slate-600">
                          {entry.type === "dir" ? "▸" : "·"}
                        </span>
                        <span className="truncate">
                          {"  ".repeat(Math.max(0, entry.path.split(/[/\\]/).length - 1))}
                          {entry.name}
                        </span>
                      </button>
                    ))}
                    {!projectTree.length && <p className="text-slate-600">Empty or unreadable</p>}
                  </div>
                </div>
              ) : (
                <p className="text-slate-500">Open a folder path to browse the project tree.</p>
              )}
              <div>
                <p className="mb-2 uppercase tracking-wide text-slate-500">session files</p>
                {(["uploads", "workspace", "artifacts"] as const).map((kind) => (
                  <div key={kind} className="mb-3">
                    <p className="mb-1 text-[10px] uppercase tracking-wide text-slate-600">{kind}</p>
                    <div className="space-y-1">
                      {(files?.[kind] || []).map((item) => (
                        <p key={`${kind}-${item.name}`} className="truncate font-mono">
                          {item.name} ({formatBytes(item.size)})
                        </p>
                      ))}
                      {!files?.[kind]?.length && <p className="text-slate-700">Empty</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        ) : (
          <button
            type="button"
            className="flex h-full w-full items-start justify-center pt-4 text-xs text-slate-400 hover:bg-white/5"
            onClick={() => setFilesOpen(true)}
            title="Expand project panel"
          >
            ⟨
          </button>
        )}
      </aside>
    </div>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={<div className="flex h-screen items-center justify-center text-slate-400">Loading…</div>}>
      <ChatPageInner />
    </Suspense>
  );
}
