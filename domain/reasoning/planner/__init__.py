"""Planner —— Strategy → ExecutionPlan。

接收已解析的 Intent + Strategy，产出可执行的计划。
计算本命盘（占星层），把 Strategy 的步骤 DAG 转成 ExecutionStep 列表。
"""

from __future__ import annotations

from datetime import datetime, timezone

from foundation.logger import get_logger
from foundation.utils import new_id
from shared.models import (
    Chart,
    ExecutionPlan,
    ExecutionStatus,
    ExecutionStep,
    Intent,
    Person,
    Strategy,
)

from domain.astrology.calculation import NatalChartCalculator

logger = get_logger("reasoning.planner")


class Planner:
    """把 Strategy 实例化为 ExecutionPlan。"""

    def __init__(self, calculator: NatalChartCalculator | None = None):
        self._calculator = calculator or NatalChartCalculator()

    def create_plan(
        self,
        intent: Intent,
        strategy: Strategy,
        person: Person,
        chart: Chart | None = None,
        enrichment: dict | None = None,
    ) -> tuple[ExecutionPlan, Chart]:
        """构建执行计划，并确保有本命盘可用。

        enrichment: 可选——来自 IntentDecomposer 的焦点提示
            {focus_houses, focus_planets, focus_house_lords, focus_aspect_pairs, focus_dimensions}
            注入到每个 ExecutionStep 的 params['_enrichment']，不影响现有模块逻辑。

        Returns:
            (plan, chart) —— chart 供 Executor 使用，避免重复计算。
        """
        if chart is None:
            chart = self._calculator.compute(person)

        enrich = enrichment or {}
        # 步骤 ID = 模块名（见 StrategyLoader._to_step），依赖即为模块名列表
        steps = [
            ExecutionStep(
                id=new_id("step"),
                strategy_step_id=step.id,
                module=step.analysis_module,
                params={**dict(step.config), "_enrichment": enrich},
                dependencies=list(step.dependencies),
                priority=step.priority,
            )
            for step in strategy.steps
        ]

        plan = ExecutionPlan(
            id=new_id("plan"),
            strategy_id=strategy.id,
            intent_id=intent.id,
            chart_ids=[chart.id],
            steps=steps,
            status=ExecutionStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        logger.info("计划创建: %s → %d 步", strategy.id, len(steps))
        return plan, chart
