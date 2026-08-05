"""感情评估 + 每日运势 + Timeline K 线 测试。"""

from datetime import datetime
import zoneinfo

import pytest

from application.agent import GardenSpiritAgent
from domain.analysis import Daily, MarriagePotential, RelationshipStatus
from domain.astrology.calculation import NatalChartCalculator
from domain.timeline import WindowScanner
from shared.enums import PersonaType, Planet
from shared.models import BirthData, GeoLocation, Person


@pytest.fixture(scope="module")
def person() -> Person:
    return Person(
        id="p_rel",
        name="关系测试",
        birth=BirthData(
            datetime(1990, 6, 15, 9, 30, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(31.2304, 121.4737, timezone_name="Asia/Shanghai", place_name="上海"),
        ),
    )


@pytest.fixture(scope="module")
def chart(person):
    return NatalChartCalculator().compute(person)


def test_relationship_status_module(chart, person):
    facts = RelationshipStatus().analyze(chart, person, {})
    assert len(facts) >= 3
    assert all(f.payload.get("rule_id") for f in facts)


def test_marriage_potential_module(chart, person):
    facts = MarriagePotential().analyze(chart, person, {})
    assert len(facts) >= 3


def test_daily_module(chart, person):
    facts = Daily().analyze(chart, person, {})
    assert len(facts) >= 1
    assert all(f.payload["theme"].startswith("daily_") for f in facts)


def test_timeline_scan(chart, person):
    scanner = WindowScanner()
    timeline = scanner.scan(chart, person, months=6, domain="career")
    assert len(timeline.windows) >= 20
    assert timeline.best_window is not None
    assert timeline.worst_window is not None
    assert all(w.start <= w.end for w in timeline.windows)
    # 机会分/压力分非负
    assert all(w.opportunity_score >= 0 and w.pressure_score >= 0 for w in timeline.windows)


def test_agent_relationship_status():
    """'我们感情怎么样' → RelationshipStatus 策略（非合盘，无需对方数据）。"""
    agent = GardenSpiritAgent()
    user = Person(
        id="u_rel", name="u",
        birth=BirthData(
            datetime(1990, 6, 15, 9, 30, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(31.2304, 121.4737, timezone_name="Asia/Shanghai", place_name="上海"),
        ),
    )
    answer = agent.handle_message("s_rel", "我们感情怎么样？", user, PersonaType.ZIRCON)
    ctx = agent.context_builder._sessions["s_rel"]
    # 不应要求对方数据（非具体对象）
    assert "出生时间" not in answer
    assert ctx.latest_conclusion is not None
    assert len(ctx.latest_conclusion.findings) > 0


def test_agent_marriage_potential():
    """'我适合结婚吗' → 婚姻潜力。"""
    agent = GardenSpiritAgent()
    user = Person(
        id="u_mar", name="u",
        birth=BirthData(
            datetime(1990, 6, 15, 9, 30, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(31.2304, 121.4737, timezone_name="Asia/Shanghai", place_name="上海"),
        ),
    )
    answer = agent.handle_message("s_mar", "我适合结婚吗？", user, PersonaType.ZIRCON)
    assert "出生时间" not in answer
    assert "解读" in answer or "倾向" in answer


def test_agent_daily():
    """'今天运势怎么样' → 每日解读（不再是信息不足）。"""
    agent = GardenSpiritAgent()
    user = Person(
        id="u_day", name="u",
        birth=BirthData(
            datetime(1990, 6, 15, 9, 30, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(31.2304, 121.4737, timezone_name="Asia/Shanghai", place_name="上海"),
        ),
    )
    answer = agent.handle_message("s_day", "今天运势怎么样", user, PersonaType.ZIRCON)
    assert "今日" in answer
    assert "尚未启用" not in answer  # Daily 不再缺失
