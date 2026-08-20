"""陪伴协议测试（self_map_design §7.2/§7.3）—— 随聊轨道的接住/镜映/递出口门控。

验证：
- should_use_companion：Chat → 陪伴；负面情绪+被安慰/被听见 → 陪伴；咨询领域 → 咨询
- companion_reply：LLM 路径（自由度只在"怎么疗愈"）+ 规则兜底（共情+镜映+开口）
- build_companion_instruction：硬线——禁止占星结论
- can_offer_chart：诉求=被梳理/被推动 且 信任达标 → 递盘；否则绝不递
- soft_pull_line：SORTED/PUSHED 有话术，HEARD/SOOTHED → None
- 接线：agent 主循环走陪伴轨道 → last_was_companion=True
- 接线：API /chat 递出口——被安慰绝不附软牵引，被梳理+信任达标才附
"""

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from shared.enums import EmotionState, IntentDomain, PersonaType, RequestType, TrustLevel
from shared.models import BirthData, GeoLocation, Intent, Person

from application.agent import GardenSpiritAgent
from application.conversation.companion import (
    build_companion_instruction,
    can_offer_chart,
    companion_reply,
    should_use_companion,
    soft_pull_line,
)
from application.conversation.emotion import EmotionPerception, EmotionResult


@pytest.fixture(scope="module")
def client():
    from foundation.config import AppConfig
    from application.api.main import create_app

    config = AppConfig()
    config.storage.db_path = ":memory:"
    app = create_app(config)
    with TestClient(app) as c:
        yield c


class FakeLLM:
    """有 complete() 的假 LLM——返回固定文本（陪伴回复用）。"""

    available = True

    def __init__(self, text: str):
        self._text = text

    def complete(self, prompt, system=None, **kwargs):
        return self._text


def _make_person() -> Person:
    return Person(
        id="p_companion",
        name="陪伴测试",
        birth=BirthData(
            datetime(1990, 6, 15, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
            GeoLocation(31.2304, 121.4737, timezone_name="Asia/Shanghai", place_name="上海"),
        ),
    )


def _intent(domain: IntentDomain, subdomain: str = "") -> Intent:
    from foundation.utils import new_id

    return Intent(
        id=new_id("intent"),
        raw_query="测试",
        domain=domain,
        subdomain=subdomain,
    )


def _emotion(state: EmotionState, request: RequestType) -> EmotionResult:
    return EmotionResult(emotion=state, request=request, source="rule")


# ---------------------------------------------------------------------------
# should_use_companion（§8 兜底：含糊/分享/倾诉 → 先陪伴）
# ---------------------------------------------------------------------------


def test_companion_chat_subdomain():
    """Chat 子领域 → 陪伴（"随便聊聊"）。"""
    assert should_use_companion(_intent(IntentDomain.DAILY, "Chat"), None) is True


def test_companion_emotional_outpouring():
    """负面情绪 + 被安慰 → 陪伴（绝不处方化）。"""
    er = _emotion(EmotionState.LOW, RequestType.SOOTHED)
    assert should_use_companion(_intent(IntentDomain.EMOTION, "Emotion"), er) is True


def test_companion_heard_positive():
    """分享（被听见，无负面情绪）→ 陪伴。"""
    er = _emotion(EmotionState.CALM, RequestType.HEARD)
    assert should_use_companion(_intent(IntentDomain.DAILY, ""), er) is True


def test_not_companion_consult_domain():
    """明确咨询领域（career）→ 咨询管线。"""
    assert should_use_companion(_intent(IntentDomain.CAREER, "Career"), None) is False


def test_not_companion_daily_fortune():
    """daily 点名"运势"（subdomain=Daily）→ 咨询。"""
    assert should_use_companion(_intent(IntentDomain.DAILY, "Daily"), None) is False


def test_companion_daily_no_subdomain():
    """daily 无细分（分享/迷茫，未点名运势）→ 陪伴兜底。"""
    assert should_use_companion(_intent(IntentDomain.DAILY, ""), None) is True


def test_sorted_request_not_auto_companion():
    """被梳理（该不该…）：情绪正但诉求是想理清 → 不强行陪伴，留咨询/澄清。"""
    er = _emotion(EmotionState.CALM, RequestType.SORTED)
    assert should_use_companion(_intent(IntentDomain.CAREER, "Career"), er) is False


# ---------------------------------------------------------------------------
# build_companion_instruction（硬线：陪伴不是解盘）
# ---------------------------------------------------------------------------


def test_instruction_is_healing_not_consult():
    """硬线：疗愈陪伴不是解盘；情绪被感知但不标签化命名。"""
    system = build_companion_instruction("星灵", EmotionState.LOW)
    assert "疗愈陪伴" in system
    assert "不是\"解盘\"" in system
    assert "占星结论" in system         # Domain 唯一产出占星结论
    assert "低落" in system              # 情绪仍被感知（但作为"不要说"的反例）
    assert "不要贴标签" in system


def test_instruction_bans_purple_psychology():
    """杀紫色心理分析腔 + 热线模板腔（林间式自然陪伴）。"""
    system = build_companion_instruction("星灵", EmotionState.CALM)
    assert "禁止以下腔调" in system
    assert "心理分析腔" in system
    assert "热线模板腔" in system
    assert "泛起的涟漪" in system
    assert "我听见了" in system  # 明确列为禁止的热线腔


def test_instruction_allows_light_astrology_but_not_consult():
    """允许轻量星盘联想（疗愈的一部分），但不给判断/吉凶。"""
    system = build_companion_instruction("星灵", EmotionState.CALM)
    assert "轻量星盘联想" in system or "联想" in system
    assert "不要给判断" in system
    assert "不要分析吉凶" in system
    assert "木星在九宫" in system   # 联想示例


# ---------------------------------------------------------------------------
# companion_reply（LLM 路径 + 规则兜底）
# ---------------------------------------------------------------------------


def test_companion_reply_llm_path():
    """LLM 可用 → 用 LLM 的话（自由度在"怎么疗愈"）。"""
    llm = FakeLLM("嗯，我听见了。你今天真的很不容易，想哭就哭，我在。")
    reply = companion_reply(
        "今天好难过，想哭",
        _emotion(EmotionState.LOW, RequestType.SOOTHED),
        llm_client=llm,
        persona=PersonaType.MOON,
    )
    assert "我听见了" in reply
    assert "占星" not in reply  # 硬线：陪伴回复里绝不出现解盘


def test_companion_reply_fallback_no_llm():
    """无 LLM → 规则兜底：共情（接住）+ 原话回映（镜映）+ 开口。"""
    reply = companion_reply(
        "今天好难过，想哭",
        _emotion(EmotionState.LOW, RequestType.SOOTHED),
        llm_client=None,
    )
    assert "难过" in reply or "不容易" in reply   # 共情
    assert "「今天好难过，想哭」" in reply        # 镜映（原话）
    assert "我都在" in reply                      # 开口
    assert "占星" not in reply


def test_companion_reply_llm_failure_falls_back():
    """LLM 抛异常 → 规则兜底（降级不阻断）。"""

    class BrokenLLM:
        available = True

        def complete(self, prompt, system=None, **kwargs):
            raise RuntimeError("llm down")

    reply = companion_reply(
        "今天好难过，想哭",
        _emotion(EmotionState.LOW, RequestType.SOOTHED),
        llm_client=BrokenLLM(),
    )
    assert "我都在" in reply


# ---------------------------------------------------------------------------
# can_offer_chart + soft_pull_line（§7.3 纯逻辑门控，LLM 无权决定）
# ---------------------------------------------------------------------------


def test_can_offer_sorted_acquaintance():
    assert can_offer_chart(RequestType.SORTED, TrustLevel.ACQUAINTANCE) is True


def test_can_offer_pushed_trusted():
    assert can_offer_chart(RequestType.PUSHED, TrustLevel.TRUSTED) is True


def test_cannot_offer_heard():
    """被听见 → 绝不递盘（递盘=没听见你）。"""
    assert can_offer_chart(RequestType.HEARD, TrustLevel.INTIMATE) is False


def test_cannot_offer_soothed():
    """被安慰 → 绝不递盘（先陪，不急着讲盘）。"""
    assert can_offer_chart(RequestType.SOOTHED, TrustLevel.TRUSTED) is False


def test_cannot_offer_stranger():
    """诉求达标但信任未达标（陌生）→ 不递盘。"""
    assert can_offer_chart(RequestType.SORTED, TrustLevel.STRANGER) is False


def test_soft_pull_lines():
    assert soft_pull_line(RequestType.SORTED) is not None
    assert soft_pull_line(RequestType.PUSHED) is not None
    assert soft_pull_line(RequestType.HEARD) is None
    assert soft_pull_line(RequestType.SOOTHED) is None


# ---------------------------------------------------------------------------
# 接线：agent 主循环
# ---------------------------------------------------------------------------


def test_agent_companion_track_sets_flags():
    agent = GardenSpiritAgent()
    person = _make_person()
    reply = agent.handle_message("sess_c1", "今天好难过，想哭", person)
    ctx = agent.get_session_context("sess_c1")
    assert ctx is not None
    assert ctx.last_was_companion is True
    assert ctx.last_was_chat is True          # casual 信号（信任层小幅加分）
    assert ctx.emotion_result.request == RequestType.SOOTHED
    assert "我都在" in reply                   # 接住+镜映+开口


def test_agent_consult_does_not_enter_companion():
    """咨询意图（该不该换工作）→ 咨询管线，不进陪伴轨道。"""
    agent = GardenSpiritAgent()
    person = _make_person()
    agent.handle_message("sess_c2", "我该不该换工作", person)
    ctx = agent.get_session_context("sess_c2")
    assert ctx.last_was_companion is False
    assert ctx.latest_conclusion is not None   # 真出了占星结论


def test_agent_begin_turn_clears_consult_state_for_chat():
    """咨询后的闲聊不能沿用上一轮 conclusion，避免 API 误报碎片/来信面板。"""
    agent = GardenSpiritAgent()
    person = _make_person()
    agent.handle_message("sess_c3", "我该不该换工作", person)
    ctx = agent.get_session_context("sess_c3")
    assert ctx.latest_conclusion is not None

    agent.handle_message("sess_c3", "你好", person)

    assert ctx.last_was_chat is True
    assert ctx.last_was_companion is False
    assert ctx.latest_conclusion is None
    assert ctx.emotion_result is None
    assert ctx.fragments == []


# ---------------------------------------------------------------------------
# 接线：API /chat 递出口
# ---------------------------------------------------------------------------


def _create_person(client) -> str:
    pid = client.post("/person", json={
        "name": "陪伴API",
        "birth": {
            "datetime_local": "1995-06-15T09:30:00",
            "location": {"place_name": "上海"},
            "time_known": True,
        },
        "gender": "F",
    }).json()["id"]
    return pid


def _to_acquaintance(client, pid):
    """写一篇日记 → 信任分 +3.0 → 认识（ACQUAINTANCE ≥ 3.0）。"""
    r = client.post("/journal", json={"person_id": pid, "content": "今天有点乱，但想坚持下去。", "mood": "平静"})
    assert r.status_code == 200


def test_chat_no_soft_pull_for_soothed(client):
    """被安慰 → 即使信任达标也不附软牵引（先陪，不递盘）。"""
    pid = _create_person(client)
    _to_acquaintance(client, pid)

    chat = client.post("/chat", json={"person_id": pid, "message": "今天好难过，想哭"})
    assert chat.status_code == 200
    data = chat.json()
    assert data["emotion"] == "low"
    assert data["request_type"] == "soothed"
    assert "盘上" not in data["answer"]  # 没有递盘


def test_chat_soft_pull_for_sorted_at_acquaintance(client):
    """被梳理 + 信任认识 → 陪伴后附软牵引递盘，且点名共振星灵（§7.3）。"""
    pid = _create_person(client)
    _to_acquaintance(client, pid)

    chat = client.post("/chat", json={
        "person_id": pid,
        "message": "我有点迷茫，该不该继续现在这条路",
    })
    assert chat.status_code == 200
    data = chat.json()
    assert data["request_type"] == "sorted"
    # 语境定刻报告"迷茫"→ 海王星被触动 → 软牵引指名海王星（不是泛泛"盘上可能有条线"）
    assert "海王星" in data["answer"]
    # 陪伴在前：递盘前必须先接住/镜映，不能上来就递盘
    assert data["answer"].index("想聊的话，我都在") < data["answer"].index("盘上")


def test_chat_no_soft_pull_for_sorted_stranger(client):
    """被梳理但还陌生 → 不递盘（信任门槛未达标）。"""
    pid = _create_person(client)  # 信任=0 → 陌生

    chat = client.post("/chat", json={
        "person_id": pid,
        "message": "我有点迷茫，该不该继续现在这条路",
    })
    assert chat.status_code == 200
    data = chat.json()
    assert data["trust_level"] == "stranger"
    assert "盘上" not in data["answer"]
