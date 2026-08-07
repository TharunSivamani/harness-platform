const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

async function request<T>(
  path: string,
  init?: RequestInit,
  userId?: string,
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(userId ? { "X-Forge-User": userId } : {}),
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error((await response.text()) || `HTTP ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export type MessageAttachment = {
  name: string;
  kind?: string;
  mime?: string;
  bytes?: number;
  path?: string;
  previewUrl?: string;
  missing?: boolean;
  deleted_at?: string;
};

export type Message = {
  message_id: string;
  role: string;
  content: string;
  metadata?: {
    thinking?: string;
    attachments?: MessageAttachment[];
    model?: string;
    provider?: string;
    profile?: string;
    [key: string]: unknown;
  };
  created_at: string;
};

export type Session = {
  session_id: string;
  user_id: string;
  title: string;
  model?: string;
  project_root?: string | null;
  updated_at?: string;
  created_at?: string;
};

export type ProjectTreeEntry = {
  name: string;
  path: string;
  type: "file" | "dir" | string;
  size?: number;
};

export type UserArtifact = {
  session_id: string;
  session_title: string;
  kind: "upload" | "artifact" | "workspace" | string;
  name: string;
  size: number;
  modified_at: string;
  url: string;
  retained?: boolean;
};

export const api = {
  me: (userId?: string) =>
    request<{ user_id: string; name: string; role: string; stats: Record<string, number> }>(
      "/users/me",
      undefined,
      userId,
    ),
  sessions: (userId?: string) =>
    request<{ sessions: Session[] }>("/sessions", undefined, userId),
  createSession: (title = "New chat", userId?: string, projectRoot?: string) =>
    request<Session>(
      "/sessions",
      {
        method: "POST",
        body: JSON.stringify({
          title,
          ...(projectRoot ? { project_root: projectRoot } : {}),
        }),
      },
      userId,
    ),
  deleteSession: (sessionId: string, userId?: string, keepArtifacts = true) =>
    request<{ deleted: boolean; session_id: string; keep_artifacts?: boolean }>(
      `/sessions/${sessionId}?keep_artifacts=${keepArtifacts ? "true" : "false"}`,
      { method: "DELETE" },
      userId,
    ),
  deleteAllSessions: (userId?: string, keepArtifacts = true) =>
    request<{
      deleted: number;
      keep_artifacts: boolean;
      artifacts_retained: number;
    }>(
      `/sessions?keep_artifacts=${keepArtifacts ? "true" : "false"}`,
      { method: "DELETE" },
      userId,
    ),
  setProject: (sessionId: string, path: string, userId?: string) =>
    request<Session>(
      `/sessions/${sessionId}/project`,
      { method: "PUT", body: JSON.stringify({ path }) },
      userId,
    ),
  projectTree: (sessionId: string, path = ".", depth = 2, userId?: string) =>
    request<{
      session_id: string;
      project_root: string;
      path: string;
      entries: ProjectTreeEntry[];
    }>(
      `/sessions/${sessionId}/project/tree?path=${encodeURIComponent(path)}&depth=${depth}`,
      undefined,
      userId,
    ),
  projectFile: (sessionId: string, path: string, userId?: string) =>
    request<{ path: string; content: string; size: number }>(
      `/sessions/${sessionId}/project/file?path=${encodeURIComponent(path)}`,
      undefined,
      userId,
    ),
  sandboxStatus: (userId?: string) =>
    request<{
      configured: string;
      effective: string;
      docker_available: boolean;
    }>("/sandbox/status", undefined, userId),
  browseFolder: (userId?: string) =>
    request<{ cancelled: boolean; path: string | null }>(
      "/system/browse-folder",
      { method: "POST" },
      userId,
    ),
  messages: (sessionId: string, userId?: string) =>
    request<{ messages: Message[] }>(
      `/sessions/${sessionId}/messages`,
      undefined,
      userId,
    ),
  chat: (
    sessionId: string,
    content: string,
    userId?: string,
    attachments: string[] = [],
    signal?: AbortSignal,
  ) =>
    request<{
      content: string;
      steps: number;
      cancelled?: boolean;
      stats: Record<string, number>;
      messages: Message[];
    }>(
      `/sessions/${sessionId}/chat`,
      {
        method: "POST",
        body: JSON.stringify({ content, attachments }),
        signal,
      },
      userId,
    ),
  cancelChat: (sessionId: string, userId?: string) =>
    request<{ cancelled: boolean; session_id: string }>(
      `/sessions/${sessionId}/chat/cancel`,
      { method: "POST" },
      userId,
    ),
  stats: (userId?: string) =>
    request<Record<string, number>>("/stats/me", undefined, userId),
  sessionStats: (sessionId: string, userId?: string) =>
    request<Record<string, number>>(
      `/sessions/${sessionId}/stats`,
      undefined,
      userId,
    ),
  files: (sessionId: string, userId?: string) =>
    request<{
      uploads: Array<{ name: string; size: number }>;
      artifacts: Array<{ name: string; size: number }>;
      workspace: Array<{ name: string; size: number }>;
    }>(`/sessions/${sessionId}/files`, undefined, userId),
  artifacts: (userId?: string) =>
    request<{ artifacts: UserArtifact[] }>("/artifacts", undefined, userId),
  deleteFile: (
    sessionId: string,
    kind: "upload" | "artifact" | "workspace",
    filename: string,
    userId?: string,
    retained = false,
  ) =>
    retained
      ? request<{
          session_id: string;
          kind: string;
          name: string;
          retained?: boolean;
        }>(
          `/retained-artifacts/${sessionId}/${encodeURIComponent(filename)}`,
          { method: "DELETE" },
          userId,
        )
      : request<{
          session_id: string;
          kind: string;
          name: string;
          messages_updated: number;
        }>(
          `/sessions/${sessionId}/files/${kind}/${encodeURIComponent(filename)}`,
          { method: "DELETE" },
          userId,
        ),
  upload: async (
    sessionId: string,
    file: File,
    userId?: string,
    options?: { attach?: boolean },
  ) => {
    const body = new FormData();
    body.append("file", file);
    const query = options?.attach ? "?attach=true" : "";
    const response = await fetch(`${API_URL}/sessions/${sessionId}/upload${query}`, {
      method: "POST",
      headers: userId ? { "X-Forge-User": userId } : {},
      body,
    });
    if (!response.ok) throw new Error(await response.text());
    return response.json() as Promise<{
      filename: string;
      bytes: number;
      attach?: boolean;
    }>;
  },
  fileUrl: (sessionId: string, kind: "upload" | "artifact" | "workspace", filename: string) =>
    `${API_URL}/sessions/${sessionId}/files/${kind}/${encodeURIComponent(filename)}`,
  streamUrl: (sessionId: string) => `${API_URL}/sessions/${sessionId}/stream`,
  tools: () =>
    request<{ tools: Array<{ name: string; description: string; permissions?: string[] }> }>(
      "/tools",
    ),
  metrics: () => request<Record<string, unknown>>("/metrics"),
  llmProviders: () =>
    request<{ providers: string[]; defaults: Record<string, string | null> }>("/llm/providers"),
  llmProfiles: () =>
    request<{
      active: string | null;
      resolved: {
        profile: string | null;
        provider: string;
        model: string;
        base_url: string | null;
      };
      profiles: LLMProfile[];
    }>("/llm/profiles"),
  saveLlmProfile: (body: {
    name: string;
    provider: string;
    base_url?: string | null;
    api_key?: string | null;
    model?: string | null;
    activate?: boolean;
  }) =>
    request<LLMProfile>("/llm/profiles", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  activateLlmProfile: (name: string) =>
    request<{
      active: string;
      resolved: {
        profile: string | null;
        provider: string;
        model: string;
        base_url: string | null;
      };
    }>(`/llm/profiles/${encodeURIComponent(name)}/activate`, { method: "POST" }),
  deleteLlmProfile: (name: string) =>
    request<{ deleted: boolean; name: string; active: string | null }>(
      `/llm/profiles/${encodeURIComponent(name)}`,
      { method: "DELETE" },
    ),
  llmModels: (body: {
    provider: string;
    base_url?: string | null;
    api_key?: string | null;
    profile?: string | null;
  }) =>
    request<{
      provider: string;
      base_url: string | null;
      models: string[];
      count?: number;
      error?: string | null;
    }>("/llm/models", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

export type LLMProfile = {
  name: string;
  provider: string;
  base_url?: string | null;
  model?: string | null;
  api_key?: string | null;
  has_api_key?: boolean;
  created_at?: string;
  updated_at?: string;
};

/** @deprecated alias used by Tools page — prefer inline tool list type */
export type ToolManifest = {
  name: string;
  description: string;
  permissions?: string[];
};

export { API_URL };
