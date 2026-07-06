/* Kindred's service worker handles standards-based Web Push notifications. */
self.addEventListener("push", (event) => {
  let payload = { title: "Kindred", body: "A character sent a message.", url: "/" };
  try {
    payload = { ...payload, ...event.data.json() };
  } catch {
    if (event.data) payload.body = event.data.text();
  }
  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: "/kindred-icon.svg",
      badge: "/kindred-icon.svg",
      data: { url: payload.url },
      tag: "kindred-character-message",
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = event.notification.data?.url || "/";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      const existing = windows.find((client) => "focus" in client);
      return existing ? existing.focus() : clients.openWindow(target);
    }),
  );
});

