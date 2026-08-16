"""分析模块基类。

分析模块是"语义镜头"：把一个主题（职业强度/时机/风险...）映射到
具体的占星事实（Facts）。它们只产出机械事实 + 主题标注，
加权与极性由 Evidence 层统一处理。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from shared.enums import Planet
from shared.models import Chart, Fact, Person


def _planet_from_enrichment_value(value: object) -> Planet | None:
    """把执行 enrichment 中的行星标识安全转成 Planet。"""
    if isinstance(value, Planet):
        return value
    raw = getattr(value, "value", value)
    if raw in (None, ""):
        return None
    try:
        return Planet(str(raw))
    except ValueError:
        return None


def focus_planets_from_enrichment(
    chart: Chart,
    kb,
    enrichment: dict | None,
    *,
    include_house_lords: bool = True,
    include_focus_houses: bool = False,
) -> list[Planet]:
    """从定位层 enrichment 派生本轮需要额外扫描的实盘承载星。"""
    from domain.astrology.common import house_lord

    enrich = enrichment or {}
    planets: list[Planet] = []

    def add(planet: Planet | None) -> None:
        if planet is not None and planet in chart.planets and planet not in planets:
            planets.append(planet)

    for key in ("focus_planets", "house_lord_planets", "house_occupants"):
        for raw in enrich.get(key) or []:
            add(_planet_from_enrichment_value(raw))

    house_keys: list[str] = []
    if include_house_lords:
        house_keys.append("focus_house_lords")
    if include_focus_houses:
        house_keys.append("focus_houses")

    for key in house_keys:
        for raw_house in enrich.get(key) or []:
            try:
                house = int(raw_house)
            except (TypeError, ValueError):
                continue
            if not 1 <= house <= 12:
                continue
            add(house_lord(chart, kb, house))

    return planets


class AnalysisModule(ABC):
    """一个可复用的分析模块。"""

    #: 模块名（与 Strategy YAML 中的 module 对应）
    name: str = "base"

    #: 该模块需要的事实类别（用于预检）
    required_indicators: list[str] = []

    @abstractmethod
    def analyze(self, chart: Chart, person: Person, params: dict) -> list[Fact]:
        """分析星盘，产出一组主题相关的事实。

        Args:
            chart: 本命盘（或行运盘等）
            person: 用户档案
            params: 来自 Strategy YAML 的模块参数

        Returns:
            list[Fact] —— 全部为机械事实，不携带极性判断。
            若模块产出了明确倾向（如时机窗口好坏），应以 THEME 类 Fact
            携带 {theme, polarity, weight, confidence} 载荷，由
            EvidenceBuilder._theme_evidence 采纳。
        """
        raise NotImplementedError
