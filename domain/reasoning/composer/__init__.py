"""Composer —— 合并 Facts 为加权 Evidence。

把 Executor 产出的 FactSet 交给 EvidenceBuilder，
用 Strategy 的 evidence_rules 完成加权与冲突消解。
"""

from __future__ import annotations

from foundation.logger import get_logger
from shared.models import EvidenceSet, FactSet, Intent, Strategy

from domain.astrology.evidence import EvidenceBuilder
from domain.astrology.knowledge import load_knowledge

logger = get_logger("reasoning.composer")


class Composer:
    """FactSet → EvidenceSet。"""

    def __init__(self, evidence_builder: EvidenceBuilder | None = None):
        if evidence_builder is None:
            evidence_builder = EvidenceBuilder(load_knowledge())
        self._builder = evidence_builder

    def compose(
        self,
        fact_set: FactSet,
        strategy: Strategy,
        intent: Intent | None = None,
        query_context: str = "",
    ) -> EvidenceSet:
        """按策略证据规则，把 Facts 转成加权 Evidence。"""
        domain = intent.domain.value if intent else fact_set.intent_domain
        context = query_context or (intent.raw_query if intent else "")
        evidence_set = self._builder.build(
            fact_set,
            domain=domain,
            query_context=context,
            evidence_rules=strategy.evidence_rules,
        )
        logger.info(
            "证据合并完成: 正%d 负%d 中性%d 冲突%d",
            len(evidence_set.positive_evidence),
            len(evidence_set.negative_evidence),
            len(evidence_set.neutral_evidence),
            len(evidence_set.conflicts),
        )
        return evidence_set
