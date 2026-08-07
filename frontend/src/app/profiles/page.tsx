"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { LLMProfile, api } from "@/lib/api";

const PROVIDER_HINTS: Record<string, string> = {
  ollama: "Local models via Ollama (default http://127.0.0.1:11434)",
  openai: "OpenAI API (https://api.openai.com/v1)",
  anthropic: "Anthropic Messages API — type the model id",
  vllm: "OpenAI-compatible vLLM server",
  openai_compatible: "Any OpenAI-compatible /v1 endpoint (OpenRouter, local gateways, …)",
  litellm: "LiteLLM proxy — set base URL to http://host:4000/v1 and fetch the model list",
};

export default function ProfilesPage() {
  const [profiles, setProfiles] = useState<LLMProfile[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [resolved, setResolved] = useState<{
    profile: string | null;
    provider: string;
    model: string;
    base_url: string | null;
  } | null>(null);
  const [providers, setProviders] = useState<string[]>(["ollama"]);
  const [defaults, setDefaults] = useState<Record<string, string | null>>({});
  const [name, setName] = useState("default");
  const [provider, setProvider] = useState("ollama");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [activate, setActivate] = useState(true);
  const [models, setModels] = useState<string[]>([]);
  const [modelFilter, setModelFilter] = useState("");
  const [customModel, setCustomModel] = useState(false);
  const [busy, setBusy] = useState(false);
  const [fetchingModels, setFetchingModels] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function refresh() {
    const [list, meta] = await Promise.all([api.llmProfiles(), api.llmProviders()]);
    setProfiles(list.profiles);
    setActive(list.active);
    setResolved(list.resolved);
    setProviders(meta.providers);
    setDefaults(meta.defaults);
    if (!baseUrl && meta.defaults[provider]) {
      setBaseUrl(meta.defaults[provider] || "");
    }
  }

  useEffect(() => {
    void refresh().catch((err) =>
      setError(err instanceof Error ? err.message : "Failed to load profiles"),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const fallback = defaults[provider];
    if (fallback && (!baseUrl || Object.values(defaults).includes(baseUrl))) {
      setBaseUrl(fallback);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [provider, defaults]);

  const filteredModels = useMemo(() => {
    const query = modelFilter.trim().toLowerCase();
    const sorted = models.slice().sort((a, b) => a.localeCompare(b));
    if (!query) return sorted;
    return sorted.filter((item) => item.toLowerCase().includes(query));
  }, [models, modelFilter]);

  function loadIntoForm(profile: LLMProfile) {
    setName(profile.name);
    setProvider(profile.provider);
    setBaseUrl(profile.base_url || defaults[profile.provider] || "");
    setModel(profile.model || "");
    setApiKey("");
    setActivate(profile.name === active);
    setCustomModel(false);
    setModelFilter("");
    setModels([]);
    setNotice(`Editing “${profile.name}”. Leave API key blank to keep the existing secret.`);
    setError("");
    void fetchModelsForForm({
      profileName: profile.name,
      providerName: profile.provider,
      url: profile.base_url || "",
      currentModel: profile.model || "",
      key: "",
    });
  }

  async function fetchModelsForForm(opts: {
    profileName: string | null;
    providerName: string;
    url: string;
    currentModel?: string;
    key?: string | null;
  }) {
    setFetchingModels(true);
    setError("");
    try {
      const data = await api.llmModels({
        provider: opts.providerName,
        base_url: opts.url || null,
        api_key: (opts.key !== undefined ? opts.key : apiKey) || null,
        profile: opts.profileName || null,
      });
      setModels(data.models);
      const selected = opts.currentModel ?? model;
      if (data.error) {
        setNotice(data.error);
        setCustomModel(true);
      } else if (!data.models.length) {
        setNotice("No models returned — check base URL / API key, or type a model id.");
        setCustomModel(true);
      } else {
        setNotice(`Loaded ${data.models.length} models from the proxy.`);
        if (selected && !data.models.includes(selected)) {
          setCustomModel(true);
          setModel(selected);
        } else {
          setCustomModel(false);
          setModel(selected || data.models[0]);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Model fetch failed");
      setCustomModel(true);
    } finally {
      setFetchingModels(false);
    }
  }

  async function onFetchModels() {
    const known = profiles.some((item) => item.name === name.trim());
    await fetchModelsForForm({
      profileName: known ? name.trim() : null,
      providerName: provider,
      url: baseUrl,
      currentModel: model,
      key: apiKey,
    });
  }

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.saveLlmProfile({
        name: name.trim(),
        provider,
        base_url: baseUrl.trim() || null,
        api_key: apiKey.trim() || null,
        model: model.trim() || null,
        activate,
      });
      setApiKey("");
      setNotice(`Saved profile “${name.trim()}”${activate ? " and set it active" : ""}.`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function onActivate(profileName: string) {
    setBusy(true);
    setError("");
    try {
      await api.activateLlmProfile(profileName);
      setNotice(`Active profile: ${profileName}`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Activate failed");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(profileName: string) {
    if (!window.confirm(`Delete LLM profile “${profileName}”?`)) return;
    setBusy(true);
    setError("");
    try {
      await api.deleteLlmProfile(profileName);
      setNotice(`Deleted “${profileName}”`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#0b0f14] text-slate-100">
      <aside className="flex w-72 shrink-0 flex-col border-r border-white/10 bg-[#0f141b]">
        <div className="border-b border-white/10 p-4">
          <p className="font-display text-2xl text-orange-300">ForgeAI</p>
          <p className="mt-1 text-xs text-slate-400">LLM profiles (same as CLI setup)</p>
          <Link href="/" className="btn-forge mt-4 flex w-full">
            Back to chat
          </Link>
          <Link href="/artifacts" className="btn-ghost mt-2 flex w-full">
            Artifacts
          </Link>
        </div>
        <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
          {profiles.map((profile) => {
            const isActive = profile.name === active;
            return (
              <div
                key={profile.name}
                className={`rounded-lg border px-3 py-3 ${isActive
                    ? "border-orange-400/40 bg-orange-500/10"
                    : "border-white/10 bg-black/20"
                  }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <button
                    type="button"
                    className="min-w-0 text-left"
                    onClick={() => loadIntoForm(profile)}
                  >
                    <p className="truncate font-medium text-slate-100">
                      {isActive ? "★ " : ""}
                      {profile.name}
                    </p>
                    <p className="mt-1 truncate font-mono text-[11px] text-slate-400">
                      {profile.provider} · {profile.model || "—"}
                    </p>
                  </button>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {!isActive && (
                    <button
                      type="button"
                      className="btn-ghost px-2 py-1 text-xs"
                      disabled={busy}
                      onClick={() => void onActivate(profile.name)}
                    >
                      Use
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn-ghost px-2 py-1 text-xs"
                    disabled={busy}
                    onClick={() => loadIntoForm(profile)}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="btn-ghost px-2 py-1 text-xs text-red-300"
                    disabled={busy}
                    onClick={() => void onDelete(profile.name)}
                  >
                    Delete
                  </button>
                </div>
              </div>
            );
          })}
          {!profiles.length && (
            <p className="px-1 text-sm text-slate-500">
              No profiles yet — create one on the right (CLI: <code>forge setup</code>).
            </p>
          )}
        </div>
      </aside>

      <main className="min-w-0 flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-2xl">
          <h1 className="font-display text-2xl text-slate-50">LLM profiles</h1>
          <p className="mt-1 text-sm text-slate-400">
            For LiteLLM: provider <code className="text-slate-300">litellm</code>, base URL{" "}
            <code className="text-slate-300">http://host:4000/v1</code>, then Fetch models and pick
            from the dropdown.
          </p>

          {resolved && (
            <div className="mt-4 rounded-lg border border-white/10 bg-white/5 px-4 py-3 font-mono text-xs text-slate-300">
              active {resolved.profile || "(env defaults)"} · {resolved.provider} ·{" "}
              {resolved.model}
              {resolved.base_url ? ` · ${resolved.base_url}` : ""}
            </div>
          )}

          {error && <p className="mt-4 text-sm text-red-300">{error}</p>}
          {notice && <p className="mt-4 text-sm text-emerald-300">{notice}</p>}

          <form className="panel mt-6 space-y-4 p-5" onSubmit={(e) => void onSave(e)}>
            <div>
              <label className="mb-1 block text-xs text-slate-400">Profile name</label>
              <input
                className="input-forge"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                placeholder="litellm-proxy"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs text-slate-400">Provider</label>
              <select
                className="input-forge"
                value={provider}
                onChange={(e) => {
                  setProvider(e.target.value);
                  setModels([]);
                  setModelFilter("");
                }}
              >
                {providers.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-slate-500">
                {PROVIDER_HINTS[provider] || "Choose a provider"}
              </p>
            </div>

            <div>
              <label className="mb-1 block text-xs text-slate-400">Base URL</label>
              <input
                className="input-forge font-mono text-xs"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder={defaults[provider] || "http://127.0.0.1:4000/v1"}
              />
            </div>

            <div>
              <label className="mb-1 block text-xs text-slate-400">API key</label>
              <input
                className="input-forge font-mono text-xs"
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={
                  provider === "ollama" ? "optional" : "paste key (blank keeps existing)"
                }
                autoComplete="off"
              />
            </div>

            <div>
              <div className="mb-1 flex items-center justify-between gap-2">
                <label className="block text-xs text-slate-400">Model</label>
                <button
                  type="button"
                  className="btn-ghost px-2 py-1 text-xs"
                  disabled={busy || fetchingModels}
                  onClick={() => void onFetchModels()}
                >
                  {fetchingModels ? "Fetching…" : "Fetch models"}
                </button>
              </div>

              {models.length > 0 && !customModel ? (
                <div className="space-y-2">
                  {models.length > 8 && (
                    <input
                      className="input-forge font-mono text-xs"
                      value={modelFilter}
                      onChange={(e) => setModelFilter(e.target.value)}
                      placeholder={`Filter ${models.length} models…`}
                    />
                  )}
                  <select
                    className="input-forge font-mono text-xs"
                    value={filteredModels.includes(model) ? model : ""}
                    onChange={(e) => setModel(e.target.value)}
                    size={Math.min(12, Math.max(4, filteredModels.length))}
                    required={!customModel}
                  >
                    {!filteredModels.includes(model) && (
                      <option value="" disabled>
                        Select a model…
                      </option>
                    )}
                    {filteredModels.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                  <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500">
                    <span>
                      Showing {filteredModels.length} of {models.length} model
                      {models.length === 1 ? "" : "s"} — click a row to select.
                    </span>
                    <button
                      type="button"
                      className="text-orange-300/90 hover:text-orange-200"
                      onClick={() => setCustomModel(true)}
                    >
                      Type custom model id
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <input
                    className="input-forge font-mono text-xs"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder="gpt-4o / claude-3-5-sonnet / my-litellm-alias"
                    required
                  />
                  {models.length > 0 && (
                    <button
                      type="button"
                      className="text-[11px] text-orange-300/90 hover:text-orange-200"
                      onClick={() => setCustomModel(false)}
                    >
                      Back to {models.length}-model dropdown
                    </button>
                  )}
                  {!models.length && (
                    <p className="text-[11px] text-slate-500">
                      Click <strong className="font-medium text-slate-400">Fetch models</strong> to
                      load the proxy list into a dropdown.
                    </p>
                  )}
                </div>
              )}
            </div>

            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input
                type="checkbox"
                checked={activate}
                onChange={(e) => setActivate(e.target.checked)}
              />
              Set as active profile after save
            </label>

            <div className="flex flex-wrap gap-2 pt-2">
              <button className="btn-forge" type="submit" disabled={busy}>
                {busy ? "Saving…" : "Save profile"}
              </button>
              <button
                type="button"
                className="btn-ghost"
                disabled={busy}
                onClick={() => {
                  setName("default");
                  setProvider("ollama");
                  setBaseUrl(defaults.ollama || "http://127.0.0.1:11434");
                  setApiKey("");
                  setModel("");
                  setActivate(true);
                  setModels([]);
                  setModelFilter("");
                  setCustomModel(false);
                  setNotice("");
                  setError("");
                }}
              >
                Reset form
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}
