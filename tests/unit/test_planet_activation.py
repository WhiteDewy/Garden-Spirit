"""星灵激活测试（self_map_design §1.1.1 语境定刻）。

验证：
- 10 星灵目录：古典十大，不含交点/凯龙/莉莉丝
- LLM 分类：受控枚举（发明 id 丢弃）、限 3 颗
- 规则兜底：关键词命中 → 对应星灵（离线可测）
- 空消息 → 不激活
- PlanetActivation：主信号 primary = 第一颗（共振星灵）
- 接线：agent 随聊轨道填 ctx.planet_activation（星灵 + 抓手 + 情绪/诉求）
- 接线：咨询轨道不激活（方向由 Domain 出，不需要语境定刻）
- 软牵引：soft_pull_line 支持共振星灵指名
"""

import json

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from shared.enums import EmotionState, Planet, RequestType
from shared.models import BirthData, GeoLocation, Person

from application.agent import GardenSpiritAgent
from application.conversation.planet_activation import (
    ACTIVATABLE_PLANETS,
    PlanetActivation,
    PlanetActivationClassifier,
)

from application.conversation.companion import soft_pull_line


@pytest.fixture(scope="module")
def client():
    from foundation.config import AppConfig
    from application.api.main import create_app

    config = AppConfig()
    config.storage.db_path = ":memory:"
    app = create_app(config)
    with TestClient(app) as c:
        yield c


class FakePlanetLLM:
    """有 complete() 的假 LLM——返回星灵 id 列表 JSON。"""

    available = True

    def __init__(self, planet_ids: list[str]):
        self._ids = planet_ids

    def complete(self, prompt, system=None, **kwargs):
        return json.dumps({"planets": self._ids})


def _make_person() -> Person:
    return Person(
        id="p_planet",
        name="星灵测试",
        birth=BirthData(
            datetime(1990, 6, 15, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
            GeoLocation(31.2304, 121.4737, timezone_name="Asia/Shanghai", place_name="上海"),
        ),
    )


# ---------------------------------------------------------------------------
# 目录：10 星灵
# ---------------------------------------------------------------------------


def test_activatable_planets_are_classical_ten():
    values = {p.value for p in ACTIVATABLE_PLANETS}
    assert values == {
        "sun", "moon", "mercury", "venus", "mars",
        "jupiter", "saturn", "uranus", "neptune", "pluto",
    }


def test_activatable_excludes_nodes_and_asteroids():
    """交点/凯龙/莉莉丝不是 10 星灵——激活只认古典十大。"""
    for p in (Planet.NORTH_NODE, Planet.SOUTH_NODE, Planet.CHIRON, Planet.LILITH):
        assert p not in ACTIVATABLE_PLANETS


# ---------------------------------------------------------------------------
# LLM 分类（受控枚举）
# ---------------------------------------------------------------------------


def test_llm_classify_valid_planets():
    c = PlanetActivationClassifier(FakePlanetLLM(["moon", "mars"]))
    assert c.classify("今天好难过") == [Planet.MOON, Planet.MARS]


def test_llm_classify_drops_invented_ids():
    """LLM 发明星灵 → 丢弃（只能从 10 个里选，不能发明）。"""
    c = PlanetActivationClassifier(FakePlanetLLM(["bogus_star", "venus", "north_node"]))
    assert c.classify("测试") == [Planet.VENUS]   # north_node 非 10 星灵也丢弃


def test_llm_classify_caps_at_max():
    many = ["sun", "moon", "mars", "venus", "jupiter"]
    c = PlanetActivationClassifier(FakePlanetLLM(many))
    assert c.classify("测试") == [Planet.SUN, Planet.MOON, Planet.MARS]


def test_llm_classify_empty_list_is_valid():
    """LLM 判断无星灵被触动 → 空数组（不激活，不触发兜底）。"""
    c = PlanetActivationClassifier(FakePlanetLLM([]))
    assert c.classify("你好") == []


def test_llm_classify_failure_falls_back():
    """LLM 返回非法结构 → 规则兜底。"""

    class BrokenLLM:
        available = True

        def complete(self, prompt, system=None, **kwargs):
            return "not json at all"

    c = PlanetActivationClassifier(BrokenLLM())
    assert c.classify("今天好难过，想哭") == [Planet.MOON]


# ---------------------------------------------------------------------------
# 规则兜底（无 LLM）
# ---------------------------------------------------------------------------


def test_rule_fallback_sadness_to_moon():
    c = PlanetActivationClassifier()
    assert c.classify("今天好难过，想哭") == [Planet.MOON]


def test_rule_fallback_anger_to_mars():
    c = PlanetActivationClassifier()
    assert c.classify("气死我了，真的太生气了") == [Planet.MARS]


def test_rule_fallback_pressure_to_saturn():
    c = PlanetActivationClassifier()
    assert c.classify("工作压力好大，责任都在我身上") == [Planet.SATURN]


def test_rule_fallback_achievement_to_sun():
    c = PlanetActivationClassifier()
    assert c.classify("最近很有成就感，找到了人生目标") == [Planet.SUN]


def test_rule_fallback_multi_planet_ordering():
    """多星激活：主信号在前。生气→火星（主），旅行→木星（次）。"""
    c = PlanetActivationClassifier()
    result = c.classify("被老板骂了，好生气，想辞职去旅行")
    assert result == [Planet.MARS, Planet.JUPITER]


def test_rule_fallback_empty_message():
    c = PlanetActivationClassifier()
    assert c.classify("") == []
    assert c.classify(None) == []


def test_rule_fallback_no_activation():
    c = PlanetActivationClassifier()
    assert c.classify("嗯嗯，好的") == []


# ---------------------------------------------------------------------------
# PlanetActivation 数据
# ---------------------------------------------------------------------------


def test_primary_is_first_planet():
    act = PlanetActivation(planets=[Planet.MOON, Planet.MARS], trigger="原话")
    assert act.primary == Planet.MOON
    assert PlanetActivation(planets=[]).primary is None


def test_activation_carries_emotion_request():
    act = PlanetActivation(
        planets=[Planet.MOON],
        trigger="今天好难过，想哭",
        emotion=EmotionState.LOW,
        request=RequestType.SOOTHED,
    )
    assert act.emotion == EmotionState.LOW
    assert act.request == RequestType.SOOTHED
    assert act.trigger == "今天好难过，想哭"


# ---------------------------------------------------------------------------
# 接线：agent 随聊轨道填激活
# ---------------------------------------------------------------------------


def test_agent_sets_activation_on_companion():
    agent = GardenSpiritAgent()
    person = _make_person()
    agent.handle_message("sess_p1", "今天好难过，想哭", person)
    ctx = agent.get_session_context("sess_p1")
    assert ctx.last_was_companion is True
    act = ctx.planet_activation
    assert act is not None
    assert act.planets == [Planet.MOON]
    assert act.trigger == "今天好难过，想哭"        # 抓手 = 用户原话
    assert act.emotion == EmotionState.LOW           # 当下情绪（EmotionPerception 出）
    assert act.request == RequestType.SOOTHED        # 诉求（EmotionPerception 出）
    assert act.primary == Planet.MOON                # 共振星灵


def test_agent_no_activation_on_consult():
    """咨询轨道不激活（方向由 Domain 出，语境定刻只管随聊）。"""
    agent = GardenSpiritAgent()
    person = _make_person()
    agent.handle_message("sess_p2", "我该不该换工作", person)
    ctx = agent.get_session_context("sess_p2")
    assert ctx.latest_conclusion is not None
    assert ctx.planet_activation is None


def test_agent_no_activation_on_greeting():
    """问候快路径不激活（没进陪伴轨道，无情绪感知）。"""
    agent = GardenSpiritAgent()
    person = _make_person()
    agent.handle_message("sess_p3", "你好", person)
    ctx = agent.get_session_context("sess_p3")
    assert ctx.planet_activation is None


# ---------------------------------------------------------------------------
# 软牵引共振星灵（§7.3）
# ---------------------------------------------------------------------------


def test_soft_pull_line_with_planet():
    assert "月亮" in soft_pull_line(RequestType.SORTED, Planet.MOON)
    assert "土星" in soft_pull_line(RequestType.PUSHED, Planet.SATURN)


def test_soft_pull_line_generic_when_no_planet():
    assert "盘上可能有条线" in soft_pull_line(RequestType.SORTED)
    assert soft_pull_line(RequestType.SORTED, None) == soft_pull_line(RequestType.SORTED)


def test_soft_pull_line_never_for_accepting_requests():
    """被听见/被安慰 → 即使给了共振星灵也不递盘。"""
    assert soft_pull_line(RequestType.HEARD, Planet.MOON) is None
    assert soft_pull_line(RequestType.SOOTHED, Planet.SUN) is None


def test_soft_pull_line_unknown_planet_fallback():
    """未知星灵值 → 通用占位（不 500）。"""
    assert soft_pull_line(RequestType.SORTED, Planet.CHIRON) is not None
