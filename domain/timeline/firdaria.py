"""法达（Firdaria）时间领主计算 + 解读。

法达 = 时间段领主系统：大限（~10年章节）+ 子限（~1年小节）。
**时间领主 × 本命条件**：本模块算"现在是哪位星在管事"，
解读复用本命解释引擎（吉凶两论/接纳/交感）读该星管辖宫的本命条件。
确定性、无 LLM。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta

from shared.constants import SIGNS_IN_ORDER
from shared.enums import Planet, Sect
from shared.models import Chart

from domain.astrology.common import aspects_to, house_lord, house_rulers
from domain.astrology.interpretation import HouseSignificationEngine, SignificationItem
from domain.astrology.interpretation.affliction import affliction_readings
from domain.astrology.interpretation.synapsis import ConnectionClassifier, effective_house
from domain.astrology.knowledge.loader import KnowledgeBase

#: 法达各主年限（75 年循环；北交 3 + 南交 2，依据宫神星网）
_FIRDARIA_YEARS = {
    Planet.SUN: 10, Planet.VENUS: 8, Planet.MERCURY: 13, Planet.MOON: 9,
    Planet.SATURN: 11, Planet.JUPITER: 12, Planet.MARS: 7,
    Planet.NORTH_NODE: 3, Planet.SOUTH_NODE: 2,
}
#: 日生：日金水月土木火 北交 南交；夜生：月土木火日金水 北交 南交（双交殿后）
_DAY_SEQUENCE = [Planet.SUN, Planet.VENUS, Planet.MERCURY, Planet.MOON,
                 Planet.SATURN, Planet.JUPITER, Planet.MARS,
                 Planet.NORTH_NODE, Planet.SOUTH_NODE]
_NIGHT_SEQUENCE = [Planet.MOON, Planet.SATURN, Planet.JUPITER, Planet.MARS,
                   Planet.SUN, Planet.VENUS, Planet.MERCURY,
                   Planet.NORTH_NODE, Planet.SOUTH_NODE]
_CHALDEAN = [Planet.SATURN, Planet.JUPITER, Planet.MARS, Planet.SUN,
             Planet.VENUS, Planet.MERCURY, Planet.MOON]


@dataclass(frozen=True)
class FirdariaPeriod:
    """法达时期：大限 + 子限。"""
    major_lord: Planet
    major_start: datetime
    major_end: datetime
    sub_lord: Planet
    sub_start: datetime
    sub_end: datetime

    def to_dict(self) -> dict:
        return {
            "major_lord": self.major_lord.value,
            "major_start": self.major_start.isoformat(),
            "major_end": self.major_end.isoformat(),
            "sub_lord": self.sub_lord.value,
            "sub_start": self.sub_start.isoformat(),
            "sub_end": self.sub_end.isoformat(),
        }


@dataclass(frozen=True)
class TimeLordCharacter:
    """时间领主本命条件 → 这一章"怎么发生"（占星师经验库）。"""

    lord: Planet
    nature: str                 # benefic / malefic / neutral
    tone: str                   # 宽松/丰盛 · 费力/硬干 · 中性
    domains: tuple[str, ...]    # 本命落宫领域（财帛/学习/工作/玄学…）
    behavior: tuple[str, ...]   # 行为特征
    effort: str                 # 过程质感：费力(受克) / 较顺 / 硬干
    afflictions: tuple = ()     # 刑克性质解读（克向谁×有无接纳）
    evidence: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "lord": self.lord.value,
            "nature": self.nature,
            "tone": self.tone,
            "domains": list(self.domains),
            "behavior": list(self.behavior),
            "effort": self.effort,
            "afflictions": [a.to_dict() for a in self.afflictions],
            "evidence": list(self.evidence),
        }


@dataclass
class FirdariaReading:
    """法达 × 本命条件的解读。"""

    period: FirdariaPeriod
    major: list[SignificationItem]              # 大限主题（大限主管辖宫 + 本命落宫）
    sub: list[SignificationItem]                # 子限主题
    major_character: TimeLordCharacter | None = None
    sub_character: TimeLordCharacter | None = None

    def to_dict(self) -> dict:
        return {
            "period": self.period.to_dict(),
            "major": [i.to_dict() for i in self.major],
            "sub": [i.to_dict() for i in self.sub],
            "major_character": self.major_character.to_dict() if self.major_character else None,
            "sub_character": self.sub_character.to_dict() if self.sub_character else None,
        }


# ---------------------------------------------------------------------------
# 计算
# ---------------------------------------------------------------------------

def compute_firdaria(
    birth_utc: datetime,
    sect: Sect,
    reference: datetime | None = None,
) -> FirdariaPeriod:
    """计算出生时刻（UTC）在参考时刻所处的法达大限 + 子限。"""
    birth = birth_utc
    if birth.tzinfo is None:
        birth = birth.replace(tzinfo=timezone.utc)
    ref = reference or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    if ref < birth:
        raise ValueError("参考时间早于出生时间")

    sequence = _DAY_SEQUENCE if sect == Sect.DAY else _NIGHT_SEQUENCE

    # 走大限（73 年后循环重来）
    cursor = birth
    idx = 0
    major_lord: Planet = sequence[0]
    major_start, major_end = birth, _add_years(birth, _FIRDARIA_YEARS[major_lord])
    while True:
        lord = sequence[idx % len(sequence)]
        years = _FIRDARIA_YEARS[lord]
        end = _add_years(cursor, years)
        if ref < end:
            major_lord, major_start, major_end = lord, cursor, end
            break
        cursor = end
        idx += 1

    # 走子限：大限等分为 7 段（7 迦勒底主，从大限主开始，北交不作子限主）
    # 依据宫神星网数据：月亮大限 9 年 ÷ 7 ≈ 470 天/段。
    major_days = max(1, (major_end - major_start).days)
    sub_days = major_days / 7.0
    sub_cursor = major_start
    for sub in _sub_order(major_lord):
        sub_end = sub_cursor + timedelta(days=sub_days)
        if ref < sub_end:
            return FirdariaPeriod(
                major_lord=major_lord, major_start=major_start, major_end=major_end,
                sub_lord=sub, sub_start=sub_cursor, sub_end=sub_end,
            )
        sub_cursor = sub_end

    # 兜底（浮点边界）：落在最后一子限
    last = _sub_order(major_lord)[-1]
    return FirdariaPeriod(
        major_lord=major_lord, major_start=major_start, major_end=major_end,
        sub_lord=last, sub_start=sub_cursor, sub_end=major_end,
    )


def _sub_order(major_lord: Planet) -> list[Planet]:
    """子限主：7 迦勒底主，从大限主开始（北交/南交大限用完整迦勒底序）。"""
    if major_lord in (Planet.NORTH_NODE, Planet.SOUTH_NODE):
        return list(_CHALDEAN)
    idx = _CHALDEAN.index(major_lord)
    return _CHALDEAN[idx:] + _CHALDEAN[:idx]


def _add_years(dt: datetime, years: float) -> datetime:
    """按年推进（含小数，月精度）。"""
    whole = int(years)
    months = int(round((years - whole) * 12))
    return dt + relativedelta(years=whole, months=months)


# ---------------------------------------------------------------------------
# 解读（时间领主 × 本命条件）
# ---------------------------------------------------------------------------

def firdaria_reading(
    chart: Chart,
    kb: KnowledgeBase,
    reference: datetime | None = None,
    domains: tuple[str, ...] = ("career", "wealth", "relationship"),
    top_n: int = 5,
) -> FirdariaReading:
    """法达 × 本命条件：读大限主/子限主管辖宫（含本命落宫）的语义场 + 行为特征。"""
    period = compute_firdaria(chart.epoch_utc, chart.sect, reference)
    engine = HouseSignificationEngine(kb)
    major = _lord_reading(chart, kb, engine, period.major_lord, domains, top_n)
    sub = _lord_reading(chart, kb, engine, period.sub_lord, domains, top_n)
    major_ch = time_lord_character(chart, kb, period.major_lord, engine)
    sub_ch = time_lord_character(chart, kb, period.sub_lord, engine)
    return FirdariaReading(period=period, major=major, sub=sub,
                           major_character=major_ch, sub_character=sub_ch)


def time_lord_character(
    chart: Chart,
    kb: KnowledgeBase,
    lord: Planet,
    engine: HouseSignificationEngine | None = None,
) -> TimeLordCharacter:
    """时间领主本命条件 → 这一章"怎么发生"。

    吉凶基调（宽松/费力）× 本命落宫领域（财帛/学习/工作/玄学）× 受克质感。
    经验例：火星（凶/行动/末度入2财帛）→ "花钱报班、硬干投入"；
            木星（吉/扩张/落3宫学习）→ "免费自学、搜集网课"。
    """
    table = kb.time_lord_character or {}
    planets = table.get("planets") or {}
    hdomains = table.get("house_domains") or {}
    pinfo = planets.get(lord.value) or {}

    nature = pinfo.get("nature", "neutral")
    behavior = tuple(pinfo.get("behavior", []) or [])
    if nature == "benefic":
        tone = "宽松/丰盛"
    elif nature == "malefic":
        tone = "费力/硬干"
    else:
        tone = "中性"

    engine = engine or HouseSignificationEngine(kb)
    classifier = ConnectionClassifier(kb)
    domains: list[str] = []
    evidence: list[str] = []
    hard_count = 0.0
    if lord in chart.planets:
        natal_house = effective_house(chart, lord)
        # YAML 未加引号的数字键解析为 int
        if natal_house in hdomains:
            domains.append(hdomains[natal_house])
        elif str(natal_house) in hdomains:
            domains.append(hdomains[str(natal_house)])
        # 领主自身受克度：刑冲有接纳=磨合(+0.4)，无接纳=硬碰(+0.8)
        for asp in aspects_to(chart, lord):
            info = kb.aspects.get(asp.aspect_type)
            if info is None or info.nature != "DYNAMIC":
                continue
            other = asp.body2 if asp.body1 == lord else asp.body1
            received = classifier.is_received(chart, lord, other)
            hard_count += 0.4 if received else 0.8
            evidence.append(f"{kb.planet(lord).name_zh}受{asp.aspect_type.value}（{'磨合' if received else '未接纳'}）")
        # 该领主管辖宫的凶证据（补充过程质感）
        ruled = [h for h in range(1, 13) if lord in house_rulers(chart, kb, h)]
        for house in ruled:
            _p, _n, _pe, nev = engine._house_quality_dual(chart, house)
            evidence.extend(nev)

    if hard_count >= 1.5:
        effort = "过程费力（受克）"
    elif nature == "malefic":
        effort = "硬干/需投入"
    elif nature == "benefic":
        effort = "较顺/有助力"
    else:
        effort = "平缓"

    return TimeLordCharacter(
        lord=lord, nature=nature, tone=tone,
        domains=tuple(domains), behavior=behavior, effort=effort,
        afflictions=tuple(affliction_readings(chart, kb, lord, classifier)),
        evidence=tuple(dict.fromkeys(evidence)),
    )


def _lord_reading(
    chart: Chart, kb: KnowledgeBase, engine: HouseSignificationEngine,
    lord: Planet, domains: tuple[str, ...], top_n: int,
) -> list[SignificationItem]:
    """读某时间领主的本命条件：管辖宫 + 本命落宫的语义场。"""
    ruled = [h for h in range(1, 13) if lord in house_rulers(chart, kb, h)]
    if lord in chart.planets:
        natal = chart.planets[lord].house.house
        if natal not in ruled:
            ruled.append(natal)

    items: list[SignificationItem] = []
    for house in ruled:
        for domain in domains:
            items.extend(engine.interpret(chart, domain, houses=[house]))

    seen: set[str] = set()
    out: list[SignificationItem] = []
    for item in sorted(items, key=lambda x: x.strength, reverse=True):
        if item.word in seen:
            continue
        seen.add(item.word)
        out.append(item)
        if len(out) >= top_n:
            break
    return out
