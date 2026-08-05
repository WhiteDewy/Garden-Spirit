"""PartnerTraits —— 对象特征分析模块（文法引擎驱动）。

通过 theme_map 的 partner_traits 配方，用 RuleEngine 合成：
- 5宫(心动/桃花) + 7宫(婚姻对象) + 8宫(亲密) 的落宫解读
- 金/火/月等行星对相位解读（激情/温柔/压抑）
- 5宫主/7宫主落宫解读

本身是薄模块：只调用 run_theme，解读内容全部在 knowledge/rules/ 里。
"""

from __future__ import annotations

from shared.models import Chart, Fact, Person

from domain.analysis.base import AnalysisModule
from domain.astrology.evidence import RuleEngine
from domain.astrology.knowledge import load_knowledge

_THEME_ID = "partner_traits"


class PartnerTraits(AnalysisModule):
    name = "PartnerTraits"
    required_indicators = ["Lordship", "AspectQuality"]

    def __init__(self, kb=None):
        self._engine = RuleEngine(kb or load_knowledge())

    def analyze(self, chart: Chart, person: Person, params: dict) -> list[Fact]:
        return self._engine.run_theme(chart, _THEME_ID)
