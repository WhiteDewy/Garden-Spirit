"""情绪感知层测试（陪伴协议第 1 步"感知"）。

验证：
- LLM 分类情绪/诉求 → EmotionResult（source=llm）
- LLM 返回无效情绪/诉求 → 规则兜底（source=rule）
- 无 LLM → 规则兜底（离线可测）
- 规则兜底的关键案例：难过→low/soothed；该不该→sorted；好累→tired/soothed
- 空消息 → 中性默认 {calm, heard}
- needs_care：负面情绪为真，平静为假
- 接线：agent.handle_message 后 ctx.emotion_result 被挂载
- 接线：API /chat 返回 emotion / request_type 字段
"""

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from shared.enums import EmotionState, RequestType
from shared.models import BirthData, GeoLocation, Person

from application.agent import GardenSpiritAgent
from application.conversation.emotion import EmotionPerception


@pytest.fixture(scope="module")
def client():
    from foundation.config import AppConfig
    from application.api.main import create_app

    config = AppConfig()
    config.storage.db_path = ":memory:"
    app = create_app(config)
    with TestClient(app) as c:
        yield c


class FakeEmotionLLM:
    """有 complete() 的假 LLM——返回结构化 JSON 字符串。"""

    available = True

    def __init__(self, payload: dict):
        self._payload = payload

    def complete(self, prompt, system=None, **kwargs):
        return json.dumps(self._payload)


def _make_person() -> Person:
    return Person(
        id="p_emotion",
        name="情绪测试",
        birth=BirthData(
            datetime(1990, 6, 15, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
            GeoLocation(31.2304, 121.4737, timezone_name="Asia/Shanghai", place_name="上海"),
        ),
    )


# --- LLM 路径 ---


def test_llm_classifies_emotion_and_request():
    p = EmotionPerception(FakeEmotionLLM(
        {"emotion": "low", "request": "soothed", "confidence": 0.9}
    ))
    r = p.perceive("今天好难过")
    assert r.emotion == EmotionState.LOW
    assert r.request == RequestType.SOOTHED
    assert r.source == "llm"
    assert r.confidence == 0.9


def test_llm_invalid_emotion_falls_back_to_rules():
    """LLM 发明情绪 → 不信它，规则兜底。"""
    p = EmotionPerception(FakeEmotionLLM(
        {"emotion": "existential_dread", "request": "soothed", "confidence": 0.9}
    ))
    r = p.perceive("今天好难过，想哭")
    assert r.emotion == EmotionState.LOW   # 规则：难过/想哭
    assert r.source == "rule"


def test_llm_invalid_request_defaults_heard():
    """LLM 发明诉求 → 兜底 heard（不崩）。"""
    p = EmotionPerception(FakeEmotionLLM(
        {"emotion": "happy", "request": "dance", "confidence": 0.8}
    ))
    r = p.perceive("太开心了")
    assert r.emotion == EmotionState.HAPPY
    assert r.request == RequestType.HEARD


def test_llm_empty_result_falls_back():
    p = EmotionPerception(FakeEmotionLLM({}))
    r = p.perceive("今天好累")
    assert r.emotion == EmotionState.TIRED
    assert r.source == "rule"


# --- memorable（§6.1 日常/正面分享时刻 → 词条式 keepsake） ---


def test_llm_memorable_true():
    """LLM 判定"值得记住的分享"（具体在意之事）→ memorable=True。"""
    p = EmotionPerception(FakeEmotionLLM(
        {"emotion": "calm", "request": "heard", "confidence": 0.9, "memorable": True}
    ))
    r = p.perceive("最近在看九门")
    assert r.memorable is True


def test_llm_memorable_string_bool():
    """LLM 返回字符串 "true" → 归一成 True（兼容宽松输出）。"""
    p = EmotionPerception(FakeEmotionLLM(
        {"emotion": "calm", "request": "heard", "memorable": "true"}
    ))
    r = p.perceive("最近在看九门")
    assert r.memorable is True


def test_llm_memorable_false_explicit():
    """LLM 明确给 false（功能性短句）→ False。"""
    p = EmotionPerception(FakeEmotionLLM(
        {"emotion": "calm", "request": "heard", "memorable": False}
    ))
    r = p.perceive("好的")
    assert r.memorable is False


def test_llm_memorable_default_false():
    """LLM 没给 memorable → 默认 False（宁缺毋滥）。"""
    p = EmotionPerception(FakeEmotionLLM(
        {"emotion": "calm", "request": "heard", "confidence": 0.8}
    ))
    r = p.perceive("最近在看九门")
    assert r.memorable is False


def test_rule_fallback_memorable_false():
    """规则兜底没有 memorable 信息 → False（确定性默认）。"""
    r = EmotionPerception().perceive("最近在看九门")
    assert r.memorable is False


# --- 规则兜底 ---


def test_rule_no_llm():
    p = EmotionPerception(llm_client=None)
    r = p.perceive("今天心情不好")
    assert r.emotion == EmotionState.LOW
    assert r.request == RequestType.SOOTHED
    assert r.source == "rule"


def test_rule_sad_soothed():
    p = EmotionPerception()
    r = p.perceive("被老板骂了，好难过，想哭")
    assert r.emotion == EmotionState.LOW
    assert r.request == RequestType.SOOTHED


def test_rule_decision_sorted():
    """该不该 → sorted（被梳理）。"""
    p = EmotionPerception()
    r = p.perceive("我该不该换工作")
    assert r.request == RequestType.SORTED


def test_rule_tired_soothed():
    p = EmotionPerception()
    r = p.perceive("好累啊，撑不住了")
    assert r.emotion == EmotionState.TIRED
    assert r.request == RequestType.SOOTHED


def test_rule_angry():
    p = EmotionPerception()
    r = p.perceive("气死我了")
    assert r.emotion == EmotionState.ANGRY


def test_rule_positive_sharing_heard():
    """纯分享见闻（无负面情绪）→ calm / heard（分享被接住，不处方化）。"""
    p = EmotionPerception()
    r = p.perceive("今天看了天空之城，画面真美")
    assert r.emotion == EmotionState.CALM
    assert r.request == RequestType.HEARD


def test_rule_empty_message_neutral():
    p = EmotionPerception()
    r = p.perceive("")
    assert r.emotion == EmotionState.CALM
    assert r.request == RequestType.HEARD
    r2 = p.perceive(None)
    assert r2.emotion == EmotionState.CALM


# --- needs_care（软牵引门控前置） ---


def test_needs_care_negative():
    assert EmotionPerception().perceive("好难过").needs_care is True
    assert EmotionPerception().perceive("好焦虑").needs_care is True
    assert EmotionPerception().perceive("好累").needs_care is True


def test_needs_care_calm_is_false():
    assert EmotionPerception().perceive("今天天气不错").needs_care is False


# --- 接线：agent 主循环 ---


def test_agent_stores_emotion_on_context():
    agent = GardenSpiritAgent()
    person = _make_person()
    agent.handle_message("sess_emo", "今天好难过，想哭", person)
    ctx = agent.get_session_context("sess_emo")
    assert ctx is not None
    assert ctx.emotion_result is not None
    assert ctx.emotion_result.emotion == EmotionState.LOW
    assert ctx.emotion_result.request == RequestType.SOOTHED


def test_agent_emotion_on_consult_intent():
    """咨询意图也挂载情绪（不影响占星管线）。"""
    agent = GardenSpiritAgent()
    person = _make_person()
    agent.handle_message("sess_emo2", "我该不该换工作", person)
    ctx = agent.get_session_context("sess_emo2")
    assert ctx.emotion_result is not None
    assert ctx.emotion_result.request == RequestType.SORTED


# --- 接线：API /chat ---


def test_chat_api_exposes_emotion(client):
    pid = client.post("/person", json={
        "name": "情绪API",
        "birth": {
            "datetime_local": "1995-06-15T09:30:00",
            "location": {"place_name": "上海"},
            "time_known": True,
        },
        "gender": "F",
    }).json()["id"]

    chat = client.post("/chat", json={
        "person_id": pid,
        "message": "今天好难过，想哭",
    })
    assert chat.status_code == 200
    data = chat.json()
    assert data["emotion"] == "low"
    assert data["request_type"] == "soothed"
