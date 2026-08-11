"""PushService —— Web Push 推送服务（VAPID 签名 + 订阅管理）。

职责：
- 暴露 VAPID 公钥给前端（订阅用）
- 接收/删除浏览器订阅（PushSubscription，加密落库由 GardenStore 负责）
- 来信时按人推送（pywebpush 签名 + ECE 内容加密）

原则：推送失败不阻断主流程（来信已落库，推送只是提醒）。404/410 =
订阅已失效，顺手清理，避免垃圾订阅堆积。无 VAPID 密钥（开发/测试）
→ 直接跳过发送，服务不炸。
"""

from __future__ import annotations

import json

from foundation.config import PushConfig
from foundation.database.store import GardenStore
from foundation.logger import get_logger
from shared.models import PushSubscription

logger = get_logger("application.push.service")

#: 推送消息存活时间（秒）。用户离线时消息保留 24h，期间上线即送达。
_TTL_SECONDS = 86400


class PushService:
    """订阅管理 + 每日来信推送。store 注入（加密落库），config 注入（VAPID）。"""

    def __init__(self, store: GardenStore, config: PushConfig):
        self._store = store
        self._config = config

    # ------------------------------------------------------------------
    # 订阅管理
    # ------------------------------------------------------------------

    def vapid_public_key(self) -> str:
        """VAPID 公钥（base64url），前端 PushManager.subscribe 用。"""
        return self._config.vapid_public_key

    def subscribe(self, person_id: str, subscription_info: dict) -> None:
        """存一条浏览器订阅（PushSubscription.toJSON() 格式）。"""
        keys = subscription_info.get("keys") or {}
        self._store.save_push_subscription(PushSubscription(
            person_id=person_id,
            endpoint=str(subscription_info.get("endpoint", "")).strip(),
            p256dh=str(keys.get("p256dh", "")),
            auth=str(keys.get("auth", "")),
        ))

    def unsubscribe(self, person_id: str, endpoint: str) -> bool:
        """退订（endpoint 失效/用户关通知）。真的删了 → True。"""
        return self._store.delete_push_subscription(person_id, endpoint)

    # ------------------------------------------------------------------
    # 推送
    # ------------------------------------------------------------------

    def send_to_person(self, person_id: str, title: str, body: str, url: str = "/") -> int:
        """给一个人的所有设备推送。返回成功送达数（0 = 无订阅/全失败）。"""
        subs = self._store.list_push_subscriptions(person_id)
        if not subs:
            return 0
        ok = 0
        for sub in subs:
            if self._send_one(sub, title, body, url):
                ok += 1
        return ok

    def _send_one(self, sub: PushSubscription, title: str, body: str, url: str) -> bool:
        """单条订阅推送。成功 → True；订阅失效（404/410）→ 清理 + False；其余异常 → 记录 + False。"""
        if not self._config.vapid_private_key:
            logger.warning("未配置 GS_VAPID_PRIVATE_KEY，跳过推送（person=%s）", sub.person_id)
            return False
        try:
            from pywebpush import WebPushException, webpush

            payload = json.dumps(
                {"title": title, "body": body, "url": url},
                ensure_ascii=False,
            )
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=self._config.vapid_private_key,
                vapid_claims={"sub": self._config.vapid_subject},
                ttl=_TTL_SECONDS,
            )
            return True
        except WebPushException as exc:
            code = getattr(getattr(exc, "response", None), "status_code", None)
            if code in (404, 410):
                logger.info("订阅失效(%s)，清理: %s", code, sub.endpoint)
                self._store.delete_push_subscription(sub.person_id, sub.endpoint)
            else:
                logger.warning("推送失败(%s): %s", code, exc)
            return False
        except Exception as exc:  # noqa: BLE001 - 网络/编码错误不阻断主流程
            logger.warning("推送异常: %s", exc)
            return False


__all__ = ["PushService"]
