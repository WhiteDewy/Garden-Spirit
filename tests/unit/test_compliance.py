"""合规测试：全量删除（PRD §8「可随时删除数据」）+ 数据导出。

覆盖：
- DELETE /person/{id}：9 张业务表级联清空 + persons 表删除 + 幂等 404
- 只删目标用户，不殃及其他用户
- GET /person/{id}/export：全表解密明文聚合，字段契约齐全
- 空用户导出（profile=None、列表空）；不存在 → 404
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from foundation.config import AppConfig
from foundation.database.store import GardenStore
from foundation.utils import new_id
from shared.enums import PersonaType, Role
from shared.models import (
    ChartProfile,
    Conversation,
    DialogueTurn,
    FragmentLight,
    JournalEntry,
    Letter,
    LifeEvent,
    MemoryItem,
    PushSubscription,
)

from application.api.main import create_app


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture(scope="module")
def client():
    config = AppConfig()
    config.storage.db_path = ":memory:"
    app = create_app(config)
    with TestClient(app) as c:
        yield c


def _payload(name: str = "盘主") -> dict:
    # 出生地用离线静态表内城市（CI 无网）
    return {
        "name": name,
        "birth": {
            "datetime_local": "1991-03-21T09:25:00",
            "location": {"place_name": "上海"},
            "time_known": True,
        },
        "house_system": "B",  # Alcabitius
    }


def _make_conversation(person_id: str) -> Conversation:
    conv = Conversation(
        id=new_id("conv"), person_id=person_id, persona=PersonaType.MOON,
        started_at=_now(), is_active=True,
    )
    conv.add_turn(DialogueTurn(
        id=new_id("t"),
        user_message="你好，我想问事业",
        assistant_response="正在看你的星图……",
        persona_used=PersonaType.MOON,
        timestamp=_now(),
    ))
    return conv


def _seed_all_tables(store: GardenStore, person_id: str) -> None:
    """往 9 张表各写一条该用户的数据（验证级联删除 + 导出齐全）。"""
    store.save_conversation(_make_conversation(person_id), summary="开场寒暄")
    store.save_memory_item(MemoryItem(
        id=new_id("m"), session_id="s1", person_id=person_id,
        role=Role.USER, content="我想换工作", timestamp=_now(),
    ))
    store.save_profile(ChartProfile(person_id=person_id, created_at=_now(), updated_at=_now()))
    store.save_journal(JournalEntry(
        id=new_id("j"), person_id=person_id, content="今天有点迷茫", created_at=_now(), updated_at=_now(),
    ))
    store.save_life_event(LifeEvent(
        id=new_id("l"), person_id=person_id, occurred_at=_now(), label="完成事业咨询", kind="consult",
    ))
    store.save_letter(Letter(
        id=new_id("lt"), person_id=person_id, letter_date="2026-08-12",
        sender="moon", title="月亮来信", body="你最近睡得好吗？",
    ))
    store.append_fragment_lights(
        person_id,
        [FragmentLight(subtype_id="moon_tide", delta=3, kind="outpouring", source="我想换工作")],
        session_id="s1",
    )
    store.save_push_subscription(PushSubscription(
        person_id=person_id, endpoint="https://push.example/ep_1", p256dh="a", auth="b",
    ))
    store.save_related_person("rel1", person_id, "小王", _birth_json())


def _birth_json() -> str:
    """对方出生数据 JSON（1991-11-02 北京，与 related_person 测试同款）。"""
    import zoneinfo

    from shared.models import BirthData, GeoLocation

    birth = BirthData(
        datetime(1991, 11, 2, 15, 45, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
        GeoLocation(39.9042, 116.4074, timezone_name="Asia/Shanghai", place_name="北京"),
    )
    from application.api.main import _birth_to_json

    return _birth_to_json(birth)


def _create_person(client, name: str = "盘主") -> str:
    return client.post("/person", json=_payload(name)).json()["id"]


# ----------------------------------------------------------------------
# 全量删除
# ----------------------------------------------------------------------


def test_delete_person_purges_all_tables(client):
    store = client.app.state.store
    pid = _create_person(client)
    _seed_all_tables(store, pid)

    resp = client.delete(f"/person/{pid}")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": pid}

    # 9 张业务表全清空
    assert store.list_conversations(pid) == []
    assert store.list_memory_items(person_id=pid) == []
    assert store.get_profile(pid) is None
    assert store.list_journals(pid) == []
    assert store.list_life_events(pid) == []
    assert store.list_letters(pid) == []
    assert store.list_fragment_lights(pid) == []
    assert store.list_push_subscriptions(pid) == []
    assert store.list_related_persons(pid) == []
    # persons 表也删了
    assert client.app.state.person_repo.get(pid) is None
    # 幂等：已删 → 再删 404
    assert client.delete(f"/person/{pid}").status_code == 404


def test_delete_person_404_unknown(client):
    assert client.delete("/person/ghost").status_code == 404


def test_purge_person_idempotent_at_store_level(client):
    """store.purge_person 返回各表行数；二次清空 → 全 0（幂等不炸）。"""
    store = client.app.state.store
    pid = _create_person(client)
    _seed_all_tables(store, pid)

    counts = store.purge_person(pid)
    assert counts["conversations"] >= 1
    assert counts["letters"] >= 1
    assert counts["push_subscriptions"] == 1

    second = store.purge_person(pid)
    assert all(v == 0 for v in second.values())


def test_delete_person_only_affects_target(client):
    store = client.app.state.store
    pid_a = _create_person(client, "甲")
    pid_b = _create_person(client, "乙")
    _seed_all_tables(store, pid_a)
    _seed_all_tables(store, pid_b)

    client.delete(f"/person/{pid_a}")

    # 甲清了，乙原样
    assert store.get_profile(pid_a) is None
    assert store.list_conversations(pid_a) == []
    assert store.get_profile(pid_b) is not None
    assert len(store.list_conversations(pid_b)) == 1
    assert client.app.state.person_repo.get(pid_b) is not None


# ----------------------------------------------------------------------
# 数据导出
# ----------------------------------------------------------------------


def test_export_person_contains_all_sections(client):
    store = client.app.state.store
    pid = _create_person(client)
    _seed_all_tables(store, pid)

    resp = client.get(f"/person/{pid}/export")
    assert resp.status_code == 200
    data = resp.json()

    # 字段契约齐全
    for key in (
        "person", "profile", "conversations", "memory_items", "journal_entries",
        "life_events", "letters", "fragment_lights", "push_subscriptions",
        "related_persons", "exported_at",
    ):
        assert key in data, f"缺少字段 {key}"

    assert data["exported_at"]
    assert data["person"]["name"] == "盘主"
    assert data["profile"]["person_id"] == pid

    # 各表明文（PII 已解密，可读）
    assert data["conversations"][0]["turns"][0]["user_message"] == "你好，我想问事业"
    assert data["memory_items"][0]["content"] == "我想换工作"
    assert data["journal_entries"][0]["content"] == "今天有点迷茫"
    assert data["life_events"][0]["label"] == "完成事业咨询"
    assert data["letters"][0]["body"] == "你最近睡得好吗？"
    assert data["letters"][0]["title"] == "月亮来信"
    assert data["fragment_lights"][0]["subtype_id"] == "moon_tide"
    assert data["fragment_lights"][0]["source"] == "我想换工作"
    assert data["push_subscriptions"][0]["endpoint"] == "https://push.example/ep_1"
    # 合盘对象带解密出生数据
    rel = data["related_persons"][0]
    assert rel["name"] == "小王"
    assert rel["birth_data"]["location"]["place_name"] == "北京"
    assert rel["birth_data"]["datetime_utc"].startswith("1991-11-02")


def test_export_person_empty_has_no_crash(client):
    """空用户（无画像/无业务数据）→ profile=None、列表空，不炸。"""
    pid = _create_person(client)
    resp = client.get(f"/person/{pid}/export")
    assert resp.status_code == 200
    data = resp.json()
    assert data["profile"] is None
    assert data["conversations"] == []
    assert data["memory_items"] == []
    assert data["related_persons"] == []
    assert data["exported_at"]


def test_export_person_404_unknown(client):
    assert client.get("/person/ghost/export").status_code == 404


def test_export_after_delete_404(client):
    pid = _create_person(client)
    client.delete(f"/person/{pid}")
    assert client.get(f"/person/{pid}/export").status_code == 404
