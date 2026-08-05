"""Strategy：定义"如何回答一个问题"——跑哪些分析模块、什么顺序、依赖关系。

Strategy 是 YAML 插件系统的核心：
- 新增占星技法只需加 YAML 文件，不改代码。
- 一个 Intent 可组合多个 StrategyStep（DAG），支持并行/条件/合并。
"""

from dataclasses import dataclass, field
from enum import Enum

from shared.enums import IntentDomain, Priority


class StrategyCombinator(str, Enum):
    """步骤组合方式。"""

    SEQUENCE = "sequence"        # A → B → C
    PARALLEL = "parallel"        # A、B、C 同时
    CONDITIONAL = "conditional"  # 若 A 为某极性则 B，否则 C
    MERGE = "merge"              # 合并 A 与 B 的输出


class StepDependencyType(str, Enum):
    """步骤依赖类型。"""

    REQUIRES_OUTPUT = "requires_output"       # 需要上一步完整输出
    REQUIRES_FACTS = "requires_facts"         # 只需要上一步的 Facts
    OPTIONAL_ENHANCEMENT = "optional"         # 可选，可跳过


@dataclass
class StrategyStep:
    """Strategy DAG 中的一个步骤。"""

    id: str
    name: str
    analysis_module: str           # 分析模块路径，如 "domain.analysis.career_strength"
    required_facts: list[str]      # 需要的 FactCategory 值
    dependencies: list[str] = field(default_factory=list)  # 依赖的步骤 id
    dependency_type: StepDependencyType = StepDependencyType.REQUIRES_OUTPUT
    config: dict[str, object] = field(default_factory=dict)
    weight_in_summary: float = 1.0  # 在最终结论中的相对重要性
    priority: Priority = Priority.MEDIUM  # 核心模块失败时应报"数据不足"


@dataclass
class Strategy:
    """一个命名策略：针对特定意图的分析步骤 DAG。

    运行时从 YAML 加载。此 dataclass 是反序列化后的内存表示。
    """

    id: str
    name: str
    description: str
    intent_domains: list[IntentDomain]     # 适用领域
    steps: list[StrategyStep] = field(default_factory=list)
    combinator: StrategyCombinator = StrategyCombinator.SEQUENCE
    default_confidence_threshold: float = 0.7
    evidence_rules: dict = field(default_factory=dict)  # 证据加权规则（来自 YAML）

    # 加载时派生
    _step_map: dict[str, StrategyStep] = field(default_factory=dict, repr=False)

    def get_step(self, step_id: str) -> StrategyStep | None:
        if not self._step_map:
            self._step_map = {s.id: s for s in self.steps}
        return self._step_map.get(step_id)

    def root_steps(self) -> list[StrategyStep]:
        """无依赖的步骤 —— DAG 的入口点。"""
        return [s for s in self.steps if not s.dependencies]
