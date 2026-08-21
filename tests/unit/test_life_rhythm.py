"""Life Rhythm 报告契约测试。"""

from datetime import datetime, timezone
import json
import zoneinfo

import pytest

from domain.astrology.calculation import NatalChartCalculator
from domain.astrology.knowledge import load_knowledge
from domain.timeline import build_life_rhythm
from shared.enums import HouseSystem
from shared.models import BirthData, GeoLocation, Person


@pytest.fixture(scope="module")
def person():
    return Person(
        id="p_xiatian_life_rhythm",
        name="夏天",
        birth=BirthData(
            datetime(1991, 3, 21, 9, 25, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(35.7, 113.35, timezone_name="Asia/Shanghai", place_name="山西陵川"),
        ),
        house_system=HouseSystem.ALCABITIUS,
    )


@pytest.fixture(scope="module")
def chart(person):
    return NatalChartCalculator().compute(person)


REF = datetime(2026, 8, 4, tzinfo=timezone.utc)


def _assert_no_old_year_lord(value):
    if isinstance(value, dict):
        assert "year_lord" not in value
        for child in value.values():
            _assert_no_old_year_lord(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_old_year_lord(child)


def test_life_rhythm_unifies_four_domain_layers(person, chart):
    """人生节律契约必须统一：本命承诺 + 法达章节 + 小限年度 + 行运触发。"""
    rhythm = build_life_rhythm(
        person,
        chart,
        load_knowledge(),
        reference=REF,
        months=4,
        domains=("career", "wealth"),
    )
    data = rhythm.to_dict()

    json.dumps(data, ensure_ascii=False)
    assert data["type"] == "life_rhythm"
    assert data["person_id"] == person.id
    assert data["chart_id"] == chart.id
    assert data["timing_authority"] == "firdaria"
    assert data["source_layers"] == [
        "natal_promise",
        "firdaria_chapter",
        "annual_activation",
        "transit_triggers",
    ]
    assert [stage["domain"] for stage in data["natal_promise"]] == ["career", "wealth"]
    assert all(stage["themes"] for stage in data["natal_promise"])
    assert data["firdaria_chapter"]["type"] == "firdaria_chapter"
    assert data["firdaria_chapter"]["timing_authority"] == "firdaria"
    assert data["firdaria_chapter"]["period"]["major_lord"] == "moon"
    assert data["firdaria_chapter"]["period"]["sub_lord"] == "mars"
    assert data["annual_activation"]["type"] == "annual_activation"
    assert data["annual_activation"]["role"] == "auxiliary"
    assert data["annual_activation"]["primary_timing_authority"] == "firdaria"
    assert len(data["transit_triggers"]) == 4
    assert all(row["type"] == "transit_trigger" for row in data["transit_triggers"])
    assert all(row["timing_authority"] == "firdaria" for row in data["transit_triggers"])
    assert all(data["annual_activation"] == row["annual_activation"] for row in data["transit_triggers"])
    _assert_no_old_year_lord(data)


def test_life_rhythm_keeps_annual_activation_auxiliary(person, chart):
    """小限宫主可参与行运观察，但不能抢法达时机权威。"""
    data = build_life_rhythm(
        person,
        chart,
        load_knowledge(),
        reference=REF,
        months=1,
        domains=("career",),
    ).to_dict()

    annual_lord = data["annual_activation"]["activation_lord"]
    trigger = data["transit_triggers"][0]
    assert annual_lord in trigger["scoring_target_planets"]
    assert set(trigger["target_planets"]).issubset(trigger["scoring_target_planets"])
    assert data["timing_authority"] == "firdaria"
    assert data["firdaria_chapter"]["timing_authority"] == "firdaria"
    assert data["annual_activation"]["role"] == "auxiliary"
    assert data["annual_activation"]["primary_timing_authority"] == "firdaria"


def test_life_rhythm_domain_months_clamped_to_timing_stack_window(person, chart):
    """Domain 直调用也只暴露当前 TimingStack 支持的 1-6 月窗口。"""
    data = build_life_rhythm(
        person,
        chart,
        load_knowledge(),
        reference=REF,
        months=12,
        domains=("career",),
    ).to_dict()

    assert data["months"] == 6
    assert len(data["transit_triggers"]) == 6
    assert all(row["timing_authority"] == "firdaria" for row in data["transit_triggers"])
