/* 星灵花园 Service Worker —— 只处理 Web Push 通知，不拦截 fetch。
 *
 * 后端 /push/trigger 通过推送服务把「今日来信」推到这里：
 *   push 事件 → showNotification → 点击 → 打开来信页
 *
 * 注意：不拦截网络请求（v1 不需要离线缓存），保持最小。
 */
self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    /* 非 JSON payload：兜底空对象 */
  }
  const title = data.title || "星灵来信";
  const options = {
    body: data.body || "你有一封新的来信，来自星灵花园。",
    icon: "/static/logo.png",
    badge: "/static/logo.png",
    data: { url: data.url || "/pages/mailbox/mailbox" },
    vibrate: [200, 100, 200],
    requireInteraction: false,
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((windows) => {
        for (const win of windows) {
          if (win.url && win.url.indexOf(url) !== -1) {
            return win.focus();
          }
        }
        return clients.openWindow(url);
      })
  );
});
