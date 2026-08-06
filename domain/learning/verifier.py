"""验前事（B1，学习层 L5）—— 用人生事件验证本命解读，为置信度校准提供依据。

梦老师方法论 §4：法达行运验证本命结构。一条已沉淀的占星判断（VerifiedFinding）
如果它的"主题星"在事件发生时的法达大限/子限里管事，就说明这个结构在这人
的生命里是"活的"——判断被验证。

确定性、无 LLM。Domain 层只算"验没验上"，不写画像（Application 层编排校准）。

判据诚实原则：**没验上 ≠ 被证伪**。事件不在某星主运期，只能算 inconclusive
（未确认），不是 refuted——占星的"缺席"不等于"反驳"。反驳只来自用户明确反馈。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from shared.enums import Planet
from shared.models import Chart, VerifiedFinding
from shared.types import EntityId

from domain.timeline.firdaria import compute_firdaria

#: 行星中文名 → Planet（语句里提取主题星用）。按最长优先避免部分匹配。
_PLANET_ZH: dict[str, Planet] = {
    "天王星": Planet.URANUS,
    "海王星": Planet.NEPTUNE,
    "冥王星": Planet.PLUTO,
    "太阳": Planet.SUN,
    "月亮": Planet.MOON,
    "水星": Planet.MERCURY,
    "金星": Planet.VENUS,
    "火星": Planet.MARS,
    "木星": Planet.JUPITER,
    "土星": Planet.SATURN,
}

#: 主题星中文名（返回给用户/写验证痕迹用）
PLANET_ZH_LOOKUP: dict[Planet, str] = {v: k for k, v in _PLANET_ZH.items()}


@dataclass(frozen=True)
class VerificationVerdict:
    """一条判断 × 一个事件 的验证结果。"""

    finding_id: EntityId
    statement: str
    subject_planet: Planet | None      # 从判断语句提取的主题星；None=未能识别
    verdict: str                       # "confirmed"(验上) | "inconclusive"(未确认)
    matched_lord: Planet | None = None  # 命中的时间领主（confirmed 时有）
    reason: str = ""                   # 人话原因


def extract_subject_planet(statement: str) -> Planet | None:
    """从判断语句提取主题星。

    例："土星落九宫：深造是职业跃迁的必经之路" → Saturn
        "7宫主金星落10宫" → Venus
        提取不到 → None（该判断无法做事件验证，跳过不误伤）。
    """
    if not statement:
        return None
    for zh in _PLANET_ZH:  # dict 保序：长名在前
        if zh in statement:
            return _PLANET_ZH[zh]
    return None


def verify_event(chart: Chart, event_date: datetime, finding: VerifiedFinding) -> VerificationVerdict:
    """单个事件 × 单个判断的验证。

    chart: 本命盘（含 epoch_utc / sect，供 compute_firdaria 倒推）。
    event_date: 事件发生时间（UTC）。早于出生时间会由 compute_firdaria 抛错。
    """
    period = compute_firdaria(chart.epoch_utc, chart.sect, reference=event_date)
    lords = (period.major_lord, period.sub_lord)

    subject = extract_subject_planet(finding.statement)
    if subject is None:
        return VerificationVerdict(
            finding_id=finding.id,
            statement=finding.statement,
            subject_planet=None,
            verdict="inconclusive",
            reason="未能识别判断中的主题星，无法做事件验证",
        )

    if subject in lords:
        zh = PLANET_ZH_LOOKUP[subject]
        return VerificationVerdict(
            finding_id=finding.id,
            statement=finding.statement,
            subject_planet=subject,
            verdict="confirmed",
            matched_lord=subject,
            reason=f"事件发生在{zh}主运期（大限{PLANET_ZH_LOOKUP[period.major_lord]}·子限{PLANET_ZH_LOOKUP[period.sub_lord]}）",
        )

    return VerificationVerdict(
        finding_id=finding.id,
        statement=finding.statement,
        subject_planet=subject,
        verdict="inconclusive",
        reason="事件不在此星主运期（未确认，不构成反驳）",
    )


def verify_all_findings(
    chart: Chart, event_date: datetime, findings: list[VerifiedFinding]
) -> list[VerificationVerdict]:
    """事件 × 全部判断：批量验证，返回与输入同序的结果列表。"""
    return [verify_event(chart, event_date, f) for f in findings]


__all__ = [
    "VerificationVerdict",
    "extract_subject_planet",
    "verify_event",
    "verify_all_findings",
]
