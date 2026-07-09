import type {
  AppSettings,
  Character,
  CharacterDraft,
  CharacterImportResult,
  Health,
  LorePack,
  LogRecord,
  Message,
  NotificationDiagnostics,
  NotificationTestResult,
  SessionInfo,
  Thread,
  UserAccount,
  UserDraft,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";
const TOKEN_KEY = "kindred.sessionToken";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = authToken.get();
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
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

async function requestForm<T>(path: string, formData: FormData): Promise<T> {
  const token = authToken.get();
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: formData,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(body.detail ?? "Request failed", response.status);
  }
  return response.json() as Promise<T>;
}

export const authToken = {
  get: () => window.localStorage.getItem(TOKEN_KEY) ?? "",
  set: (token: string) => window.localStorage.setItem(TOKEN_KEY, token),
  clear: () => window.localStorage.removeItem(TOKEN_KEY),
};

export const api = {
  auth: {
    login: (username: string, password: string) =>
      request<{ token: string; session: SessionInfo }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      }),
    me: () => request<SessionInfo>("/auth/me"),
  },
  health: () => request<Health>("/health"),
  users: {
    list: () => request<UserAccount[]>("/users"),
    create: (draft: UserDraft & { password: string }) =>
      request<UserAccount>("/users", { method: "POST", body: JSON.stringify(draft) }),
    update: (id: number, draft: Partial<UserDraft>) =>
      request<UserAccount>(`/users/${id}`, {
        method: "PATCH",
        body: JSON.stringify(draft),
      }),
    remove: (id: number) => request<void>(`/users/${id}`, { method: "DELETE" }),
  },
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
    importBundle: (bundle: unknown, nameConflict: "rename" | "skip" = "rename") =>
      request<CharacterImportResult>(`/characters/import?name_conflict=${nameConflict}`, {
        method: "POST",
        body: JSON.stringify(bundle),
      }),
  },
  lore: {
    list: () => request<LorePack[]>("/lore-packs"),
    importPack: (bundle: unknown) =>
      request<LorePack>("/lore-packs/import", {
        method: "POST",
        body: JSON.stringify(bundle),
      }),
    getAssignment: (characterId: number) =>
      request<{ pack_ids: number[] }>(`/characters/${characterId}/lore-packs`),
    setAssignment: (characterId: number, packIds: number[]) =>
      request<{ pack_ids: number[] }>(`/characters/${characterId}/lore-packs`, {
        method: "PUT",
        body: JSON.stringify({ pack_ids: packIds }),
      }),
    remove: (id: number) => request<void>(`/lore-packs/${id}`, { method: "DELETE" }),
  },
  threads: {
    list: (scope: "mine" | "all" = "mine") => request<Thread[]>(`/threads?scope=${scope}`),
    create: (characterId: number, title = "Conversation") =>
      request<Thread>("/threads", {
        method: "POST",
        body: JSON.stringify({ character_id: characterId, title }),
      }),
    update: (threadId: number, title: string) =>
      request<Thread>(`/threads/${threadId}`, {
        method: "PATCH",
        body: JSON.stringify({ title }),
      }),
    remove: (threadId: number) => request<void>(`/threads/${threadId}`, { method: "DELETE" }),
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
  system: {
    restore: (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return requestForm<{ status: string; manifest: Record<string, unknown> }>(
        "/system/restore",
        formData,
      );
    },
    reset: () =>
      request<{ status: string; seeded_characters: number; confirmed: string }>("/system/reset", {
        method: "POST",
        body: JSON.stringify({ confirm: "RESET" }),
      }),
  },
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
  testNotification: (characterId: number, content?: string) =>
    request<NotificationTestResult>("/notifications/test", {
      method: "POST",
      body: JSON.stringify({ character_id: characterId, content }),
    }),
  notificationDiagnostics: (scope: "mine" | "all" = "mine") =>
    request<NotificationDiagnostics>(`/notifications/diagnostics?scope=${scope}`),
  deleteNotificationSubscription: (subscriptionId: number) =>
    request<void>(`/notifications/subscriptions/${subscriptionId}`, { method: "DELETE" }),
};

export function exportUrl(
  format: "markdown" | "json",
  filters: Record<string, string> = {},
): string {
  const token = authToken.get();
  const params = new URLSearchParams({
    format,
    ...filters,
    ...(token ? { access_token: token } : {}),
  });
  return `${API_BASE}/logs/export?${params}`;
}

function tokenParams(extra: Record<string, string> = {}): URLSearchParams {
  const token = authToken.get();
  return new URLSearchParams({
    ...extra,
    ...(token ? { access_token: token } : {}),
  });
}

export function charactersExportUrl(): string {
  return `${API_BASE}/characters/export?${tokenParams()}`;
}

export function characterExportUrl(characterId: number): string {
  return `${API_BASE}/characters/${characterId}/export?${tokenParams()}`;
}

export function lorePackExportUrl(packId: number): string {
  return `${API_BASE}/lore-packs/${packId}/export?${tokenParams()}`;
}

export function systemBackupUrl(): string {
  return `${API_BASE}/system/backup?${tokenParams()}`;
}

export function websocketUrl(): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const token = authToken.get();
  const params = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${protocol}//${window.location.host}/api/events/ws${params}`;
}
