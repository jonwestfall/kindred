import { useState } from "react";

import { api } from "../api";
import { Icon } from "./Icon";

function toApplicationServerKey(value: string): ArrayBuffer {
  const padding = "=".repeat((4 - (value.length % 4)) % 4);
  const base64 = (value + padding).replace(/-/g, "+").replace(/_/g, "/");
  const bytes = Uint8Array.from(atob(base64), (character) => character.charCodeAt(0));
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
}

export function NotificationButton() {
  const [state, setState] = useState<NotificationPermission | "unsupported">(
    "Notification" in window ? Notification.permission : "unsupported",
  );
  const [note, setNote] = useState("");

  async function enable() {
    if (!("Notification" in window) || !("serviceWorker" in navigator)) {
      setState("unsupported");
      setNote("This browser does not support notifications.");
      return;
    }
    const permission = await Notification.requestPermission();
    setState(permission);
    if (permission !== "granted") {
      setNote("Permission was not granted.");
      return;
    }
    const registration = await navigator.serviceWorker.register("/sw.js");
    const key = await api.notificationKey();
    if (!key.web_push_configured || !key.public_key) {
      setNote("In-app alerts enabled. Add VAPID keys for background Web Push.");
      return;
    }
    const existing = await registration.pushManager.getSubscription();
    const subscription =
      existing ??
      (await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: toApplicationServerKey(key.public_key),
      }));
    await api.subscribe(subscription);
    setNote("Background Web Push is enabled.");
  }

  return (
    <div className="notification-control">
      <button
        className="icon-button"
        type="button"
        onClick={enable}
        title="Notification settings"
        aria-label="Enable notifications"
      >
        <Icon name={state === "granted" ? "check" : "bell"} />
      </button>
      {note ? <span className="floating-note">{note}</span> : null}
    </div>
  );
}
