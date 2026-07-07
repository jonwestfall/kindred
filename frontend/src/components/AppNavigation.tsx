import { Icon, type IconName } from "./Icon";

export type ViewName =
  | "chat"
  | "characters"
  | "activity"
  | "lore"
  | "admin"
  | "settings"
  | "system";

const primary: Array<{ id: ViewName; label: string; icon: IconName }> = [
  { id: "chat", label: "Chats", icon: "chat" },
  { id: "characters", label: "Characters", icon: "characters" },
  { id: "activity", label: "Activity", icon: "activity" },
  { id: "lore", label: "Lore", icon: "activity" },
];

const secondary: Array<{ id: ViewName; label: string; icon: IconName }> = [
  { id: "admin", label: "Admin", icon: "system" },
  { id: "settings", label: "Settings", icon: "settings" },
  { id: "system", label: "System", icon: "system" },
];

function NavGroup({
  items,
  active,
  onChange,
}: {
  items: typeof primary;
  active: ViewName;
  onChange: (view: ViewName) => void;
}) {
  return items.map((item) => (
    <button
      className={`nav-item ${active === item.id ? "nav-item--active" : ""}`}
      key={item.id}
      onClick={() => onChange(item.id)}
      type="button"
    >
      <Icon name={item.icon} />
      <span>{item.label}</span>
    </button>
  ));
}

export function AppNavigation({
  active,
  onChange,
  localReady,
  onNewCharacter,
  isAdmin,
}: {
  active: ViewName;
  onChange: (view: ViewName) => void;
  localReady: boolean;
  onNewCharacter: () => void;
  isAdmin: boolean;
}) {
  const visiblePrimary = isAdmin
    ? primary
    : primary.filter((item) => !["characters", "lore"].includes(item.id));
  const visibleSecondary = isAdmin
    ? secondary
    : secondary.filter((item) => item.id === "system");
  return (
    <aside className="app-nav">
      <button className="brand" type="button" onClick={() => onChange("chat")}>
        <Icon name="feather" size={25} />
        <span>Kindred</span>
      </button>
      <nav aria-label="Main navigation">
        <NavGroup items={visiblePrimary} active={active} onChange={onChange} />
        <div className="nav-divider" />
        <NavGroup items={visibleSecondary} active={active} onChange={onChange} />
      </nav>
      <div className="nav-footer">
        {isAdmin ? (
          <button className="new-character-nav" type="button" onClick={onNewCharacter}>
            <Icon name="plus" size={17} />
            <span>New character</span>
          </button>
        ) : null}
        <div className="local-status">
          <span className={`status-dot ${localReady ? "is-ready" : ""}`} />
          <div>
            <strong>{localReady ? "Local model ready" : "Local model offline"}</strong>
            <span>{localReady ? "Available for chats" : "Start Ollama or llama.cpp"}</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
