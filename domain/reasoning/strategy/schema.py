"""Strategy YAML 的 pydantic schema。

新增策略 = 新增 YAML 文件，schema 保证格式合法。
"""

from pydantic import BaseModel, Field, model_validator

from shared.enums import Priority

PRIORITY_MAP = {
    "high": Priority.HIGH,
    "medium": Priority.MEDIUM,
    "low": Priority.LOW,
}


class StrategyStepYAML(BaseModel):
    """一个分析模块步骤。"""

    module: str = Field(..., description="分析模块名，如 CareerStrength")
    priority: str = Field("medium", description="high/medium/low")
    params: dict = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list, description="依赖的模块名")
    weight: float = Field(1.0, description="在最终结论中的相对重要性")

    def priority_enum(self) -> Priority:
        return PRIORITY_MAP.get(self.priority, Priority.MEDIUM)


class StrategyYAML(BaseModel):
    """一个完整策略定义。"""

    intent: str = Field(..., description='意图引用，如 "Career.ChangeJob"')
    version: str = "1.0"
    description: str = ""
    required_analysis: list[StrategyStepYAML] = Field(..., min_length=1)
    needed_indicators: list[str] = Field(default_factory=list)
    evidence_rules: dict = Field(
        default_factory=dict,
        description="positive_weight / negative_weight / min_confidence / conflict_threshold",
    )
    model_dependencies: dict[str, list[str]] = Field(
        default_factory=dict, description="模块 DAG 依赖"
    )

    @model_validator(mode="after")
    def _validate_dependencies(self) -> "StrategyYAML":
        module_names = {s.module for s in self.required_analysis}
        for dep, deps in self.model_dependencies.items():
            if dep not in module_names:
                raise ValueError(f"model_dependencies 引用了未定义模块: {dep}")
            for d in deps:
                if d not in module_names:
                    raise ValueError(f"{dep} 依赖了未定义模块: {d}")
        return self
