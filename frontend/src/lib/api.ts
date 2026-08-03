const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed (${response.status})`);
  }

  return response.json() as Promise<T>;
}

export type ToolManifest = {
  name: string;
  description: string;
  keywords: string[];
  priority: number;
  permissions: string[];
};

export type ChatResponse = {
  task_id: string;
  success: boolean;
  output: unknown;
  error: string | null;
  execution_time?: number;
  session_id?: string;
};

export type SessionDetail = {
  session_id: string;
  created_at: string;
  summary: string | null;
  messages: Array<{
    role: string;
    content: string;
    timestamp: string;
  }>;
};

export const api = {
  health: () => request<{ status: string; version?: string }>("/health"),
  tools: () => request<{ tools: ToolManifest[] }>("/tools"),
  sessions: () => request<{ sessions: string[] }>("/sessions"),
  createSession: () =>
    request<{ session_id: string; workspace_id: string; created_at: string }>(
      "/session",
      { method: "POST", body: JSON.stringify({ metadata: { source: "ui" } }) },
    ),
  getSession: (id: string) => request<SessionDetail>(`/session/${id}`),
  chat: (message: string, sessionId?: string | null) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        session_id: sessionId || null,
      }),
    }),
  runTool: (tool: string, arguments_: Record<string, unknown>) =>
    request<{
      success: boolean;
      output: unknown;
      error: string | null;
      execution_time: number;
    }>("/tool", {
      method: "POST",
      body: JSON.stringify({ tool, arguments: arguments_ }),
    }),
  metrics: () => request<Record<string, unknown>>("/metrics"),
  events: () =>
    request<{
      events: Array<{
        event_id: string;
        type: string;
        payload: Record<string, unknown>;
        timestamp: string;
      }>;
    }>("/events?limit=30"),
};

export { API_URL };
