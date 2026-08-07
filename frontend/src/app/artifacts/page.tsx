"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { UserArtifact, API_URL, api } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import { ConfirmDialog } from "@/components/ConfirmDialog";

const IMAGE_EXT = /\.(png|jpe?g|gif|webp|bmp|tiff?)$/i;

function artifactHref(item: UserArtifact): string {
  if (item.retained || item.url.startsWith("/retained-artifacts/")) {
    return `${API_URL}${item.url}`;
  }
  return api.fileUrl(
    item.session_id,
    item.kind as "upload" | "artifact" | "workspace",
    item.name,
  );
}

export default function ArtifactsPage() {
  const [userId, setUserId] = useState("local");
  const [artifacts, setArtifacts] = useState<UserArtifact[]>([]);
  const [filter, setFilter] = useState<"all" | "upload" | "artifact" | "workspace">("all");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<UserArtifact | null>(null);

  async function refresh(uid = userId) {
    try {
      const data = await api.artifacts(uid);
      setArtifacts(data.artifacts);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load artifacts");
    }
  }

  useEffect(() => {
    void refresh(userId);
  }, [userId]);

  const visible = useMemo(
    () => (filter === "all" ? artifacts : artifacts.filter((item) => item.kind === filter)),
    [artifacts, filter],
  );

  async function confirmDelete() {
    if (!pendingDelete) return;
    const item = pendingDelete;
    const key = `${item.session_id}:${item.kind}:${item.name}`;
    setBusyId(key);
    try {
      await api.deleteFile(
        item.session_id,
        item.kind as "upload" | "artifact" | "workspace",
        item.name,
        userId,
        Boolean(item.retained),
      );
      setPendingDelete(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#0b0f14] text-slate-100">
      <aside className="flex w-72 shrink-0 flex-col border-r border-white/10 bg-[#0f141b]">
        <div className="border-b border-white/10 p-4">
          <p className="font-display text-2xl text-orange-300">ForgeAI</p>
          <p className="mt-1 text-xs text-slate-400">All session files</p>
          <Link href="/" className="btn-forge mt-4 flex w-full">
            Back to chat
          </Link>
        </div>
        <div className="space-y-2 p-4 text-xs text-slate-400">
          <label className="mb-1 block">User id</label>
          <input
            className="input-forge"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
          />
          <p className="pt-2 text-slate-500">
            Clearing chats keeps artifacts here. Uploads and workspace files are removed with their
            chat.
          </p>
        </div>
      </aside>

      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-white/10 px-6 py-4">
          <div>
            <h1 className="font-display text-xl">Artifacts</h1>
            <p className="text-xs text-slate-400">{visible.length} files</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {(["all", "upload", "artifact", "workspace"] as const).map((kind) => (
              <button
                key={kind}
                type="button"
                className={`rounded-lg px-3 py-1.5 text-xs ${filter === kind ? "bg-orange-500/20 text-orange-200" : "bg-white/5 text-slate-400"
                  }`}
                onClick={() => setFilter(kind)}
              >
                {kind}
              </button>
            ))}
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
          <div className="mx-auto grid max-w-5xl gap-3">
            {visible.map((item) => {
              const key = `${item.session_id}:${item.kind}:${item.name}:${item.retained ? "r" : "s"}`;
              const isImage =
                (item.kind === "upload" || item.kind === "artifact") && IMAGE_EXT.test(item.name);
              const href = artifactHref(item);
              return (
                <div
                  key={key}
                  className="flex flex-wrap items-center gap-4 rounded-2xl border border-white/10 bg-white/[0.03] p-4"
                >
                  {isImage ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={href}
                      alt={item.name}
                      className="h-16 w-16 rounded-lg object-cover"
                    />
                  ) : (
                    <div className="flex h-16 w-16 items-center justify-center rounded-lg bg-white/5 font-mono text-[10px] text-slate-500">
                      {item.kind}
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{item.name}</p>
                    <p className="mt-1 font-mono text-[11px] text-slate-500">
                      {item.session_title} · {formatBytes(item.size)} · {item.kind}
                      {item.retained ? " · retained" : ""}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    {!item.retained && (
                      <Link href={`/?session=${item.session_id}`} className="btn-ghost">
                        Open chat
                      </Link>
                    )}
                    <a className="btn-ghost" href={href} target="_blank" rel="noreferrer">
                      Download
                    </a>
                    <button
                      type="button"
                      className="btn-ghost text-red-200 hover:border-red-400/40"
                      disabled={busyId === key}
                      onClick={() => setPendingDelete(item)}
                    >
                      {busyId === key ? "…" : "Delete"}
                    </button>
                  </div>
                </div>
              );
            })}
            {!visible.length && (
              <p className="py-20 text-center text-sm text-slate-500">No files yet.</p>
            )}
            {error && <p className="text-sm text-red-300">{error}</p>}
          </div>
        </div>
      </main>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete this file?"
        description={
          pendingDelete
            ? `“${pendingDelete.name}” will be removed from disk.${pendingDelete.retained
              ? ""
              : " Chat text stays as memory; the model will no longer receive this file on later turns."
            }`
            : ""
        }
        confirmLabel="Delete file"
        busy={busyId !== null}
        onCancel={() => {
          if (!busyId) setPendingDelete(null);
        }}
        onConfirm={() => void confirmDelete()}
      />
    </div>
  );
}
