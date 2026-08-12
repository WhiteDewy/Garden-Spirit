"""记忆镜头（recall lens）测试：同一份记忆，十种读法。

十颗行星都是 TA 内心的人格——记忆是同一份（person 维度），差别只在每颗星
按自己擅长的角度去"读"：重排豆荚优先级（recall_priority）、优先擅长领域
（recall_domains）、换开场话术（recall_frames）。确定性、无 LLM。

覆盖：
- /recall?persona= 按镜头重排豆荚：土星先事业、金星先关系（领域偏好优先于置信度）
- /recall?persona= 重排豆荚种类顺序：土星 domain_summary 排最前
- /opening?persona= 换话术：月亮用"现在心里还沉吗"、土星用"还守得住吗"
- /opening?persona= 换哪种豆荚先讲（土星先讲领域、不先讲确认过）
- 缺省 / 未知 persona：默认顺序 + 月亮兜底
- 纯逻辑 _recall_hook(persona=…) 直接换读法
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from foundation.config import AppConfig
from foundation.utils import new_id
from shared.enums import PersonaType
from shared.models import ChartProfile, DomainSummary, KeyDate, VerifiedFinding

from application.api.main import create_app
from application.conversation.persona import get_persona
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


def _create_person(client) -> str:
    return client.post("/person", json={
        "name": "盘主",
        "birth": {
            "datetime_local": "1991-03-21T09:25:00",
            "location": {"place_name": "上海"},
            "time_known": True,
        },
        "house_system": "B",
    }).json()["id"]


def _seed_two_domains(client, person_id: str) -> None:
    """画像：key_date + 确认判断 + career/relationship 两个领域（career 置信度更高）。"""
    store = client.app.state.store
    now = _now()
    prof = ChartProfile(person_id=person_id, created_at=now, updated_at=now)
    prof.key_dates.append(KeyDate(id=new_id("k"), date=now, label="考虑换工作", kind="event"))
    prof.verified_findings.append(VerifiedFinding(
        id=new_id("f"), statement="土星落九宫：深造是职业跃迁的必经之路",
        confidence=0.8, user_feedback="confirmed",
    ))
    # 默认按置信度降序：career(0.9) 在前 → 镜头偏好才能和置信度区分开
    prof.domain_summaries["career"] = DomainSummary(
        domain="career", summary="最近三个月你越来越相信自己的判断",
        confidence=0.9, updated_at=now,
    )
    prof.domain_summaries["relationship"] = DomainSummary(
        domain="relationship", summary="你在一段关系里感到被认真对待",
        confidence=0.7, updated_at=now,
    )
    prof.trust_signals["deep_consult"] = 1  # 让 /opening 走老用户分支
    prof.trust_score = 6.0
    store.save_profile(prof)


# ----------------------------------------------------------------------
# /recall?persona= 镜头重排
# ----------------------------------------------------------------------


def test_recall_lens_domain_preference_beats_confidence(client):
    pid = _create_person(client)
    _seed_two_domains(client, pid)

    # 默认（无镜头）：按置信度降序，career(0.9) 在前
    default_domains = [i["detail"] for i in client.get(f"/person/{pid}/recall").json()["items"]
                       if i["kind"] == "domain_summary"]
    assert default_domains == ["career", "relationship"]

    # 土星（擅长事业）：career 仍在前（与置信度一致，但不说明镜头没生效——见金星）
    saturn = [i["detail"] for i in
              client.get(f"/person/{pid}/recall", params={"persona": "saturn"}).json()["items"]
              if i["kind"] == "domain_summary"]
    assert saturn == ["career", "relationship"]

    # 金星（擅长关系）：relationship 跳到最前——镜头偏好 > 置信度
    venus = [i["detail"] for i in
             client.get(f"/person/{pid}/recall", params={"persona": "venus"}).json()["items"]
             if i["kind"] == "domain_summary"]
    assert venus == ["relationship", "career"]


def test_recall_lens_reranks_kind_order(client):
    pid = _create_person(client)
    _seed_two_domains(client, pid)

    # 默认：key_date 起头
    items = client.get(f"/person/{pid}/recall").json()["items"]
    assert items[0]["kind"] == "key_date"

    # 土星（recall_priority 以 domain_summary 起头）→ 第一条是领域摘要
    items = client.get(f"/person/{pid}/recall", params={"persona": "saturn"}).json()["items"]
    assert items[0]["kind"] == "domain_summary"
    assert items[0]["detail"] == "career"


# ----------------------------------------------------------------------
# /opening?persona= 换话术 + 换先讲哪种豆荚
# ----------------------------------------------------------------------


def test_opening_lens_swaps_frame_and_kind(client):
    pid = _create_person(client)
    _seed_two_domains(client, pid)

    # 默认话术：先讲确认过的事
    opening = client.get(f"/person/{pid}/opening").json()["opening"]
    assert "说起来，上次你确认过——「土星落九宫：深造是职业跃迁的必经之路」" in opening

    # 月亮：先讲情绪关键日期 + 换话术（"现在心里还沉吗"）
    opening = client.get(f"/person/{pid}/opening", params={"persona": "moon"}).json()["opening"]
    assert "我记得你那时候说「考虑换工作」——现在心里还沉吗？" in opening
    assert "说起来，上次你确认过" not in opening

    # 土星：先讲事业领域摘要 + 换话术（"还守得住吗"），不再先讲确认过
    opening = client.get(f"/person/{pid}/opening", params={"persona": "saturn"}).json()["opening"]
    assert "你扛着的career课题——「最近三个月你越来越相信自己的判断」，还守得住吗？" in opening
    assert "说起来，上次你确认过" not in opening


def test_unknown_persona_falls_back_moon(client):
    pid = _create_person(client)
    _seed_two_domains(client, pid)
    opening = client.get(f"/person/{pid}/opening", params={"persona": "ghost"}).json()["opening"]
    assert "现在心里还沉吗" in opening  # 未知字符串 → 月亮兜底（产品默认星灵）


# ----------------------------------------------------------------------
# 纯逻辑：_recall_hook(persona=…)
# ----------------------------------------------------------------------


def test_recall_hook_persona_reranks_and_reframes():
    recall = {
        "confirmed_findings": [{"statement": "确认过的事"}],
        "key_dates": [{"label": "考虑换工作"}],
        "domain_summaries": [{"domain": "career", "summary": "相信自己"}],
    }
    # 默认：confirmed 先讲
    assert _recall_hook(recall) == "说起来，上次你确认过——「确认过的事」。"
    # 土星：domain_summary 先讲 + 土星话术
    assert _recall_hook(recall, persona=get_persona("saturn")) == \
        "你扛着的career课题——「相信自己」，还守得住吗？"
    # 月亮：key_date 先讲 + 月亮话术
    assert _recall_hook(recall, persona=get_persona("moon")) == \
        "我记得你那时候说「考虑换工作」——现在心里还沉吗？"


def test_recall_hook_none_still_works_with_persona():
    assert _recall_hook(None, persona=get_persona("pluto")) is None
    assert _recall_hook({}, persona=get_persona("mars")) is None
