import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, api } from "./api";
import type { Character, CharacterDraft, Health, Message, Thread } from "./types";
import { AppNavigation, type ViewName } from "./components/AppNavigation";
import { NotificationButton } from "./components/NotificationButton";
import { ChatPage } from "./features/chat/ChatPage";
import { CharacterForm } from "./features/characters/CharacterForm";
import { CharactersPage } from "./features/characters/CharactersPage";
import { ActivityPage } from "./features/activity/ActivityPage";
import { SettingsPage } from "./features/settings/SettingsPage";
import { SystemPage } from "./features/system/SystemPage";

export default function App() {
  const [view, setView] = useState<ViewName>("chat");
  const [characters, setCharacters] = useState<Character[]>([]);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [selectedThread, setSelectedThread] = useState<Thread | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const [editing, setEditing] = useState<Character | "new" | null>(null);
  const [error, setError] = useState("");

  const refreshBase = useCallback(async () => {
    const [nextCharacters, nextThreads] = await Promise.all([
      api.characters.list(),
      api.threads.list(),
    ]);
    setCharacters(nextCharacters);
    setThreads(nextThreads);
    setSelectedThread((current) => {
      if (current) {
        return nextThreads.find((thread) => thread.id === current.id) ?? null;
      }
      const requested = Number(new URLSearchParams(window.location.search).get("thread"));
      return nextThreads.find((thread) => thread.id === requested) ?? nextThreads[0] ?? null;
    });
  }, []);

  useEffect(() => {
    Promise.all([refreshBase(), api.health().then(setHealth)]).catch((caught) => {
      setError(caught instanceof Error ? caught.message : "Kindred could not load.");
    });
  }, [refreshBase]);

  useEffect(() => {
    if (!selectedThread) {
      setMessages([]);
      return;
    }
    setMessagesLoading(true);
    api.threads
      .messages(selectedThread.id)
      .then(setMessages)
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Messages failed."))
      .finally(() => setMessagesLoading(false));
  }, [selectedThread?.id]);

  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    let socket: WebSocket | null = null;
    let retry: number | undefined;
    const connect = () => {
      socket = new WebSocket(`${protocol}//${window.location.host}/api/events/ws`);
      socket.onmessage = (event) => {
        const payload = JSON.parse(event.data) as {
          type: string;
          thread_id: number;
          character_name: string;
          content: string;
        };
        if (payload.type === "character_message") {
          void refreshBase();
          if (payload.thread_id === selectedThread?.id) {
            api.threads.messages(payload.thread_id).then(setMessages);
          }
          if (
            "Notification" in window &&
            Notification.permission === "granted" &&
            document.visibilityState !== "visible"
          ) {
            new Notification(payload.character_name, { body: payload.content });
          }
        }
      };
      socket.onclose = () => {
        retry = window.setTimeout(connect, 5000);
      };
    };
    connect();
    return () => {
      if (retry) window.clearTimeout(retry);
      socket?.close();
    };
  }, [refreshBase, selectedThread?.id]);

  const localReady = useMemo(
    () =>
      Boolean(health?.backends.ollama?.available || health?.backends.llamacpp?.available),
    [health],
  );

  async function openCharacterChat(character: Character) {
    const existing = threads.find((thread) => thread.character_id === character.id);
    const thread = existing ?? (await api.threads.create(character.id));
    if (!existing) await refreshBase();
    setSelectedThread(thread);
    setView("chat");
  }

  async function saveCharacter(draft: CharacterDraft) {
    if (editing && editing !== "new") {
      await api.characters.update(editing.id, draft);
    } else {
      await api.characters.create(draft);
    }
    setEditing(null);
    await refreshBase();
  }

  async function reloadSelected() {
    await refreshBase();
    if (selectedThread) setMessages(await api.threads.messages(selectedThread.id));
  }

  let content: React.ReactNode;
  if (view === "chat") {
    content = (
      <ChatPage
        characters={characters}
        threads={threads}
        selectedThread={selectedThread}
        messages={messages}
        loading={messagesLoading}
        onSelectThread={setSelectedThread}
        onCreateThread={openCharacterChat}
        onMessageSent={reloadSelected}
      />
    );
  } else if (view === "characters") {
    content = (
      <CharactersPage
        characters={characters}
        onCreate={() => setEditing("new")}
        onEdit={setEditing}
        onDuplicate={async (character) => {
          await api.characters.duplicate(character.id);
          await refreshBase();
        }}
        onDelete={async (character) => {
          if (!window.confirm(`Delete ${character.name} and every conversation with them?`)) return;
          await api.characters.remove(character.id);
          await refreshBase();
        }}
        onChat={openCharacterChat}
      />
    );
  } else if (view === "activity") {
    content = <ActivityPage characters={characters} />;
  } else if (view === "settings") {
    content = <SettingsPage characters={characters} />;
  } else {
    content = <SystemPage />;
  }

  return (
    <div className="app-shell">
      <AppNavigation
        active={view}
        onChange={setView}
        localReady={localReady}
        onNewCharacter={() => setEditing("new")}
      />
      <main className="main-area">
        <div className="topbar">
          <div className="topbar-title">
            {view === "chat" ? "Conversations" : view[0].toUpperCase() + view.slice(1)}
          </div>
          <NotificationButton />
          <div className="user-mark">Local</div>
        </div>
        {error ? (
          <div className="global-error" role="alert">
            <span>{error}</span>
            <button type="button" onClick={() => setError("")}>
              Dismiss
            </button>
          </div>
        ) : null}
        {content}
      </main>
      {editing ? (
        <CharacterForm
          character={editing === "new" ? undefined : editing}
          onSave={saveCharacter}
          onClose={() => setEditing(null)}
        />
      ) : null}
    </div>
  );
}

