"""职业领域分析模块的共享辅助。

宫主星、尊贵、相位评分等逻辑在此统一，避免 Risk/Opportunity/Finance
重复实现。全部为纯领域逻辑（原则三）。
"""

from __future__ import annotations

from datetime import datetime, timezone

from foundation.utils import new_id
from shared.constants import SIGNS_IN_ORDER
from shared.enums import AspectApplication, FactCategory, Planet, Sign
from shared.models import Aspect, Chart, Fact

from domain.astrology.knowledge import DignityEngine
from domain.astrology.knowledge.loader import KnowledgeBase


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
