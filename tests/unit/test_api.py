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
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from foundation.config import AppConfig
from foundation.database.encryption import _generate_key

from shared.models import Letter

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


def test_persistent_db_requires_stable_encryption_key(monkeypatch, tmp_path):
    """真实文件库缺少 GS_ENCRYPTION_KEY 时拒绝启动，避免写入随机密钥密文。"""
    monkeypatch.delenv("GS_ENCRYPTION_KEY", raising=False)
    config = AppConfig()
    config.storage.db_path = str(tmp_path / "garden_spirit.db")
    config.storage.encryption_key = ""

    with pytest.raises(RuntimeError, match="GS_ENCRYPTION_KEY"):
        create_app(config)


def test_persistent_db_starts_with_configured_encryption_key(tmp_path):
    """部署显式配置稳定密钥时，文件库正常启动。"""
    config = AppConfig()
    config.storage.db_path = str(tmp_path / "garden_spirit.db")
    config.storage.encryption_key = _generate_key()

    app = create_app(config)

    assert app.state.config.storage.encryption_key == config.storage.encryption_key


def test_memory_db_does_not_require_encryption_key(monkeypatch):
    """:memory: 测试库不持久化，允许底层使用随机开发密钥。"""
    monkeypatch.delenv("GS_ENCRYPTION_KEY", raising=False)
    config = AppConfig()
    config.storage.db_path = ":memory:"
    config.storage.encryption_key = ""

    app = create_app(config)

    assert app.state.config.storage.db_path == ":memory:"


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


def test_phone_auth_creates_single_self_profile():
    """手机号是身份源：一个手机号只能绑定一个唯一本人档案。"""
    config = AppConfig()
    config.storage.db_path = ":memory:"
    config.debug = True
    app = create_app(config)
    with TestClient(app) as c:
        login = c.post("/auth/phone/verify", json={"phone": "18513821306", "code": "000000"})
        assert login.status_code == 200
        account = login.json()
        assert account["phone"] == "18513821306"
        assert account["self_person_id"] is None

        created = c.post(f"/account/{account['account_id']}/self", json=_person_payload())
        assert created.status_code == 200
        self_id = created.json()["self_person_id"]
        assert self_id
        assert created.json()["self_profile"]["birth"]["location"]["place_name"] == "上海"

        repeated_login = c.post("/auth/phone/verify", json={"phone": "18513821306", "code": "000000"})
        assert repeated_login.status_code == 200
        assert repeated_login.json()["self_person_id"] == self_id

        duplicate = c.post(f"/account/{account['account_id']}/self", json=_person_payload())
        assert duplicate.status_code == 409


def test_phone_auth_allows_any_debug_phone_with_dev_code():
    """开发临时万能码开放任意手机号，方便注册流程手测。"""
    config = AppConfig()
    config.storage.db_path = ":memory:"
    config.debug = True
    app = create_app(config)
    with TestClient(app) as c:
        resp = c.post("/auth/phone/verify", json={"phone": "13900000000", "code": "000000"})
    assert resp.status_code == 200
    assert resp.json()["phone"] == "13900000000"


def test_phone_auth_rejects_wrong_dev_code():
    """开发万能码仍限定 000000，避免任意验证码都能进。"""
    config = AppConfig()
    config.storage.db_path = ":memory:"
    config.debug = True
    app = create_app(config)
    with TestClient(app) as c:
        resp = c.post("/auth/phone/verify", json={"phone": "13900000000", "code": "123456"})
    assert resp.status_code == 403


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
    assert data["house_system"] == "B"

    got = client.get(f"/person/{pid}")
    assert got.status_code == 200
    assert got.json()["id"] == pid
    assert got.json()["is_premium"] is False  # 会员位 v0.5 预留


@pytest.mark.parametrize("house_system", ["B", "W", "P"])
def test_person_accepts_registration_house_system_choice(client, house_system):
    """注册页可在阿卡比特/整宫/普拉西德之间切换；后端按显式选择落库。"""
    payload = _person_payload()
    payload["house_system"] = house_system

    resp = client.post("/person", json=payload)

    assert resp.status_code == 200
    assert resp.json()["house_system"] == house_system


def test_person_rejects_unknown_house_system(client):
    """非法宫制应明确 422，避免前端误传时变成服务端 500。"""
    payload = _person_payload()
    payload["house_system"] = "X"

    resp = client.post("/person", json=payload)

    assert resp.status_code == 422
    assert "宫位制" in resp.json()["detail"]


def test_person_creation_generates_today_letter(client):
    """建档即生成当天来信；信箱读取只返回同一封，不再二次生成。"""
    resp = client.post("/person", json=_person_payload())
    assert resp.status_code == 200
    pid = resp.json()["id"]

    letters = client.get(f"/person/{pid}/letters")
    assert letters.status_code == 200
    data = letters.json()
    assert len(data["items"]) == 1
    assert data["total"] == 1
    assert data["items"][0]["kind"] == "daily"
    assert data["items"][0]["body"]

    today = client.post("/mailbox/today", json={"person_id": pid})
    assert today.status_code == 200
    assert today.json()["id"] == data["items"][0]["id"]


def test_mailbox_force_refresh_requires_debug(client):
    """强刷入口只给开发/管理员工具；普通配置不可用。"""
    config = AppConfig()
    config.storage.db_path = ":memory:"
    config.debug = False
    app = create_app(config)
    with TestClient(app) as c:
        pid = c.post("/person", json=_person_payload()).json()["id"]
        resp = c.post("/mailbox/today/force-refresh", json={"person_id": pid})

    assert resp.status_code == 403


def test_debug_env_enables_mailbox_force_refresh(monkeypatch):
    """本地设置 GS_DEBUG=1 后可调用强刷入口。"""
    monkeypatch.setenv("GS_DEBUG", "1")
    config = AppConfig()
    config.storage.db_path = ":memory:"
    app = create_app(config)
    with TestClient(app) as c:
        pid = c.post("/person", json=_person_payload()).json()["id"]
        first = c.post("/mailbox/today", json={"person_id": pid}).json()
        refreshed = c.post("/mailbox/today/force-refresh", json={"person_id": pid})

    assert refreshed.status_code == 200
    assert refreshed.json()["id"] == first["id"]


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
    # 咨询记录补意图/需求（喂记忆写回）：domain=八大领域，need=诉求类型
    assert events[0]["domain"] == "career"
    assert events[0]["need"] in ("heard", "soothed", "sorted", "pushed")


def test_chat_accepts_observatory_report_intent(client):
    """主题观星台入口上下文可透传到 Chat；它只做路由/澄清素材，不改变基础合约。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]

    chat = client.post("/chat", json={
        "person_id": pid,
        "message": "我想看和母亲的关系对我事业的影响",
        "report_intent": {
            "entry_source": "observatory",
            "entry_topic_key": "career",
            "primary_topic": "career",
            "secondary_topics": ["family"],
            "intent_shape": "cross_topic_influence",
            "report_type": "theme",
            "user_focus_text": "我想看和母亲的关系对我事业的影响",
        },
    })

    assert chat.status_code == 200
    data = chat.json()
    assert data["answer"]
    assert data["session_id"]
    assert data["mode"] == "deep"


def test_chat_rejects_invalid_observatory_report_intent(client):
    """报告型入口字段是受控契约；非法类型不能污染后续意图与报告编译。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]

    chat = client.post("/chat", json={
        "person_id": pid,
        "message": "我想看看最近",
        "report_intent": {
            "entry_source": "observatory",
            "entry_topic_key": "career",
            "intent_shape": "made_up_shape",
            "report_type": "weekly",
        },
    })

    assert chat.status_code == 422


def test_life_rhythm_endpoint_exposes_domain_report_contract(client):
    """Life Rhythm 独立出口：不复用成长事件 timeline，四层素材由 Domain 给出。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]

    resp = client.get(f"/person/{pid}/life-rhythm?months=3")

    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "life_rhythm"
    assert data["person_id"] == pid
    assert data["timing_authority"] == "firdaria"
    assert data["source_layers"] == [
        "natal_promise",
        "firdaria_chapter",
        "annual_activation",
        "transit_triggers",
    ]
    assert data["natal_promise"]
    assert data["firdaria_chapter"]["type"] == "firdaria_chapter"
    assert data["firdaria_chapter"]["timing_authority"] == "firdaria"
    assert data["annual_activation"]["role"] == "auxiliary"
    assert data["annual_activation"]["primary_timing_authority"] == "firdaria"
    assert len(data["transit_triggers"]) == 3
    assert all(row["timing_authority"] == "firdaria" for row in data["transit_triggers"])
    assert "year_lord" not in data
    assert "year_lord" not in data["annual_activation"]


def test_life_rhythm_months_are_bounded(client):
    """报告窗口先锁 1-6 个月，避免前端任意拉长扫描造成慢请求。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]

    resp = client.get(f"/person/{pid}/life-rhythm?months=12")

    assert resp.status_code == 422



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
    assert len(lst.json()["items"]) == 1
    assert lst.json()["items"][0]["id"] == eid

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
    assert len(lst.json()["items"]) == 1


def _keepsake_letter(pid: str, idx: int) -> Letter:
    """构造一封 keepsake 来信（供分页测试直接落库，避免依赖聊天情绪分支）。"""
    return Letter(
        id=f"ks-{idx}",
        person_id=pid,
        letter_date=f"2026-08-{idx:02d}",
        sender="moon",
        title="「想被抱抱的我」来信",
        body=f"正文{idx}",
        kind="keepsake",
        created_at=datetime(2026, 8, idx, 12, 0, 0, tzinfo=timezone.utc),
        metadata={},
    )


def test_letters_paginated_kind_filter(client):
    """信箱分页：kind 过滤 + page_size 翻页 + has_more 正确（默认 20 条一页）。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    store = client.app.state.store
    for i in range(1, 6):
        store.save_letter(_keepsake_letter(pid, i))

    # 默认全部：5 keepsake + 1 daily（建档生成）
    all_ = client.get(f"/person/{pid}/letters").json()
    assert all_["total"] == 6
    assert len(all_["items"]) == 6
    assert all_["has_more"] is False

    # kind=keepsake / kind=daily 过滤
    ks = client.get(f"/person/{pid}/letters", params={"kind": "keepsake"}).json()
    assert ks["total"] == 5
    assert all(l["kind"] == "keepsake" for l in ks["items"])
    dy = client.get(f"/person/{pid}/letters", params={"kind": "daily"}).json()
    assert dy["total"] == 1
    assert dy["items"][0]["kind"] == "daily"

    # page_size=2 翻页：第 3 页只剩 1 条，has_more 收敛
    p1 = client.get(f"/person/{pid}/letters", params={"kind": "keepsake", "page": 1, "page_size": 2}).json()
    assert len(p1["items"]) == 2
    assert p1["total"] == 5
    assert p1["has_more"] is True
    p3 = client.get(f"/person/{pid}/letters", params={"kind": "keepsake", "page": 3, "page_size": 2}).json()
    assert len(p3["items"]) == 1
    assert p3["has_more"] is False


def test_journal_paginated(client):
    """手账分页：20 条一页，has_more 按 total 正确收敛。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    for i in range(3):
        client.post("/journal", json={"person_id": pid, "content": f"日记{i}"})

    page = client.get(f"/person/{pid}/journal", params={"page": 1, "page_size": 2}).json()
    assert page["total"] == 3
    assert len(page["items"]) == 2
    assert page["has_more"] is True

    page2 = client.get(f"/person/{pid}/journal", params={"page": 2, "page_size": 2}).json()
    assert len(page2["items"]) == 1
    assert page2["has_more"] is False


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
    returning = again.json()["opening"]
    # 老用户：认得出名字 + 记得上次话题 + 回访亲昵（同天刚聊过 → "我们又见面了"）
    assert "测试用户" in returning
    assert "上次我们聊到" in returning
    assert any(h in returning for h in ("我们又见面了", "昨天才聊过", "欢迎回来"))
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
    chart = client.app.state.chart_cache.get_or_compute(person)

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


def test_personas_endpoint_returns_ten_planet_personas(client):
    """GET /personas 暴露前端星灵选择器需要的 10 颗星灵。"""
    resp = client.get("/personas")
    assert resp.status_code == 200
    personas = resp.json()
    assert len(personas) == 10
    assert [p["key"] for p in personas] == [
        "sun", "moon", "mercury", "venus", "mars",
        "jupiter", "saturn", "uranus", "neptune", "pluto",
    ]
    assert all(p["name"] and p["healing_name"] and p["style"] for p in personas)


def test_chat_uses_preferred_persona_when_body_omits_persona(client):
    """用户未显式传 persona 时，/chat 读取偏好人格并写入会话。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    client.put(f"/person/{pid}/preferences", json={"preferred_persona": "saturn"})

    chat = client.post("/chat", json={
        "person_id": pid,
        "session_id": "sess_pref_saturn",
        "message": "你好，今天随便聊聊",
    })
    assert chat.status_code == 200

    ctx = client.app.state.agent.get_session_context("sess_pref_saturn")
    assert ctx is not None
    assert ctx.persona.value == "saturn"


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


# --- Web Push（真实推送通道）---

def test_push_vapid_public_key(client):
    resp = client.get("/push/vapid-public-key")
    assert resp.status_code == 200
    body = resp.json()
    assert "public_key" in body
    assert isinstance(body["public_key"], str)


def test_push_subscribe_unknown_person_404(client):
    resp = client.post("/push/subscribe", json={
        "person_id": "ghost",
        "subscription": {"endpoint": "ep_x", "keys": {"p256dh": "a", "auth": "b"}},
    })
    assert resp.status_code == 404


def test_push_subscribe_then_unsubscribe(client):
    pid = client.post("/person", json=_person_payload()).json()["id"]
    sub = {"endpoint": "https://push.example/ep_1",
           "keys": {"p256dh": "k1", "auth": "k2"}}

    r1 = client.post("/push/subscribe", json={"person_id": pid, "subscription": sub})
    assert r1.status_code == 200
    assert r1.json()["ok"] is True

    # 幂等 upsert：同 endpoint 重复订阅不炸
    r2 = client.post("/push/subscribe", json={"person_id": pid, "subscription": sub})
    assert r2.status_code == 200
    assert r2.json()["ok"] is True

    r3 = client.post("/push/unsubscribe",
                     json={"person_id": pid, "endpoint": "https://push.example/ep_1"})
    assert r3.status_code == 200
    assert r3.json()["deleted"] is True

    # 已删 → deleted False（幂等）
    r4 = client.post("/push/unsubscribe",
                     json={"person_id": pid, "endpoint": "https://push.example/ep_1"})
    assert r4.json()["deleted"] is False


def test_push_trigger_skips_quiet(client):
    """push_frequency=quiet → 触发时跳过（不生成来信、不推送）。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    client.put(f"/person/{pid}/preferences", json={"push_frequency": "quiet"})

    resp = client.post("/push/trigger")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_persons"] >= 1
    assert data["skipped_quiet"] >= 1   # 至少这个 quiet 用户被跳过
    assert data["pushed"] == 0          # 无 VAPID 私钥（测试）永远推不出


def test_push_trigger_no_subscription(client):
    """daily 用户但没订阅过（无 endpoint）→ 记为 skipped_no_sub，不崩。"""
    client.post("/person", json=_person_payload())

    resp = client.post("/push/trigger")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_persons"] >= 1
    assert data["skipped_no_sub"] >= 1  # 至少这个 daily 无订阅用户
    assert data["pushed"] == 0


# --- 首页红点（来信未读 + 待验证）---

def test_garden_letter_unread_true(client):
    """刚生成的今日来信 read_at=None → 首页信箱红点亮起。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    g = client.get(f"/garden?person_id={pid}").json()
    assert g["letter_unread"] is True
    # 信件本身也带 read_at 字段（None = 未读）
    assert g["letter"]["read_at"] is None


def test_mark_read_today_clears_unread(client):
    """打开信箱（read-today）→ 首页再拉 /garden → 信箱红点消除。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    assert client.get(f"/garden?person_id={pid}").json()["letter_unread"] is True

    r = client.post(f"/person/{pid}/letters/read-today")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["marked"] == 1

    # 已标记后，今日来信 read_at 非空 → 红点消失；幂等再标 → 0
    g = client.get(f"/garden?person_id={pid}").json()
    assert g["letter_unread"] is False
    assert g["letter"]["read_at"] is not None
    assert client.post(f"/person/{pid}/letters/read-today").json()["marked"] == 0


def test_mark_read_today_unknown_person_404(client):
    resp = client.post("/person/ghost/letters/read-today")
    assert resp.status_code == 404


def test_garden_pending_verifications_dot(client):
    """有待验证判断 → pending_verifications>0（我的宇宙 nav 红点后端字段）。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    _inject_finding(client, pid, "土星落九宫：深造是必经之路", fid="dot1")
    g = client.get(f"/garden?person_id={pid}").json()
    assert g["pending_verifications"] == 1


def _seed_report_sources(client, pid: str, session_id: str = "report_s1") -> str:
    """Report Compiler MVP：测试只种后端已有素材，不走 LLM 造结论。"""
    from foundation.utils import new_id, utc_now_aware
    from shared.enums import PersonaType, Role
    from shared.models import (
        ChartProfile,
        Conversation,
        DialogueTurn,
        DomainSummary,
        FragmentLight,
        Letter,
        LifeEvent,
        MemoryItem,
        VerifiedFinding,
    )

    store = client.app.state.store
    now = utc_now_aware()
    conv = Conversation(
        id=session_id,
        person_id=pid,
        persona=PersonaType.MOON,
        started_at=now,
        is_active=True,
    )
    conv.add_turn(DialogueTurn(
        id=new_id("t"),
        user_message="我想把最近事业和情绪整理一下",
        assistant_response="我们先把已确认的线索收拢。",
        persona_used=PersonaType.MOON,
        timestamp=now,
    ))
    store.save_conversation(conv, summary="事业和情绪整理")

    profile = ChartProfile(person_id=pid, created_at=now, updated_at=now)
    profile.domain_summaries["career"] = DomainSummary(
        domain="career",
        summary="最近在重新评估职业方向。",
        confidence=0.8,
        evidence_notes=["来自对话"],
        updated_at=now,
    )
    profile.verified_findings.append(VerifiedFinding(
        id="vf_report",
        statement="土星线索显示事业选择需要长期结构。",
        confidence=0.72,
        domain="career",
    ))
    store.save_profile(profile)

    store.save_memory_item(MemoryItem(
        id="mem_report",
        session_id=session_id,
        person_id=pid,
        role=Role.USER,
        content="我担心工作方向走错了",
        timestamp=now,
    ))
    store.save_life_event(LifeEvent(
        id="evt_report",
        person_id=pid,
        occurred_at=now,
        label="完成事业复盘",
        kind="consult",
        domain="career",
    ))
    store.save_letter(Letter(
        id="lt_report",
        person_id=pid,
        letter_date="2026-08-21",
        sender="moon",
        title="月亮来信",
        body="你愿意把这段卡住说出来。",
        kind="keepsake",
        created_at=now,
    ))
    store.append_fragment_lights(
        pid,
        [FragmentLight(subtype_id="moon_tide", delta=5, kind="outpouring", source="工作方向很乱")],
        session_id=session_id,
    )
    return session_id


def test_compile_chat_digest_uses_backend_sources_and_refs(client):
    """Report Compiler 小报告：只整理已有素材，且每段都有 source_refs。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]
    session_id = _seed_report_sources(client, pid)

    resp = client.post(
        f"/person/{pid}/reports/compile",
        json={"report_type": "chat_digest", "source": "chat", "session_id": session_id, "topic": "事业复盘"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "report"
    assert data["status"] == "draft"
    assert data["report_type"] == "chat_digest"
    assert data["person_id"] == pid
    assert data["sections"]
    assert all(s["source_refs"] for s in data["sections"])
    ref_types = {ref["type"] for section in data["sections"] for ref in section["source_refs"]}
    assert {"profile", "finding", "conversation", "memory", "timeline", "fragment_light", "letter"}.issubset(ref_types)
    assert {ref["type"] for ref in data["source_refs"]} == ref_types
    assert "net_score" not in str(data)


def test_compile_report_without_backend_material_returns_422(client):
    """无对话/画像/记忆/来信等素材 → 不伪造报告，安全 422。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]

    resp = client.post(
        f"/person/{pid}/reports/compile",
        json={"report_type": "chat_digest", "source": "chat", "topic": "空白主题"},
    )

    assert resp.status_code == 422
    assert "暂无足够素材" in resp.json()["detail"]


def test_compile_life_rhythm_report_preserves_timing_authority_boundary(client):
    """Life Rhythm 报告草稿：引用 Domain 四层素材，不暴露旧 year_lord / net_score。"""
    pid = client.post("/person", json=_person_payload()).json()["id"]

    resp = client.post(
        f"/person/{pid}/reports/compile",
        json={"report_type": "life_rhythm", "source": "observatory", "months": 3},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["report_type"] == "life_rhythm"
    assert data["sections"]
    keys = {s["key"] for s in data["sections"]}
    assert {"life_rhythm_authority", "firdaria_chapter", "annual_activation"}.issubset(keys)
    assert all(s["source_refs"] for s in data["sections"])
    assert {ref["type"] for ref in data["source_refs"]} == {"life_rhythm"}
    text = str(data)
    assert "法达是主章节" in text
    assert "annual_activation" in text
    assert "year_lord" not in text
    assert "net_score" not in text
