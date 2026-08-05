"""Evidence：Facts + 加权解释。

Evidence 回答"这个事实对这个具体问题意味着什么"。

**冲突消解（原则三防火墙）**：证据的权重与极性只由 Domain 规则产生。
冲突消解采用确定性规则，从不涉及 LLM：
  1. 置信度比较：高置信度者胜
  2. 权重比较：强权重者胜
  3. 特异性：针对特定宫/星球的证据胜于泛泛证据
  4. 来源质量：先天尊贵证据 > 后天证据 > 图形证据
  5. 相互抵消：权重相等相反时记为中性
"""

from dataclasses import dataclass, field
from datetime import datetime

from shared.enums import EvidenceConfidence, EvidencePolarity
from shared.types import Confidence, EntityId, Weight


@dataclass(frozen=True)
class Evidence:
    """一条加权证据。

    每条 Evidence 引用一条 Fact。同一条 Fact 可被不同领域的
    多条 Evidence 以不同相关性引用。
    """

    id: EntityId
    fact_id: EntityId
    polarity: EvidencePolarity
    weight: Weight                  # 权值（可为负）
    confidence: Confidence          # 0-1 数值置信度
    evidence_confidence: EvidenceConfidence  # 分档置信度
    domain: str                     # 相关意图领域
    analysis_module: str            # 产出该证据的分析模块
    reasoning: str                  # 为什么有这个权重（Domain 逻辑，人类可读）
    generated_at: datetime
    metadata: dict[str, object] = field(default_factory=dict)
    # metadata 可含 {"rule_id": ..., "rule_version": ..., "conflict_context": {...}}


@dataclass
class EvidenceConflict:
    """一条冲突证据及其消解结果。"""

    evidence_a_id: EntityId
    evidence_b_id: EntityId
    conflict_description: str       # 如 "火星入庙(+3) 与 火星失势(-4) 冲突"
    resolution_strategy: str        # 如 "higher_confidence" / "more_specific"
    winner_id: EntityId | None      # None = 抵消为中性的证据保留为中性
    resolution_reasoning: str


@dataclass
class EvidenceSet:
    """针对特定领域查询的加权、已消解的证据集合。

    Evidence 层的输出，Reasoner 的输入。
    """

    id: EntityId
    fact_set_id: EntityId
    domain: str
    query_context: str               # 正在回答什么问题
    positive_evidence: list[Evidence] = field(default_factory=list)
    negative_evidence: list[Evidence] = field(default_factory=list)
    neutral_evidence: list[Evidence] = field(default_factory=list)
    conflicts: list[EvidenceConflict] = field(default_factory=list)
    resolved_conflicts: list[EvidenceConflict] = field(default_factory=list)
    generated_at: datetime | None = None

    @property
    def all_evidence(self) -> list[Evidence]:
        return (
            self.positive_evidence
            + self.negative_evidence
            + self.neutral_evidence
        )

    @property
    def net_weight(self) -> float:
        """所有证据的 (权重 × 置信度) 之和。"""
        return sum(e.weight * e.confidence for e in self.all_evidence)

    @property
    def positive_weight(self) -> float:
        return sum(e.weight * e.confidence for e in self.positive_evidence)

    @property
    def negative_weight(self) -> float:
        return sum(abs(e.weight) * e.confidence for e in self.negative_evidence)

    @property
    def dominant_theme(self) -> EvidencePolarity:
        """整体极性。"""
        if abs(self.positive_weight - self.negative_weight) < 0.5:
            return EvidencePolarity.NEUTRAL
        return (
            EvidencePolarity.POSITIVE
            if self.positive_weight > self.negative_weight
            else EvidencePolarity.NEGATIVE
        )
