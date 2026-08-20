"""星灵推荐引擎 —— 今日该见哪位星灵（self_map §11 + homepage_design §6.1）。

行运推荐 = 三轴评分（确定性、无 LLM，硬线：占星结论全由 Domain 出）：
- ① 今日行运活跃（权重 0.5）：行运行星×本命行星相位加权——今日"谁在动"
- ② 近期共振（权重 0.3）：34 子类·行星区深度分——最近"你常聊谁"
- ③ 长期课题（权重 0.2）：本命相位/落宫 → 每星课题端（本期留位；未实现并入前两轴）

输出给 API 层：评分 + 可解释理由（"今日行运土星合你本命太阳"）。
人格映射（疗愈名/口吻）在 Application 层做——Domain 不依赖 Application。

行运显著性参考：法达大限/子限主（时间领主：现在谁在"管事"）+ 角宫 bonus。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from foundation.astronomy import ephemeris as swe_wrap
from shared.constants import ANGULAR_HOUSES, ASPECT_ZH, PLANETS_IN_ORDER, SE_PLANET_IDS
from shared.enums import AspectType, HouseSystem, Planet
from shared.models import Chart

from domain.astrology.calculation.transit import TransitCalculator
from domain.timeline.firdaria import compute_firdaria

#: 相位权重（行星被"触"的强度）
_ASPECT_WEIGHTS = {
    AspectType.CONJUNCTION: 3.0,
    AspectType.OPPOSITION: 2.0,
    AspectType.TRINE: 2.0,
    AspectType.SQUARE: 2.0,
    AspectType.SEXTILE: 1.0,
}
#: 行运行星落角宫（1/4/7/10）bonus
_ANGULAR_BONUS = 1.0
#: 法达大限/子限主 bonus（时间领主）
_FIRDARIA_MAJOR_BONUS = 2.0
_FIRDARIA_SUB_BONUS = 1.0

#: 三轴权重（homepage_design §6.1；③ 未实现 → 并入前两轴，按比例重分配）
_W_TRANSIT = 0.5 / 0.8
_W_RESONANCE = 0.3 / 0.8
_W_THEME = 0.0

#: 行星中文名（Domain 内联；人格名字在 Application 层，不进推理层）
_PLANET_ZH = {
    Planet.SUN: "太阳", Planet.MOON: "月亮", Planet.MERCURY: "水星",
    Planet.VENUS: "金星", Planet.MARS: "火星", Planet.JUPITER: "木星",
    Planet.SATURN: "土星", Planet.URANUS: "天王星",
    Planet.NEPTUNE: "海王星", Planet.PLUTO: "冥王星",
}

#: 34 子类行星区 → 行星（近期共振喂给哪颗星）
_FRAGMENT_PLANET = {
    "sun_core": Planet.SUN, "moon_tide": Planet.MOON,
    "mercury_maze": Planet.MERCURY, "venus_love": Planet.VENUS,
    "mars_action": Planet.MARS, "jupiter_faith": Planet.JUPITER,
    "saturn_order": Planet.SATURN, "uranus_awake": Planet.URANUS,
    "neptune_dream": Planet.NEPTUNE, "pluto_depth": Planet.PLUTO,
}
#: 行星 → 行星区子类 id（反向查表）
_PLANET_FRAGMENT = {v: k for k, v in _FRAGMENT_PLANET.items()}

#: 归一化上限：原始行运加权和到此值 → 该轴视为满分。
#: 10 行运体全部计分时，单颗本命行星日加权和常达 8~11（+角宫/法达 bonus），
#: cap 太低会把顶部拍平、无法区分"今天谁最活跃"，故取 15。
_TRANSIT_CAP = 15.0
_RESONANCE_CAP = 10.0


@dataclass(frozen=True)
class PlanetActivationScore:
    """一颗星灵今日的激活分（原始结果，供 API 层映射成推荐出参）。

    score 已含三轴加权（0-10）。reason_parts 可追溯（为什么推荐它）。
    """

    planet: Planet
    score: float            # 综合分（≈0-10；行运+共振双满的极端日略超）
    transit_score: float    # ① 行运活跃（0-15）
    resonance_score: float  # ② 近期共振（0-10）
    transit_count: int      # 命中相位数（可解释"今天谁在动"）
    reason_parts: list[str] = field(default_factory=list)
    is_firdaria_major_lord: bool = False
    is_firdaria_sub_lord: bool = False


def score_spirits(
    natal: Chart,
    target: datetime,
    latitude: float,
    longitude: float,
    house_system: HouseSystem | str | None = None,
    fragment_depths: dict[str, int] | None = None,
    kb=None,
) -> list[PlanetActivationScore]:
    """对 10 颗星灵打分（按综合分降序）。

    纯 Domain 计算：行运相位（10 行星全当行运体）+ 角宫 bonus + 法达领主 + 近期共振。
    """
    # 行运相位：显式传 10 行星（不动 TransitCalculator 默认外行星集，避免改 timing 行为）
    aspects = TransitCalculator(kb).transit_aspects(
        natal, target, transit_bodies=PLANETS_IN_ORDER
    )

    # 行运行星位置 + 今日角宫（lat/lon 用出生地——行运落宫以盘主出生地为准）
    jd = swe_wrap.to_julian_day(target)
    transit_positions: dict[Planet, float] = {}
    for p in PLANETS_IN_ORDER:
        if p in SE_PLANET_IDS:
            transit_positions[p] = swe_wrap.planet_full(jd, p)["longitude"]
    hs = house_system or HouseSystem.ALCABITIUS
    hs_val = hs.value if hasattr(hs, "value") else str(hs)
    cusps = swe_wrap.house_cusps(jd, latitude, longitude, hs_val)["cusps"]
    angular_transits = {
        p for p in transit_positions
        if _house_of_longitude(transit_positions[p], cusps) in ANGULAR_HOUSES
    }

    # 法达领主（时间领主：大限主/子限主）
    period = None
    if natal.sect is not None:
        try:
            period = compute_firdaria(natal.epoch_utc, natal.sect, target)
        except ValueError:
            period = None  # 目标早于出生 → 无法达（防御）

    fragment_depths = fragment_depths or {}

    scores: list[PlanetActivationScore] = []
    for p in PLANETS_IN_ORDER:
        transit_sum = 0.0
        count = 0
        parts: list[str] = []

        # ① 行运相位（p 作为行运体 or 本命目标都被"触"）
        for a in aspects:
            # 只对 10 颗候选星计分（行运侧已限定 10 行星；本命侧可能含北交点等）
            if a.body1 not in _PLANET_ZH or a.body2 not in _PLANET_ZH:
                continue
            w = _ASPECT_WEIGHTS.get(a.aspect_type, 0.0)
            if w <= 0.0:
                continue
            if a.body1 == p:
                transit_sum += w
                count += 1
                parts.append(
                    f"行运{_PLANET_ZH[p]}{ASPECT_ZH[a.aspect_type.value]}你本命{_PLANET_ZH[a.body2]}"
                )
            elif a.body2 == p:
                transit_sum += w
                count += 1
                parts.append(
                    f"行运{_PLANET_ZH[a.body1]}{ASPECT_ZH[a.aspect_type.value]}你本命{_PLANET_ZH[p]}"
                )
        if p in angular_transits:
            transit_sum += _ANGULAR_BONUS
            parts.append(f"行运{_PLANET_ZH[p]}落今日角宫")

        # 法达领主 bonus
        is_major = period is not None and period.major_lord == p
        is_sub = period is not None and period.sub_lord == p
        if is_major:
            transit_sum += _FIRDARIA_MAJOR_BONUS
            parts.append(f"当前法达大限主{_PLANET_ZH[p]}")
        if is_sub:
            transit_sum += _FIRDARIA_SUB_BONUS
            parts.append(f"当前法达子限主{_PLANET_ZH[p]}")

        # ② 近期共振（34 子类·行星区深度分）
        frag_key = _PLANET_FRAGMENT.get(p)
        depth = fragment_depths.get(frag_key, 0) if frag_key else 0
        resonance = min(float(depth), _RESONANCE_CAP)
        if depth > 0:
            parts.append(f"最近你常聊{_PLANET_ZH[p]}")

        transit_norm = min(transit_sum, _TRANSIT_CAP)
        final = transit_norm * _W_TRANSIT + resonance * _W_RESONANCE + _W_THEME * 0.0

        scores.append(
            PlanetActivationScore(
                planet=p,
                score=round(final, 2),
                transit_score=round(transit_norm, 2),
                resonance_score=round(resonance, 2),
                transit_count=count,
                reason_parts=parts,
                is_firdaria_major_lord=is_major,
                is_firdaria_sub_lord=is_sub,
            )
        )

    scores.sort(key=lambda s: s.score, reverse=True)
    return scores


def _house_of_longitude(lon: float, cusps: dict[int, float]) -> int:
    """黄道经度 → 宫位（宫头 1..12，跨 0° 的宫处理包裹）。"""
    lon = lon % 360.0
    pts = [cusps[i] % 360.0 for i in range(1, 13)]
    for h in range(1, 12):
        a, b = pts[h - 1], pts[h]
        if a <= b:
            if a <= lon < b:
                return h
        else:  # 跨 0°（如 11 宫头 350 → 12 宫头 20）
            if lon >= a or lon < b:
                return h
    return 12


__all__ = ["PlanetActivationScore", "score_spirits"]
