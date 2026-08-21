"""Life Rhythm —— 人生节律报告后端契约。

本模块只做 Domain-first 的确定性编排：
本命承诺 → 法达章节 → 年度小限辅助 → 行运触发。

硬线：法达仍是 timing_authority；年度小限只作为辅助层，不输出 year_lord。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from domain.astrology.interpretation.models import HouseSynapsis, SignificationItem
from domain.astrology.interpretation.natal import DOMAIN_ZH, NATAL_DOMAINS, natal_reading
from domain.astrology.knowledge.loader import KnowledgeBase
from domain.timeline.annual_activation import AnnualActivation
from domain.timeline.firdaria import FirdariaReading
from domain.timeline.timing_stack import build_timing_stack
from shared.models import Chart, Person

_SOURCE_LAYERS = (
    "natal_promise",
    "firdaria_chapter",
    "annual_activation",
    "transit_triggers",
)


@dataclass(frozen=True)
class LifeStage:
    """本命承诺：人生主题的底色与可发展方向。"""

    domain: str
    domain_label: str
    themes: tuple[SignificationItem, ...] = field(default_factory=tuple)
    synapsis: tuple[HouseSynapsis, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        """JSON 友好出口：只暴露确定性本命素材。"""
        return {
            "type": "natal_promise",
            "domain": self.domain,
            "domain_label": self.domain_label,
            "themes": [item.to_dict() for item in self.themes],
            "synapsis": [item.to_dict() for item in self.synapsis],
        }


@dataclass(frozen=True)
class LifeChapter:
    """法达章节：人生阶段的主时间轴。"""

    firdaria: FirdariaReading

    def to_dict(self) -> dict:
        """JSON 友好出口：明确法达是唯一时机权威。"""
        return {
            "type": "firdaria_chapter",
            "timing_authority": "firdaria",
            **self.firdaria.to_dict(),
        }


@dataclass(frozen=True)
class LifeRhythm:
    """人生节律：本命承诺 + 法达章节 + 小限年度 + 行运触发。"""

    person_id: str
    chart_id: str
    generated_at: datetime
    months: int
    natal_promise: tuple[LifeStage, ...]
    firdaria_chapter: LifeChapter
    annual_activation: AnnualActivation
    transit_triggers: tuple[dict, ...]

    def to_dict(self) -> dict:
        """报告契约出口：供 API/前端消费，不含 LLM 生成内容。"""
        return {
            "type": "life_rhythm",
            "person_id": self.person_id,
            "chart_id": self.chart_id,
            "generated_at": self.generated_at.isoformat(),
            "months": self.months,
            "timing_authority": "firdaria",
            "source_layers": list(_SOURCE_LAYERS),
            "natal_promise": [stage.to_dict() for stage in self.natal_promise],
            "firdaria_chapter": self.firdaria_chapter.to_dict(),
            "annual_activation": self.annual_activation.to_dict(),
            "transit_triggers": list(self.transit_triggers),
        }


def build_life_rhythm(
    person: Person,
    chart: Chart,
    kb: KnowledgeBase,
    reference: datetime | None = None,
    *,
    months: int = 6,
    domains: tuple[str, ...] = NATAL_DOMAINS,
) -> LifeRhythm:
    """构建 Life Rhythm 报告契约。

    该函数不产生新的占星判断，只把既有确定性层统一成可审计结构：
    - natal_promise：本命语义场 Top 主题；
    - firdaria_chapter：法达大限/子限与时间领主本命条件；
    - annual_activation：年度小限辅助层；
    - transit_triggers：法达目标星/帮手星/年度辅助星上的行运触发。
    """
    ref = reference or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    requested_months = min(6, max(1, int(months)))

    natal = natal_reading(chart, kb, domains=domains)
    stack = build_timing_stack(person, chart, kb, reference=ref)

    stages = tuple(
        LifeStage(
            domain=domain,
            domain_label=DOMAIN_ZH.get(domain, domain),
            themes=tuple(natal.top(domain, 3)),
            synapsis=tuple(natal.synapsis[:3]),
        )
        for domain in domains
        if natal.top(domain, 3)
    )

    return LifeRhythm(
        person_id=person.id,
        chart_id=chart.id,
        generated_at=ref,
        months=requested_months,
        natal_promise=stages,
        firdaria_chapter=LifeChapter(stack.firdaria),
        annual_activation=stack.annual_activation,
        transit_triggers=tuple(_transit_trigger(row) for row in stack.transits[:requested_months]),
    )


def _transit_trigger(row: dict) -> dict:
    """TimingStack 月行运行 → Life Rhythm 触发行。

    保留三层目标星，便于审计：直接目标、互溶/接纳帮手、实际扫描目标。
    """
    return {
        "type": "transit_trigger",
        "month": row.get("month", ""),
        "score": row.get("score", 0.0),
        "tag": row.get("tag", "中性"),
        "timing_authority": "firdaria",
        "target_planets": list(row.get("target_planets") or []),
        "helper_target_planets": list(row.get("helper_target_planets") or []),
        "scoring_target_planets": list(row.get("scoring_target_planets") or []),
        "annual_activation": row.get("annual_activation"),
    }
