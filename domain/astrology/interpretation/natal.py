"""本命解读组合：跨 8 域跑语义场引擎，产出结构化本命解读。

对应 PRD"初识 First Reading"场景（生成本命盘 → 你是这样的星灵气质）。
确定性、无 LLM；直接可调用、可测试；LLM 转述层可据此织人话。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shared.models import Chart

from domain.astrology.interpretation.models import HouseSynapsis, SignificationItem
from domain.astrology.interpretation.signification import HouseSignificationEngine
from domain.astrology.interpretation.synapsis import detect_synapsis
from domain.astrology.knowledge.loader import KnowledgeBase

#: 本命解读覆盖的问题域（领域引擎 v2：10 个语义场域；daily 是跨域行运视图，不在此表）
NATAL_DOMAINS: tuple[str, ...] = (
    "career", "wealth", "relationship", "emotion",
    "health", "family", "learning", "growth", "network", "self",
)

DOMAIN_ZH: dict[str, str] = {
    "career": "职业",
    "wealth": "财富",
    "relationship": "感情",
    "emotion": "情绪",
    "health": "健康",
    "family": "家庭",
    "learning": "学习",
    "growth": "远方·信念",
    "network": "人际·社群",
    "self": "自我",
}


@dataclass
class NatalReading:
    """一份结构化本命解读。"""

    chart: Chart
    synapsis: list[HouseSynapsis] = field(default_factory=list)
    domains: dict[str, list[SignificationItem]] = field(default_factory=dict)

    def top(self, domain: str, n: int = 3) -> list[SignificationItem]:
        """某域的 Top-N 解读。"""
        return self.domains.get(domain, [])[:n]

    def to_dict(self) -> dict:
        """出口：跨 8 域本命解读，JSON 友好。"""
        return {
            "synapsis": [s.to_dict() for s in self.synapsis],
            "domains": {
                dom: [i.to_dict() for i in items]
                for dom, items in self.domains.items()
            },
        }


def natal_reading(
    chart: Chart,
    kb: KnowledgeBase,
    domains: tuple[str, ...] = NATAL_DOMAINS,
) -> NatalReading:
    """跨域组合本命解读（确定性，无 LLM）。"""
    engine = HouseSignificationEngine(kb)
    reading = NatalReading(chart=chart, synapsis=detect_synapsis(chart, kb))
    for domain in domains:
        reading.domains[domain] = engine.interpret(chart, domain, max_items=5)
    return reading
