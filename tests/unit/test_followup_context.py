"""追问消解：蒸馏上下文 → 继承活跃话题 + 时间窗口偏移。

覆盖：IntentRouter 时间指代追问、直接命中优先、Timing 偏移、端到端多轮。
"""

from datetime import datetime
import zoneinfo

import pytest

from application.agent import GardenSpiritAgent
from domain.analysis import Timing
from domain.astrology.calculation import NatalChartCalculator
from domain.reasoning.intent import IntentRouter
from shared.enums import HouseSystem, IntentDomain, PersonaType
from shared.models import BirthData, GeoLocation, Person


@pytest.fixture(scope="module")
def person() -> Person:
    return Person(
        id="p_followup",
        name="测试",
        birth=BirthData(
            datetime(1991, 3, 21, 9, 25, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(35.7, 113.35, timezone_name="Asia/Shanghai", place_name="山西陵川"),
        ),
        house_system=HouseSystem.ALCABITIUS,
    )


def test_followup_time_inherits_active_topic():
    """无头时间追问 → 继承活跃话题（career/ChangeJob），不要求澄清。"""
    router = IntentRouter()
    context = {"active_domain": "career", "active_subdomain": "ChangeJob"}
    intent = router.route("那明年呢？", context=context)

    assert not intent.requires_clarification
    assert intent.domain == IntentDomain.CAREER
    assert intent.subdomain == "ChangeJob"
    slot = intent.get_slot("time_start_offset")
    assert slot is not None
    assert slot.normalized_value == "5"  # 明年 → 2027-01（相对 2026-08）


def test_followup_requires_context():
    """无上下文时，无头追问仍是澄清（不应凭空继承话题）。"""
    router = IntentRouter()
    intent = router.route("那明年呢？")
    assert intent.requires_clarification


def test_direct_hit_beats_followup():
    """直接命中领域规则时，不覆盖为追问（时间词只是背景）。"""
    router = IntentRouter()
    intent = router.route("我明年该换工作吗？", context={"active_domain": "career"})
    assert intent.domain == IntentDomain.CAREER
    assert intent.subdomain == "ChangeJob"
    assert intent.get_slot("time_start_offset") is None  # 本轮不落时间偏移槽


def test_followup_other_time_terms():
    router = IntentRouter()
    ctx = {"active_domain": "career", "active_subdomain": "ChangeJob"}
    for q, expected in [("那下个月呢？", "1"), ("那后年呢？", "17"), ("那具体哪几个月比较好？", "0")]:
        intent = router.route(q, context=ctx)
        assert not intent.requires_clarification, f"{q} 应消解"
        assert intent.get_slot("time_start_offset").normalized_value == expected


def test_timing_start_offset(person):
    """Timing 支持窗口起点偏移：偏移后窗口落在目标区间。"""
    chart = NatalChartCalculator().compute(person)
    facts = Timing().analyze(chart, person, {"window_months": 3, "start_offset_months": 5})
    windows = [f for f in facts if f.payload.get("theme") == "timing_window"]
    assert len(windows) > 0
    for w in windows:
        assert w.payload["window_start"] >= "2027-01"


def test_agent_multiturn_followup(person):
    """端到端：先问转行，再追问"那明年呢？" → 继承策略并偏移窗口。"""
    agent = GardenSpiritAgent()
    sid = "mt_test"

    first = agent.handle_message(
        sid, "我想换工作，换行业去做AI产品经理，今年合适吗？", person, PersonaType.MOON
    )
    ctx = agent.context_builder._sessions[sid]
    assert ctx.latest_intent.subdomain == "ChangeJob"

    follow = agent.handle_message(sid, "那明年呢？", person, PersonaType.MOON)
    # 不再掉进澄清
    assert "不确定你想问哪方面" not in follow
    # 窗口应包含明年（2027）
    assert "2027" in follow
