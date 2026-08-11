"""application.push —— Web Push 推送层。

订阅管理 + 每日来信推送（VAPID 签名）。纯编排，不碰占星、不依赖 LLM。
"""

from application.push.service import PushService

__all__ = ["PushService"]
