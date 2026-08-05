"""Wealth —— 财运分析模块（文法引擎驱动）。

theme_map 的 wealth 配方：2宫(正财) + 8宫(偏财/共同资源) + 11宫(进账/人脉)，
木/土/金/水四颗财帛相关行星的落宫与相位。
"""

from __future__ import annotations

from shared.models import Chart, Fact, Person

from domain.analysis.base import AnalysisModule
from domain.astrology.evidence import RuleEngine
from domain.astrology.knowledge import load_knowledge

_THEME_ID = "wealth"


class Wealth(AnalysisModule):
    name = "Wealth"
    required_indicators = ["Lordship", "AspectQuality"]

    def __init__(self, kb=None):
        self._engine = RuleEngine(kb or load_knowledge())

    def analyze(self, chart: Chart, person: Person, params: dict) -> list[Fact]:
        return self._engine.run_theme(chart, _THEME_ID)
