"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";

type Artifact = {
  artifact_id: string;
  name: string;
  media_type: string;
  size: number;
  version: number;
  created_at: string;
};

export default function ArtifactsPage() {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [error, setError] = useState("");
  const [name, setName] = useState("note.txt");
  const [content, setContent] = useState("hello from ForgeAI UI");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      const data = await api.artifacts();
      setArtifacts(data.artifacts);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load artifacts");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function onUpload(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"}/upload`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name,
            content,
            media_type: "text/plain",
          }),
        },
      );
      if (!response.ok) throw new Error(await response.text());
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
      <section className="panel p-5">
        <h1 className="font-display text-2xl text-steel-50">Artifacts</h1>
        <p className="mt-1 text-sm text-steel-300">
          First-class outputs stored by the runtime
        </p>

        <div className="mt-5 space-y-3">
          {artifacts.map((artifact) => (
            <div
              key={artifact.artifact_id}
              className="rounded-lg border border-steel-700 bg-steel-950/50 p-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium text-steel-50">{artifact.name}</p>
                  <p className="mt-1 font-mono text-[11px] text-steel-500">
                    v{artifact.version} · {artifact.media_type} · {artifact.size}{" "}
                    bytes
                  </p>
                </div>
                <a
                  className="btn-ghost"
                  href={api.artifactUrl(artifact.artifact_id)}
                  target="_blank"
                  rel="noreferrer"
                >
                  Download
                </a>
              </div>
            </div>
          ))}
          {!artifacts.length && (
            <p className="text-sm text-steel-400">No artifacts yet.</p>
          )}
        </div>
        {error && <p className="mt-4 text-sm text-red-300">{error}</p>}
      </section>

      <section className="panel p-5">
        <h2 className="font-display text-xl text-steel-50">Upload</h2>
        <form onSubmit={onUpload} className="mt-4 space-y-3">
          <input
            className="input-forge"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="filename.txt"
          />
          <textarea
            className="input-forge min-h-40"
            value={content}
            onChange={(event) => setContent(event.target.value)}
          />
          <button className="btn-forge" type="submit" disabled={busy}>
            {busy ? "Uploading…" : "Upload to workspace"}
          </button>
        </form>
      </section>
    </div>
  );
}
