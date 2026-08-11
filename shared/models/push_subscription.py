"""PushSubscription —— 浏览器 Web Push 订阅（VAPID 推送目标）。

浏览器的 PushManager.subscribe() 产出一条订阅：endpoint（推送服务 URL）
+ keys.p256dh / keys.auth（内容加密密钥）。服务端保存它，才能在来信时
主动推送。p256dh/auth 属于敏感数据（能定向加密推送），落库必须加密。

v1 每设备一条，person_id + endpoint 复合主键（同人多设备共存）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from shared.types import EntityId


@dataclass
class PushSubscription:
    """一条浏览器推送订阅。endpoint 是复合主键的一部分（按设备去重）。"""

    person_id: EntityId
    endpoint: str
    p256dh: str = ""          # keys.p256dh（内容加密公钥，落库加密）
    auth: str = ""            # keys.auth（共享密钥，落库加密）
    created_at: datetime | None = None


__all__ = ["PushSubscription"]
