"""Psychology —— 职业心理状态分析模块（文法引擎驱动）。

theme_map 的 career_psychology 配方：
- 6宫(工作负荷) + 12宫(倦怠/隐性压力) 的月/日/水/土落宫
- 压力相位对（月土/日土/火土/月火）给出"倦怠风险"极性
"""

from __future__ import annotations

from shared.models import Chart, Fact, Person

from domain.analysis.base import AnalysisModule
from domain.astrology.evidence import RuleEngine
from domain.astrology.knowledge import load_knowledge

_THEME_ID = "career_psychology"


class Psychology(AnalysisModule):
    name = "Psychology"
    required_indicators = ["AspectQuality"]

    def __init__(self, kb=None):
        self._engine = RuleEngine(kb or load_knowledge())

    def analyze(self, chart: Chart, person: Person, params: dict) -> list[Fact]:
        return self._engine.run_theme(chart, _THEME_ID)
