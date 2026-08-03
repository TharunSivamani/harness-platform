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
  return response.json() as Promise<T>;
}

export type Message = {
  message_id: string;
  role: string;
  content: string;
  metadata?: Record<string, unknown>;
  created_at: string;
};

export type Session = {
  session_id: string;
  user_id: string;
  title: string;
  model?: string;
  updated_at?: string;
  created_at?: string;
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
  createSession: (title = "New chat", userId?: string) =>
    request<Session>(
      "/sessions",
      { method: "POST", body: JSON.stringify({ title }) },
      userId,
    ),
  messages: (sessionId: string, userId?: string) =>
    request<{ messages: Message[] }>(
      `/sessions/${sessionId}/messages`,
      undefined,
      userId,
    ),
  chat: (sessionId: string, content: string, userId?: string) =>
    request<{
      content: string;
      steps: number;
      stats: Record<string, number>;
      messages: Message[];
    }>(
      `/sessions/${sessionId}/chat`,
      { method: "POST", body: JSON.stringify({ content }) },
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
  upload: async (sessionId: string, file: File, userId?: string) => {
    const body = new FormData();
    body.append("file", file);
    const response = await fetch(`${API_URL}/sessions/${sessionId}/upload`, {
      method: "POST",
      headers: userId ? { "X-Forge-User": userId } : {},
      body,
    });
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  },
  streamUrl: (sessionId: string) => `${API_URL}/sessions/${sessionId}/stream`,
  tools: () => request<{ tools: Array<{ name: string; description: string }> }>("/tools"),
};

export { API_URL };
