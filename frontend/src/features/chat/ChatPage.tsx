import { FormEvent, useEffect, useRef, useState } from "react";

import { ApiError, api } from "../../api";
import type { Character, Message, Thread } from "../../types";
import { formatTime, lightMarkdown } from "../../utils";
import { Avatar } from "../../components/Avatar";
import { Icon } from "../../components/Icon";

function ConversationList({
  characters,
  threads,
  selectedId,
  onSelectThread,
  onSelectCharacter,
}: {
  characters: Character[];
  threads: Thread[];
  selectedId: number | null;
  onSelectThread: (thread: Thread) => void;
  onSelectCharacter: (character: Character) => void;
}) {
  const threadCharacterIds = new Set(threads.map((thread) => thread.character_id));
  return (
    <section className="conversation-list" aria-label="Conversations">
      <div className="pane-title">
        <div>
          <h1>Chats</h1>
          <p>Recent conversations</p>
        </div>
      </div>
      <div className="search-field compact">
        <Icon name="search" size={17} />
        <input aria-label="Search conversations" placeholder="Search conversations" />
      </div>
      <div className="conversation-rows">
        {threads.map((thread) => (
          <button
            key={thread.id}
            type="button"
            className={`conversation-row ${selectedId === thread.id ? "is-selected" : ""}`}
            onClick={() => onSelectThread(thread)}
          >
            <Avatar name={thread.character_name} src={thread.avatar_url} />
            <span className="conversation-copy">
              <span className="conversation-name">
                <strong>{thread.character_name}</strong>
                <time>{formatTime(thread.last_message_at ?? thread.updated_at)}</time>
              </span>
              <small className="conversation-owner">Owner: {thread.owner_label}</small>
              <span>{thread.last_message || "Start a conversation"}</span>
            </span>
          </button>
        ))}
        {characters
          .filter((character) => !threadCharacterIds.has(character.id))
          .map((character) => (
            <button
              key={`new-${character.id}`}
              type="button"
              className="conversation-row"
              onClick={() => onSelectCharacter(character)}
            >
              <Avatar name={character.name} src={character.avatar_url} />
              <span className="conversation-copy">
                <span className="conversation-name">
                  <strong>{character.name}</strong>
                </span>
                <span>No messages yet</span>
              </span>
            </button>
          ))}
      </div>
    </section>
  );
}

function MessageBubble({ message, character }: { message: Message; character: Character }) {
  const incoming = message.sender === "character";
  return (
    <div className={`message-line ${incoming ? "incoming" : "outgoing"}`}>
      {incoming ? <Avatar name={character.name} src={character.avatar_url} size="small" /> : null}
      <div className="message-stack">
        <div className="message-bubble">{lightMarkdown(message.content)}</div>
        <time>
          {formatTime(message.timestamp)}
          {message.initiated ? " · initiated" : ""}
        </time>
      </div>
    </div>
  );
}

export function ChatPage({
  characters,
  threads,
  selectedThread,
  messages,
  loading,
  onSelectThread,
  onCreateThread,
  onMessageSent,
}: {
  characters: Character[];
  threads: Thread[];
  selectedThread: Thread | null;
  messages: Message[];
  loading: boolean;
  onSelectThread: (thread: Thread) => void;
  onCreateThread: (character: Character) => Promise<void>;
  onMessageSent: () => Promise<void>;
}) {
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const selectedCharacter = characters.find(
    (character) => character.id === selectedThread?.character_id,
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!selectedThread || !draft.trim() || sending) return;
    const content = draft.trim();
    setDraft("");
    setSending(true);
    setError("");
    try {
      await api.threads.send(selectedThread.id, content);
      await onMessageSent();
    } catch (caught) {
      setDraft(content);
      setError(caught instanceof ApiError ? caught.message : "Message could not be sent.");
      await onMessageSent();
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="chat-layout">
      <ConversationList
        characters={characters}
        threads={threads}
        selectedId={selectedThread?.id ?? null}
        onSelectThread={onSelectThread}
        onSelectCharacter={(character) => void onCreateThread(character)}
      />
      <section className="chat-pane" aria-label="Selected conversation">
        {selectedThread && selectedCharacter ? (
          <>
            <header className="chat-header">
              <Avatar name={selectedCharacter.name} src={selectedCharacter.avatar_url} />
              <div>
                <strong>{selectedCharacter.name}</strong>
                <span>
                  {selectedCharacter.backend === "openai_compatible"
                    ? "Cloud backend enabled"
                    : `${selectedCharacter.backend} · ${selectedCharacter.model}`}
                </span>
              </div>
              <button className="icon-button" type="button" aria-label="Conversation information">
                <Icon name="info" />
              </button>
            </header>
            {selectedCharacter.backend === "openai_compatible" ? (
              <div className="cloud-warning">
                Cloud mode is enabled for this character. Every call is checked against your limits.
              </div>
            ) : null}
            <div className="messages" aria-live="polite">
              <div className="day-divider">
                <span>Conversation</span>
              </div>
              {loading ? <p className="empty-copy">Loading messages…</p> : null}
              {!loading && messages.length === 0 ? (
                <div className="empty-conversation">
                  <Avatar
                    name={selectedCharacter.name}
                    src={selectedCharacter.avatar_url}
                    size="large"
                  />
                  <h2>Begin with {selectedCharacter.name}</h2>
                  <p>{selectedCharacter.description || "Say hello when you are ready."}</p>
                </div>
              ) : null}
              {messages.map((message) => (
                <MessageBubble
                  key={message.id}
                  message={message}
                  character={selectedCharacter}
                />
              ))}
              <div ref={bottomRef} />
            </div>
            <form className="composer" onSubmit={submit}>
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    event.currentTarget.form?.requestSubmit();
                  }
                }}
                placeholder="Write a message…"
                aria-label="Message"
                rows={1}
              />
              <button className="primary-button send-button" disabled={sending || !draft.trim()}>
                <span>{sending ? "Thinking…" : "Send"}</span>
                <Icon name="send" size={17} />
              </button>
              {error ? <p className="form-error composer-error">{error}</p> : null}
            </form>
          </>
        ) : (
          <div className="empty-conversation empty-conversation--page">
            <Icon name="chat" size={34} />
            <h2>Choose a character</h2>
            <p>Select a conversation, or start a new one from the list.</p>
          </div>
        )}
      </section>
    </div>
  );
}
