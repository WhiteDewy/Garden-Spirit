"""Executor —— 按 ExecutionPlan 执行分析模块。

按依赖（DAG）顺序运行分析模块，聚合所有 Facts 为 FactSet。
只调用 Domain 层，绝不调用 LLM（原则二）。
"""

from __future__ import annotations

from foundation.logger import get_logger
from foundation.utils import new_id, utc_now
from shared.models import Chart, ExecutionPlan, ExecutionStatus, ExecutionStep, Fact, FactSet, Person

from domain.analysis import AnalysisModule

logger = get_logger("reasoning.executor")


class Executor:
    """分析模块调度器。"""

    def __init__(self, modules: dict[str, AnalysisModule] | None = None):
        self._modules: dict[str, AnalysisModule] = dict(modules or {})

    # ------------------------------------------------------------------

    def register(self, module: AnalysisModule) -> None:
        """注册分析模块（按 module.name）。"""
        self._modules[module.name] = module

    def register_all(self, modules: list[AnalysisModule]) -> None:
        for m in modules:
            self.register(m)

    def has_module(self, name: str) -> bool:
        return name in self._modules

    # ------------------------------------------------------------------

    def execute(
        self, plan: ExecutionPlan, chart: Chart, person: Person
    ) -> FactSet:
        """执行计划，产出聚合 Facts。

        DAG 拓扑：迭代运行"依赖已满足"的步骤；无进展（成环）时停止。
        """
        all_facts: list[Fact] = []
        executed: set[str] = set()
        step_by_id = {s.id: s for s in plan.steps}

        while True:
            progressed = False
            for step in plan.steps:
                if step.id in executed:
                    continue
                if not all(
                    (d not in step_by_id) or (d in executed)
                    for d in step.dependencies
                ):
                    continue

                self._run_step(step, chart, person, all_facts)
                executed.add(step.id)
                progressed = True

            if not progressed:
                # 无法进展：依赖成环或缺少根步骤
                skipped = [s for s in plan.steps if s.id not in executed]
                for s in skipped:
                    s.status = ExecutionStatus.SKIPPED
                break

        fact_set = FactSet(
            id=new_id("facts"),
            chart_ids=plan.chart_ids,
            intent_domain="",
            facts=all_facts,
            generated_at=utc_now(),
        )
        plan.status = ExecutionStatus.COMPLETED
        plan.completed_at = utc_now()
        logger.info(
            "执行完成: %d/%d 步骤, %d 事实",
            len(executed),
            len(plan.steps),
            len(all_facts),
        )
        return fact_set

    # ------------------------------------------------------------------

    def _run_step(
        self, step: ExecutionStep, chart: Chart, person: Person, sink: list[Fact]
    ) -> None:
        step.status = ExecutionStatus.RUNNING
        step.started_at = utc_now()
        try:
            module = self._modules.get(step.module)
            if module is None:
                raise KeyError(f"分析模块未注册: {step.module}")
            facts = module.analyze(chart, person, step.params)
            sink.extend(facts)
            step.status = ExecutionStatus.COMPLETED
        except Exception as e:  # noqa: BLE001
            step.status = ExecutionStatus.FAILED
            step.error_message = str(e)
            logger.error("执行步骤失败 %s: %s", step.module, e)
        step.completed_at = utc_now()
