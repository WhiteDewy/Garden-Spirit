"""星灵花园 API 骨架测试（W1：/health /person /chat /profile /timeline）。

验证：
- 建档/读档往返（含出生数据解析）
- 非法出生时间 → 422
- 未知用户 → 404
- /chat 接通 Agent（无 LLM 走降级路径仍能回答）
- 对话后写回：/person/{id}/profile 出现画像（产品循环后半段）
- /person/{id}/timeline 返回成长事件
"""

import pytest
from fastapi.testclient import TestClient

from foundation.config import AppConfig

from application.api.main import create_app


@pytest.fixture(autouse=True)
def _offline_geocode(monkeypatch):
    """强制离线 geocoding——API 测试不依赖网络与 GS_AMAP_KEY（见 geocoding 模块）。"""
    monkeypatch.setenv("GS_GEOCODE_OFFLINE", "1")


@pytest.fixture(scope="module")
def client():
    config = AppConfig()
    config.storage.db_path = ":memory:"
    app = create_app(config)
    with TestClient(app) as c:
        yield c


def _person_payload() -> dict:
    return {
        "name": "测试用户",
        "birth": {
            "datetime_local": "1995-06-15T09:30:00",  # 本地墙钟时间
            "location": {"place_name": "上海"},        # 城市名 → 后端 geocode
            "time_known": True,
        },
        "gender": "F",
    }


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_person_roundtrip(client):
    resp = client.post("/person", json=_person_payload())
    assert resp.status_code == 200
    data = resp.json()
    pid = data["id"]
    assert data["name"] == "测试用户"
    assert data["place_name"] == "上海"
    assert data["time_known"] is True

    got = client.get(f"/person/{pid}")
    assert got.status_code == 200
    assert got.json()["id"] == pid
    assert got.json()["is_premium"] is False  # 会员位 v0.5 预留


def test_person_missing_datetime_422(client):
    """缺少 datetime_local（必填）→ 422。"""
    payload = _person_payload()
    del payload["birth"]["datetime_local"]
    resp = client.post("/person", json=payload)
    assert resp.status_code == 422


def test_person_not_found_404(client):
    resp = client.get("/person/ghost")
    assert resp.status_code == 404


def test_chat_requires_person(client):
    resp = client.post("/chat", json={"person_id": "ghost", "message": "你好"})
    assert resp.status_code == 404


def test_chat_then_profile_writeback(client):
    """端到端：建档 → 对话 → 写回 → 画像/时间轴出现数据。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]

    chat = client.post("/chat", json={
        "person_id": pid,
        "message": "我该不该离职？",
    })
    assert chat.status_code == 200
    data = chat.json()
    assert data["answer"]                    # 无 LLM 也有降级回答
    assert data["session_id"]
    assert data["intent_domain"] == "career"

    # 写回：画像出现（Domain 的 conclusion.summary 被并入 career 摘要）
    prof = client.get(f"/person/{pid}/profile")
    assert prof.status_code == 200
    domains = prof.json()["domain_summaries"]
    assert "career" in domains
    assert domains["career"]["summary"]

    # 写回：成长事件出现（kind=consult）
    tl = client.get(f"/person/{pid}/timeline")
    assert tl.status_code == 200
    events = tl.json()
    assert len(events) >= 1
    assert events[0]["kind"] == "consult"


def test_chat_followup_same_session(client):
    """同一 session_id 多轮追问，仍能回答（会话延续）。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    first = client.post("/chat", json={"person_id": pid, "message": "我该不该离职？"}).json()
    second = client.post("/chat", json={
        "person_id": pid,
        "session_id": first["session_id"],
        "message": "那明年呢？",
    })
    assert second.status_code == 200
    assert second.json()["session_id"] == first["session_id"]
    assert second.json()["answer"]


def test_chat_mode_echo_and_fallback(client):
    """咨询模式：接受并回传；非法 mode 安全回退 deep。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    quick = client.post("/chat", json={"person_id": pid, "message": "我该不该离职？", "mode": "quick"})
    assert quick.status_code == 200
    assert quick.json()["mode"] == "quick"

    deep = client.post("/chat", json={"person_id": pid, "message": "我该不该离职？"})
    assert deep.json()["mode"] == "deep"  # 默认

    bogus = client.post("/chat", json={"person_id": pid, "message": "你好", "mode": "bogus"})
    assert bogus.status_code == 200        # 不 500
    assert bogus.json()["mode"] == "deep"  # 回退默认


def test_journal_create_list_update(client):
    """花园日记：创建（AI 摘要）→ 列表 → 编辑。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]

    created = client.post("/journal", json={
        "person_id": pid, "content": "今天认真想了想离职的事。", "mood": "清醒",
    })
    assert created.status_code == 200
    j = created.json()
    assert j["content"] == "今天认真想了想离职的事。"
    assert j["mood"] == "清醒"
    assert j["ai_summary"]  # 降级摘要非空
    eid = j["id"]

    # 列表
    lst = client.get(f"/person/{pid}/journal")
    assert lst.status_code == 200
    assert len(lst.json()) == 1
    assert lst.json()[0]["id"] == eid

    # 编辑（用户改写成长记录后覆盖）
    upd = client.put(f"/journal/{eid}", json={"content": "改过的正文"})
    assert upd.status_code == 200
    assert upd.json()["content"] == "改过的正文"
    assert upd.json()["ai_summary"] != j["ai_summary"]

    # 时间轴出现 journal 事件
    tl = client.get(f"/person/{pid}/timeline").json()
    assert any(e["kind"] == "journal" for e in tl)


def test_journal_empty_content_422(client):
    pid = client.post("/person", json=_person_payload()).json()["id"]
    resp = client.post("/journal", json={"person_id": pid, "content": "   "})
    assert resp.status_code == 422


def test_mailbox_today_and_list(client):
    """信箱：今天来信（幂等）+ 收件箱列表。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]

    l1 = client.post("/mailbox/today", json={"person_id": pid})
    assert l1.status_code == 200
    letter = l1.json()
    assert letter["body"]
    assert letter["sender_zh"]  # 如 "月亮"

    # 幂等：同一天再取同封
    l2 = client.post("/mailbox/today", json={"person_id": pid})
    assert l2.json()["id"] == letter["id"]

    # 列表
    lst = client.get(f"/person/{pid}/letters")
    assert lst.status_code == 200
    assert len(lst.json()) == 1


def test_mailbox_today_unknown_person_404(client):
    resp = client.post("/mailbox/today", json={"person_id": "ghost"})
    assert resp.status_code == 404


def test_garden_aggregate(client):
    """花园首页聚合：今日来信 + 继续昨天 + 画像领域。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]

    # 先聊一次 → 有画像领域 + 会话摘要
    client.post("/chat", json={"person_id": pid, "message": "我该不该离职？"})

    g = client.get(f"/garden?person_id={pid}")
    assert g.status_code == 200
    data = g.json()
    assert data["letter"]["body"]                 # 今日来信
    assert data["continue_from"]["summary"]        # 继续昨天
    assert "career" in data["domains"]             # 我的宇宙领域


def test_garden_unknown_person_404(client):
    resp = client.get("/garden?person_id=ghost")
    assert resp.status_code == 404


def test_journal_update_not_found_404(client):
    resp = client.put("/journal/ghost", json={"content": "hi"})
    assert resp.status_code == 404


def test_profile_404_before_chat(client):
    """没对话过的用户，画像 404（而不是空壳）。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    resp = client.get(f"/person/{pid}/profile")
    assert resp.status_code == 404


def test_timeline_empty_before_chat(client):
    pid = client.post("/person", json=_person_payload()).json()["id"]
    resp = client.get(f"/person/{pid}/timeline")
    assert resp.status_code == 200
    assert resp.json() == []


# --- 出生地解析（geocode 路径，不做硬编码降级）---

def test_person_city_geocoded(client):
    """只给城市名 → 后端解析出经纬度（PersonOut 展示城市名 + 时区）。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    got = client.get(f"/person/{pid}").json()
    assert got["place_name"] == "上海"


def test_person_time_unknown_noon_fallback(client):
    """不知道出生时间 → time_known=false（后端正午降级）。"""
    payload = _person_payload()
    payload["birth"]["time_known"] = False
    pid = client.post("/person", json=payload).json()["id"]
    assert client.get(f"/person/{pid}").json()["time_known"] is False


def test_person_unknown_city_422(client):
    """出生地解析失败 → 422 明确报错，绝不静默用错误坐标。"""
    payload = _person_payload()
    payload["birth"]["location"] = {"place_name": "不存在的城市xyz"}
    resp = client.post("/person", json=payload)
    assert resp.status_code == 422
    assert "无法解析出生地" in resp.json()["detail"]


def test_person_missing_location_422(client):
    payload = _person_payload()
    payload["birth"]["location"] = {}
    resp = client.post("/person", json=payload)
    assert resp.status_code == 422


def test_person_explicit_coords_requires_tz(client):
    """给了经纬度但没给时区 → 422（不允许歧义时区）。"""
    payload = _person_payload()
    payload["birth"]["location"] = {"latitude": 31.23, "longitude": 121.47}
    resp = client.post("/person", json=payload)
    assert resp.status_code == 422


def test_person_explicit_coords_path(client):
    """精确路径：经纬度 + IANA 时区。"""
    payload = _person_payload()
    payload["birth"]["location"] = {
        "latitude": 31.23,
        "longitude": 121.47,
        "timezone_name": "Asia/Shanghai",
        "place_name": "手动指定",
    }
    resp = client.post("/person", json=payload)
    assert resp.status_code == 200
    assert resp.json()["place_name"] == "手动指定"


def test_person_bad_local_datetime_422(client):
    payload = _person_payload()
    payload["birth"]["datetime_local"] = "not-a-time"
    resp = client.post("/person", json=payload)
    assert resp.status_code == 422


# --- A2 关系层：信任度量 / 开场白 / 判断验证 ---


def test_chat_builds_trust(client):
    """深度咨询（deep）→ 信任分 +6，等级推进到"认识"。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    chat = client.post("/chat", json={"person_id": pid, "message": "我该不该离职？"})
    assert chat.status_code == 200
    assert chat.json()["trust_level"] == "acquaintance"  # 6 ≥ 3 < 10

    profile = client.app.state.store.get_profile(pid)
    assert profile.trust_score == 6.0
    assert profile.trust_signals == {"deep_consult": 1}


def test_casual_chat_small_trust(client):
    """问候/闲聊 → 小幅信任分（0.5），等级仍是"陌生"。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    chat = client.post("/chat", json={"person_id": pid, "message": "随便聊聊"})
    assert chat.status_code == 200
    assert chat.json()["trust_level"] == "stranger"

    profile = client.app.state.store.get_profile(pid)
    assert profile.trust_score == 0.5
    assert profile.trust_signals == {"casual_chat": 1}


def test_opening_new_vs_returning(client):
    """开场白：首次见面自我介绍；聊过后变成欢迎回来（含上次话题）。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]

    first = client.get(f"/person/{pid}/opening")
    assert first.status_code == 200
    assert "星灵" in first.json()["opening"]          # 自我介绍
    assert first.json()["trust_level"] == "stranger"

    client.post("/chat", json={"person_id": pid, "message": "我该不该离职？"})

    again = client.get(f"/person/{pid}/opening")
    assert "欢迎回来" in again.json()["opening"]      # 老用户
    assert again.json()["trust_level"] == "acquaintance"


def test_journal_builds_trust(client):
    """写日记 → 信任信号 journal（+3）。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    client.post("/journal", json={"person_id": pid, "content": "今天认真想了想离职的事。"})

    profile = client.app.state.store.get_profile(pid)
    assert profile.trust_score == 3.0
    assert profile.trust_signals == {"journal": 1}


def test_finding_feedback_bumps_trust(client):
    """验证一条沉淀判断（confirmed）→ 信任 +4，user_feedback 落库。"""
    from foundation.utils import utc_now_aware
    from shared.models import ChartProfile, VerifiedFinding

    pid = client.post("/person", json=_person_payload()).json()["id"]
    # 离线测试不产 verified_findings → 直接注入一条
    store = client.app.state.store
    profile = store.get_profile(pid)
    if profile is None:
        profile = ChartProfile(person_id=pid, created_at=utc_now_aware(), updated_at=utc_now_aware())
    profile.verified_findings.append(VerifiedFinding(
        id="vf1", statement="土星落九宫：深造是职业跃迁的必经之路", confidence=0.7,
    ))
    store.save_profile(profile)

    resp = client.post(f"/person/{pid}/findings/vf1/feedback", json={"feedback": "confirmed"})
    assert resp.status_code == 200
    assert resp.json()["trust_level"] == "acquaintance"  # 4 ≥ 3

    got = client.app.state.store.get_profile(pid)
    assert got.verified_findings[0].user_feedback == "confirmed"
    assert got.trust_score == 4.0


def test_finding_feedback_unknown_finding_404(client):
    pid = client.post("/person", json=_person_payload()).json()["id"]
    resp = client.post(f"/person/{pid}/findings/nope/feedback", json={"feedback": "confirmed"})
    assert resp.status_code == 404


def test_finding_feedback_invalid_value_422(client):
    pid = client.post("/person", json=_person_payload()).json()["id"]
    resp = client.post(f"/person/{pid}/findings/vf1/feedback", json={"feedback": "maybe"})
    assert resp.status_code == 422


# --- B1 学习层：验前事 + 反馈置信度校准 ---


def _inject_finding(client, pid: str, statement: str, confidence: float = 0.6, fid: str = "vf1"):
    """离线测试不产 verified_findings → 直接注入一条沉淀判断。"""
    from foundation.utils import utc_now_aware
    from shared.models import ChartProfile, VerifiedFinding

    store = client.app.state.store
    profile = store.get_profile(pid)
    if profile is None:
        profile = ChartProfile(person_id=pid, created_at=utc_now_aware(), updated_at=utc_now_aware())
    profile.verified_findings.append(VerifiedFinding(id=fid, statement=statement, confidence=confidence))
    store.save_profile(profile)
    return store


def test_feedback_calibrates_confidence(client):
    """B1：反馈 confirmed/refuted → 置信度 ±0.15，new_confidence 回传。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    store = _inject_finding(client, pid, "土星落九宫：深造是职业跃迁的必经之路", confidence=0.6)

    resp = client.post(f"/person/{pid}/findings/vf1/feedback", json={"feedback": "confirmed"})
    assert resp.status_code == 200
    assert resp.json()["new_confidence"] == 0.75

    got = store.get_profile(pid)
    assert got.verified_findings[0].user_feedback == "confirmed"
    assert got.verified_findings[0].confirmed_at is not None  # 首次被确认

    resp2 = client.post(f"/person/{pid}/findings/vf1/feedback", json={"feedback": "refuted"})
    assert resp2.json()["new_confidence"] == 0.6  # 0.75 - 0.15


def test_record_life_event_with_verification(client):
    """B1 端到端：记录人生事件 → 法达倒推 → 判断验上 → 置信度 +0.1 → 时间轴可见。"""
    from datetime import datetime, timezone

    from domain.learning.verifier import PLANET_ZH_LOOKUP
    from domain.timeline.firdaria import compute_firdaria

    pid = client.post("/person", json=_person_payload()).json()["id"]
    person = client.app.state.person_repo.get(pid)
    chart = client.app.state.agent._calculator.compute(person)

    event_date = datetime(2021, 9, 1, tzinfo=timezone.utc)
    period = compute_firdaria(chart.epoch_utc, chart.sect, reference=event_date)
    major_zh = PLANET_ZH_LOOKUP[period.major_lord]

    store = _inject_finding(client, pid, f"{major_zh}落9宫：深造是必经之路", confidence=0.6)

    resp = client.post(f"/person/{pid}/events", json={"label": "去留学", "occurred_at": "2021-09-01"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["calibrated"] is True
    assert data["period_major"] == period.major_lord.value
    assert data["verifications"][0]["verdict"] == "confirmed"

    got = store.get_profile(pid)
    assert got.verified_findings[0].confidence == 0.7  # +0.1
    assert any("去留学" in n for n in got.verified_findings[0].verification_notes)

    tl = client.get(f"/person/{pid}/timeline").json()
    assert any(e["kind"] == "life" and e["label"] == "去留学" for e in tl)


def test_record_life_event_bad_time_422(client):
    """事件时间格式错误 → 422。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    resp = client.post(f"/person/{pid}/events", json={"label": "xx", "occurred_at": "not-a-time"})
    assert resp.status_code == 422


def test_capability_question_gets_intro(client):
    """"我来这里能学到什么"这类元问题 → 能力介绍，不是泛泛闲聊。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    r = client.post("/chat", json={"person_id": pid, "message": "我能从里这里学到什么呀"})
    assert r.status_code == 200
    assert "星盘" in r.json()["answer"]       # 先交代身份/专业
    assert "看懂自己" in r.json()["answer"]   # 再落到能学什么
    assert "想先从哪块开始" in r.json()["answer"]


def test_capability_question_identity(client):
    """"你是谁/你能做什么/你有什么专业" → 能力介绍。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    for q in ("你是谁", "你能做什么", "这个app有什么用",
              "你擅长什么专业", "你的专业是什么"):
        r = client.post("/chat", json={"person_id": pid, "message": q})
        assert "星盘" in r.json()["answer"], q


def test_capability_not_swallow_real_question(client):
    """长句里的"学什么"是真实提问（如考研），不能被能力介绍吞掉。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    r = client.post("/chat", json={"person_id": pid, "message": "我适合学什么专业方向，考研还是直接工作"})
    # 超过 40 字上限 → 走正常意图路由（Learning/职业），不是能力介绍
    assert "想先聊哪一块" not in r.json()["answer"]


# --- B2 行动层：待验证清单 + 偏好 ---


def test_list_findings_with_status(client):
    """GET /findings：罗列全部判断 + 验证状态；pending_only 过滤。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    store = _inject_finding(client, pid, "土星落九宫：深造是必经之路", confidence=0.6, fid="f1")
    # 再注入一条已被用户确认的（并给 f1 标上领域）
    from shared.models import VerifiedFinding

    profile = store.get_profile(pid)
    profile.verified_findings[0].domain = "career"
    profile.verified_findings.append(VerifiedFinding(
        id="f2", statement="月亮落7宫：依赖核心在伴侣", confidence=0.7, user_feedback="confirmed",
        domain="relationship",
    ))
    store.save_profile(profile)

    all_items = client.get(f"/person/{pid}/findings").json()
    assert len(all_items) == 2
    statuses = {i["id"]: i["status"] for i in all_items}
    assert statuses == {"f1": "unverified", "f2": "verified"}
    assert all_items[0]["domain"] == "career"

    pending = client.get(f"/person/{pid}/findings?pending_only=true").json()
    assert [i["id"] for i in pending] == ["f1"]


def test_list_findings_404(client):
    resp = client.get("/person/ghost/findings")
    assert resp.status_code == 404


def test_preferences_roundtrip(client):
    """PUT /preferences 部分更新 → GET 返回默认补全。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]

    upd = client.put(f"/person/{pid}/preferences", json={"push_frequency": "quiet"})
    assert upd.status_code == 200
    assert upd.json()["push_frequency"] == "quiet"
    assert upd.json()["sensitive_topics"] == []       # 未设置补默认
    assert upd.json()["preferred_persona"] == ""

    got = client.get(f"/person/{pid}/preferences").json()
    assert got["push_frequency"] == "quiet"

    # 部分更新不清掉已设字段
    upd2 = client.put(f"/person/{pid}/preferences", json={"sensitive_topics": ["health"]})
    assert upd2.json()["push_frequency"] == "quiet"
    assert upd2.json()["sensitive_topics"] == ["health"]


def test_preferences_invalid_422(client):
    pid = client.post("/person", json=_person_payload()).json()["id"]
    resp = client.put(f"/person/{pid}/preferences", json={"push_frequency": "every_hour"})
    assert resp.status_code == 422

    resp2 = client.put(f"/person/{pid}/preferences", json={"preferred_persona": "nope"})
    assert resp2.status_code == 422


def test_garden_pending_verifications(client):
    """行动层表面：/garden 返回待验证判断数。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    _inject_finding(client, pid, "土星落九宫：深造是必经之路", fid="f1")

    g = client.get(f"/garden?person_id={pid}").json()
    assert g["pending_verifications"] == 1

    # 验证后计数归零
    client.post(f"/person/{pid}/findings/f1/feedback", json={"feedback": "confirmed"})
    g2 = client.get(f"/garden?person_id={pid}").json()
    assert g2["pending_verifications"] == 0
