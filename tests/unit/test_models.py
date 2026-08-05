"""Phase 1 验证：共享模型契约测试。

这些测试确保冻结的 schema 不被破坏。
"""

from datetime import datetime, timezone

import pytest

from shared.enums import (
    AspectType,
    EvidencePolarity,
    FactCategory,
    HouseSystem,
    IntentDomain,
    Planet,
    Sign,
    ZodiacType,
)
from foundation.utils import birth_data_fallback
from shared.models import (
    BirthData,
    Chart,
    Conclusion,
    Evidence,
    EvidenceSet,
    Fact,
    FactSet,
    GeoLocation,
    Intent,
    IntentSlot,
    Person,
    Strategy,
    StrategyStep,
)


def make_person() -> Person:
    loc = GeoLocation(31.2304, 121.4737, timezone_name="Asia/Shanghai", place_name="上海")
    birth = BirthData(
        datetime(1990, 6, 15, 9, 30, tzinfo=timezone.utc),
        loc,
        time_known=True,
    )
    return Person(id="p1", name="测试用户", birth=birth)


def test_geolocation_validates_bounds():
    with pytest.raises(ValueError):
        GeoLocation(91.0, 0.0)
    with pytest.raises(ValueError):
        GeoLocation(0.0, 181.0)


def test_birthdata_requires_utc():
    loc = GeoLocation(0.0, 0.0)
    with pytest.raises(ValueError):
        BirthData(datetime(1990, 6, 15, 9, 30), loc)  # naive datetime


def test_birth_data_fallback_sets_noon():
    """time_known=False → 时分替换为正午 12:00，日期与时区保留。"""
    loc = GeoLocation(31.2304, 121.4737, timezone_name="Asia/Shanghai", place_name="上海")
    src = datetime(1990, 6, 15, 9, 30, tzinfo=timezone.utc)
    bd = birth_data_fallback(src, loc, time_known=False)
    assert bd.time_known is False
    assert bd.datetime_utc.hour == 12
    assert bd.datetime_utc.minute == 0
    assert bd.datetime_utc.year == 1990
    assert bd.datetime_utc.month == 6
    assert bd.datetime_utc.day == 15
    assert bd.datetime_utc.tzinfo is not None  # 时区保留


def test_birth_data_fallback_known_unchanged():
    """time_known=True → 原样透传，不碰时分。"""
    loc = GeoLocation(31.2304, 121.4737, timezone_name="Asia/Shanghai", place_name="上海")
    src = datetime(1990, 6, 15, 9, 30, tzinfo=timezone.utc)
    bd = birth_data_fallback(src, loc, time_known=True)
    assert bd.time_known is True
    assert bd.datetime_utc.hour == 9
    assert bd.datetime_utc.minute == 30


def test_person_roundtrip():
    p = make_person()
    assert p.birth.location.place_name == "上海"
    assert p.birth.time_known is True
    assert hash(p) == hash("p1")


def test_chart_construction():
    p = make_person()
    chart = Chart(
        id="c1",
        person_id=p.id,
        chart_type="natal",
        calculated_at_utc=datetime.now(timezone.utc),
        julian_day=2454774.0,
        epoch_utc=p.birth.datetime_utc,
        location="上海",
        zodiac=ZodiacType.TROPICAL,
        house_system=HouseSystem.PLACIDUS,
    )
    assert chart.zodiac == ZodiacType.TROPICAL
    assert chart.house_system == HouseSystem.PLACIDUS
    assert chart.planets == {}


def test_fact_and_factset():
    f = Fact(
        id="f1",
        category=FactCategory.POSITION,
        chart_id="c1",
        description="火星在白羊座5.3度十宫",
        extracted_at=datetime.now(timezone.utc),
        payload={"planet": "mars", "sign": "aries", "degree": 5.3, "house": 10},
    )
    fs = FactSet(id="fs1", chart_ids=["c1"], intent_domain="career", facts=[f])
    assert fs.get_by_planet(Planet.MARS) == [f]
    assert fs.get_by_category(FactCategory.POSITION) == [f]
    assert bool(fs) is True
    assert len(fs) == 1


def test_evidence_net_weight():
    ev = Evidence(
        id="e1",
        fact_id="f1",
        polarity=EvidencePolarity.POSITIVE,
        weight=3.0,
        confidence=0.9,
        evidence_confidence="high",
        domain="career",
        analysis_module="career_strength",
        reasoning="火星入庙落十宫",
        generated_at=datetime.now(timezone.utc),
    )
    es = EvidenceSet(
        id="es1",
        fact_set_id="fs1",
        domain="career",
        query_context="换工作",
        positive_evidence=[ev],
    )
    assert es.net_weight == pytest.approx(2.70)
    assert es.positive_weight == pytest.approx(2.70)
    assert es.dominant_theme == EvidencePolarity.POSITIVE


def test_strategy_root_steps():
    step = StrategyStep(
        id="s1",
        name="职业强度",
        analysis_module="domain.analysis.career_strength",
        required_facts=["position", "dignity"],
    )
    strategy = Strategy(
        id="st1",
        name="换工作分析",
        description="测试",
        intent_domains=[IntentDomain.CAREER],
        steps=[step],
    )
    assert strategy.root_steps() == [step]
    assert strategy.get_step("s1") == step


def test_intent_slot_lookup():
    slot = IntentSlot(name="timeframe", raw_value="今年", normalized_value="2026")
    intent = Intent(
        id="i1",
        raw_query="我想换工作今年合适吗",
        domain=IntentDomain.CAREER,
        subdomain="career_change",
        slots={"timeframe": slot},
        domain_confidence=0.95,
    )
    assert intent.get_slot("timeframe").normalized_value == "2026"


def test_conclusion_defaults():
    c = Conclusion(
        id="cl1",
        intent_id="i1",
        evidence_set_id="es1",
        domain="career",
        summary="盘面支持换工作",
        overall_confidence=0.8,
        overall_polarity=EvidencePolarity.POSITIVE,
    )
    assert c.overall_polarity == EvidencePolarity.POSITIVE
    assert c.findings == []
    assert c.time_periods == []
