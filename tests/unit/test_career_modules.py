"""Career 领域分析模块测试：Risk / Opportunity / Finance。"""

from copy import deepcopy
from datetime import datetime, timezone
import zoneinfo

import pytest

from domain.analysis import CareerStrength, Finance, Opportunity, Risk, Timing
from domain.astrology.common import aspects_to, house_lord
from domain.astrology.evidence import EvidenceBuilder
from domain.astrology.calculation import NatalChartCalculator
from domain.astrology.knowledge import load_knowledge
from shared.enums import AspectApplication, AspectType, ChartType, DignityState, EvidencePolarity, FactCategory, HouseSystem, Planet, PlanetSpeed, Sect, Sign, ZodiacType
from shared.models import (
    Aspect,
    BirthData,
    Chart,
    ChartAcceptance,
    ChartPlanet,
    EclipticPosition,
    GeoLocation,
    HouseCusp,
    HousePosition,
    Person,
    SignPosition,
    FactSet,
)



def _venus_virgo_mixed_chart() -> Chart:
    """金星处女 10.5°：落陷 + 三分/界/面，旧净分为 +2，容易误判为纯支撑。"""
    now = datetime.now(timezone.utc)
    return Chart(
        id="career_mixed_dignity",
        person_id="p",
        chart_type=ChartType.NATAL,
        calculated_at_utc=now,
        julian_day=0.0,
        epoch_utc=now,
        location="",
        zodiac=ZodiacType.TROPICAL,
        house_system=HouseSystem.WHOLE_SIGN,
        planets={
            Planet.VENUS: ChartPlanet(
                planet=Planet.VENUS,
                ecliptic=EclipticPosition(longitude=160.5),
                sign=SignPosition(sign=Sign.VIRGO, degree_absolute=160.5, degree_in_sign=10.5),
                house=HousePosition(house=5, cusp_degree=90.0, distance_from_cusp=70.5),
                speed=PlanetSpeed.DIRECT,
                speed_deg_per_day=1.0,
            )
        },
        house_cusps={
            1: HouseCusp(house=1, degree=330.0, sign=Sign.PISCES),
            2: HouseCusp(house=2, degree=30.0, sign=Sign.TAURUS),
            3: HouseCusp(house=3, degree=60.0, sign=Sign.GEMINI),
            4: HouseCusp(house=4, degree=60.0, sign=Sign.GEMINI),
            5: HouseCusp(house=5, degree=90.0, sign=Sign.CANCER),
            6: HouseCusp(house=6, degree=120.0, sign=Sign.LEO),
            7: HouseCusp(house=7, degree=150.0, sign=Sign.VIRGO),
            8: HouseCusp(house=8, degree=180.0, sign=Sign.LIBRA),
            9: HouseCusp(house=9, degree=210.0, sign=Sign.SCORPIO),
            10: HouseCusp(house=10, degree=30.0, sign=Sign.TAURUS),
            11: HouseCusp(house=11, degree=270.0, sign=Sign.CAPRICORN),
            12: HouseCusp(house=12, degree=300.0, sign=Sign.AQUARIUS),
        },
        midheaven=SignPosition(sign=Sign.TAURUS, degree_absolute=30.0, degree_in_sign=0.0),
        sect=Sect.DAY,
    )


def _career_risk_house_chart(planet: Planet, house: int) -> Chart:
    """只触发位置型职业风险，避免相位/尊贵干扰风险符号回归。"""
    now = datetime.now(timezone.utc)
    planets = {
        Planet.SUN: ChartPlanet(
            planet=Planet.SUN,
            ecliptic=EclipticPosition(longitude=10.0),
            sign=SignPosition(sign=Sign.ARIES, degree_absolute=10.0, degree_in_sign=10.0),
            house=HousePosition(house=1, cusp_degree=0.0, distance_from_cusp=10.0),
            speed=PlanetSpeed.DIRECT,
            speed_deg_per_day=1.0,
        ),
        Planet.SATURN: ChartPlanet(
            planet=Planet.SATURN,
            ecliptic=EclipticPosition(longitude=300.0),
            sign=SignPosition(sign=Sign.AQUARIUS, degree_absolute=300.0, degree_in_sign=0.0),
            house=HousePosition(house=1, cusp_degree=270.0, distance_from_cusp=30.0),
            speed=PlanetSpeed.DIRECT,
            speed_deg_per_day=0.1,
        ),
    }
    cp = planets[planet]
    planets[planet] = ChartPlanet(
        planet=cp.planet,
        ecliptic=cp.ecliptic,
        sign=cp.sign,
        house=HousePosition(house=house, cusp_degree=cp.house.cusp_degree, distance_from_cusp=cp.house.distance_from_cusp),
        speed=cp.speed,
        speed_deg_per_day=cp.speed_deg_per_day,
    )
    return Chart(
        id=f"career_risk_{planet.value}_{house}",
        person_id="p",
        chart_type=ChartType.NATAL,
        calculated_at_utc=now,
        julian_day=0.0,
        epoch_utc=now,
        location="",
        zodiac=ZodiacType.TROPICAL,
        house_system=HouseSystem.WHOLE_SIGN,
        planets=planets,
        house_cusps={
            1: HouseCusp(house=1, degree=0.0, sign=Sign.ARIES),
            2: HouseCusp(house=2, degree=30.0, sign=Sign.TAURUS),
            3: HouseCusp(house=3, degree=60.0, sign=Sign.GEMINI),
            4: HouseCusp(house=4, degree=90.0, sign=Sign.CANCER),
            5: HouseCusp(house=5, degree=120.0, sign=Sign.LEO),
            6: HouseCusp(house=6, degree=150.0, sign=Sign.VIRGO),
            7: HouseCusp(house=7, degree=180.0, sign=Sign.LIBRA),
            8: HouseCusp(house=8, degree=210.0, sign=Sign.SCORPIO),
            9: HouseCusp(house=9, degree=240.0, sign=Sign.SAGITTARIUS),
            10: HouseCusp(house=10, degree=270.0, sign=Sign.CAPRICORN),
            11: HouseCusp(house=11, degree=300.0, sign=Sign.AQUARIUS),
            12: HouseCusp(house=12, degree=330.0, sign=Sign.PISCES),
        },
        midheaven=SignPosition(sign=Sign.CAPRICORN, degree_absolute=270.0, degree_in_sign=0.0),
        sect=Sect.DAY,
    )


def _jupiter_sagittarius_strength_chart() -> Chart:
    """木星射手入庙：触发 CareerStrength/Opportunity 的正向 DIGNITY fact。"""
    now = datetime.now(timezone.utc)
    return Chart(
        id="career_jupiter_dignity",
        person_id="p",
        chart_type=ChartType.NATAL,
        calculated_at_utc=now,
        julian_day=0.0,
        epoch_utc=now,
        location="",
        zodiac=ZodiacType.TROPICAL,
        house_system=HouseSystem.WHOLE_SIGN,
        planets={
            Planet.JUPITER: ChartPlanet(
                planet=Planet.JUPITER,
                ecliptic=EclipticPosition(longitude=250.0),
                sign=SignPosition(sign=Sign.SAGITTARIUS, degree_absolute=250.0, degree_in_sign=10.0),
                house=HousePosition(house=10, cusp_degree=240.0, distance_from_cusp=10.0),
                speed=PlanetSpeed.DIRECT,
                speed_deg_per_day=0.1,
            ),
        },
        house_cusps={
            1: HouseCusp(house=1, degree=330.0, sign=Sign.PISCES),
            2: HouseCusp(house=2, degree=0.0, sign=Sign.ARIES),
            3: HouseCusp(house=3, degree=30.0, sign=Sign.TAURUS),
            4: HouseCusp(house=4, degree=60.0, sign=Sign.GEMINI),
            5: HouseCusp(house=5, degree=90.0, sign=Sign.CANCER),
            6: HouseCusp(house=6, degree=120.0, sign=Sign.LEO),
            7: HouseCusp(house=7, degree=150.0, sign=Sign.VIRGO),
            8: HouseCusp(house=8, degree=180.0, sign=Sign.LIBRA),
            9: HouseCusp(house=9, degree=210.0, sign=Sign.SCORPIO),
            10: HouseCusp(house=10, degree=240.0, sign=Sign.SAGITTARIUS),
            11: HouseCusp(house=11, degree=270.0, sign=Sign.CAPRICORN),
            12: HouseCusp(house=12, degree=300.0, sign=Sign.AQUARIUS),
        },
        midheaven=SignPosition(sign=Sign.SAGITTARIUS, degree_absolute=240.0, degree_in_sign=0.0),
        sect=Sect.DAY,
    )


def _enrichment_carrier_aspect_chart() -> Chart:
    """默认事业目标不命中；只有定位层承载者会触发相位事实。"""
    now = datetime.now(timezone.utc)
    return Chart(
        id="career_enrichment_carriers",
        person_id="p",
        chart_type=ChartType.NATAL,
        calculated_at_utc=now,
        julian_day=0.0,
        epoch_utc=now,
        location="",
        zodiac=ZodiacType.TROPICAL,
        house_system=HouseSystem.WHOLE_SIGN,
        planets={
            Planet.VENUS: ChartPlanet(
                planet=Planet.VENUS,
                ecliptic=EclipticPosition(longitude=190.0),
                sign=SignPosition(sign=Sign.LIBRA, degree_absolute=190.0, degree_in_sign=10.0),
                house=HousePosition(house=5, cusp_degree=120.0, distance_from_cusp=70.0),
                speed=PlanetSpeed.DIRECT,
                speed_deg_per_day=1.0,
            ),
            Planet.MARS: ChartPlanet(
                planet=Planet.MARS,
                ecliptic=EclipticPosition(longitude=100.0),
                sign=SignPosition(sign=Sign.CANCER, degree_absolute=100.0, degree_in_sign=10.0),
                house=HousePosition(house=2, cusp_degree=30.0, distance_from_cusp=70.0),
                speed=PlanetSpeed.DIRECT,
                speed_deg_per_day=1.0,
            ),
            Planet.MERCURY: ChartPlanet(
                planet=Planet.MERCURY,
                ecliptic=EclipticPosition(longitude=70.0),
                sign=SignPosition(sign=Sign.GEMINI, degree_absolute=70.0, degree_in_sign=10.0),
                house=HousePosition(house=4, cusp_degree=90.0, distance_from_cusp=20.0),
                speed=PlanetSpeed.DIRECT,
                speed_deg_per_day=1.0,
            ),
        },
        house_cusps={
            1: HouseCusp(house=1, degree=330.0, sign=Sign.PISCES),
            2: HouseCusp(house=2, degree=0.0, sign=Sign.ARIES),
            3: HouseCusp(house=3, degree=60.0, sign=Sign.GEMINI),
            4: HouseCusp(house=4, degree=90.0, sign=Sign.CANCER),
            5: HouseCusp(house=5, degree=120.0, sign=Sign.LEO),
            6: HouseCusp(house=6, degree=150.0, sign=Sign.VIRGO),
            7: HouseCusp(house=7, degree=180.0, sign=Sign.LIBRA),
            8: HouseCusp(house=8, degree=210.0, sign=Sign.SCORPIO),
            9: HouseCusp(house=9, degree=240.0, sign=Sign.SAGITTARIUS),
            10: HouseCusp(house=10, degree=270.0, sign=Sign.CAPRICORN),
            11: HouseCusp(house=11, degree=300.0, sign=Sign.AQUARIUS),
            12: HouseCusp(house=12, degree=330.0, sign=Sign.PISCES),
        },
        midheaven=SignPosition(sign=Sign.CAPRICORN, degree_absolute=270.0, degree_in_sign=0.0),
        aspects=[
            Aspect(
                Planet.MARS,
                Planet.VENUS,
                AspectType.SQUARE,
                90.0,
                1.0,
                AspectApplication.APPLYING,
            ),
            Aspect(
                Planet.VENUS,
                Planet.MERCURY,
                AspectType.TRINE,
                120.0,
                1.0,
                AspectApplication.APPLYING,
            ),
        ],
        sect=Sect.DAY,
    )


def _assert_dignity_payload_auditable(fact):
    payload = fact.payload
    assert "raw_score" in payload
    assert "essential_pos" in payload
    assert "essential_neg" in payload
    assert isinstance(payload["raw_score"], int)
    assert isinstance(payload["essential_pos"], float)
    assert isinstance(payload["essential_neg"], float)


def _assert_split_axis_payload_auditable(payload):
    assert "raw_score" in payload
    assert "essential_pos" in payload
    assert "essential_neg" in payload
    assert isinstance(payload["raw_score"], int)
    assert isinstance(payload["essential_pos"], float)
    assert isinstance(payload["essential_neg"], float)


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
        assert w.payload["timing_authority"] == "firdaria"
        assert w.payload["firdaria_major_lord"] in w.payload["target_planets"]
        assert w.payload["firdaria_sub_lord"] in w.payload["target_planets"]
        annual = w.payload["annual_activation"]
        assert annual["type"] == "annual_activation"
        assert annual["role"] == "auxiliary"
        assert annual["primary_timing_authority"] == "firdaria"
        assert annual["activation_lord"] in w.payload["annual_target_planets"]
        assert annual["activation_lord"] in w.payload["scoring_target_planets"]
        assert "year_lord" not in annual


def test_timing_targets_include_question_significators(chart):
    """Timing 行运窗口打到法达领主 + 本轮问题征象星/宫主星，不再固定旧年度领主/太阳。"""
    timing = Timing(load_knowledge())
    targets = timing._timing_targets(
        chart,
        Planet.MOON,
        Planet.MARS,
        {"focus_planets": ["venus"], "focus_house_lords": [10]},
    )
    assert {Planet.MOON, Planet.MARS, Planet.VENUS}.issubset(targets)
    assert house_lord(chart, load_knowledge(), 10) in targets


def test_timing_targets_merge_focus_houses_and_lord_houses(chart):
    """Timing 同时接收显式宫主星追踪宫位与聚焦宫位，不能二选一丢信号。"""
    timing = Timing(load_knowledge())
    targets = timing._timing_targets(
        chart,
        Planet.MOON,
        Planet.MARS,
        {"focus_house_lords": [10], "focus_houses": [7]},
    )
    assert house_lord(chart, load_knowledge(), 10) in targets
    assert house_lord(chart, load_knowledge(), 7) in targets


def test_timing_helper_targets_from_reception_are_auditable(chart, person):
    """Timing 额外扫描互溶/接纳帮手星，但不把帮手混进直接目标星。"""
    chart = deepcopy(chart)
    chart.receptions = []
    chart.acceptances = [ChartAcceptance(
        acceptor=Planet.JUPITER,
        accepted=Planet.VENUS,
        dignities=(DignityState.EXALTATION,),
        dignity_type=DignityState.EXALTATION,
        score=4,
        aspect_type=AspectType.TRINE,
        aspect_nature="HARMONIOUS",
        description_zh="木星接纳金星",
    )]
    facts = Timing().analyze(
        chart,
        person,
        {"window_months": 1, "_enrichment": {"focus_planets": ["venus"]}},
    )
    window = next(f for f in facts if f.payload.get("theme") == "timing_window")
    assert "venus" in window.payload["target_planets"]
    assert "jupiter" not in window.payload["target_planets"]
    assert window.payload["helper_target_planets"] == ["jupiter"]
    assert "jupiter" in window.payload["scoring_target_planets"]
    assert "帮手星" in window.description


def test_timing_helper_targets_do_not_duplicate_direct_targets(chart):
    """若帮手星本身已是法达/问题目标，helper_targets 不重复暴露。"""
    chart = deepcopy(chart)
    chart.receptions = []
    chart.acceptances = [ChartAcceptance(
        acceptor=Planet.MOON,
        accepted=Planet.VENUS,
        dignities=(DignityState.DOMICILE,),
        dignity_type=DignityState.DOMICILE,
        score=5,
        aspect_type=AspectType.CONJUNCTION,
        aspect_nature="HARMONIOUS",
        description_zh="月亮接纳金星",
    )]
    timing = Timing(load_knowledge())
    targets = {Planet.MOON, Planet.VENUS}
    helpers = timing._helper_targets(chart, targets)
    assert helpers.isdisjoint(targets)


def test_timing_window_payload_exposes_firdaria_targets(chart, person):
    facts = Timing().analyze(
        chart,
        person,
        {"window_months": 1, "_enrichment": {"focus_planets": ["venus"]}},
    )
    window = next(f for f in facts if f.payload.get("theme") == "timing_window")
    assert window.payload["timing_authority"] == "firdaria"
    assert "venus" in window.payload["target_planets"]
    annual = window.payload["annual_activation"]
    assert annual["role"] == "auxiliary"
    assert annual["primary_timing_authority"] == "firdaria"
    assert window.payload["annual_target_planets"] == [annual["activation_lord"]]
    assert set(window.payload["annual_target_planets"]).issubset(window.payload["scoring_target_planets"])
    assert "year_lord" not in window.payload
    assert "年度小限" in window.description
    assert "法达" in window.description
    assert "年主星" not in window.description


def test_risk_produces_facts(chart):
    facts = Risk().analyze(chart, None, {})
    themes = [f for f in facts if f.category == FactCategory.THEME]
    assert any(t.payload.get("theme") == "career_risk" for t in themes)


def test_risk_negative_score_maps_to_negative_polarity():
    """职业风险分是负向计分：分数低于阈值时必须暴露为 NEGATIVE，而不是误判 neutral。"""
    facts = Risk().analyze(_venus_virgo_mixed_chart(), None, {})
    theme = next(
        f for f in facts
        if f.category == FactCategory.THEME and f.payload.get("theme") == "career_risk"
    )

    assert theme.payload["score"] < -1.0
    assert theme.payload["polarity"] == EvidencePolarity.NEGATIVE.value


def test_risk_twelfth_house_obstacle_uses_negative_score():
    """事业行星十二宫是风险项，必须扣分，不能抵消凶星/尊贵风险。"""
    facts = Risk().analyze(_career_risk_house_chart(Planet.SUN, 12), None, {})
    obstacle = next(
        f for f in facts
        if f.category == FactCategory.POSITION and f.payload.get("planet") == "sun"
    )
    theme = next(
        f for f in facts
        if f.category == FactCategory.THEME and f.payload.get("theme") == "career_risk"
    )

    assert obstacle.payload["score"] == -1.5
    assert theme.payload["score"] == -1.5
    assert theme.payload["polarity"] == EvidencePolarity.NEGATIVE.value


def test_risk_saturn_sixth_house_workload_uses_negative_score():
    """土星六宫是工作负荷风险项，风险模块内分数方向应保持负向。"""
    facts = Risk().analyze(_career_risk_house_chart(Planet.SATURN, 6), None, {})
    workload = next(
        f for f in facts
        if f.category == FactCategory.POSITION and f.payload.get("planet") == "saturn"
    )
    theme = next(
        f for f in facts
        if f.category == FactCategory.THEME and f.payload.get("theme") == "career_risk"
    )

    assert workload.payload["score"] == -1.0
    assert theme.payload["score"] == -1.0
    assert theme.payload["polarity"] == EvidencePolarity.NEUTRAL.value


def test_risk_uses_enrichment_house_lords_as_dynamic_targets():
    """Risk 不只扫固定事业目标：定位层给到的 7R 也必须进入压力相位扫描。"""
    chart = _enrichment_carrier_aspect_chart()

    assert not Risk().analyze(chart, None, {})

    facts = Risk().analyze(
        chart,
        None,
        {"_enrichment": {"focus_house_lords": [7]}},
    )
    aspect = next(f for f in facts if f.category == FactCategory.ASPECT)

    assert aspect.payload["theme"] == "career_risk"
    assert {aspect.payload["body1"], aspect.payload["body2"]} == {"mars", "venus"}
    assert any(f.payload.get("theme") == "career_risk" for f in facts)


def test_opportunity_produces_facts(chart):
    facts = Opportunity().analyze(chart, None, {})
    themes = [f for f in facts if f.category == FactCategory.THEME]
    assert any(t.payload.get("theme") == "career_opportunity" for t in themes)


def test_opportunity_uses_enrichment_focus_houses_as_dynamic_targets():
    """Opportunity 不只扫固定事业目标：定位层聚焦宫位的宫主星也必须进入助力扫描。"""
    chart = _enrichment_carrier_aspect_chart()

    assert not Opportunity().analyze(chart, None, {})

    facts = Opportunity().analyze(
        chart,
        None,
        {"_enrichment": {"focus_houses": [3]}},
    )
    aspect = next(f for f in facts if f.category == FactCategory.ASPECT)

    assert aspect.payload["theme"] == "career_opportunity"
    assert {aspect.payload["body1"], aspect.payload["body2"]} == {"venus", "mercury"}
    assert any(f.payload.get("theme") == "career_opportunity" for f in facts)


def test_career_strength_uses_enrichment_house_lords_as_dynamic_targets():
    """CareerStrength 不只看固定事业行星：定位层承载者也要进入尊贵/位置扫描。"""
    chart = _enrichment_carrier_aspect_chart()

    default_facts = CareerStrength().analyze(chart, None, {})
    assert not any(f.payload.get("planet") == "venus" for f in default_facts)

    facts = CareerStrength().analyze(
        chart,
        None,
        {"_enrichment": {"focus_house_lords": [7]}},
    )

    venus_dignity = next(
        f
        for f in facts
        if f.category == FactCategory.DIGNITY and f.payload.get("planet") == "venus"
    )
    assert venus_dignity.payload["theme"] == "career_strength"
    assert venus_dignity.payload["essential_pos"] > 0


def test_finance_produces_facts(chart):
    facts = Finance().analyze(chart, None, {})
    themes = [f for f in facts if f.category == FactCategory.THEME]
    assert any(t.payload.get("theme") == "career_finance" for t in themes)


def test_finance_uses_enrichment_focus_houses_as_dynamic_aspect_targets():
    """Finance 保持二/八宫核心逻辑，同时把定位层聚焦宫主星纳入财务相位扫描。"""
    chart = _enrichment_carrier_aspect_chart()

    default_facts = Finance().analyze(chart, None, {})
    assert not any(f.category == FactCategory.ASPECT for f in default_facts)

    facts = Finance().analyze(
        chart,
        None,
        {"_enrichment": {"focus_houses": [3]}},
    )
    aspect = next(f for f in facts if f.category == FactCategory.ASPECT)

    assert aspect.payload["theme"] == "career_finance"
    assert {aspect.payload["body1"], aspect.payload["body2"]} == {"venus", "mercury"}
    assert any(f.payload.get("theme") == "career_finance" for f in facts)


def test_career_strength_mixed_debility_does_not_become_positive_theme():
    """职业强度消费 assess_planet：金星处女净分为正，也不能把落陷十宫主顶成正向主题。"""
    facts = CareerStrength().analyze(_venus_virgo_mixed_chart(), None, {})
    theme = next(f for f in facts if f.payload.get("theme") == "career_strength")

    assert theme.payload["polarity"] != EvidencePolarity.POSITIVE.value
    assert theme.payload["score"] < 0
    assert "本质状态承压" in theme.description


def test_opportunity_does_not_treat_mixed_debility_as_pure_support():
    """职业机会消费 assess_planet：净分 +2 也不能把金星处女落陷说成收入机会有支撑。"""
    facts = Opportunity().analyze(_venus_virgo_mixed_chart(), None, {})

    assert not any("收入机会有支撑" in f.description for f in facts)


def test_finance_marks_mixed_dignity_as_supported_but_limited():
    """财务模块仍可记录混合尊贵，但文案必须显式保留受限，不得只说良好/支撑。"""
    facts = Finance().analyze(_venus_virgo_mixed_chart(), None, {})
    descriptions = [f.description for f in facts]

    assert any("财务本质状态：落陷（有支撑但受限）" in d for d in descriptions)
    assert any("共同资源/他方资金有支撑但受限" in d for d in descriptions)
    assert not any("共同资源/他方资金良好" in d for d in descriptions)


def test_finance_mixed_debility_does_not_create_positive_theme():
    """财务主题评分消费 assess_planet：混合尊贵不能因净分 +2 被抬成正向主题。"""
    facts = Finance().analyze(_venus_virgo_mixed_chart(), None, {})
    theme = next(
        f for f in facts
        if f.category == FactCategory.THEME and f.payload.get("theme") == "career_finance"
    )

    assert theme.payload["polarity"] != EvidencePolarity.POSITIVE.value
    assert theme.payload["score"] < 0


def test_finance_mixed_debility_does_not_emit_positive_dignity_evidence():
    """财务 DIGNITY fact 进入 EvidenceBuilder 后，也不能因旧净分 +2 变成正向证据。"""
    facts = Finance().analyze(_venus_virgo_mixed_chart(), None, {})
    dignity_fact = next(f for f in facts if f.category == FactCategory.DIGNITY)

    assert dignity_fact.payload["raw_score"] == 2
    assert dignity_fact.payload["score"] < 0
    assert dignity_fact.payload["dignity"] == DignityState.FALL.value

    fs = FactSet(id="fs", chart_ids=["career_mixed_dignity"], intent_domain="career", facts=facts)
    es = EvidenceBuilder(load_knowledge()).build(fs, domain="career", query_context="换工作")
    dignity_evidence = [e for e in es.negative_evidence if e.fact_id == dignity_fact.id]

    assert len(dignity_evidence) == 1
    assert not any(e.fact_id == dignity_fact.id for e in es.positive_evidence)


def test_career_strength_dignity_fact_exposes_split_axis_payload():
    """CareerStrength 的 DIGNITY fact 必须带 raw_score + split-axis，证据层可审计。"""
    facts = CareerStrength().analyze(_jupiter_sagittarius_strength_chart(), None, {})
    dignity_fact = next(f for f in facts if f.category == FactCategory.DIGNITY)

    _assert_dignity_payload_auditable(dignity_fact)
    assert dignity_fact.payload["score"] > 0
    assert dignity_fact.payload["essential_pos"] > 0
    assert dignity_fact.payload["essential_neg"] == 0


def test_opportunity_dignity_fact_exposes_split_axis_payload():
    """Opportunity 的木星尊贵 fact 也必须可审计，不只暴露净分。"""
    facts = Opportunity().analyze(_jupiter_sagittarius_strength_chart(), None, {})
    dignity_fact = next(f for f in facts if f.category == FactCategory.DIGNITY)

    _assert_dignity_payload_auditable(dignity_fact)
    assert dignity_fact.payload["score"] == dignity_fact.payload["raw_score"]
    assert dignity_fact.payload["essential_pos"] > 0
    assert dignity_fact.payload["essential_neg"] == 0


def test_risk_debility_fact_exposes_split_axis_payload():
    """Risk 的十宫主失势/落陷 fact 必须保留原始尊贵分与 split-axis。"""
    facts = Risk().analyze(_venus_virgo_mixed_chart(), None, {})
    dignity_fact = next(f for f in facts if f.category == FactCategory.DIGNITY)

    _assert_dignity_payload_auditable(dignity_fact)
    assert dignity_fact.payload["score"] < 0
    assert dignity_fact.payload["essential_neg"] > 0


def test_finance_mixed_lordship_fact_exposes_split_axis_payload():
    """Finance 的八宫主 LORDSHIP fact 也要可审计，避免未来被证据层误读 raw score。"""
    facts = Finance().analyze(_venus_virgo_mixed_chart(), None, {})
    lordship_fact = next(f for f in facts if f.category == FactCategory.LORDSHIP)

    _assert_split_axis_payload_auditable(lordship_fact.payload)
    assert lordship_fact.payload["raw_score"] == 2
    assert lordship_fact.payload["score"] < 0
    assert lordship_fact.payload["essential_pos"] > 0
    assert lordship_fact.payload["essential_neg"] > 0


def test_opportunity_income_lordship_fact_exposes_split_axis_payload():
    """Opportunity 的收入机会 LORDSHIP fact 保留 raw_score + split-axis，便于未来证据化审计。"""
    chart = deepcopy(_jupiter_sagittarius_strength_chart())
    chart.house_cusps[2] = HouseCusp(house=2, degree=240.0, sign=Sign.SAGITTARIUS)
    facts = Opportunity().analyze(chart, None, {})
    lordship_fact = next(
        f for f in facts
        if f.category == FactCategory.LORDSHIP and f.payload.get("theme") == "career_opportunity"
    )

    _assert_split_axis_payload_auditable(lordship_fact.payload)
    assert lordship_fact.payload["score"] == lordship_fact.payload["raw_score"]
    assert lordship_fact.payload["essential_pos"] > 0
    assert lordship_fact.payload["essential_neg"] == 0


def test_career_modules_registered_in_agent():
    from application.agent import GardenSpiritAgent

    agent = GardenSpiritAgent()
    for name in ("CareerStrength", "Timing", "Risk", "Opportunity", "Finance"):
        assert agent.executor.has_module(name), f"{name} 未注册"
