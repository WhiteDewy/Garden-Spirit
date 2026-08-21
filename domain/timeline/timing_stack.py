"""时机栈合成（TimingStack）：一次调用回答"当前处于什么时期"。

合成五层推运 + 行运窗口：
法达（章节/子限）→ 日返（年度快照）→ 次限月亮（情绪季节）
→ 月返（当月）→ 三限月亮（细情绪）→ 行运窗口（触发月份）。
确定性、无 LLM；to_dict() 出口（供 app 消费）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from domain.analysis import Timing
from domain.astrology.knowledge.loader import KnowledgeBase
from domain.timeline.annual_activation import AnnualActivation, compute_annual_activation
from domain.timeline.firdaria import FirdariaReading, firdaria_reading
from domain.timeline.lunar_return import LunarReturn, LunarReturnCalculator
from domain.timeline.progressed import ProgressedMoon, ProgressedMoonCalculator
from domain.timeline.solar_return import SolarReturn, SolarReturnCalculator
from shared.models import Chart, GeoLocation, Person

#: 行运窗口扫描月数
_TRANSIT_MONTHS = 6


@dataclass
class TimingStack:
    """当前时期合成对象。"""

    firdaria: FirdariaReading
    annual_activation: AnnualActivation
    solar_return: SolarReturn
    lunar_return: LunarReturn
    progressed_moon: ProgressedMoon          # 次限
    tertiary_moon: ProgressedMoon            # 三限
    transit_targets: list[str] = field(default_factory=list)  # 法达 + 问题目标星
    helper_transit_targets: list[str] = field(default_factory=list)  # 互溶/接纳帮手星
    scoring_transit_targets: list[str] = field(default_factory=list)  # 实际扫描目标星
    transits: list[dict] = field(default_factory=list)  # 月窗口

    def to_dict(self) -> dict:
        return {
            "type": "timing_stack",
            "timing_authority": "firdaria",
            "transit_targets": self.transit_targets,
            "helper_transit_targets": self.helper_transit_targets,
            "scoring_transit_targets": self.scoring_transit_targets,
            "firdaria": self.firdaria.to_dict(),
            "annual_activation": self.annual_activation.to_dict(),
            "solar_return": self.solar_return.to_dict(),
            "lunar_return": self.lunar_return.to_dict(),
            "progressed_moon": self.progressed_moon.to_dict(),
            "tertiary_moon": self.tertiary_moon.to_dict(),
            "transits": self.transits,
        }


def build_timing_stack(
    person: Person,
    chart: Chart,
    kb: KnowledgeBase,
    reference: datetime | None = None,
    location: GeoLocation | None = None,
    house_system=None,
    enrichment: dict | None = None,
) -> TimingStack:
    """合成当前时期（法达 + 返回盘 + 推运 + 行运）。"""
    loc = location or person.birth.location
    birth_utc = person.birth.datetime_utc
    ref = reference or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)

    # 行运窗口（法达大限/子限 + 本轮问题征象星 + 接纳/互溶帮手星）
    timing = Timing(kb)
    firdaria = firdaria_reading(chart, kb, ref)
    annual_activation = compute_annual_activation(
        chart,
        kb,
        ref,
        firdaria_major_lord=firdaria.period.major_lord,
        firdaria_sub_lord=firdaria.period.sub_lord,
    )
    targets = timing._timing_targets(
        chart,
        firdaria.period.major_lord,
        firdaria.period.sub_lord,
        enrichment,
    )
    helper_targets = timing._helper_targets(chart, targets)
    annual_helper_targets = {annual_activation.activation_lord} if annual_activation.activation_lord in chart.planets else set()
    scoring_targets = targets | helper_targets | annual_helper_targets
    sorted_targets = [p.value for p in sorted(targets, key=lambda p: p.value)]
    sorted_helper_targets = [p.value for p in sorted(helper_targets, key=lambda p: p.value)]
    sorted_scoring_targets = [p.value for p in sorted(scoring_targets, key=lambda p: p.value)]
    transits: list[dict] = []
    from dateutil.relativedelta import relativedelta

    for i in range(_TRANSIT_MONTHS):
        month = ref.replace(day=1) + relativedelta(months=i)
        score = timing._month_score(chart, month, scoring_targets)
        transits.append({
            "month": month.strftime("%Y-%m"),
            "score": round(score, 2),
            "tag": "有利" if score >= 0.5 else ("不利" if score <= -0.5 else "中性"),
            "timing_authority": "firdaria",
            "target_planets": sorted_targets,
            "helper_target_planets": sorted_helper_targets,
            "scoring_target_planets": sorted_scoring_targets,
            "annual_activation": annual_activation.to_dict(),
        })

    stack = TimingStack(
        firdaria=firdaria,
        annual_activation=annual_activation,
        solar_return=SolarReturnCalculator().compute(chart, loc, ref, house_system=house_system,
                                                     birth_location=person.birth.location),
        lunar_return=LunarReturnCalculator().compute(chart, loc, ref, house_system=house_system,
                                                     birth_location=person.birth.location),
        progressed_moon=ProgressedMoonCalculator().compute(chart, birth_utc, ref),
        tertiary_moon=ProgressedMoonCalculator().compute(chart, birth_utc, ref, mode="tertiary"),
        transit_targets=sorted_targets,
        helper_transit_targets=sorted_helper_targets,
        scoring_transit_targets=sorted_scoring_targets,
        transits=transits,
    )
    return stack
