"""ThemeModule —— theme_map 驱动的通用分析模块基类。

大部分主题模块只是"跑一个 theme_map 配方"，本质相同。
子类只需声明 name + theme_id。
"""

from __future__ import annotations

from shared.models import Chart, Fact, Person

from domain.analysis.base import AnalysisModule
from domain.astrology.evidence import RuleEngine
from domain.astrology.knowledge import load_knowledge


class ThemeModule(AnalysisModule):
    """按 theme_map 配方产解读的薄模块。"""

    theme_id: str = ""

    def __init__(self, kb=None):
        self._engine = RuleEngine(kb or load_knowledge())

    def analyze(self, chart: Chart, person: Person, params: dict) -> list[Fact]:
        return self._engine.run_theme(chart, self.theme_id)
