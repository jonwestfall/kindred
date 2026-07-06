import type {
  AppSettings,
  Character,
  CharacterDraft,
  Health,
  LogRecord,
  Message,
  Thread,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(body.detail ?? "Request failed", response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<Health>("/health"),
  characters: {
    list: () => request<Character[]>("/characters"),
    create: (draft: CharacterDraft) =>
      request<Character>("/characters", { method: "POST", body: JSON.stringify(draft) }),
    update: (id: number, draft: Partial<CharacterDraft>) =>
      request<Character>(`/characters/${id}`, {
        method: "PATCH",
        body: JSON.stringify(draft),
      }),
    remove: (id: number) => request<void>(`/characters/${id}`, { method: "DELETE" }),
    duplicate: (id: number) =>
      request<Character>(`/characters/${id}/duplicate`, { method: "POST" }),
  },
  threads: {
    list: () => request<Thread[]>("/threads"),
    create: (characterId: number) =>
      request<Thread>("/threads", {
        method: "POST",
        body: JSON.stringify({ character_id: characterId, title: "Conversation" }),
      }),
    messages: (threadId: number) => request<Message[]>(`/threads/${threadId}/messages`),
    send: (threadId: number, content: string) =>
      request<Message>(`/threads/${threadId}/messages`, {
        method: "POST",
        body: JSON.stringify({ content }),
      }),
  },
  logs: (params: URLSearchParams) => request<LogRecord[]>(`/logs?${params}`),
  settings: {
    get: () => request<AppSettings>("/settings"),
    update: (section: keyof AppSettings, value: object | string) =>
      request<AppSettings>("/settings", {
        method: "PATCH",
        body: JSON.stringify({ section, value }),
      }),
  },
  usage: () => request<Record<string, unknown>>("/usage"),
  daemonRun: (characterId?: number) =>
    request<Array<Record<string, unknown>>>(
      `/daemon/run-once${characterId ? `?character_id=${characterId}` : ""}`,
      { method: "POST" },
    ),
  notificationKey: () =>
    request<{ public_key: string; web_push_configured: boolean }>(
      "/notifications/public-key",
    ),
  subscribe: (subscription: PushSubscription) =>
    request<{ status: string }>("/notifications/subscribe", {
      method: "POST",
      body: JSON.stringify(subscription),
    }),
};

export function exportUrl(
  format: "markdown" | "json",
  filters: Record<string, string> = {},
): string {
  const params = new URLSearchParams({ format, ...filters });
  return `${API_BASE}/logs/export?${params}`;
}

