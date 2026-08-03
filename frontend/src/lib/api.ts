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
  artifacts: () =>
    request<{
      artifacts: Array<{
        artifact_id: string;
        name: string;
        media_type: string;
        size: number;
        version: number;
        created_at: string;
        metadata: Record<string, unknown>;
      }>;
    }>("/artifacts"),
  executions: () =>
    request<{
      executions: Array<{
        record_id: string;
        tool: string;
        success: boolean;
        duration: number;
        error: string | null;
        created_at: string;
      }>;
    }>("/executions?limit=30"),
  artifactUrl: (id: string) => `${API_URL}/artifacts/${id}`,
  startAutonomous: (goal: string, sessionId?: string | null, maxSteps?: number) =>
    request<Record<string, any>>("/agent/autonomous", {
      method: "POST",
      body: JSON.stringify({
        goal,
        session_id: sessionId || null,
        max_steps: maxSteps ?? null,
        auto_approve: true,
      }),
    }),
  getRun: (runId: string) => request<Record<string, any>>(`/agent/runs/${runId}`),
  approveRun: (runId: string) =>
    request<{ run_id: string; status: string }>(`/agent/runs/${runId}/approve`, {
      method: "POST",
      body: "{}",
    }),
  sandboxStatus: () => request<Record<string, unknown>>("/sandbox/status"),
};

export { API_URL };
