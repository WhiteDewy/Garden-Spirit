"""WindowScanner —— 人生 K 线扫描器。

按周扫描未来 N 个月，聚合行运对本命关键行星的吉凶相位，
产出机会分/压力分的时序曲线。这是人生 K 线的数据来源。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from foundation.logger import get_logger
from foundation.utils import utc_now
from shared.constants import ASPECT_ZH
from shared.enums import EvidencePolarity, Planet
from shared.models import Chart, Person, Timeline, TimelineWindow

from domain.astrology.calculation import TransitCalculator
from domain.astrology.knowledge import load_knowledge

logger = get_logger("timeline.scanner")

# K 线参考行运（外行星为背景，日月水金火为细节）
_SIGNIFICATORS = [
    Planet.JUPITER,
    Planet.SATURN,
    Planet.URANUS,
    Planet.NEPTUNE,
    Planet.PLUTO,
    Planet.SUN,
    Planet.MERCURY,
    Planet.VENUS,
    Planet.MARS,
]

# 各领域关注的本命行星
_DOMAIN_FOCUS = {
    "career": [Planet.SUN, Planet.SATURN, Planet.JUPITER, Planet.MERCURY],
    "relationship": [Planet.VENUS, Planet.MOON, Planet.MARS, Planet.SATURN],
    "wealth": [Planet.JUPITER, Planet.SATURN, Planet.VENUS, Planet.MERCURY],
    "general": [
        Planet.SUN, Planet.MOON, Planet.MERCURY, Planet.VENUS, Planet.MARS,
        Planet.JUPITER, Planet.SATURN, Planet.URANUS, Planet.NEPTUNE, Planet.PLUTO,
    ],
}


class WindowScanner:
    """行运扫描器。"""

    def __init__(self, kb=None):
        self._kb = kb or load_knowledge()
        self._transit = TransitCalculator(self._kb)

    def scan(
        self,
        chart: Chart,
        person: Person,
        months: int = 12,
        domain: str = "general",
        window_days: int = 7,
    ) -> Timeline:
        """扫描未来 months 个月，按 window_days 步长聚合。"""
        focus = _DOMAIN_FOCUS.get(domain, _DOMAIN_FOCUS["general"])
        start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        total_windows = max(1, int(months * 30 / window_days))

        windows: list[TimelineWindow] = []
        for i in range(total_windows):
            w_start = start + timedelta(days=window_days * i)
            w_end = w_start + timedelta(days=window_days)
            w_mid = w_start + timedelta(days=window_days / 2)

            opportunity, pressure, transits = self._window_scores(chart, w_mid, focus)
            quality = (
                EvidencePolarity.POSITIVE if opportunity - pressure > 0.5
                else EvidencePolarity.NEGATIVE if pressure - opportunity > 0.5
                else EvidencePolarity.NEUTRAL
            )
            windows.append(
                TimelineWindow(
                    start=w_start,
                    end=w_end,
                    opportunity_score=round(opportunity, 2),
                    pressure_score=round(pressure, 2),
                    quality=quality,
                    key_transits=transits[:3],
                )
            )

        timeline = Timeline(
            person_id=person.id,
            chart_id=chart.id,
            label=f"{domain} K 线 · 未来 {months} 个月",
            windows=windows,
            generated_at=utc_now(),
        )
        logger.info(
            "K 线扫描完成: %d 个窗口, 最佳=%s, 最差=%s",
            len(windows),
            timeline.best_window.start.strftime("%Y-%m") if timeline.best_window else "-",
            timeline.worst_window.start.strftime("%Y-%m") if timeline.worst_window else "-",
        )
        return timeline

    # ------------------------------------------------------------------

    def _window_scores(
        self, chart: Chart, moment: datetime, focus: list[Planet]
    ) -> tuple[float, float, list[str]]:
        """某时刻的机会分/压力分/主要行运。"""
        aspects = self._transit.transit_aspects(chart, moment, _SIGNIFICATORS)
        opportunity = 0.0
        pressure = 0.0
        transits: list[tuple[float, str]] = []

        for aspect in aspects:
            if aspect.body2 not in focus:
                continue
            info = self._kb.aspects.get(aspect.aspect_type)
            if info is None:
                continue
            base = info.weight_multiplier
            if aspect.body1 in (Planet.JUPITER, Planet.SATURN):
                base *= 1.2          # 木土影响最持久
            if aspect.application.value == "applying":
                base *= 1.2
            elif aspect.application.value == "separating":
                base *= 0.8

            if info.nature == "HARMONIOUS":
                opportunity += base
            elif info.nature == "DYNAMIC":
                pressure += base

            transits.append((
                base,
                f"{self._kb.planet(aspect.body1).name_zh}"
                f"{ASPECT_ZH.get(aspect.aspect_type.value, aspect.aspect_type.value)}"
                f"你本命的{self._kb.planet(aspect.body2).name_zh}",
            ))

        transits.sort(key=lambda t: abs(t[0]), reverse=True)
        return opportunity, pressure, [t[1] for t in transits]
