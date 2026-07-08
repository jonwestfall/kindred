/* Kindred's service worker handles standards-based Web Push notifications. */
self.addEventListener("push", (event) => {
  let payload = {
    title: "Kindred",
    body: "A character sent a message.",
    url: "/",
    tag: `kindred-message-${Date.now()}`,
  };
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
      tag: payload.tag,
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = event.notification.data?.url || "/";
  const targetUrl = new URL(target, self.location.origin).href;
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      const existing = windows.find((client) => new URL(client.url).origin === self.location.origin);
      if (!existing) return clients.openWindow(targetUrl);
      if ("navigate" in existing) {
        return existing.navigate(targetUrl).then((client) => {
          const nextClient = client || existing;
          return "focus" in nextClient ? nextClient.focus() : nextClient;
        });
      }
      return "focus" in existing ? existing.focus() : clients.openWindow(targetUrl);
    }),
  );
});
