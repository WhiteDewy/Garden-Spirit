"""合盘对象持久化测试：store CRUD + API 端点 + /chat 恢复链路。

覆盖：
- related_persons 表 CRUD（加密落库，列表不碰出生数据）
- POST/GET/DELETE /person/{id}/related 端点
- /chat 带 related_person_id → 会话上下文注入合盘对象（多轮不再断链）
- 跨用户访问拒绝
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from foundation.config import AppConfig
from foundation.database.store import GardenStore
from shared.models import BirthData, GeoLocation, Person

from application.api.main import _birth_from_json, _birth_to_json, create_app


@pytest.fixture()
def store():
    s = GardenStore(":memory:")
    yield s
    s.close()


def _birth() -> BirthData:
    """一个确定的对方出生数据（1991-11-02 15:45 北京）。"""
    return BirthData(
        datetime(1991, 11, 2, 15, 45, tzinfo=__import__("zoneinfo").ZoneInfo("Asia/Shanghai")),
        GeoLocation(39.9042, 116.4074, timezone_name="Asia/Shanghai", place_name="北京"),
    )


# ----------------------------------------------------------------------
# store 层 CRUD
# ----------------------------------------------------------------------


def test_store_save_and_get_related_person(store):
    rel_id = store.save_related_person("rel1", "owner1", "小王", _birth_to_json(_birth()))
    assert rel_id == "rel1"

    got = store.get_related_person("rel1")
    assert got is not None
    assert got["person_id"] == "owner1"
    assert got["name"] == "小王"
    assert got["birth_data"] == _birth()
    assert got["birth_data"].location.place_name == "北京"


def test_store_list_related_persons(store):
    store.save_related_person("a", "owner1", "小王", _birth_to_json(_birth()))
    store.save_related_person("b", "owner1", "小李", _birth_to_json(_birth()))
    names = [d["name"] for d in store.list_related_persons("owner1")]
    assert sorted(names) == ["小李", "小王"]
    # 列表视图不带出生数据（隐私：不主动解密）
    assert all("birth_data" not in d for d in store.list_related_persons("owner1"))


def test_store_list_empty(store):
    assert store.list_related_persons("nobody") == []


def test_store_list_respects_owner(store):
    store.save_related_person("a", "owner1", "小王", _birth_to_json(_birth()))
    store.save_related_person("b", "owner2", "小李", _birth_to_json(_birth()))
    assert [d["name"] for d in store.list_related_persons("owner1")] == ["小王"]
    assert [d["name"] for d in store.list_related_persons("owner2")] == ["小李"]


def test_store_delete_related_person(store):
    store.save_related_person("a", "owner1", "小王", _birth_to_json(_birth()))
    assert store.delete_related_person("a") is True
    assert store.get_related_person("a") is None
    assert store.delete_related_person("a") is False  # 已删 → False


def test_store_encrypted_at_rest(store, tmp_path):
    """出生数据/名字必须 Fernet 加密落库，不存明文（PRD §8 红线）。"""
    store = GardenStore(str(tmp_path / "garden.db"))
    store.save_related_person("rel_enc", "owner1", "小王", _birth_to_json(_birth()))
    import sqlite3

    conn = sqlite3.connect(str(tmp_path / "garden.db"))
    row = conn.execute("SELECT name_enc, birth_data_enc FROM related_persons WHERE id='rel_enc'").fetchone()
    conn.close()
    assert row is not None
    # Fernet token 形如 gAAAAA…（base64，含 '.' 与固定前缀），不是明文 JSON
    assert "小王" not in row[0]
    assert "1991" not in row[1]
    assert "gAAAAA" in row[0]
    store.close()


def test_birth_json_roundtrip():
    """_birth_to_json/_birth_from_json 往返一致（与 persons 表同格式）。"""
    birth = _birth()
    assert _birth_from_json(_birth_to_json(birth)) == birth


# ----------------------------------------------------------------------
# API 端点
# ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    config = AppConfig()
    config.storage.db_path = ":memory:"
    app = create_app(config)
    with TestClient(app) as c:
        yield c


def _owner_payload() -> dict:
    return {
        "name": "盘主",
        "birth": {
            "datetime_local": "1995-06-15T09:30:00",
            "location": {"place_name": "上海"},
            "time_known": True,
        },
    }


def _related_payload(name="小王") -> dict:
    return {
        "name": name,
        "birth": {
            "datetime_local": "1991-11-02T15:45:00",
            "location": {"place_name": "北京"},
            "time_known": True,
        },
    }


def _create_owner(client) -> str:
    return client.post("/person", json=_owner_payload()).json()["id"]


def test_api_related_roundtrip(client):
    pid = _create_owner(client)

    resp = client.post(f"/person/{pid}/related", json=_related_payload())
    assert resp.status_code == 200
    rel = resp.json()
    rel_id = rel["id"]
    assert rel["name"] == "小王"

    # 列表
    lst = client.get(f"/person/{pid}/related")
    assert lst.status_code == 200
    assert [x["id"] for x in lst.json()] == [rel_id]
    # 列表不暴露出生数据
    assert "birth" not in lst.json()[0]

    # 删除
    dele = client.delete(f"/person/{pid}/related/{rel_id}")
    assert dele.status_code == 200
    assert client.get(f"/person/{pid}/related").json() == []


def test_api_related_unknown_owner_404(client):
    resp = client.post("/person/nope/related", json=_related_payload())
    assert resp.status_code == 404


def test_api_related_cross_user_delete_404(client):
    pid1 = _create_owner(client)
    pid2 = _create_owner(client)
    rel_id = client.post(f"/person/{pid1}/related", json=_related_payload()).json()["id"]
    # 用户2 不能删用户1 的合盘对象
    assert client.delete(f"/person/{pid2}/related/{rel_id}").status_code == 404
    # 用户1 的还在
    assert client.get(f"/person/{pid1}/related").json()[0]["id"] == rel_id


def test_chat_restores_related_person(client):
    """端→端：POST /related 保存 → /chat 带 related_person_id → 会话注入合盘对象。

    这是"多轮断链修复"的核心验证——之前 related_person 只活在内存里，
    现在从 DB 恢复到会话上下文。
    """
    pid = _create_owner(client)
    rel_id = client.post(f"/person/{pid}/related", json=_related_payload()).json()["id"]

    resp = client.post("/chat", json={
        "person_id": pid,
        "message": "我和小王的关系怎么样",
        "related_person_id": rel_id,
    })
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    # 会话上下文里已注入合盘对象（不再需要问出生数据）
    ctx = client.app.state.agent.get_session_context(session_id)
    assert ctx is not None
    assert ctx.related_person is not None
    assert ctx.related_person.name == "小王"
    assert ctx.related_person.birth.location.place_name == "北京"
    assert ctx.pending_related_person is False
    # 响应不再要求提供对方出生数据
    assert resp.json()["needs_related_person"] is False


def test_store_related_person_gender_notes_update(store):
    """合盘对象编辑字段也要加密持久化，并支持 owner 更新。"""
    store.save_related_person(
        "rel_fields", "owner1", "小王", _birth_to_json(_birth()), gender="M", notes="同事"
    )
    got = store.get_related_person("rel_fields")
    assert got is not None
    assert got["gender"] == "M"
    assert got["notes"] == "同事"

    assert store.update_related_person(
        "rel_fields", "owner1", "小李", _birth_to_json(_birth()), gender="F", notes="朋友"
    ) is True
    updated = store.get_related_person("rel_fields")
    assert updated is not None
    assert updated["name"] == "小李"
    assert updated["gender"] == "F"
    assert updated["notes"] == "朋友"
    assert store.update_related_person(
        "rel_fields", "other", "坏覆盖", _birth_to_json(_birth())
    ) is False


def test_api_related_detail_and_update(client):
    """合盘档案页可读取/修改出生数据、性别与备注；跨 owner 仍 404。"""
    pid = _create_owner(client)
    payload = _related_payload()
    payload.update({"gender": "M", "notes": "老同学"})
    rel_id = client.post(f"/person/{pid}/related", json=payload).json()["id"]

    detail = client.get(f"/person/{pid}/related/{rel_id}")
    assert detail.status_code == 200
    assert detail.json()["birth"]["location"]["place_name"] == "北京"
    assert detail.json()["gender"] == "M"
    assert detail.json()["notes"] == "老同学"

    update_payload = _related_payload("小李")
    update_payload.update({"gender": "F", "notes": "合盘对象"})
    updated = client.put(f"/person/{pid}/related/{rel_id}", json=update_payload)
    assert updated.status_code == 200
    assert updated.json()["name"] == "小李"
    assert updated.json()["gender"] == "F"
    assert updated.json()["notes"] == "合盘对象"

    other = _create_owner(client)
    assert client.get(f"/person/{other}/related/{rel_id}").status_code == 404
    assert client.put(f"/person/{other}/related/{rel_id}", json=update_payload).status_code == 404


def test_chat_invalid_related_id_silent(client):
    """不存在的 related_person_id → 静默跳过（不 500，走普通对话路径）。"""
    pid = _create_owner(client)
    resp = client.post("/chat", json={
        "person_id": pid,
        "message": "你好",
        "related_person_id": "ghost_id",
    })
    assert resp.status_code == 200


def test_chat_cross_user_related_denied(client):
    """别人的 related_person_id 传进来 → 拒绝恢复（安全），但对话本身不炸。"""
    pid1 = _create_owner(client)
    pid2 = _create_owner(client)
    rel_id = client.post(f"/person/{pid1}/related", json=_related_payload()).json()["id"]

    resp = client.post("/chat", json={
        "person_id": pid2,
        "message": "帮我看看我和小王的合盘",
        "related_person_id": rel_id,
    })
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]
    ctx = client.app.state.agent.get_session_context(session_id)
    # 跨用户对象不注入
    assert ctx.related_person is None
