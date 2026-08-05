"""Timing —— 时机分析模块。

方法（v1 冻结）：年度推运（Annual Profection）定年主题，
再对时间窗口按月扫描行运相位（木星/土星/天王星等对本命年主星与太阳）。
不做卜卦。

产出：每个有利/不利时间窗口一条 THEME 事实。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta

from foundation.logger import get_logger
from foundation.utils import new_id
from shared.enums import EvidencePolarity, FactCategory, Planet, Sign
from shared.models import Chart, Fact, Person

from domain.analysis.base import AnalysisModule
from domain.astrology.calculation import TransitCalculator
from domain.astrology.knowledge import load_knowledge

logger = get_logger("analysis.timing")

_WINDOW_BONUS = 0.5
_FAVORABLE_THRESHOLD = 0.5


class Timing(AnalysisModule):
    name = "Timing"
    required_indicators = ["Timing"]

    def __init__(self, kb=None):
        self._kb = kb or load_knowledge()
        self._transit = TransitCalculator(self._kb)

    def analyze(self, chart: Chart, person: Person, params: dict) -> list[Fact]:
        facts: list[Fact] = []
        months = int(params.get("window_months", 6))
        # 窗口起点偏移（月）：追问"那明年呢？"时从偏移处扫描
        start_offset = int(params.get("start_offset_months", 0))

        now = datetime.now(timezone.utc)
        year_lord = self._year_lord(chart, person, now)
        if year_lord is None:
            logger.warning("无法确定年主星，Timing 模块跳过")
            return facts

        # 逐月扫描
        monthly_scores: list[tuple[datetime, float]] = []
        for i in range(months):
            month_start = now.replace(day=1) + relativedelta(months=i + start_offset)
            score = self._month_score(chart, month_start, year_lord)
            monthly_scores.append((month_start, score))

        # 分组为窗口
        windows = self._group_windows(monthly_scores, year_lord, chart)
        for window in windows:
            facts.append(self._window_fact(chart, window))

        logger.info("Timing: %d 个月扫描 → %d 个时间窗口", months, len(windows))
        return facts

    # ------------------------------------------------------------------

    def _year_lord(self, chart: Chart, person: Person, reference: datetime) -> Planet | None:
        """年度推运年主星。

        age = 已满周岁；推运宫位 = (age % 12) + 1；
        年主星 = 该宫宫头星座的传统守护星。
        """
        birth = person.birth.datetime_utc
        if birth.tzinfo is not None:
            birth = birth.astimezone(timezone.utc).replace(tzinfo=None)
        age = reference.year - birth.year - (
            1 if (reference.month, reference.day) < (birth.month, birth.day) else 0
        )
        house_num = (age % 12) + 1

        cusp = chart.house_cusps.get(house_num)
        if cusp is None:
            return None
        sign: Sign = cusp.sign
        return self._kb.sign(sign).traditional_ruler

    def _month_score(
        self, chart: Chart, month_start: datetime, year_lord: Planet
    ) -> float:
        """某月的行运强度分：Σ(行运对年主星的相位权值) + 太阳信号。"""
        aspects = self._transit.transit_aspects(chart, month_start)
        score = 0.0
        targets = {year_lord, Planet.SUN}
        for aspect in aspects:
            if aspect.body2 not in targets:
                continue
            info = self._kb.aspects.get(aspect.aspect_type)
            if info is None:
                continue
            base = info.weight_multiplier
            # 入相加成
            if aspect.application.value == "applying":
                base *= 1.2
            elif aspect.application.value == "separating":
                base *= 0.8
            # 行星强度：木星/土星/天王/海王/冥王权重递增
            if aspect.body1 == Planet.JUPITER:
                base *= 1.0
            elif aspect.body1 == Planet.SATURN:
                base *= 1.2
            elif aspect.body1 in (Planet.URANUS, Planet.NEPTUNE, Planet.PLUTO):
                base *= 0.8

            if info.nature == "HARMONIOUS":
                score += base
            elif info.nature == "DYNAMIC":
                score -= base
        return score

    def _group_windows(
        self,
        monthly_scores: list[tuple[datetime, float]],
        year_lord: Planet,
        chart: Chart,
    ) -> list[dict]:
        """把连续同向的月份聚合成窗口。"""
        windows: list[dict] = []
        current = None  # {"months": [...], "direction": str}

        for month_start, score in monthly_scores:
            direction = "favorable" if score >= _FAVORABLE_THRESHOLD else (
                "unfavorable" if score <= -_FAVORABLE_THRESHOLD else "neutral"
            )
            if current is None:
                current = {"months": [(month_start, score)], "direction": direction}
            elif current["direction"] == direction:
                current["months"].append((month_start, score))
            else:
                windows.append(current)
                current = {"months": [(month_start, score)], "direction": direction}
        if current:
            windows.append(current)

        result = []
        for w in windows:
            months, direction = w["months"], w["direction"]
            net = sum(s for _, s in months)
            result.append(
                {
                    "direction": direction,
                    "start": months[0][0],
                    "end": months[-1][0] + relativedelta(months=1) - timedelta(days=1),
                    "net_score": net,
                    "year_lord": year_lord,
                }
            )
        return result

    def _window_fact(self, chart: Chart, window: dict) -> Fact:
        direction = window["direction"]
        if direction == "favorable":
            polarity = EvidencePolarity.POSITIVE
        elif direction == "unfavorable":
            polarity = EvidencePolarity.NEGATIVE
        else:
            polarity = EvidencePolarity.NEUTRAL

        net = window["net_score"]
        weight = min(4.0, max(0.5, abs(net)))
        confidence = 0.65

        lord = self._kb.planet(window["year_lord"]).name_zh
        label = f"{window['start'].strftime('%Y-%m')} 至 {window['end'].strftime('%Y-%m')}"
        quality = {
            "favorable": "有利",
            "unfavorable": "不利",
            "neutral": "中性",
        }[direction]

        return Fact(
            id=new_id("fact"),
            category=FactCategory.THEME,
            chart_id=chart.id,
            description=f"时间窗口 {label}：行运对年主星{lord}总体{quality}（净分{net:+.1f}）",
            extracted_at=datetime.now(timezone.utc),
            payload={
                "theme": "timing_window",
                "polarity": polarity.value,
                "weight": weight,
                "confidence": confidence,
                "window_start": window["start"].isoformat(),
                "window_end": window["end"].isoformat(),
                "direction": direction,
                "module": self.name,
            },
        )
