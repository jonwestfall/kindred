export type BackendName = "ollama" | "llamacpp" | "openai_compatible";

export interface Character {
  id: number;
  name: string;
  avatar_url: string;
  description: string;
  personality: string;
  speaking_style: string;
  backstory: string;
  goals: string;
  boundaries: string;
  backend: BackendName;
  model: string;
  temperature: number;
  initiative_frequency: number;
  cooldown_minutes: number;
  created_at: string;
  updated_at: string;
}

export type CharacterDraft = Omit<Character, "id" | "created_at" | "updated_at">;

export interface CharacterImportResult {
  created: Character[];
  skipped: string[];
}

export interface LoreFact {
  id: number;
  pack_id: number;
  pack_name?: string | null;
  title: string;
  content: string;
  keywords: string[];
  tags: string[];
  source_reference: string;
  weight: number;
  created_at: string;
}

export interface LorePack {
  id: number;
  name: string;
  description: string;
  source_title: string;
  source_author: string;
  source_reference: string;
  facts: LoreFact[];
  fact_count: number;
  character_ids: number[];
  created_at: string;
  updated_at: string;
}

export interface Thread {
  id: number;
  character_id: number;
  user_id: number | null;
  character_name: string;
  avatar_url: string;
  title: string;
  owner_label: string;
  owner_username?: string | null;
  owner_display_name?: string | null;
  created_at: string;
  updated_at: string;
  last_message?: string;
  last_message_at?: string;
}

export interface Message {
  id: number;
  thread_id: number;
  character_id: number;
  sender: "user" | "character" | "system";
  content: string;
  timestamp: string;
  backend: string;
  model: string;
  prompt_context_summary: string;
  character_rationale: string;
  initiated: boolean;
}

export interface NotificationTestResult {
  status: "sent";
  web_push_configured: boolean;
  subscription_count: number;
  thread_id: number;
  message: Message;
}

export interface NotificationSubscription {
  id: number;
  user_id: number | null;
  owner_label: string;
  owner_username?: string | null;
  owner_display_name?: string | null;
  endpoint_host: string;
  endpoint_preview: string;
  created_at: string;
  has_keys: boolean;
}

export interface NotificationDelivery {
  id: number;
  timestamp: string;
  channel: string;
  status: "sent" | "failed" | "expired" | "skipped";
  detail: string;
  endpoint_host: string;
  endpoint_preview: string;
  user_id: number | null;
  owner_label: string;
  owner_username?: string | null;
  owner_display_name?: string | null;
  thread_id?: number | null;
  message_id?: number | null;
  character_id?: number | null;
}

export interface NotificationDiagnostics {
  scope: "mine" | "all";
  notifications_enabled: boolean;
  web_push_configured: boolean;
  vapid_subject: string;
  active_websocket_count: number;
  subscription_count: number;
  subscriptions: NotificationSubscription[];
  recent_deliveries: NotificationDelivery[];
}

export interface LogRecord extends Message {
  character_name: string;
  thread_title: string;
}

export interface AppSettings {
  daemon: {
    enabled: boolean;
    quiet_hours_start: string;
    quiet_hours_end: string;
    check_interval_seconds: number;
    global_messages_per_hour: number;
    global_messages_per_day: number;
  };
  limits: {
    requests_per_hour: number;
    requests_per_day: number;
    tokens_per_day: number;
    cloud_spend_ceiling_usd: number;
    image_generations_per_day: number;
  };
  notifications: { enabled: boolean };
  world_notes: string;
}

export interface Health {
  status: string;
  version: string;
  repository_url: string;
  api: { version: string; build: string };
  frontend: { version: string; build: string };
  runtime: { python: string; platform: string; build: string };
  database: string;
  database_schema_version: number;
  environment: string;
  backends: Record<string, Record<string, unknown>>;
  daemon: { process_enabled: boolean; settings: Record<string, unknown> };
}

export interface SessionInfo {
  username: string;
  role: "admin" | "user";
  user_id: number | null;
}

export interface UserAccount {
  id: number;
  username: string;
  display_name: string;
  disabled: boolean;
  character_ids: number[];
  created_at: string;
  updated_at: string;
}

export interface UserDraft {
  username: string;
  display_name: string;
  password?: string;
  disabled: boolean;
  character_ids: number[];
}
