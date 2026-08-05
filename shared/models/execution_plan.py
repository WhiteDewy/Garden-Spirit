"""ExecutionPlan：Strategy 针对具体查询的运行时实例化。

Planner 把 Strategy DAG 转成可执行计划，Executor 按依赖顺序执行。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from shared.enums import Priority
from shared.types import EntityId


class ExecutionStatus(str, Enum):
    """执行状态。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ExecutionStep:
    """一个具体、已排期的执行步骤（带运行时状态）。"""

    id: EntityId
    strategy_step_id: str
    module: str                        # 分析模块路径
    params: dict = field(default_factory=dict)   # 模块参数（来自 Strategy YAML）
    priority: Priority = Priority.MEDIUM         # 核心模块失败 → 数据不足
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str = ""
    output_fact_set_id: EntityId | None = None
    output_evidence_set_id: EntityId | None = None
    retries: int = 0
    max_retries: int = 1
    timeout_seconds: int = 300
    dependencies: list[str] = field(default_factory=list)  # 依赖的 step id

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.SKIPPED,
        )


@dataclass
class ExecutionPlan:
    """一个 Strategy 对特定查询的运行时实例。"""

    id: EntityId
    strategy_id: str
    intent_id: EntityId
    chart_ids: list[EntityId]
    steps: list[ExecutionStep] = field(default_factory=list)
    status: ExecutionStatus = ExecutionStatus.PENDING
    created_at: datetime | None = None
    completed_at: datetime | None = None
