"use client";

import { FormEvent, useEffect, useState } from "react";
import { ToolManifest, api } from "@/lib/api";

export default function ToolsPage() {
  const [tools, setTools] = useState<ToolManifest[]>([]);
  const [selected, setSelected] = useState("calculator");
  const [argsJson, setArgsJson] = useState('{\n  "expression": "5 * (12 + 8)"\n}');
  const [result, setResult] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .tools()
      .then((data) => {
        setTools(data.tools);
        if (data.tools[0]) setSelected(data.tools[0].name);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load tools"));
  }, []);

  useEffect(() => {
    if (selected === "calculator") {
      setArgsJson('{\n  "expression": "5 * (12 + 8)"\n}');
    } else if (selected === "python") {
      setArgsJson('{\n  "code": "sum([1, 2, 3, 4])"\n}');
    } else if (selected === "filesystem") {
      setArgsJson('{\n  "action": "list",\n  "path": "."\n}');
    } else if (selected === "terminal") {
      setArgsJson('{\n  "command": "echo forge-ok"\n}');
    } else if (selected === "search") {
      setArgsJson('{\n  "query": "Python asyncio",\n  "max_results": 3\n}');
    } else {
      setArgsJson("{\n}\n");
    }
  }, [selected]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setResult("");
    try {
      const args = JSON.parse(argsJson) as Record<string, unknown>;
      const response = await api.runTool(selected, args);
      setResult(JSON.stringify(response, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tool call failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
      <section className="panel p-5">
        <h1 className="font-display text-2xl text-steel-50">Tools</h1>
        <p className="mt-1 text-sm text-steel-300">
          Discover manifests and execute through the kernel.
        </p>

        <div className="mt-5 space-y-3">
          {tools.map((tool) => (
            <button
              key={tool.name}
              type="button"
              onClick={() => setSelected(tool.name)}
              className={`w-full rounded-lg border px-3 py-3 text-left transition ${
                selected === tool.name
                  ? "border-ember-500/50 bg-ember-500/10"
                  : "border-steel-700 bg-steel-950/40 hover:border-steel-500"
              }`}
            >
              <p className="font-medium text-steel-50">{tool.name}</p>
              <p className="mt-1 text-xs text-steel-300">{tool.description}</p>
              <p className="mt-2 font-mono text-[11px] text-steel-500">
                {(tool.permissions || []).join(", ") || "no permissions listed"}
              </p>
            </button>
          ))}
          {!tools.length && !error && (
            <p className="text-sm text-steel-400">Loading tools…</p>
          )}
        </div>
      </section>

      <section className="panel p-5">
        <h2 className="font-display text-xl text-steel-50">Execute `{selected}`</h2>
        <form onSubmit={onSubmit} className="mt-4 space-y-3">
          <textarea
            className="input-forge min-h-40 font-mono"
            value={argsJson}
            onChange={(event) => setArgsJson(event.target.value)}
          />
          <button className="btn-forge" type="submit" disabled={busy}>
            {busy ? "Executing…" : "Run tool"}
          </button>
        </form>

        {error && (
          <pre className="mt-4 overflow-x-auto rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-200">
            {error}
          </pre>
        )}
        {result && (
          <pre className="mt-4 overflow-x-auto rounded-lg border border-steel-700 bg-steel-950/70 p-3 font-mono text-xs text-steel-200">
            {result}
          </pre>
        )}
      </section>
    </div>
  );
}
