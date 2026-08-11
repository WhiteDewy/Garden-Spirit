/**
 * Web Push 订阅工具（H5 专用）。
 *
 * 职责：把浏览器的 PushManager 订阅流程封装成两个纯函数，
 *      调用方（index.vue）只关心"要不要订阅、结果如何"。
 *
 * 非 H5 环境（小程序 / App）：浏览器 API 不存在 → 所有函数安静返回 false，
 *      不抛错、不打断页面流程。推送是增强能力，不是硬依赖。
 */

import api from "@/api/client";

/** base64url → Uint8Array：PushManager.subscribe 的 applicationServerKey 需要 */
function urlB64ToUint8Array(base64Url: string): Uint8Array {
  const padding = "=".repeat((4 - (base64Url.length % 4)) % 4);
  const base64 = (base64Url + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

/** 环境检查：浏览器 + Service Worker + 推送 + 通知 全可用才返回 true */
function isSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

/** 请求通知权限（不重复请求）：granted 直接过 / default 弹窗 / denied 拒绝 */
async function ensurePermission(): Promise<boolean> {
  if (!isSupported()) return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;
  const result = await Notification.requestPermission();
  return result === "granted";
}

/**
 * 订阅流程：拿 SW → 拿 VAPID 公钥 → pushManager.subscribe → 上报后端。
 * 后端 save_push_subscription 是幂等 upsert，重复调用安全。
 * 返回 true = 订阅成功（含已有订阅复用）。
 */
export async function subscribePush(personId: string): Promise<boolean> {
  if (!isSupported()) return false;
  try {
    const permission = await ensurePermission();
    if (!permission) return false;

    const registration = await navigator.serviceWorker.ready;
    // 已有订阅直接复用（换 VAPID 公钥时才需要重新订阅）
    let subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      const { public_key } = await api.getVapidPublicKey();
      if (!public_key) return false;
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlB64ToUint8Array(public_key),
      });
    }
    await api.pushSubscribe(personId, (subscription as PushSubscription).toJSON() as any);
    return true;
  } catch (e) {
    console.warn("[push] 订阅失败:", e);
    return false;
  }
}

/** 取消订阅：删后端记录 + 清浏览器订阅。返回 true = 已退订。 */
export async function unsubscribePush(personId: string): Promise<boolean> {
  if (!isSupported()) return false;
  try {
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();
    if (subscription) {
      const endpoint = (subscription as PushSubscription).endpoint;
      await api.pushUnsubscribe(personId, endpoint);
      await subscription.unsubscribe();
    }
    return true;
  } catch (e) {
    console.warn("[push] 退订失败:", e);
    return false;
  }
}
