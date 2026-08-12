"""记忆召回测试：GET /recall 豆荚聚合 + /garden recall + /opening 记忆钩子。

覆盖：
- 空用户 → has_memory=False、items 空
- 五类豆荚齐全：key_date / confirmed_finding / domain_summary / top_fragment / recent_topic
- 只取 confirmed 的沉淀判断；领域按 confidence 降序
- 会话摘要自然化（旧转写"用户:/星灵:"剥干净）
- /opening 记忆钩子（confirmed > key_date > domain，无召回完全兼容）
- 端点 404
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from foundation.config import AppConfig
from foundation.utils import new_id
from shared.enums import PersonaType, Role
from shared.models import (
    ChartProfile,
    Conversation,
    DialogueTurn,
    DomainSummary,
    FragmentLight,
    KeyDate,
    MemoryItem,
    VerifiedFinding,
)

from application.api.main import create_app
from application.relationship.service import _recall_hook


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
    return {
        "name": name,
        "birth": {
            "datetime_local": "1991-03-21T09:25:00",
            "location": {"place_name": "上海"},
            "time_known": True,
        },
        "house_system": "B",
    }


def _create_person(client, name: str = "盘主") -> str:
    return client.post("/person", json=_payload(name)).json()["id"]


def _make_conversation(person_id: str) -> Conversation:
    conv = Conversation(
        id=new_id("conv"), person_id=person_id, persona=PersonaType.MOON,
        started_at=_now(), is_active=True,
    )
    conv.add_turn(DialogueTurn(
        id=new_id("t"), user_message="你好", assistant_response="你好呀",
        persona_used=PersonaType.MOON, timestamp=_now(),
    ))
    return conv


def _seed_rich_profile(client, person_id: str) -> None:
    """画像三件套：key_date + confirmed finding + 领域摘要（信任信号达标）。"""
    store = client.app.state.store
    now = _now()
    prof = ChartProfile(person_id=person_id, created_at=now, updated_at=now)
    prof.key_dates.append(KeyDate(id=new_id("k"), date=now, label="考虑换工作", kind="event"))
    prof.verified_findings.append(VerifiedFinding(
        id=new_id("f"), statement="土星落九宫：深造是职业跃迁的必经之路",
        confidence=0.8, user_feedback="confirmed",
    ))
    prof.verified_findings.append(VerifiedFinding(
        id=new_id("f2"), statement="被反驳的判断", confidence=0.9, user_feedback="refuted",
    ))
    prof.domain_summaries["career"] = DomainSummary(
        domain="career", summary="最近三个月你越来越相信自己的判断",
        confidence=0.6, updated_at=now,
    )
    # 信任信号：让 /opening 走"老用户"分支（否则只吐自我介绍）
    prof.trust_signals["deep_consult"] = 1
    prof.trust_score = 6.0
    store.save_profile(prof)
    # 点亮账本 + 一段旧转写摘要的会话
    store.append_fragment_lights(
        person_id,
        [
            FragmentLight(subtype_id="moon_tide", delta=5, kind="outpouring", source="晚上睡不着"),
            FragmentLight(subtype_id="sun_core", delta=2, kind="mention", source="最近有干劲"),
        ],
        session_id="s1",
    )
    store.save_conversation(
        _make_conversation(person_id),
        summary="用户: 我想换工作\n星灵: 那你觉得卡在哪？",
    )


# ----------------------------------------------------------------------
# GET /recall
# ----------------------------------------------------------------------


def test_recall_empty_has_no_memory(client):
    pid = _create_person(client)
    resp = client.get(f"/person/{pid}/recall")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_memory"] is False
    assert data["items"] == []


def test_recall_aggregates_all_five_kinds(client):
    pid = _create_person(client)
    _seed_rich_profile(client, pid)
    data = client.get(f"/person/{pid}/recall").json()

    assert data["has_memory"] is True
    kinds = {item["kind"] for item in data["items"]}
    assert kinds == {
        "key_date", "confirmed_finding", "domain_summary",
        "top_fragment", "recent_topic",
    }

    by_kind = {item["kind"]: item for item in data["items"]}
    assert by_kind["key_date"]["label"] == "考虑换工作"
    assert by_kind["confirmed_finding"]["label"] == "土星落九宫：深造是职业跃迁的必经之路"
    assert by_kind["domain_summary"]["label"] == "最近三个月你越来越相信自己的判断"
    assert by_kind["domain_summary"]["detail"] == "career"
    # top_fragment 有两条（月亮5、太阳2）：按深度降序，第一条是月亮
    top_fragments = [i for i in data["items"] if i["kind"] == "top_fragment"]
    assert "月亮" in top_fragments[0]["label"]
    assert top_fragments[0]["detail"] == "深度 5"
    assert "太阳" in top_fragments[1]["label"]
    assert top_fragments[1]["detail"] == "深度 2"
    # recent_topic：旧转写摘要被自然化（无"用户:"前缀）
    assert by_kind["recent_topic"]["label"] == "我想换工作"


def test_recall_excludes_unconfirmed_findings(client):
    pid = _create_person(client)
    _seed_rich_profile(client, pid)  # 含一条 refuted
    items = client.get(f"/person/{pid}/recall").json()["items"]
    labels = [i["label"] for i in items if i["kind"] == "confirmed_finding"]
    assert "被反驳的判断" not in labels
    assert all("土星落九宫" in l for l in labels)


def test_recall_domain_summaries_confidence_desc(client):
    store = client.app.state.store
    pid = _create_person(client)
    now = _now()
    prof = ChartProfile(person_id=pid, created_at=now, updated_at=now)
    prof.domain_summaries["low"] = DomainSummary(
        domain="low", summary="低置信摘要", confidence=0.2, updated_at=now)
    prof.domain_summaries["high"] = DomainSummary(
        domain="high", summary="高置信摘要", confidence=0.9, updated_at=now)
    store.save_profile(prof)

    items = client.get(f"/person/{pid}/recall").json()["items"]
    domains = [i for i in items if i["kind"] == "domain_summary"]
    assert [i["label"] for i in domains] == ["高置信摘要", "低置信摘要"]


def test_recall_recent_topic_naturalizes_transcribe(client):
    store = client.app.state.store
    pid = _create_person(client)
    store.save_conversation(
        _make_conversation(pid),
        summary="用户: 我最近睡不好\n星灵: 是不是心里有件事压着？",
    )
    items = client.get(f"/person/{pid}/recall").json()["items"]
    topics = [i["label"] for i in items if i["kind"] == "recent_topic"]
    assert topics == ["我最近睡不好"]
    assert all("用户:" not in t and "星灵:" not in t for t in topics)


def test_recall_404_unknown(client):
    assert client.get("/person/ghost/recall").status_code == 404


# ----------------------------------------------------------------------
# /opening 记忆钩子
# ----------------------------------------------------------------------


def test_opening_includes_recall_hook(client):
    pid = _create_person(client)
    _seed_rich_profile(client, pid)
    opening = client.get(f"/person/{pid}/opening").json()["opening"]
    assert "上次你确认过——「土星落九宫：深造是职业跃迁的必经之路」" in opening
    # confirmed > key_date 优先级：不先提"考虑换工作"
    assert "你以前提过「考虑换工作」" not in opening


def test_opening_without_recall_backward_compatible(client):
    """空用户/无记忆豆荚 → 开场白与旧行为完全一致（不出现记忆钩子）。"""
    pid = _create_person(client)
    opening = client.get(f"/person/{pid}/opening").json()["opening"]
    assert "我是住在你星盘里的星灵" in opening
    assert "确认过" not in opening
    assert "提过" not in opening


# ----------------------------------------------------------------------
# /garden recall 字段
# ----------------------------------------------------------------------


def test_garden_carries_recall(client):
    pid = _create_person(client)
    # 空用户 → recall 为 None（前端少一个空态）
    garden = client.get(f"/garden?person_id={pid}").json()
    assert garden["recall"] is None

    _seed_rich_profile(client, pid)
    garden = client.get(f"/garden?person_id={pid}").json()
    assert garden["recall"]["has_memory"] is True
    assert any(i["kind"] == "confirmed_finding" for i in garden["recall"]["items"])


# ----------------------------------------------------------------------
# 纯逻辑：_recall_hook 优先级
# ----------------------------------------------------------------------


def test_recall_hook_priority_and_missing():
    assert _recall_hook(None) is None
    assert _recall_hook({}) is None
    # confirmed > key_date
    assert _recall_hook({
        "confirmed_findings": [{"statement": "确认过的事"}],
        "key_dates": [{"label": "某天"}],
    }) == "说起来，上次你确认过——「确认过的事」。"
    # 只有 key_date
    assert _recall_hook({"key_dates": [{"label": "考虑离职"}]}) == \
        "你以前提过「考虑离职」，现在有变化吗？"
    # 只有 domain_summary
    assert _recall_hook({"domain_summaries": [{"domain": "career", "summary": "相信自己"}]}) == \
        "关于career，我记得你说过「相信自己」。"
    # 全空字符串 → None
    assert _recall_hook({"confirmed_findings": [{"statement": ""}], "key_dates": []}) is None
