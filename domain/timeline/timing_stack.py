"""时机栈合成（TimingStack）：一次调用回答"当前处于什么时期"。

合成六层推运 + 行运窗口：
法达（章节）→ 年主星（当年）→ 日返（年度快照）→ 次限月亮（情绪季节）
→ 月返（当月）→ 三限月亮（细情绪）→ 行运窗口（触发月份）。
确定性、无 LLM；to_dict() 出口（供 app 消费）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from domain.analysis import Timing
from domain.astrology.knowledge.loader import KnowledgeBase
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

    year_lord: str
    firdaria: FirdariaReading
    solar_return: SolarReturn
    lunar_return: LunarReturn
    progressed_moon: ProgressedMoon          # 次限
    tertiary_moon: ProgressedMoon            # 三限
    transits: list[dict] = field(default_factory=list)  # 月窗口

    def to_dict(self) -> dict:
        return {
            "type": "timing_stack",
            "year_lord": self.year_lord,
            "firdaria": self.firdaria.to_dict(),
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
) -> TimingStack:
    """合成当前时期（法达 + 返回盘 + 推运 + 行运）。"""
    loc = location or person.birth.location
    birth_utc = person.birth.datetime_utc
    ref = reference or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)

    # 行运窗口（年主星 + 逐月扫描）
    timing = Timing(kb)
    year_lord = timing._year_lord(chart, person, ref)
    transits: list[dict] = []
    from dateutil.relativedelta import relativedelta

    for i in range(_TRANSIT_MONTHS):
        month = ref.replace(day=1) + relativedelta(months=i)
        score = timing._month_score(chart, month, year_lord)
        transits.append({
            "month": month.strftime("%Y-%m"),
            "score": round(score, 2),
            "tag": "有利" if score >= 0.5 else ("不利" if score <= -0.5 else "中性"),
        })

    stack = TimingStack(
        year_lord=year_lord.value,
        firdaria=firdaria_reading(chart, kb, ref),
        solar_return=SolarReturnCalculator().compute(chart, loc, ref, house_system=house_system,
                                                     birth_location=person.birth.location),
        lunar_return=LunarReturnCalculator().compute(chart, loc, ref, house_system=house_system,
                                                     birth_location=person.birth.location),
        progressed_moon=ProgressedMoonCalculator().compute(chart, birth_utc, ref),
        tertiary_moon=ProgressedMoonCalculator().compute(chart, birth_utc, ref, mode="tertiary"),
        transits=transits,
    )
    return stack
