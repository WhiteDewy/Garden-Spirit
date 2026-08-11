"""Phase 4 集成测试：Career/ChangeJob 端到端。

从用户话语到结论，走通完整链路（无 LLM）。
"""

from datetime import datetime
import zoneinfo

import pytest

from application.agent import GardenSpiritAgent
from domain.reasoning.intent import IntentRouter
from shared.enums import IntentDomain, PersonaType
from shared.models import BirthData, GeoLocation, Person


@pytest.fixture(scope="module")
def person() -> Person:
    return Person(
        id="p_career",
        name="测试用户",
        birth=BirthData(
            datetime(1990, 6, 15, 9, 30, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(31.2304, 121.4737, timezone_name="Asia/Shanghai", place_name="上海"),
        ),
    )


@pytest.fixture(scope="module")
def agent() -> GardenSpiritAgent:
    return GardenSpiritAgent()


def test_intent_router_change_job():
    intent = IntentRouter().route("我想换工作，今年合适吗")
    assert intent.domain == IntentDomain.CAREER
    assert intent.subdomain == "ChangeJob"
    assert not intent.requires_clarification


def test_intent_router_family():
    intent = IntentRouter().route("我原生家庭对我影响大吗")
    assert intent.domain == IntentDomain.FAMILY


def test_intent_router_requires_clarification():
    """真正模糊的输入才需澄清（问候已路由到 Chat，不再澄清）。"""
    intent = IntentRouter().route("我想问点事")
    assert intent.requires_clarification


def test_full_pipeline_change_job(agent, person):
    """从话语到回答的完整链路。"""
    answer = agent.handle_message(
        "session_1", "我想换工作，今年合适吗？", person, PersonaType.MOON
    )
    # 有实质回答，不是澄清提问
    assert "换工作" in answer or "职业" in answer or "询问" in answer
    assert "解读" in answer

    # 会话状态已更新
    ctx = agent.context_builder._sessions["session_1"]
    assert ctx.latest_intent is not None
    assert ctx.latest_conclusion is not None
    assert ctx.latest_conclusion.overall_confidence > 0.0
    assert len(ctx.latest_conclusion.findings) > 0


def test_astrology_domain_does_not_need_llm(agent, person):
    """原则二：无 LLM 也能给出完整结论。"""
    answer = agent.handle_message(
        "session_2", "我的事业运怎么样？", person, PersonaType.URANUS
    )
    assert "解读" in answer


def test_pipeline_is_deterministic(agent, person):
    """同一输入产出确定性结论（无随机性）。"""
    a1 = agent.handle_message("session_3", "我要不要创业？", person, PersonaType.MOON)
    a2 = agent.handle_message("session_3b", "我要不要创业？", person, PersonaType.MOON)
    assert a1 == a2
