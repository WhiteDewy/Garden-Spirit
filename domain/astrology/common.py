"""领域分析模块的共享辅助。

宫主星、尊贵、相位评分、单星强度等逻辑在此统一，避免各模块重复实现。
全部为纯领域逻辑（原则三）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from foundation.utils import new_id
from shared.constants import SIGNS_IN_ORDER
from shared.enums import AspectApplication, AspectType, FactCategory, Planet, PlanetSpeed, Sect, Sign
from shared.models import Aspect, Chart, Fact

from domain.astrology.knowledge import DignityEngine
from domain.astrology.knowledge.loader import KnowledgeBase

# 吉凶星集（用于单星强度的星性加权；三王星/虚点不在此列，只做关联影响）
BENEFICS = {Planet.JUPITER, Planet.VENUS}
MALEFICS = {Planet.MARS, Planet.SATURN}

# 传统七曜（sect/燃烧/日核 只在七曜上有传统意义）
_CLASSICAL = {
    Planet.SUN, Planet.MOON, Planet.MERCURY, Planet.VENUS,
    Planet.MARS, Planet.JUPITER, Planet.SATURN,
}
# 参与燃烧/日核判定的星（七曜去太阳；三王星/虚点不参与）
_COMBUSTIBLE = _CLASSICAL - {Planet.SUN}
# 燃烧/日核/日光下 阈值（度）
_CAZIMI_ORB = 17.0 / 60.0          # 日核：合日 17 角分内（最强得吉）
_COMBUST_ORB = 8.5                  # 燃烧：合日 8.5° 内（最强受克）
_UNDER_BEAMS_ORB = 17.0             # 日光下：合日 17° 内

# 次要相位（非托勒密主相位）：半六合/半刑/八分相/梅花/五相/倍五相——不参与强度计分
_MINOR_ASPECTS = {
    AspectType.SEMISEXTILE, AspectType.SEMISQUARE, AspectType.SESQUIQUADRATE,
    AspectType.QUINCUNX, AspectType.QUINTILE, AspectType.BIQUINTILE,
}


def combustion_state(chart: Chart, planet: Planet) -> tuple[float, str | None]:
    """燃烧/日核状态 → (分数, 标签)。太阳/三王星/虚点返回 (0, None)。"""
    if planet not in _COMBUSTIBLE or planet not in chart.planets:
        return 0.0, None
    sun = chart.planets.get(Planet.SUN)
    if sun is None:
        return 0.0, None
    sep = abs(
        (chart.planets[planet].ecliptic.longitude - sun.ecliptic.longitude + 180.0) % 360.0 - 180.0
    )
    if sep <= _CAZIMI_ORB:
        return 1.0, "日核"
    if sep <= _COMBUST_ORB:
        return -1.0, "燃烧"
    if sep <= _UNDER_BEAMS_ORB:
        return -0.5, "日光下"
    return 0.0, None


def _benefic_malefic_scale(planet: Planet, chart_sect: Sect | None) -> float:
    """吉凶星昼夜缩放系数（乘在吉/凶权重上，F4a）。

    吉星得时 → 1.0（满额吉），失时 → 0.5；凶星得时 → 0.5（减半凶），失时 → 1.0。
    得时：木星/土星 = 日盘，金星/火星 = 夜盘。
    """
    if chart_sect is None:
        return 1.0
    in_sect = (
        (planet in (Planet.JUPITER, Planet.SATURN) and chart_sect == Sect.DAY)
        or (planet in (Planet.VENUS, Planet.MARS) and chart_sect == Sect.NIGHT)
    )
    if planet in BENEFICS:
        return 1.0 if in_sect else 0.5
    if planet in MALEFICS:
        return 0.5 if in_sect else 1.0
    return 1.0


ASPECT_ZH = {
    "conjunction": "合", "opposition": "冲", "trine": "三合", "square": "刑",
    "sextile": "六合", "quincunx": "梅花", "semisextile": "半六合",
    "semisquare": "半刑", "sesquiquadrate": "八分相",
    "quintile": "五相", "biquintile": "倍五相",
}


def house_lord(chart: Chart, kb: KnowledgeBase, house_num: int) -> Planet | None:
    """某宫的守护星 = 宫头星座的传统守护星。"""
    cusp = chart.house_cusps.get(house_num)
    if cusp is None:
        return None
    sign: Sign = cusp.sign
    return kb.sign(sign).traditional_ruler


def house_rulers(chart: Chart, kb: KnowledgeBase, house: int) -> list[Planet]:
    """某宫的所有守护星：宫头星座守护 + 被劫夺星座守护。

    例：夏天盘 6宫头天秤（金星）+ 劫夺天蝎（火星）→ [金星, 火星]。
    """
    rulers: list[Planet] = []
    cusp_lord = house_lord(chart, kb, house)
    if cusp_lord is not None:
        rulers.append(cusp_lord)
    for deg in _intercepted_sign_degrees(chart, house):
        ruler = kb.sign(SIGNS_IN_ORDER[int(deg // 30) % 12]).traditional_ruler
        if ruler is not None and ruler not in rulers:
            rulers.append(ruler)
    return rulers


def _intercepted_sign_degrees(chart: Chart, house: int) -> list[float]:
    """某宫内被完全包住的星座起始经度（无宫头落入的整星座）。"""
    start = chart.house_cusps[house].degree
    end = chart.house_cusps[house % 12 + 1].degree
    if end <= start:
        end += 360.0
    return [s for s in range(0, 360, 30) if start < s and s + 30 < end]


def dignity_total(
    chart: Chart, kb: KnowledgeBase, planet: Planet, dignity: DignityEngine | None = None
) -> int:
    """行星的先天尊贵总分。"""
    if planet not in chart.planets:
        return 0
    engine = dignity or DignityEngine(kb)
    cp = chart.planets[planet]
    _states, total = engine.compute(planet, cp.sign.sign, cp.sign.degree_in_sign, chart.sect)
    return total


def aspects_to(
    chart: Chart, target: Planet, sources: set[Planet] | None = None
) -> list[Aspect]:
    """target 与 sources 中行星的所有相位（不指定 sources = 全部）。"""
    result: list[Aspect] = []
    for aspect in chart.aspects:
        if target not in (aspect.body1, aspect.body2):
            continue
        other = aspect.body2 if aspect.body1 == target else aspect.body1
        if sources is None or other in sources:
            result.append(aspect)
    return result


def aspect_score(kb: KnowledgeBase, aspect: Aspect) -> float:
    """相位强度分：吉相为正，凶相为负，入相加成。

    权重来自 aspects.yaml（原则三）。与 Timing 模块的月评分一致。
    """
    info = kb.aspects.get(aspect.aspect_type)
    if info is None:
        return 0.0
    base = info.weight_multiplier
    if aspect.application == AspectApplication.APPLYING:
        base *= 1.2
    elif aspect.application == AspectApplication.SEPARATING:
        base *= 0.8
    if info.nature == "HARMONIOUS":
        return base
    if info.nature == "DYNAMIC":
        return -base
    return 0.0


@dataclass(frozen=True)
class PlanetAssessment:
    """三轴行星评估：本质（尊贵）× 境遇（燃烧/吉凶星sect/角续果/逆行/日月sect light）× 关系（相位/接纳）。

    吉凶两论：三轴各带自己的 (pos, neg, 证据)，不互相抵消。
    本质决定「这星本质上行不行」，境遇决定「这星境遇上顺不顺」，关系决定「外界帮不帮/压不压」。
    """

    planet: Planet
    essential_pos: float
    essential_neg: float
    essential_ev: tuple[str, ...]
    accidental_pos: float
    accidental_neg: float
    accidental_ev: tuple[str, ...]
    relational_pos: float
    relational_neg: float
    relational_ev: tuple[str, ...]

    @property
    def pos(self) -> float:
        return self.essential_pos + self.accidental_pos + self.relational_pos

    @property
    def neg(self) -> float:
        return self.essential_neg + self.accidental_neg + self.relational_neg

    @property
    def evidence(self) -> tuple[str, ...]:
        return self.essential_ev + self.accidental_ev + self.relational_ev

    @property
    def essential_net(self) -> float:
        return self.essential_pos - self.essential_neg

    @property
    def accidental_net(self) -> float:
        return self.accidental_pos - self.accidental_neg

    @property
    def relational_net(self) -> float:
        return self.relational_pos - self.relational_neg


def _angularity_score(chart: Chart, kb: KnowledgeBase, planet: Planet) -> float:
    """角续果（境遇轴）：角宫 +1.0、续宫 +0.5、果宫 0。"""
    house = chart.planets[planet].house.house
    angularity = kb.house(house).angularity
    if angularity == "ANGULAR":
        return 1.0
    if angularity == "SUCCEDENT":
        return 0.5
    return 0.0


def _sect_light_score(chart: Chart, planet: Planet) -> float:
    """日月 sect light（境遇轴）：日盘太阳亮 +0.5/月亮暗 -0.5；夜盘反之。其余行星不计。"""
    if planet not in (Planet.SUN, Planet.MOON):
        return 0.0
    if chart.sect == Sect.DAY:
        return 0.5 if planet == Planet.SUN else -0.5
    if chart.sect == Sect.NIGHT:
        return 0.5 if planet == Planet.MOON else -0.5
    return 0.0


def assess_planet(
    chart: Chart,
    kb: KnowledgeBase,
    planet: Planet,
    dignity: DignityEngine | None = None,
    classifier=None,
) -> PlanetAssessment:
    """三轴评估一颗星（预计算查表：同一颗星在同一盘上只算一次）。

    唯一状态评估入口（阶段 1 起逐步替代 4 套重复逻辑）。吉凶两论：三轴各带 pos/neg。
    """
    key = (planet, dignity is None, classifier is None)
    cached = chart.planet_assessments.get(key)
    if cached is not None:
        return cached
    result = _assess_planet(chart, kb, planet, dignity, classifier)
    chart.planet_assessments[key] = result
    return result


def _assess_planet(
    chart: Chart,
    kb: KnowledgeBase,
    planet: Planet,
    dignity: DignityEngine | None = None,
    classifier=None,
) -> PlanetAssessment:
    """assess_planet 实算主体（三轴：本质×境遇×关系）。"""
    from domain.astrology.interpretation.synapsis import ConnectionClassifier  # noqa: PLC0415

    engine = dignity or DignityEngine(kb)
    clf = classifier or ConnectionClassifier(kb)
    name = kb.planet(planet).name_zh

    epos, eneg = 0.0, 0.0
    eev: list[str] = []
    apos, aneg = 0.0, 0.0
    aev: list[str] = []
    rpos, rneg = 0.0, 0.0
    rev: list[str] = []

    if planet not in chart.planets:
        return PlanetAssessment(planet, 0.0, 0.0, (), 0.0, 0.0, (), 0.0, 0.0, ())

    # —— 本质轴：尊贵（庙旺陷三分界面） ——
    dt = dignity_total(chart, kb, planet, engine)
    if dt > 0:
        epos += dt * 0.35
        eev.append(f"{name}尊贵{dt:+d}")
    elif dt < 0:
        eneg += abs(dt) * 0.35
        eev.append(f"{name}受克（尊贵{dt:+d}）")

    # —— 境遇轴：燃烧/日核 ——
    cb_score, cb_tag = combustion_state(chart, planet)
    if cb_score > 0:
        apos += cb_score
        aev.append(f"{name}{cb_tag}")
    elif cb_score < 0:
        aneg += -cb_score
        aev.append(f"{name}{cb_tag}")

    # —— 境遇轴：吉凶星性按昼夜缩放 ——
    if planet in BENEFICS:
        apos += 0.8 * _benefic_malefic_scale(planet, chart.sect)
        aev.append(f"{name}为吉星")
    if planet in MALEFICS:
        aneg += 0.8 * _benefic_malefic_scale(planet, chart.sect)
        aev.append(f"{name}为凶星")

    # —— 境遇轴：角续果 ——
    ang = _angularity_score(chart, kb, planet)
    if ang > 0:
        apos += ang
        aev.append(f"{name}落角宫" if ang >= 1.0 else f"{name}落续宫")

    # —— 境遇轴：逆行 ——
    if chart.planets[planet].speed == PlanetSpeed.RETROGRADE:
        aneg += 0.5
        aev.append(f"{name}逆行")

    # —— 境遇轴：日月 sect light ——
    sl = _sect_light_score(chart, planet)
    if sl > 0:
        apos += sl
        aev.append(f"{name}得时")
    elif sl < 0:
        aneg += -sl
        aev.append(f"{name}失时")

    # —— 关系轴：相位（吉凶 + 接纳，次要相位排除） ——
    for asp in aspects_to(chart, planet):
        if asp.aspect_type in _MINOR_ASPECTS:
            continue
        info = kb.aspects.get(asp.aspect_type)
        if info is None:
            continue
        other = asp.body2 if asp.body1 == planet else asp.body1
        other_zh = kb.planet(other).name_zh
        azh = ASPECT_ZH.get(asp.aspect_type.value, asp.aspect_type.value)
        asc = aspect_score(kb, asp)
        if info.nature == "HARMONIOUS":
            rpos += asc * 0.3
            rev.append(f"{name}{azh}{other_zh}（和谐）")
        elif info.nature == "DYNAMIC":
            received = clf.is_received(chart, planet, other)
            weight = 0.3 if received else 0.5
            tag = "磨合" if received else "未接纳"
            rneg += abs(asc) * weight
            rev.append(f"{name}受{other_zh}{azh}（{tag}）")

    # —— 关系轴：互溶/接纳（帮手星，正向） ——
    for helper, kind in clf.helpers_of(chart, planet):
        if kind == "mutual":
            rpos += 0.5
            rev.append(f"{name}↔{kb.planet(helper).name_zh}互溶")
        else:
            rpos += 0.3
            rev.append(f"{kb.planet(helper).name_zh}接纳{name}")

    return PlanetAssessment(
        planet=planet,
        essential_pos=epos, essential_neg=eneg, essential_ev=tuple(dict.fromkeys(eev)),
        accidental_pos=apos, accidental_neg=aneg, accidental_ev=tuple(dict.fromkeys(aev)),
        relational_pos=rpos, relational_neg=rneg, relational_ev=tuple(dict.fromkeys(rev)),
    )


def planet_strength(
    chart: Chart,
    kb: KnowledgeBase,
    planet: Planet,
    dignity: DignityEngine | None = None,
    classifier=None,
) -> tuple[float, float, list[str]]:
    """单星状态 → (吉分量, 凶分量, 证据)。assess_planet 的向后兼容薄包装（两轴合并）。"""
    a = assess_planet(chart, kb, planet, dignity, classifier)
    return a.pos, a.neg, list(a.evidence)


def theme_fact(
    chart: Chart,
    module: str,
    theme: str,
    polarity,
    weight: float,
    confidence: float,
    description: str,
    extra: dict | None = None,
) -> Fact:
    """构造一条 THEME 事实（由 EvidenceBuilder 采纳为加权证据）。"""
    payload: dict = {
        "theme": theme,
        "polarity": polarity.value,
        "weight": weight,
        "confidence": confidence,
        "module": module,
    }
    if extra:
        payload.update(extra)
    return Fact(
        id=new_id("fact"),
        category=FactCategory.THEME,
        chart_id=chart.id,
        description=description,
        extracted_at=datetime.now(timezone.utc),
        payload=payload,
    )
