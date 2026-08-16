"""Timing —— 时机分析模块。

方法（v3）：法达大限/子限定时期主轴，再对时间窗口按月扫描行运相位。
行运只打到「当前时间领主 + 本轮问题相关征象星/宫主星」，不再用旧年度领主或固定太阳兜底。
不做卜卦。

产出：每个有利/不利时间窗口一条 THEME 事实。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta

from foundation.logger import get_logger
from foundation.utils import new_id
from shared.enums import EvidencePolarity, FactCategory, Planet
from shared.models import Chart, Fact, Person

from domain.analysis.base import AnalysisModule
from domain.astrology.calculation import TransitCalculator
from domain.astrology.common import house_lord
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
        from domain.timeline.firdaria import compute_firdaria  # noqa: PLC0415

        period = compute_firdaria(chart.epoch_utc, chart.sect, now)
        targets = self._timing_targets(chart, period.major_lord, period.sub_lord, params.get("_enrichment"))
        helper_targets = self._helper_targets(chart, targets)
        scoring_targets = targets | helper_targets
        if not scoring_targets:
            logger.warning("无法确定法达/问题目标星，Timing 模块跳过")
            return facts

        # 逐月扫描
        monthly_scores: list[tuple[datetime, float]] = []
        for i in range(months):
            month_start = now.replace(day=1) + relativedelta(months=i + start_offset)
            score = self._month_score(chart, month_start, scoring_targets)
            monthly_scores.append((month_start, score))

        # 分组为窗口
        windows = self._group_windows(
            monthly_scores,
            targets,
            helper_targets,
            period.major_lord,
            period.sub_lord,
            chart,
        )
        for window in windows:
            facts.append(self._window_fact(chart, window))

        logger.info("Timing: %d 个月扫描 → %d 个时间窗口", months, len(windows))
        return facts

    # ------------------------------------------------------------------

    def _timing_targets(
        self,
        chart: Chart,
        major_lord: Planet,
        sub_lord: Planet,
        enrichment: dict | None = None,
    ) -> set[Planet]:
        """法达时间领主 + 本轮问题相关征象星/宫主星。"""
        targets: set[Planet] = {major_lord, sub_lord}
        enrich = enrichment or {}
        for raw in enrich.get("focus_planets") or []:
            planet = self._planet_from_value(raw)
            if planet is not None:
                targets.add(planet)
        raw_houses = [*(enrich.get("focus_house_lords") or []), *(enrich.get("focus_houses") or [])]
        for raw_house in raw_houses:
            try:
                house = int(raw_house)
            except (TypeError, ValueError):
                continue
            lord = house_lord(chart, self._kb, house)
            if lord is not None:
                targets.add(lord)
        return {planet for planet in targets if planet in chart.planets}

    def _helper_targets(self, chart: Chart, targets: set[Planet]) -> set[Planet]:
        """本命互溶/激活接纳里的帮手星，也作为行运触发观察对象。"""
        from domain.astrology.interpretation.synapsis import ConnectionClassifier  # noqa: PLC0415

        clf = ConnectionClassifier(self._kb)
        helpers: set[Planet] = set()
        for target in targets:
            for ally in clf.ally_timeline(chart, target):
                if ally.helper in chart.planets:
                    helpers.add(ally.helper)
        return helpers - targets

    @staticmethod
    def _planet_from_value(value: object) -> Planet | None:
        """受控地把 enrichment 字符串转成 Planet。"""
        if isinstance(value, Planet):
            return value
        if not isinstance(value, str):
            return None
        try:
            return Planet(value.lower())
        except ValueError:
            return None

    def _month_score(
        self, chart: Chart, month_start: datetime, targets: set[Planet]
    ) -> float:
        """某月的行运强度分：Σ(行运对目标时间领主/问题征象星的相位权值)。"""
        aspects = self._transit.transit_aspects(chart, month_start)
        score = 0.0
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
        targets: set[Planet],
        helper_targets: set[Planet],
        major_lord: Planet,
        sub_lord: Planet,
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
                    "targets": sorted(targets, key=lambda p: p.value),
                    "helper_targets": sorted(helper_targets, key=lambda p: p.value),
                    "scoring_targets": sorted(targets | helper_targets, key=lambda p: p.value),
                    "firdaria_major_lord": major_lord,
                    "firdaria_sub_lord": sub_lord,
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

        major = self._kb.planet(window["firdaria_major_lord"]).name_zh
        sub = self._kb.planet(window["firdaria_sub_lord"]).name_zh
        target_names = "、".join(self._kb.planet(p).name_zh for p in window["targets"])
        helper_names = "、".join(self._kb.planet(p).name_zh for p in window["helper_targets"])
        target_phrase = target_names if not helper_names else f"{target_names}（含帮手星：{helper_names}）"
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
            description=(
                f"时间窗口 {label}：法达{major}大限/{sub}子限，"
                f"行运对{target_phrase}总体{quality}（净分{net:+.1f}）"
            ),
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
                "timing_authority": "firdaria",
                "firdaria_major_lord": window["firdaria_major_lord"].value,
                "firdaria_sub_lord": window["firdaria_sub_lord"].value,
                "target_planets": [p.value for p in window["targets"]],
                "helper_target_planets": [p.value for p in window["helper_targets"]],
                "scoring_target_planets": [p.value for p in window["scoring_targets"]],
            },
        )
