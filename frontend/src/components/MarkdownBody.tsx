"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function looksLikeJson(text: string): boolean {
  const trimmed = text.trim();
  return (
    (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
    (trimmed.startsWith("[") && trimmed.endsWith("]"))
  );
}

function formatRaw(text: string): string {
  if (!looksLikeJson(text)) return text;
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  async function onCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // ignore clipboard failures (insecure context, permissions)
    }
  }

  return (
    <button
      type="button"
      className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-black/20 px-2 py-1 text-[11px] text-slate-300 transition hover:border-white/25 hover:bg-black/35 hover:text-slate-100"
      onClick={() => void onCopy()}
      title="Copy raw output"
    >
      <svg
        viewBox="0 0 24 24"
        className="h-3.5 w-3.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        aria-hidden
      >
        <rect x="9" y="9" width="11" height="11" rx="2" />
        <path d="M5 15V5a2 2 0 0 1 2-2h10" />
      </svg>
      {copied ? "Copied" : label}
    </button>
  );
}

export function MarkdownBody({
  content,
  showCopy = true,
  className = "",
}: {
  content: string;
  showCopy?: boolean;
  className?: string;
}) {
  const raw = formatRaw(content);
  const asJson = looksLikeJson(content.trim());

  return (
    <div className={`relative ${className}`}>
      {showCopy && (
        <div className="mb-2 flex justify-end">
          <CopyButton text={raw} />
        </div>
      )}
      {asJson ? (
        <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-[13px] leading-relaxed text-slate-200">
          {raw}
        </pre>
      ) : (
        <div className="forge-md">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}
