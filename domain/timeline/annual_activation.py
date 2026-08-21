"""年度小限（Annual Profection）辅助层。

年度小限只回答「这一生日年被哪一宫激活」：
- 1 岁一宫，逐年顺行；age % 12 + 1 得激活宫位。
- 激活宫主星作为年度辅助观察对象。
- 法达仍是时机主轴；小限只提供年度主题/辅助证据，不输出 year_lord。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from dateutil.relativedelta import relativedelta

from domain.astrology.common import house_lord
from domain.astrology.interpretation import HouseSignificationEngine, SignificationItem
from domain.astrology.knowledge.loader import KnowledgeBase
from shared.enums import Planet
from shared.models import Chart

_DEFAULT_DOMAINS = ("career", "wealth", "relationship", "family", "self")


@dataclass(frozen=True)
class AnnualActivation:
    """生日年小限激活层：只作年度辅助，不抢法达时机权威。"""

    age: int
    annual_start: datetime
    annual_end: datetime
    activation_house: int
    activation_lord: Planet | None
    themes: tuple[SignificationItem, ...] = field(default_factory=tuple)
    firdaria_overlap: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        """出口：JSON 友好，明确标注为法达下的辅助层。"""
        return {
            "type": "annual_activation",
            "role": "auxiliary",
            "primary_timing_authority": "firdaria",
            "age": self.age,
            "annual_start": self.annual_start.isoformat(),
            "annual_end": self.annual_end.isoformat(),
            "activation_house": self.activation_house,
            "activation_lord": self.activation_lord.value if self.activation_lord else None,
            "themes": [item.to_dict() for item in self.themes],
            "firdaria_overlap": list(self.firdaria_overlap),
        }


def compute_annual_activation(
    chart: Chart,
    kb: KnowledgeBase,
    reference: datetime | None = None,
    *,
    firdaria_major_lord: Planet | None = None,
    firdaria_sub_lord: Planet | None = None,
    domains: tuple[str, ...] = _DEFAULT_DOMAINS,
    top_n: int = 5,
) -> AnnualActivation:
    """计算当前生日年小限激活宫位与年度主题。

    小限是年度辅助层：激活宫位/宫主可参与解释与行运观察，但不改变
    timing_authority=firdaria，也不产出旧式 year_lord。
    """
    birth = chart.epoch_utc
    if birth.tzinfo is None:
        birth = birth.replace(tzinfo=timezone.utc)
    ref = reference or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    if ref < birth:
        raise ValueError("参考时间早于出生时间")

    annual_start, annual_end, age = _birthday_year_bounds(birth, ref)
    activation_house = age % 12 + 1
    activation_lord = house_lord(chart, kb, activation_house)
    engine = HouseSignificationEngine(kb)
    themes: list[SignificationItem] = []
    for domain in domains:
        themes.extend(engine.interpret(chart, domain, houses=[activation_house], max_items=top_n))

    seen_words: set[tuple[int, str, str]] = set()
    unique_themes: list[SignificationItem] = []
    for item in sorted(themes, key=lambda i: i.strength, reverse=True):
        key = (item.house, item.word, item.polarity)
        if key in seen_words:
            continue
        seen_words.add(key)
        unique_themes.append(item)
        if len(unique_themes) >= top_n:
            break

    overlap: list[str] = []
    if activation_lord is not None:
        if activation_lord == firdaria_major_lord:
            overlap.append("major_lord")
        if activation_lord == firdaria_sub_lord:
            overlap.append("sub_lord")

    return AnnualActivation(
        age=age,
        annual_start=annual_start,
        annual_end=annual_end,
        activation_house=activation_house,
        activation_lord=activation_lord,
        themes=tuple(unique_themes),
        firdaria_overlap=tuple(overlap),
    )


def _birthday_year_bounds(birth: datetime, ref: datetime) -> tuple[datetime, datetime, int]:
    """返回当前生日年起止与周岁年龄。"""
    age = ref.year - birth.year
    annual_start = birth + relativedelta(years=age)
    if annual_start > ref:
        age -= 1
        annual_start = birth + relativedelta(years=age)
    annual_end = birth + relativedelta(years=age + 1)
    return annual_start, annual_end, age
