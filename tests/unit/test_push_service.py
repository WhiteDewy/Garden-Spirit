"""PushService 单元测试（Web Push 订阅管理 + 发送管线）。

验证：
- VAPID 公钥透传（前端订阅用）
- subscribe 解包 PushSubscription.toJSON() → 加密落库（读回明文）
- 缺 keys 的异常载荷也安静落库（p256dh/auth 兜底空串）
- unsubscribe 删除 + 幂等
- send_to_person：无订阅 → 0；无 VAPID 私钥（开发/测试）→ 跳过不炸
"""

from foundation.config import PushConfig
from foundation.database.store import GardenStore
from shared.models import PushSubscription

from application.push import PushService


def _make_service(**vapid_kwargs) -> tuple[PushService, GardenStore]:
    store = GardenStore(":memory:")
    cfg = PushConfig(**vapid_kwargs)
    return PushService(store, cfg), store


def test_vapid_public_key_returns_config():
    service, _ = _make_service(vapid_public_key="pub_abc")
    assert service.vapid_public_key() == "pub_abc"


def test_subscribe_then_list_roundtrip():
    """浏览器 toJSON() 格式 → 存库 → 读回明文密钥。"""
    service, store = _make_service()
    service.subscribe("p1", {
        "endpoint": "https://push.example/ep_1",
        "keys": {"p256dh": "k_p256dh", "auth": "k_auth"},
    })
    subs = store.list_push_subscriptions("p1")
    assert len(subs) == 1
    assert subs[0].endpoint == "https://push.example/ep_1"
    assert subs[0].p256dh == "k_p256dh"
    assert subs[0].auth == "k_auth"


def test_subscribe_missing_keys_graceful():
    """异常载荷（无 keys / 空 endpoint）→ 安静落库，不炸。"""
    service, store = _make_service()
    service.subscribe("p1", {"endpoint": "  ", "keys": None})
    subs = store.list_push_subscriptions("p1")
    assert len(subs) == 1
    assert subs[0].endpoint == ""    # strip 后为空
    assert subs[0].p256dh == ""
    assert subs[0].auth == ""


def test_unsubscribe_removes():
    service, store = _make_service()
    service.subscribe("p1", {"endpoint": "ep_1", "keys": {"p256dh": "a", "auth": "b"}})
    assert service.unsubscribe("p1", "ep_1") is True
    assert store.list_push_subscriptions("p1") == []
    # 幂等：删不存在的 → False
    assert service.unsubscribe("p1", "ep_1") is False


def test_send_to_person_no_subscription_returns_zero():
    service, _ = _make_service()
    assert service.send_to_person("p1", "标题", "正文") == 0


def test_send_to_person_without_vapid_key_skips():
    """有订阅但没配 VAPID 私钥（开发/测试）→ 跳过发送，返回 0，不抛错。"""
    service, store = _make_service()  # vapid_private_key 默认 ""
    store.save_push_subscription(PushSubscription(
        person_id="p1", endpoint="https://push.example/ep_1", p256dh="a", auth="b",
    ))
    assert service.send_to_person("p1", "标题", "正文") == 0
    # 订阅仍保留（跳过 ≠ 失效清理）
    assert len(store.list_push_subscriptions("p1")) == 1
