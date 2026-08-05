"""Reasoner —— EvidenceSet → Conclusion。

完全确定性：由净分、置信度与冲突消解结果推导结论。无 LLM（原则二）。
"""

from __future__ import annotations

from foundation.logger import get_logger
from foundation.utils import new_id, utc_now
from shared.enums import Verdict
from shared.models import Conclusion, EvidenceSet, Intent

from domain.astrology.evidence import ConfidenceEngine

from domain.reasoning.conclusion import ConclusionBuilder

logger = get_logger("reasoning.reasoner")


class Reasoner:
    """证据 → 结论。"""

    def __init__(
        self,
        confidence: ConfidenceEngine | None = None,
        conclusion_builder: ConclusionBuilder | None = None,
    ):
        self._confidence = confidence or ConfidenceEngine()
        self._builder = conclusion_builder or ConclusionBuilder()

    def reason(
        self,
        evidence_set: EvidenceSet,
        intent: Intent,
        failed_core_modules: list[str] | None = None,
    ) -> Conclusion:
        """综合证据，产出结论。

        failed_core_modules: 策略中高优先级但执行失败的模块。
            核心模块缺失时，宁可报"数据不足"，也不从残缺证据硬造结论
            （正确性红线——之前的 relationship 误导案例）。
        """
        net_score = self._confidence.net_score(evidence_set)
        confidence = self._confidence.aggregate_confidence(evidence_set)
        verdict = self._confidence.verdict(net_score, confidence)

        failed = failed_core_modules or []
        if failed:
            verdict = Verdict.NEEDS_MORE_DATA
            confidence = min(confidence, 0.3)

        conclusion = Conclusion(
            id=new_id("conclusion"),
            intent_id=intent.id,
            evidence_set_id=evidence_set.id,
            domain=intent.domain.value,
            summary="",
            overall_confidence=confidence,
            overall_polarity=evidence_set.dominant_theme,
            generated_at=utc_now(),
            metadata={
                "net_score": net_score,
                "verdict": verdict.value,
                "conflict_count": len(evidence_set.resolved_conflicts),
                "failed_core_modules": failed,
            },
        )
        self._builder.populate(conclusion, evidence_set, intent, verdict, net_score, failed)
        logger.info(
            "结论生成: verdict=%s score=%.2f conf=%.2f findings=%d",
            verdict.value, net_score, confidence, len(conclusion.findings),
        )
        return conclusion
