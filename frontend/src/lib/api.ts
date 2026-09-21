import { AuthToken, Conversation, Message } from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export const api = {
  auth: {
    register: (username: string, email: string, password: string) =>
      request<AuthToken>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ username, email, password }),
      }),

    login: (username: string, password: string) =>
      request<AuthToken>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      }),

    me: () => request("/auth/me"),
  },

  // ── Conversations ───────────────────────────────────────────────────────────

  conversations: {
    list: () => request<Conversation[]>("/chat/conversations"),

    create: (title = "New Chat") =>
      request<Conversation>("/chat/conversations", {
        method: "POST",
        body: JSON.stringify({ title }),
      }),

    delete: (id: number) =>
      request(`/chat/conversations/${id}`, { method: "DELETE" }),

    rename: (id: number, title: string) =>
      request<Conversation>(`/chat/conversations/${id}/title`, {
        method: "PATCH",
        body: JSON.stringify({ title }),
      }),

    getMessages: (id: number) =>
      request<Message[]>(`/chat/conversations/${id}/messages`),
  },

  // ── Streaming chat ──────────────────────────────────────────────────────────

  chat: {
    /**
     * Streams an AI response token by token.
     * Calls `onToken` for each token, `onDone` when finished, `onError` on failure.
     */
    stream: async (
      conversationId: number,
      content: string,
      onToken: (token: string) => void,
      onDone: (memoryCount: number) => void,
      onError: (err: string) => void
    ) => {
      const token = getToken();
      const res = await fetch(
        `${BASE_URL}/chat/conversations/${conversationId}/messages`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ content }),
        }
      );

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Stream failed" }));
        onError(err.detail || "Stream failed");
        return;
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let finalMemoryCount = 0;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.token) onToken(data.token);
            if (data.done) {
              finalMemoryCount = data.memory_count || 0;
              onDone(finalMemoryCount);
            }
            if (data.error) onError(data.error);
          } catch {
            // skip malformed lines
          }
        }
      }
    },
  },

  // ── Memory (IMDCRA) ────────────────────────────────────────────────────────
  memory: {
    listActive: () => request<import("./types").Memory[]>("/memory/"),
    listArchived: () => request<import("./types").Memory[]>("/memory/archived"),
    getStats: () => request<import("./types").MemoryStats>("/memory/stats"),
    runDecay: () =>
      request<import("./types").DecayReport>("/memory/run-decay", { method: "POST" }),
    delete: (memoryId: string) =>
      request(`/memory/${memoryId}`, { method: "DELETE" }),
  },
};
