"""Career 领域分析模块测试：Risk / Opportunity / Finance。"""

from datetime import datetime
import zoneinfo

import pytest

from domain.analysis import CareerStrength, Finance, Opportunity, Risk, Timing
from domain.astrology.common import aspects_to, house_lord
from domain.astrology.calculation import NatalChartCalculator
from domain.astrology.knowledge import load_knowledge
from shared.enums import FactCategory, Planet
from shared.models import BirthData, GeoLocation, Person


@pytest.fixture(scope="module")
def person() -> Person:
    return Person(
        id="p_mod",
        name="模块测试",
        birth=BirthData(
            datetime(1990, 6, 15, 9, 30, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(31.2304, 121.4737, timezone_name="Asia/Shanghai", place_name="上海"),
        ),
    )


@pytest.fixture(scope="module")
def chart(person) -> "Chart":
    return NatalChartCalculator().compute(person)


def test_house_lord(chart):
    kb = load_knowledge()
    lord = house_lord(chart, kb, 10)
    assert lord is not None


def test_aspects_to(chart):
    aspects = aspects_to(chart, Planet.SUN)
    assert len(aspects) > 0


def test_career_strength_produces_facts(chart):
    facts = CareerStrength().analyze(chart, None, {})
    assert len(facts) > 0
    # 应产出主题总结
    themes = [f for f in facts if f.category == FactCategory.THEME]
    assert any(t.payload.get("theme") == "career_strength" for t in themes)


def test_timing_produces_windows(chart, person):
    facts = Timing().analyze(chart, person, {"window_months": 3})
    windows = [f for f in facts if f.payload.get("theme") == "timing_window"]
    assert len(windows) > 0
    for w in windows:
        assert w.payload["window_start"] < w.payload["window_end"]
        assert w.payload["polarity"] in ("positive", "negative", "neutral")


def test_risk_produces_facts(chart):
    facts = Risk().analyze(chart, None, {})
    themes = [f for f in facts if f.category == FactCategory.THEME]
    assert any(t.payload.get("theme") == "career_risk" for t in themes)


def test_opportunity_produces_facts(chart):
    facts = Opportunity().analyze(chart, None, {})
    themes = [f for f in facts if f.category == FactCategory.THEME]
    assert any(t.payload.get("theme") == "career_opportunity" for t in themes)


def test_finance_produces_facts(chart):
    facts = Finance().analyze(chart, None, {})
    themes = [f for f in facts if f.category == FactCategory.THEME]
    assert any(t.payload.get("theme") == "career_finance" for t in themes)


def test_all_modules_registered():
    from application.agent import GardenSpiritAgent

    agent = GardenSpiritAgent()
    for name in ("CareerStrength", "Timing", "Risk", "Opportunity", "Finance"):
        assert agent.executor.has_module(name), f"{name} 未注册"
