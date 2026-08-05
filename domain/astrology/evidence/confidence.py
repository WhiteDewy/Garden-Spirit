"""置信度引擎 —— 原则三防火墙的核心。

证据的极性、权重、置信度、冲突消解，全部由这里的确定性规则产生。
LLM 永不参与。

冲突消解策略（按优先级）：
  1. higher_confidence      高置信度者胜
  2. higher_weight          强权重者胜
  3. more_specific          更具体（针对特定宫/星球）者胜
  4. essential_over_pattern 先天尊贵证据 > 图形/泛泛证据
  5. mutual_offset          权重相近则相互抵消，记为中性
"""

from __future__ import annotations

import math

from foundation.config import EvidenceConfig
from shared.enums import EvidenceConfidence, EvidencePolarity, Verdict
from shared.models import Evidence, EvidenceConflict, EvidenceSet

_CONFIDENCE_BUCKETS: list[tuple[float, EvidenceConfidence]] = [
    (0.9, EvidenceConfidence.VERY_HIGH),
    (0.7, EvidenceConfidence.HIGH),
    (0.5, EvidenceConfidence.MODERATE),
    (0.3, EvidenceConfidence.LOW),
]


class ConfidenceEngine:
    """置信度计算与冲突消解。"""

    def __init__(self, config: EvidenceConfig | None = None):
        self.config = config or EvidenceConfig()

    # ------------------------------------------------------------------
    # 置信度
    # ------------------------------------------------------------------

    @staticmethod
    def bucket(confidence: float) -> EvidenceConfidence:
        """数值置信度 → 分档。"""
        for threshold, bucket in _CONFIDENCE_BUCKETS:
            if confidence >= threshold:
                return bucket
        return EvidenceConfidence.SPECULATIVE

    @staticmethod
    def corroborate(base_confidence: float, independent_count: int) -> float:
        """多方佐证增强置信度（有上限）。

        佐证增幅保守（count/5），且整体封顶 0.9——占星解读是解释性的，
        不应显得"绝对确定"。
        conf = base + (1 - base) * (1 - exp(-count / 5))
        """
        if independent_count <= 1:
            return base_confidence
        boost = (1.0 - base_confidence) * (1.0 - math.exp(-independent_count / 5.0))
        return min(0.9, base_confidence + boost)

    # ------------------------------------------------------------------
    # 冲突消解
    # ------------------------------------------------------------------

    @staticmethod
    def _subject(evidence: Evidence) -> str:
        """证据的主题（冲突判定的基础）。分析模块写入 metadata["subject"]。"""
        return str(evidence.metadata.get("subject", "general"))

    @staticmethod
    def _specificity(evidence: Evidence) -> int:
        """特异性：明确指向某星球/宫位者更具体。"""
        meta = evidence.metadata
        score = 0
        if "planet" in meta or "subject" in meta and ":" in str(meta.get("subject", "")):
            score += 1
        if "house" in meta:
            score += 1
        return score

    @staticmethod
    def _is_essential(evidence: Evidence) -> bool:
        """是否基于先天尊贵（essential）来源。"""
        return evidence.analysis_module in ("dignity", "reception") or evidence.metadata.get(
            "source_quality"
        ) == "essential"

    def detect_conflicts(self, evidence_set: EvidenceSet) -> list[EvidenceConflict]:
        """检测同一主题下极性相反的成对证据。"""
        conflicts: list[EvidenceConflict] = []
        all_items = evidence_set.all_evidence
        for i, a in enumerate(all_items):
            for b in all_items[i + 1:]:
                if a.polarity == b.polarity or a.polarity == EvidencePolarity.NEUTRAL or b.polarity == EvidencePolarity.NEUTRAL:
                    continue
                if self._subject(a) == self._subject(b):
                    conflicts.append(
                        EvidenceConflict(
                            evidence_a_id=a.id,
                            evidence_b_id=b.id,
                            conflict_description=(
                                f"{a.reasoning} (极性{a.polarity.value}) "
                                f"vs {b.reasoning} (极性{b.polarity.value})"
                            ),
                            resolution_strategy="pending",
                            winner_id=None,
                            resolution_reasoning="",
                        )
                    )
        return conflicts

    def resolve_conflict(self, a: Evidence, b: Evidence) -> tuple[str, Evidence | None]:
        """按策略阶梯消解一对冲突。返回 (策略, 胜者 or None)。"""
        # 1. 置信度
        if abs(a.confidence - b.confidence) > 0.1:
            winner = a if a.confidence > b.confidence else b
            return "higher_confidence", winner
        # 2. 权重
        if abs(abs(a.weight) - abs(b.weight)) > 0.5:
            winner = a if abs(a.weight) > abs(b.weight) else b
            return "higher_weight", winner
        # 3. 特异性
        if self._specificity(a) != self._specificity(b):
            winner = a if self._specificity(a) > self._specificity(b) else b
            return "more_specific", winner
        # 4. 来源质量
        if self._is_essential(a) != self._is_essential(b):
            winner = a if self._is_essential(a) else b
            return "essential_over_pattern", winner
        # 5. 相互抵消
        return "mutual_offset", None

    def resolve_all(self, evidence_set: EvidenceSet) -> list[EvidenceConflict]:
        """执行消解，记录策略与胜者。"""
        conflicts = self.detect_conflicts(evidence_set)
        resolved: list[EvidenceConflict] = []
        by_id = {e.id: e for e in evidence_set.all_evidence}

        for conflict in conflicts:
            a = by_id.get(conflict.evidence_a_id)
            b = by_id.get(conflict.evidence_b_id)
            if not a or not b:
                continue
            strategy, winner = self.resolve_conflict(a, b)
            conflict.resolution_strategy = strategy
            conflict.winner_id = winner.id if winner else None
            conflict.resolution_reasoning = (
                f"按{strategy}策略"
                + (f"，{winner.reasoning}" if winner else "，相互抵消记为中性")
            )
            resolved.append(conflict)
        return resolved

    # ------------------------------------------------------------------
    # 结论判定
    # ------------------------------------------------------------------

    def net_score(self, evidence_set: EvidenceSet) -> float:
        """净分 = Σ(权重 × 置信度)。"""
        return evidence_set.net_weight

    def verdict(self, net_score: float, confidence: float) -> Verdict:
        """净分 → 结论。"""
        if confidence < self.config.min_confidence:
            return Verdict.NEEDS_MORE_DATA
        threshold = self.config.conflict_threshold
        if abs(net_score) < threshold:
            return Verdict.NEUTRAL
        return Verdict.FAVORABLE if net_score > 0 else Verdict.UNFAVORABLE

    def aggregate_confidence(self, evidence_set: EvidenceSet) -> float:
        """整体置信度 = 加权平均置信度 × 证据量修正。"""
        items = evidence_set.all_evidence
        if not items:
            return 0.0
        base = sum(e.confidence * abs(e.weight) for e in items) / sum(
            abs(e.weight) or 1.0 for e in items
        )
        return self.corroborate(base, len(items))
