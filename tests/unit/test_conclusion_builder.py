"""ConclusionBuilder 回归：审计评分不得抢占用户可见 Finding。"""

from datetime import datetime, timezone

from domain.reasoning.conclusion import ConclusionBuilder
from shared.enums import EvidenceConfidence, EvidencePolarity, IntentDomain
from shared.models import Evidence, EvidenceSet, Intent


def _ev(
    eid: str,
    reasoning: str,
    weight: float,
    *,
    score: float | None = None,
    polarity: EvidencePolarity = EvidencePolarity.POSITIVE,
) -> Evidence:
    metadata = {"theme": "career_strength"}
    if score is not None:
        metadata["score"] = score
    return Evidence(
        id=eid,
        fact_id=f"fact-{eid}",
        polarity=polarity,
        weight=weight,
        confidence=0.8,
        evidence_confidence=EvidenceConfidence.HIGH,
        domain="career",
        analysis_module="CareerStrength",
        reasoning=reasoning,
        generated_at=datetime.now(timezone.utc),
        metadata=metadata,
    )


def test_scored_aggregate_evidence_does_not_become_representative_finding():
    """score 字段只做内部审计；用户可见 Finding 优先展示具体证据。"""
    concrete = _ev("concrete", "十宫主土星入庙，事业根基有稳定承载", 2.0)
    aggregate = _ev("aggregate", "职业强度综合评分 9（十宫主土星尊贵分5）", 5.0, score=9.0)
    evidence_set = EvidenceSet(
        id="es1",
        fact_set_id="fs1",
        domain="career",
        query_context="换工作",
        positive_evidence=[concrete, aggregate],
    )

    findings = ConclusionBuilder()._build_findings(evidence_set)

    assert len(findings) == 1
    assert findings[0].text == "十宫主土星入庙，事业根基有稳定承载"
    assert findings[0].supporting_evidence_ids == ["concrete", "aggregate"]
    assert findings[0].weight == (2.0 * 0.8) + (5.0 * 0.8)


def test_scored_aggregate_is_kept_when_it_is_the_only_theme_evidence():
    """没有可替代的具体证据时，不因 score 元数据丢掉主题判断。"""
    aggregate = _ev("aggregate", "职业机会侧有外部助力可以借用（吉星助力与人脉位势）", 2.0, score=2.0)
    evidence_set = EvidenceSet(
        id="es1",
        fact_set_id="fs1",
        domain="career",
        query_context="换工作",
        positive_evidence=[aggregate],
    )

    findings = ConclusionBuilder()._build_findings(evidence_set)

    assert len(findings) == 1
    assert findings[0].text == "职业机会侧有外部助力可以借用（吉星助力与人脉位势）"


def test_descriptive_findings_still_sort_by_weight():
    """描述性解读不走主题代表证据折叠，继续按原权重排序。"""
    weak = _ev("weak", "轻量观察", 1.0)
    strong = _ev("strong", "强观察", 3.0)
    evidence_set = EvidenceSet(
        id="es1",
        fact_set_id="fs1",
        domain="career",
        query_context="换工作",
        positive_evidence=[weak, strong],
    )

    findings = ConclusionBuilder()._build_findings(evidence_set, descriptive=True)

    assert [f.text for f in findings[:2]] == ["强观察", "轻量观察"]


def test_populate_keeps_score_metadata_out_of_user_visible_first_choice():
    """populate 全链也保持 Finding 文案不被 score 聚合项抢占。"""
    from shared.enums import Verdict
    from shared.models import Conclusion

    concrete = _ev("concrete", "十宫主土星入庙，事业根基有稳定承载", 2.0)
    aggregate = _ev("aggregate", "职业强度综合评分 9（十宫主土星尊贵分5）", 5.0, score=9.0)
    evidence_set = EvidenceSet(
        id="es1",
        fact_set_id="fs1",
        domain="career",
        query_context="换工作",
        positive_evidence=[concrete, aggregate],
    )
    intent = Intent(id="i1", raw_query="换工作", domain=IntentDomain.CAREER)
    conclusion = Conclusion(
        id="c1",
        intent_id="i1",
        evidence_set_id="es1",
        domain="career",
        summary="",
    )

    ConclusionBuilder().populate(conclusion, evidence_set, intent, Verdict.FAVORABLE, 5.6)

    assert conclusion.findings[0].text == "十宫主土星入庙，事业根基有稳定承载"
    assert "综合评分" not in conclusion.findings[0].text
