"""领域引擎 v2 黄金测试：三轨合成器。

合成盘直接构造 Chart（可控、确定性），验证：
- §4 三轨合读：征象×宫主×互溶桥 → 五档结论（顺遂/有平台缺锋芒/有能力不对口）
- R9：轨A 领域行星角色必须来自 planet_nature.domain_signals，而不是 profile.core_planets
- 硬线：占星结论由 DomainCompositor 确定性产出，无 LLM
"""

from datetime import datetime, timezone

import pytest

from shared.enums import (
    AspectApplication,
    AspectType,
    ChartType,
    HouseSystem,
    Planet,
    PlanetSpeed,
    Sect,
    Sign,
    ZodiacType,
)
from shared.models import (
    Aspect,
    Chart,
    ChartPlanet,
    EclipticPosition,
    HouseCusp,
    HousePosition,
    SignPosition,
)

from domain.astrology.interpretation import DomainCompositor
from domain.astrology.knowledge import load_knowledge


# ---------------------------------------------------------------------------
# 合成盘构建（确定性夹具）
# ---------------------------------------------------------------------------

_SIGN_START = {
    Sign.ARIES: 0, Sign.TAURUS: 30, Sign.GEMINI: 60, Sign.CANCER: 90,
    Sign.LEO: 120, Sign.VIRGO: 150, Sign.LIBRA: 180, Sign.SCORPIO: 210,
    Sign.SAGITTARIUS: 240, Sign.CAPRICORN: 270, Sign.AQUARIUS: 300, Sign.PISCES: 330,
}


def _planet(planet: Planet, sign: Sign, deg: float, house: int) -> ChartPlanet:
    abs_deg = _SIGN_START[sign] + deg
    return ChartPlanet(
        planet=planet,
        ecliptic=EclipticPosition(longitude=abs_deg),
        sign=SignPosition(sign=sign, degree_absolute=abs_deg, degree_in_sign=deg),
        house=HousePosition(house=house, cusp_degree=_SIGN_START[sign], distance_from_cusp=deg),
        speed=PlanetSpeed.DIRECT,
        speed_deg_per_day=1.0,
    )


def _chart(
    planets: dict[Planet, ChartPlanet],
    cusps: dict[int, tuple[Sign, float]],
    aspects: tuple[Aspect, ...] = (),
) -> Chart:
    now = datetime.now(timezone.utc)
    return Chart(
        id="c_synth",
        person_id="p_synth",
        chart_type=ChartType.NATAL,
        calculated_at_utc=now,
        julian_day=2460000.0,
        epoch_utc=now,
        location="合成盘",
        zodiac=ZodiacType.TROPICAL,
        house_system=HouseSystem.EQUAL,
        planets=planets,
        house_cusps={h: HouseCusp(house=h, degree=deg, sign=s) for h, (s, deg) in cusps.items()},
        aspects=list(aspects),
        sect=Sect.DAY,
    )


@pytest.fixture(scope="module")
def kb():
    return load_knowledge()


# ---------------------------------------------------------------------------
# §4 三轨合成器：合读规则（五档）
# ---------------------------------------------------------------------------

def _minimal_career_profile(core_houses):
    """注入最小 career 配方：只控制 轨B 核心宫；轨A 必须来自 planet_nature.domain_signals。"""
    from domain.reasoning.intent.intent_profiles import IntentProfile

    return {
        "career": IntentProfile(
            domain="career",
            label_zh="职业",
            description="test",
            core_houses=core_houses,
            house_lords=core_houses,
        )
    }


def _smooth_chart() -> Chart:
    """10R木星庙 + 太阳庙 + 日月相位桥 → 顺遂。"""
    cusps = {
        1: (Sign.ARIES, 5.0), 2: (Sign.TAURUS, 35.0), 3: (Sign.GEMINI, 65.0),
        4: (Sign.CANCER, 95.0), 5: (Sign.LEO, 125.0), 6: (Sign.VIRGO, 155.0),
        7: (Sign.LIBRA, 185.0), 8: (Sign.SCORPIO, 215.0), 9: (Sign.SAGITTARIUS, 245.0),
        10: (Sign.SAGITTARIUS, 250.0), 11: (Sign.CAPRICORN, 275.0), 12: (Sign.AQUARIUS, 305.0),
    }
    planets = {
        Planet.SUN: _planet(Planet.SUN, Sign.LEO, 15.0, 3),
        Planet.MARS: _planet(Planet.MARS, Sign.ARIES, 12.0, 1),
        Planet.JUPITER: _planet(Planet.JUPITER, Sign.SAGITTARIUS, 20.0, 10),
        Planet.SATURN: _planet(Planet.SATURN, Sign.CAPRICORN, 12.0, 10),
        Planet.URANUS: _planet(Planet.URANUS, Sign.ARIES, 20.0, 1),
    }
    aspects = (Aspect(Planet.SUN, Planet.JUPITER, AspectType.TRINE, 120.0, 1.0,
                      AspectApplication.SEPARATING),)
    return _chart(planets, cusps, aspects)


def _mismatch_chart() -> Chart:
    """10宫头双鱼（10R木星双子落陷）弱结构；太阳庙强征象；无桥 → 有能力不对口。"""
    cusps = {
        1: (Sign.ARIES, 5.0), 2: (Sign.TAURUS, 35.0), 3: (Sign.GEMINI, 65.0),
        4: (Sign.CANCER, 95.0), 5: (Sign.LEO, 125.0), 6: (Sign.VIRGO, 155.0),
        7: (Sign.LIBRA, 185.0), 8: (Sign.SCORPIO, 215.0), 9: (Sign.SAGITTARIUS, 245.0),
        10: (Sign.PISCES, 335.0), 11: (Sign.ARIES, 5.0), 12: (Sign.TAURUS, 35.0),
    }
    planets = {
        Planet.SUN: _planet(Planet.SUN, Sign.LEO, 15.0, 3),
        Planet.MARS: _planet(Planet.MARS, Sign.ARIES, 12.0, 1),
        Planet.JUPITER: _planet(Planet.JUPITER, Sign.GEMINI, 15.0, 10),  # 陷
        Planet.SATURN: _planet(Planet.SATURN, Sign.CANCER, 12.0, 4),     # 陷
        Planet.URANUS: _planet(Planet.URANUS, Sign.ARIES, 20.0, 1),
    }
    # 木星受刑（三王星未接纳）→ 结构更弱；无 太阳-木星 桥
    aspects = (Aspect(Planet.JUPITER, Planet.URANUS, AspectType.SQUARE, 90.0, 1.0,
                      AspectApplication.SEPARATING),)
    return _chart(planets, cusps, aspects)


def _platform_weak_edge_chart() -> Chart:
    """10R金星庙（结构强）+ career 核心四星整体受克（征象弱）+ 无桥 → 有平台缺锋芒。"""
    cusps = {
        1: (Sign.ARIES, 5.0), 2: (Sign.TAURUS, 35.0), 3: (Sign.GEMINI, 65.0),
        4: (Sign.CANCER, 95.0), 5: (Sign.LEO, 125.0), 6: (Sign.VIRGO, 155.0),
        7: (Sign.LIBRA, 185.0), 8: (Sign.SCORPIO, 215.0), 9: (Sign.SAGITTARIUS, 245.0),
        10: (Sign.TAURUS, 35.0), 11: (Sign.GEMINI, 65.0), 12: (Sign.CANCER, 95.0),
    }
    planets = {
        Planet.VENUS: _planet(Planet.VENUS, Sign.TAURUS, 12.0, 10),       # 10R庙，结构强
        Planet.SUN: _planet(Planet.SUN, Sign.AQUARIUS, 15.0, 3),          # 弱
        Planet.MARS: _planet(Planet.MARS, Sign.CANCER, 12.0, 4),          # 弱
        Planet.JUPITER: _planet(Planet.JUPITER, Sign.GEMINI, 12.0, 3),    # 弱
        Planet.SATURN: _planet(Planet.SATURN, Sign.CANCER, 12.0, 4),      # 弱
        Planet.URANUS: _planet(Planet.URANUS, Sign.ARIES, 20.0, 1),
    }
    return _chart(planets, cusps)


def test_compositor_smooth(kb):
    """有桥+结构强+征象强 → 顺遂。"""
    c = DomainCompositor(kb, _minimal_career_profile([10]))
    r = c.compose(_smooth_chart(), "career")
    assert r is not None
    assert r.code == "smooth"
    assert r.title == "顺遂"
    tracks = {t.track: t for t in r.tracks}
    assert tracks["B"].verdict == "strong"
    assert tracks["A"].verdict == "strong"
    assert tracks["C"].score >= 2.5


def test_compositor_capability_mismatch(kb):
    """无桥+结构弱+征象强 → 有能力不对口（太阳尊贵落3宫 vs 10宫落陷，§7.2）。"""
    c = DomainCompositor(kb, _minimal_career_profile([10]))
    r = c.compose(_mismatch_chart(), "career")
    assert r is not None
    assert r.code == "capability_mismatch"
    tracks = {t.track: t for t in r.tracks}
    assert tracks["B"].verdict == "weak"      # 10R木星落陷 → 结构弱
    assert tracks["A"].verdict == "strong"    # 太阳庙 → 征象好
    assert tracks["C"].verdict == "none"      # 无桥


def test_compositor_platform_weak_edge(kb):
    """无桥+结构强+征象弱 → 有平台缺锋芒。"""
    c = DomainCompositor(kb, _minimal_career_profile([10]))
    r = c.compose(_platform_weak_edge_chart(), "career")
    assert r is not None
    assert r.code == "platform_weak_edge"
    tracks = {t.track: t for t in r.tracks}
    assert tracks["B"].verdict == "strong"
    assert tracks["A"].verdict == "weak"
    assert tracks["C"].verdict == "none"


def test_compositor_unknown_domain_returns_none(kb):
    c = DomainCompositor(kb, {})
    assert c.compose(_smooth_chart(), "bogus") is None


def test_compositor_all_11_domains_composable(kb):
    """真实配方：11 域全部可合成（含 growth/network/self/daily）。"""
    c = DomainCompositor(kb)
    for domain in ("career", "relationship", "wealth", "health", "emotion", "family",
                   "learning", "growth", "network", "self", "daily"):
        r = c.compose(_smooth_chart(), domain)
        assert r is not None, f"{domain} 无可合成结论"
        assert len(r.tracks) == 3
        # 结论可追溯：带三轨
        assert r.tracks[0].track == "A" and r.tracks[1].track == "B" and r.tracks[2].track == "C"


def test_compositor_to_dict_serializable(kb):
    c = DomainCompositor(kb, _minimal_career_profile([10]))
    r = c.compose(_smooth_chart(), "career")
    d = r.to_dict()
    assert d["code"] == "smooth"
    assert d["tracks"][0]["track"] == "A"
    assert "score" in d["tracks"][0]
