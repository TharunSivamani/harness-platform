"use client";

import { useEffect, useMemo, useState } from "react";
import { Message, api } from "@/lib/api";
import { CopyButton, MarkdownBody } from "@/components/MarkdownBody";

function pretty(content: string) {
  try {
    const parsed = JSON.parse(content);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return content;
  }
}

function parseToolPayload(content: string): {
  success?: boolean;
  output?: unknown;
  error?: string | null;
  metadata?: Record<string, unknown>;
} | null {
  try {
    const parsed = JSON.parse(content);
    if (parsed && typeof parsed === "object") return parsed as {
      success?: boolean;
      output?: unknown;
      error?: string | null;
      metadata?: Record<string, unknown>;
    };
  } catch {
    // ignore
  }
  return null;
}

function summarizeTool(message: Message): {
  name: string;
  success: boolean;
  summary: string;
  detail: string;
} {
  const metaTool =
    typeof message.metadata?.tool === "string" ? message.metadata.tool : "tool";
  const payload = parseToolPayload(message.content);
  const success =
    typeof message.metadata?.success === "boolean"
      ? message.metadata.success
      : Boolean(payload?.success);
  const error =
    (typeof payload?.error === "string" && payload.error) ||
    (typeof message.metadata?.error === "string" ? message.metadata.error : "");
  const output =
    payload?.output !== undefined && payload?.output !== null
      ? String(payload.output)
      : "";
  const path =
    payload?.metadata && typeof payload.metadata.path === "string"
      ? payload.metadata.path
      : null;
  const command =
    payload?.metadata && typeof payload.metadata.command === "string"
      ? payload.metadata.command
      : null;

  let summary = success ? "ok" : "failed";
  if (success && path) summary = path;
  else if (success && output) summary = output.slice(0, 80);
  else if (!success && error) summary = error.slice(0, 120);
  else if (!success && command) summary = `failed: ${command}`;
  else if (!success) summary = "failed";

  return {
    name: metaTool,
    success,
    summary,
    detail: pretty(message.content),
  };
}

function ThinkingBlock({
  thinking,
  defaultOpen = false,
  live = false,
}: {
  thinking: string;
  defaultOpen?: boolean;
  live?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen || live);
  useEffect(() => {
    if (live) setOpen(true);
  }, [live]);
  return (
    <div className="mb-3 overflow-hidden rounded-xl border border-violet-400/20 bg-violet-500/5">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-xs text-violet-200/90"
      >
        <span className="inline-flex items-center gap-2 font-medium tracking-wide">
          <span
            className={`h-1.5 w-1.5 rounded-full ${live ? "animate-pulse bg-violet-300" : "bg-violet-400/70"}`}
          />
          {live ? "Thinking…" : "Thought"}
        </span>
        <span className="text-[11px] uppercase tracking-wider text-violet-300/60">
          {open ? "Hide" : "Show"}
        </span>
      </button>
      {open && (
        <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap border-t border-violet-400/10 px-3 py-2 font-mono text-[12px] leading-relaxed text-violet-100/75">
          {thinking}
        </pre>
      )}
    </div>
  );
}

function AttachmentThumbs({
  sessionId,
  attachments,
}: {
  sessionId: string | null;
  attachments?: Array<{ name: string; kind?: string; previewUrl?: string; missing?: boolean }>;
}) {
  if (!attachments?.length) return null;
  return (
    <div className="mb-2 flex flex-wrap gap-2">
      {attachments.map((item) => {
        if (item.missing) {
          return (
            <span
              key={item.name}
              className="rounded-lg border border-dashed border-white/20 px-2 py-1 font-mono text-[11px] text-slate-500"
            >
              {item.name} (deleted)
            </span>
          );
        }
        const src =
          item.previewUrl ||
          (sessionId && item.kind === "image"
            ? api.fileUrl(sessionId, "upload", item.name)
            : null);
        if (src) {
          return (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              key={item.name}
              src={src}
              alt={item.name}
              className="h-24 w-24 rounded-lg border border-white/10 object-cover"
            />
          );
        }
        return (
          <span
            key={item.name}
            className="rounded-lg border border-white/10 bg-black/20 px-2 py-1 font-mono text-[11px]"
          >
            {item.name}
          </span>
        );
      })}
    </div>
  );
}

function ToolChip({ message }: { message: Message }) {
  const [open, setOpen] = useState(false);
  const info = summarizeTool(message);
  return (
    <div
      className={`rounded-xl border px-3 py-2 ${info.success
        ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-100"
        : "border-red-400/30 bg-red-500/10 text-red-100"
        }`}
    >
      <button
        type="button"
        className="flex w-full items-start justify-between gap-3 text-left"
        onClick={() => setOpen((value) => !value)}
      >
        <div className="min-w-0">
          <p className="font-mono text-[12px] font-medium">
            {info.success ? "✓" : "✕"} {info.name}
          </p>
          <p className="mt-0.5 truncate font-mono text-[11px] opacity-80">{info.summary}</p>
        </div>
        <span className="shrink-0 text-[10px] uppercase tracking-wider opacity-50">
          {open ? "Hide" : "Details"}
        </span>
      </button>
      {open && (
        <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap border-t border-white/10 pt-2 font-mono text-[11px] leading-relaxed opacity-90">
          {info.detail}
        </pre>
      )}
    </div>
  );
}

type TranscriptItem =
  | { kind: "user" | "assistant"; message: Message }
  | { kind: "tools"; id: string; messages: Message[]; thinking?: string | null };

function buildTranscript(messages: Message[]): TranscriptItem[] {
  const items: TranscriptItem[] = [];
  let index = 0;
  while (index < messages.length) {
    const message = messages[index];
    if (message.role === "user") {
      items.push({ kind: "user", message });
      index += 1;
      continue;
    }

    if (message.role === "tool") {
      const tools: Message[] = [];
      while (index < messages.length && messages[index].role === "tool") {
        tools.push(messages[index]);
        index += 1;
      }
      items.push({ kind: "tools", id: tools[0]?.message_id || `tools-${index}`, messages: tools });
      continue;
    }

    if (message.role === "assistant") {
      const hasToolCalls = Array.isArray(message.metadata?.tool_calls)
        ? message.metadata.tool_calls.length > 0
        : false;
      const thinking =
        typeof message.metadata?.thinking === "string" ? message.metadata.thinking : null;
      const text = (message.content || "").trim();

      // Tool-call-only assistant turns: fold into the following tool results.
      if (hasToolCalls || (!text && index + 1 < messages.length && messages[index + 1].role === "tool")) {
        const tools: Message[] = [];
        let cursor = index + 1;
        while (cursor < messages.length && messages[cursor].role === "tool") {
          tools.push(messages[cursor]);
          cursor += 1;
        }
        if (tools.length) {
          items.push({
            kind: "tools",
            id: message.message_id,
            messages: tools,
            thinking: text ? null : thinking,
          });
          index = cursor;
          continue;
        }
      }

      items.push({ kind: "assistant", message });
      index += 1;
      continue;
    }

    // Unknown roles — show as assistant-like
    items.push({ kind: "assistant", message });
    index += 1;
  }
  return items;
}

export function ChatTranscript({
  messages,
  sessionId,
}: {
  messages: Message[];
  sessionId: string | null;
}) {
  const items = useMemo(() => buildTranscript(messages), [messages]);

  return (
    <>
      {items.map((item) => {
        if (item.kind === "tools") {
          const failed = item.messages.some((message) => !summarizeTool(message).success);
          return (
            <div
              key={item.id}
              className={`max-w-3xl space-y-2 rounded-2xl border px-4 py-3 ${failed
                ? "border-red-400/20 bg-red-500/5"
                : "border-cyan-500/20 bg-cyan-500/5"
                }`}
            >
              <p className="text-[11px] uppercase tracking-wide text-slate-400">
                {item.messages.length === 1 ? "Tool" : `${item.messages.length} tools`}
              </p>
              {item.thinking ? <ThinkingBlock thinking={item.thinking} /> : null}
              <div className="space-y-2">
                {item.messages.map((message) => (
                  <ToolChip key={message.message_id} message={message} />
                ))}
              </div>
            </div>
          );
        }

        const message = item.message;
        const thinking =
          typeof message.metadata?.thinking === "string" ? message.metadata.thinking : null;
        const attachments = Array.isArray(message.metadata?.attachments)
          ? message.metadata.attachments
          : undefined;
        const text = (message.content || "").trim();
        if (item.kind === "assistant" && !text && !thinking) {
          return null;
        }

        return (
          <div
            key={message.message_id}
            className={`max-w-3xl rounded-2xl px-4 py-3 text-sm ${item.kind === "user"
                ? "ml-auto bg-orange-500/20 text-orange-50"
                : "bg-white/5 text-slate-100"
              }`}
          >
            <div className="mb-1 flex items-center justify-between gap-3">
              <div className="flex min-w-0 items-center gap-2">
                <p className="text-[11px] uppercase tracking-wide opacity-60">{message.role}</p>
                {item.kind === "assistant" &&
                  typeof message.metadata?.model === "string" &&
                  message.metadata.model && (
                    <span
                      className="truncate rounded border border-white/10 bg-black/20 px-1.5 py-0.5 font-mono text-[10px] text-slate-400"
                      title={
                        [
                          message.metadata.profile,
                          message.metadata.provider,
                          message.metadata.model,
                        ]
                          .filter(Boolean)
                          .join(" · ")
                      }
                    >
                      {message.metadata.model}
                    </span>
                  )}
              </div>
              {item.kind === "assistant" && text && text !== "(attachment)" && (
                <CopyButton text={text} />
              )}
            </div>
            {item.kind === "user" && (
              <AttachmentThumbs sessionId={sessionId} attachments={attachments} />
            )}
            {item.kind === "assistant" && thinking && <ThinkingBlock thinking={thinking} />}
            {text && text !== "(attachment)" && (
              item.kind === "user" ? (
                <pre className="whitespace-pre-wrap font-mono text-[13px] leading-relaxed">
                  {text}
                </pre>
              ) : (
                <MarkdownBody content={text} showCopy={false} />
              )
            )}
          </div>
        );
      })}
    </>
  );
}

export { ThinkingBlock, AttachmentThumbs };
