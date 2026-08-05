"""Phase 3 验证：ConfidenceEngine（防火墙）+ EvidenceBuilder + 冲突消解。"""

from datetime import datetime, timezone

import pytest

from domain.astrology.evidence import ConfidenceEngine, EvidenceBuilder
from domain.astrology.knowledge import load_knowledge
from shared.enums import (
    AspectApplication,
    DignityState,
    EvidenceConfidence,
    EvidencePolarity,
    FactCategory,
    Verdict,
)
from shared.models import Evidence, EvidenceSet, Fact, FactSet


def make_evidence(
    eid: str,
    polarity: EvidencePolarity,
    weight: float,
    confidence: float,
    subject: str = "general",
    reasoning: str = "",
) -> Evidence:
    return Evidence(
        id=eid,
        fact_id="f",
        polarity=polarity,
        weight=weight,
        confidence=confidence,
        evidence_confidence=ConfidenceEngine.bucket(confidence),
        domain="career",
        analysis_module="test",
        reasoning=reasoning,
        generated_at=datetime.now(timezone.utc),
        metadata={"subject": subject},
    )


def test_bucket_thresholds():
    engine = ConfidenceEngine()
    assert engine.bucket(0.95) == EvidenceConfidence.VERY_HIGH
    assert engine.bucket(0.75) == EvidenceConfidence.HIGH
    assert engine.bucket(0.6) == EvidenceConfidence.MODERATE
    assert engine.bucket(0.35) == EvidenceConfidence.LOW
    assert engine.bucket(0.1) == EvidenceConfidence.SPECULATIVE


def test_corroboration():
    engine = ConfidenceEngine()
    assert engine.corroborate(0.5, 1) == pytest.approx(0.5)
    boosted = engine.corroborate(0.5, 5)
    assert 0.5 < boosted < 0.99


def test_verdict_thresholds():
    engine = ConfidenceEngine()
    assert engine.verdict(2.0, 0.8) == Verdict.FAVORABLE
    assert engine.verdict(-2.0, 0.8) == Verdict.UNFAVORABLE
    assert engine.verdict(0.1, 0.8) == Verdict.NEUTRAL
    assert engine.verdict(2.0, 0.1) == Verdict.NEEDS_MORE_DATA


def test_conflict_detection_same_subject():
    engine = ConfidenceEngine()
    a = make_evidence("a", EvidencePolarity.POSITIVE, 3.0, 0.9, "planet:mars", "火星入庙")
    b = make_evidence("b", EvidencePolarity.NEGATIVE, 4.0, 0.8, "planet:mars", "火星刑土星")
    es = EvidenceSet(
        id="es", fact_set_id="fs", domain="career",
        query_context="换工作",
        positive_evidence=[a], negative_evidence=[b],
    )
    conflicts = engine.detect_conflicts(es)
    assert len(conflicts) == 1


def test_conflict_no_detection_different_subject():
    engine = ConfidenceEngine()
    a = make_evidence("a", EvidencePolarity.POSITIVE, 3.0, 0.9, "planet:mars")
    b = make_evidence("b", EvidencePolarity.NEGATIVE, 4.0, 0.8, "planet:saturn")
    es = EvidenceSet(
        id="es", fact_set_id="fs", domain="career",
        query_context="x", positive_evidence=[a], negative_evidence=[b],
    )
    assert engine.detect_conflicts(es) == []


def test_conflict_resolution_higher_confidence_wins():
    engine = ConfidenceEngine()
    a = make_evidence("a", EvidencePolarity.POSITIVE, 3.0, 0.95, "planet:mars", "高置信证据")
    b = make_evidence("b", EvidencePolarity.NEGATIVE, 4.0, 0.5, "planet:mars", "低置信证据")
    strategy, winner = engine.resolve_conflict(a, b)
    assert strategy == "higher_confidence"
    assert winner.id == "a"


def test_conflict_resolution_mutual_offset():
    engine = ConfidenceEngine()
    a = make_evidence("a", EvidencePolarity.POSITIVE, 3.0, 0.8, "planet:mars")
    b = make_evidence("b", EvidencePolarity.NEGATIVE, 3.0, 0.8, "planet:mars")
    strategy, winner = engine.resolve_conflict(a, b)
    assert strategy == "mutual_offset"
    assert winner is None


def test_evidence_builder_dignity():
    kb = load_knowledge()
    builder = EvidenceBuilder(kb)
    fact = Fact(
        id="f1", category=FactCategory.DIGNITY, chart_id="c1",
        description="火星在白羊座入庙",
        extracted_at=datetime.now(timezone.utc),
        payload={"planet": "mars", "sign": "aries", "dignity": "domicile", "score": 5},
    )
    fs = FactSet(id="fs", chart_ids=["c1"], intent_domain="career", facts=[fact])
    es = builder.build(fs, domain="career", query_context="换工作")
    assert len(es.positive_evidence) == 1
    ev = es.positive_evidence[0]
    assert ev.weight == pytest.approx(5.0)
    assert ev.polarity == EvidencePolarity.POSITIVE


def test_evidence_builder_detriment():
    kb = load_knowledge()
    builder = EvidenceBuilder(kb)
    fact = Fact(
        id="f1", category=FactCategory.DIGNITY, chart_id="c1",
        description="月亮在天蝎座落陷",
        extracted_at=datetime.now(timezone.utc),
        payload={"planet": "moon", "sign": "scorpio", "dignity": "fall", "score": -4},
    )
    fs = FactSet(id="fs", chart_ids=["c1"], intent_domain="career", facts=[fact])
    es = builder.build(fs, domain="career", query_context="换工作")
    assert len(es.negative_evidence) == 1
    assert es.negative_evidence[0].weight == pytest.approx(4.0)


def test_evidence_builder_aspect_nature():
    kb = load_knowledge()
    builder = EvidenceBuilder(kb)
    fact = Fact(
        id="f1", category=FactCategory.ASPECT, chart_id="c1",
        description="太阳三合土星",
        extracted_at=datetime.now(timezone.utc),
        payload={"body1": "sun", "body2": "saturn", "aspect": "trine",
                 "orb": 2.0, "applying": "applying"},
    )
    fs = FactSet(id="fs", chart_ids=["c1"], intent_domain="career", facts=[fact])
    es = builder.build(fs, domain="career", query_context="换工作")
    assert len(es.positive_evidence) == 1
    # trine 基权重 1.0 × 入相 1.2
    assert es.positive_evidence[0].weight == pytest.approx(1.2)


def test_dominant_theme():
    a = make_evidence("a", EvidencePolarity.POSITIVE, 3.0, 0.9)
    b = make_evidence("b", EvidencePolarity.NEGATIVE, 1.0, 0.9)
    es = EvidenceSet(
        id="es", fact_set_id="fs", domain="career", query_context="x",
        positive_evidence=[a], negative_evidence=[b],
    )
    assert es.dominant_theme == EvidencePolarity.POSITIVE
