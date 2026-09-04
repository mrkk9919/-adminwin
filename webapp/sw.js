/* Wing Bank — Service Worker (Push Notifications) */

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  if (!event.data) return;

  let payload;
  try {
    payload = event.data.json();
  } catch {
    payload = { title: "Wing Bank", body: event.data.text(), data: {} };
  }

  const { title = "Wing Bank", body = "", data = {} } = payload;

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: "/app-logo-nobg.png",
      badge: "/favicon.svg",
      tag: "wing-bank-payment",
      renotify: true,
      data,
      vibrate: [200, 100, 200],
      actions: [
        { action: "view", title: "View" },
        { action: "dismiss", title: "Dismiss" },
      ],
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  if (event.action === "dismiss") return;

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ("focus" in client) {
          client.focus();
          return;
        }
      }
      return self.clients.openWindow("/");
    })
  );
});
