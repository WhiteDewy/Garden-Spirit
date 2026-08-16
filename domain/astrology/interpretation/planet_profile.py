"""行星档案（Planet Profile）—— 每颗星的完整单点解读。确定性、无 LLM。

用户理念：金火月日木土都是星盘里的单点配置。本模块把每颗星的完整档案
（落座风格 / 落宫领域 / 尊贵状态 / 支持者 / 破坏者 / 掌宫）一次性算齐。
主题分析（感情/事业/财）从全星档案里**有选择地抓取**，而非只算相关星。

数据来源（全部 YAML + 确定性规则，原则三）：
- 落座风格: knowledge/planet_sign_style.yaml
- 落宫领域: knowledge/rules/planet_in_house.yaml
- 尊贵状态: assess_planet()（knowledge/dignity.yaml，吉凶两论）
- 支持/破坏: aspects_to() + ConnectionClassifier.is_received()（knowledge/aspects.yaml）
- 掌宫: house_rulers()（common.py）
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.enums import AspectType, Planet
from shared.models import Chart

from domain.astrology.common import aspects_to, assess_planet, house_rulers
from domain.astrology.interpretation.synapsis import ConnectionClassifier, effective_house
from domain.astrology.knowledge.loader import KnowledgeBase

#: 次要动态相位（半刑45°/八分相135°/梅花150°）不参与受克判定
_MINOR_DYNAMIC = {
    AspectType.SEMISQUARE,
    AspectType.SESQUIQUADRATE,
    AspectType.QUINCUNX,
}

_ASPECT_ZH = {
    "conjunction": "合", "opposition": "冲", "trine": "三合", "square": "刑",
    "sextile": "六合", "quincunx": "梅花", "semisextile": "半六合",
    "semisquare": "半刑", "sesquiquadrate": "八分相",
    "quintile": "五相", "biquintile": "倍五相",
}

#: 主要可用的行星（排除虚点/南北交）
_MAIN_PLANETS = (
    Planet.SUN, Planet.MOON, Planet.MERCURY, Planet.VENUS, Planet.MARS,
    Planet.JUPITER, Planet.SATURN, Planet.URANUS, Planet.NEPTUNE, Planet.PLUTO,
)


@dataclass(frozen=True)
class PlanetProfile:
    """一颗星的完整档案。"""

    planet: Planet
    sign_style: str              # 行星×落座风格
    behavior_style: str          # 星座行为方式（供前端/转述消费）
    house_name: str              # "落X宫"
    house_domain: str            # 落宫领域解读
    dignity_label: str           # 入庙/入旺/落陷/失势/游走（混合时可带括注）
    dignity_score: int
    supporters: tuple[str, ...]      # 谁在帮它
    underminers: tuple[str, ...]     # 谁在破坏它
    rulings: tuple[int, ...]         # 掌哪些宫
    ruling_labels: tuple[str, ...]   # 掌宫的领域标签

    def to_dict(self) -> dict:
        """出口：JSON 友好（供 LLM 转述 + 星灵 app 消费）。"""
        return {
            "planet": self.planet.value,
            "sign_style": self.sign_style,
            "behavior_style": self.behavior_style,
            "house_name": self.house_name,
            "house_domain": self.house_domain,
            "dignity_label": self.dignity_label,
            "dignity_score": self.dignity_score,
            "supporters": list(self.supporters),
            "underminers": list(self.underminers),
            "rulings": list(self.rulings),
            "ruling_labels": list(self.ruling_labels),
        }


# ---------------------------------------------------------------------------
# 单点读取
# ---------------------------------------------------------------------------

def read_planet(
    chart: Chart,
    kb: KnowledgeBase,
    planet: Planet,
    classifier: ConnectionClassifier | None = None,
) -> PlanetProfile:
    """读一颗星的完整档案。"""
    if planet not in chart.planets:
        return PlanetProfile(
            planet=planet, sign_style="", behavior_style="", house_name="",
            house_domain="", dignity_label="", dignity_score=0,
            supporters=(), underminers=(), rulings=(), ruling_labels=(),
        )

    classifier = classifier or ConnectionClassifier(kb)
    cp = chart.planets[planet]
    sign = cp.sign.sign
    house = cp.house.house

    # 落座风格
    sign_style = _sign_style(kb, planet, sign)
    behavior_style = kb.sign(sign).behavior_style

    # 落宫领域（复用 planet_in_house.yaml 的 base）
    house_domain = _house_domain(kb, planet, house)

    # 尊贵（消费 assess_planet：本质轴内部也吉凶两论，不用净分抹掉混合态）
    assessment = assess_planet(chart, kb, planet, classifier=classifier)
    dignity_score = _dignity_score_from_assessment(assessment)
    dignity_label = _dignity_label_from_assessment(assessment)

    # 支持者 / 破坏者
    supporters, underminers = _aspect_partners(chart, kb, planet, classifier)

    # 掌宫
    rulings, ruling_labels = _rulings(chart, kb, planet)

    return PlanetProfile(
        planet=planet,
        sign_style=sign_style,
        behavior_style=behavior_style,
        house_name=f"落{house}宫",
        house_domain=house_domain,
        dignity_label=dignity_label,
        dignity_score=dignity_score,
        supporters=tuple(supporters),
        underminers=tuple(underminers),
        rulings=tuple(rulings),
        ruling_labels=tuple(ruling_labels),
    )


def read_all_planets(
    chart: Chart,
    kb: KnowledgeBase,
    planets: tuple[Planet, ...] = _MAIN_PLANETS,
) -> list[PlanetProfile]:
    """全星档案列表（默认10颗主星）。"""
    classifier = ConnectionClassifier(kb)
    return [read_planet(chart, kb, p, classifier) for p in planets]


# ---------------------------------------------------------------------------
# 主题抓取（留接口）—— 从全星档案里按需选择
# ---------------------------------------------------------------------------

def pick_for_theme(
    profiles: list[PlanetProfile],
    planets: tuple[Planet, ...],
) -> list[PlanetProfile]:
    """按主题选行星组合。

    例：
      pick_for_theme(profiles, (VENUS, MARS, MOON))  # 感情
      pick_for_theme(profiles, (SUN, JUPITER, SATURN))  # 事业
      pick_for_theme(profiles, (JUPITER, SATURN, VENUS, MERCURY))  # 财
    """
    wanted = set(planets)
    return [p for p in profiles if p.planet in wanted]


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------

def _sign_style(kb: KnowledgeBase, planet: Planet, sign) -> str:
    """落座风格：查 YAML；兜底用 行星significations × 星座keywords 拼接。"""
    table = kb.planet_sign_style or {}
    planet_entries = table.get(planet.value) or {}
    style = planet_entries.get(sign.value)
    if style:
        return style
    # 兜底拼接
    p_zh = kb.planet(planet).significations_zh
    p_kw = p_zh[0] if p_zh else planet.value
    s_kw = "、".join(kb.sign(sign).keywords_zh[:2])
    return f"{planet}落在{sign.name_zh}——{p_kw}的能量带着{s_kw}的特质"


def _house_domain(kb: KnowledgeBase, planet: Planet, house: int) -> str:
    """落宫领域：查 planet_in_house.yaml 的 base。"""
    rules = kb.planet_in_house_rules or {}
    key = f"{planet.value}_{house}"
    entry = rules.get(key)
    if entry and entry.get("base"):
        return entry["base"]
    fallback = rules.get("_fallback") or {}
    return fallback.get("base", f"{planet.value}落{house}宫")


def _dignity_score_from_assessment(assessment) -> int:
    """旧 score 字段：混合本质尊贵时优先暴露失势/落陷，避免净分抹掉受限。"""
    pos_score = round(assessment.essential_pos / 0.35)
    neg_score = round(assessment.essential_neg / 0.35)
    if pos_score > 0 and neg_score > 0:
        if _has_essential_fall(assessment):
            return -5
        if neg_score >= 2:
            return -2
        return 0
    return pos_score - neg_score


def _has_essential_fall(assessment) -> bool:
    """本质轴是否含落陷；失势/落陷不能只靠负分幅度区分。"""
    return any("落陷" in ev for ev in assessment.essential_ev)


def _dignity_label(score: int) -> str:
    if score >= 5:
        return "入庙"
    if score >= 2:
        return "入旺"
    if score <= -5:
        return "落陷"
    if score <= -2:
        return "失势"
    return "游走"


def _dignity_label_from_assessment(assessment) -> str:
    """尊贵标签：沿用旧字段，但混合本质尊贵优先暴露失势/落陷。"""
    base = _dignity_label(_dignity_score_from_assessment(assessment))
    if assessment.essential_pos > 0 and assessment.essential_neg > 0:
        if assessment.essential_neg > assessment.essential_pos:
            return f"{base}（有支撑）"
        if assessment.essential_pos > assessment.essential_neg:
            return f"{base}（有支撑但受限）"
        return "游走（吉凶并见）"
    return base


def _aspect_partners(
    chart: Chart,
    kb: KnowledgeBase,
    planet: Planet,
    classifier: ConnectionClassifier,
) -> tuple[list[str], list[str]]:
    """支持者（吉相/有接纳）+ 破坏者（主相位刑冲，排除次要相位）。"""
    supporters: list[str] = []
    underminers: list[str] = []
    outer_set = set(kb.affliction_quality.get("outer", [])) if kb.affliction_quality else set()

    for asp in aspects_to(chart, planet):
        info = kb.aspects.get(asp.aspect_type)
        if info is None:
            continue
        other = asp.body2 if asp.body1 == planet else asp.body1
        other_zh = kb.planet(other).name_zh
        azh = _ASPECT_ZH.get(asp.aspect_type.value, asp.aspect_type.value)
        received = classifier.is_received(chart, planet, other)

        if info.nature == "HARMONIOUS":
            tag = "有接纳" if received else "吉相"
            supporters.append(f"{other_zh}{azh}（{tag}）")
        elif info.nature == "DYNAMIC":
            if asp.aspect_type in _MINOR_DYNAMIC:
                continue  # 次要相位不计入受克
            if received:
                underminers.append(f"{other_zh}{azh}（磨合）")
            elif other in outer_set:
                underminers.append(f"{other_zh}{azh}（外部压力）")
            else:
                underminers.append(f"{other_zh}{azh}（无接纳）")

    # 去重保序
    return list(dict.fromkeys(supporters)), list(dict.fromkeys(underminers))


def _rulings(chart: Chart, kb: KnowledgeBase, planet: Planet) -> tuple[list[int], list[str]]:
    """掌宫列表 + 领域标签（来自 time_lord_character.house_domains）。"""
    rules = [h for h in range(1, 13) if planet in house_rulers(chart, kb, h)]
    domains = (kb.time_lord_character or {}).get("house_domains", {})
    labels: list[str] = []
    for h in rules:
        label = domains.get(h) or domains.get(str(h))
        labels.append(str(label) if label else f"{h}宫")
    return rules, labels
