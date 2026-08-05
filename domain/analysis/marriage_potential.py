"""MarriagePotential —— 婚姻潜力分析模块（文法引擎驱动）。

theme_map 的 marriage_potential 配方：7宫 + 金/土/木 + 7宫主 + 时机，
聚焦承诺能力与婚姻祝福（单盘，无需对方数据）。
"""

from __future__ import annotations

from shared.models import Chart, Fact, Person

from domain.analysis.base import AnalysisModule
from domain.astrology.evidence import RuleEngine
from domain.astrology.knowledge import load_knowledge

_THEME_ID = "marriage_potential"


class MarriagePotential(AnalysisModule):
    name = "MarriagePotential"
    required_indicators = ["Lordship", "AspectQuality"]

    def __init__(self, kb=None):
        self._engine = RuleEngine(kb or load_knowledge())

    def analyze(self, chart: Chart, person: Person, params: dict) -> list[Fact]:
        return self._engine.run_theme(chart, _THEME_ID)
