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

export interface Thread {
  id: number;
  character_id: number;
  character_name: string;
  avatar_url: string;
  title: string;
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
  database: string;
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
