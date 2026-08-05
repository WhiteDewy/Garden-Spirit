"""RelationshipStatus —— 感情状态分析模块（文法引擎驱动）。

theme_map 的 relationship_status 配方：5/7宫 + 金/月/火 + 7宫主，
聚焦"你的关系模式与健康度"（单盘，无需对方数据）。
"""

from __future__ import annotations

from shared.models import Chart, Fact, Person

from domain.analysis.base import AnalysisModule
from domain.astrology.evidence import RuleEngine
from domain.astrology.knowledge import load_knowledge

_THEME_ID = "relationship_status"


class RelationshipStatus(AnalysisModule):
    name = "RelationshipStatus"
    required_indicators = ["Lordship", "AspectQuality"]

    def __init__(self, kb=None):
        self._engine = RuleEngine(kb or load_knowledge())

    def analyze(self, chart: Chart, person: Person, params: dict) -> list[Fact]:
        return self._engine.run_theme(chart, _THEME_ID)
