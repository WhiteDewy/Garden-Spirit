"""Runtime consult call-plan contract tests."""

from datetime import datetime, timezone

import pytest

from application.agent.runtime import GardenSpiritAgent
from shared.enums import EvidencePolarity, IntentDomain, PersonaType
from shared.models import Conclusion, Intent


class _AvailableLLM:
    available = True


class _CallPlan:
    def __init__(self, intent: Intent):
        self.intent = intent

    def to_dict(self) -> dict:
        return {
            "domain": self.intent.domain.value,
            "focus_house": 10,
            "topic_id": "career",
            "topic_label": "事业",
            "primary_house": 10,
            "primary_planets": ["sun"],
            "natural_significators": ["sun"],
            "output_structure": None,
            "cross_readings": [],
            "guardrails": [],
        }


class _Resolver:
    def __init__(self):
        self.intent_seen = None

    def resolve_call_plan(self, intent: Intent):
        self.intent_seen = intent
        return _CallPlan(intent)

    def resolve_topic(self, _question: str):  # pragma: no cover - should never be called
        raise AssertionError("runtime must use resolve_call_plan(intent), not legacy resolve_topic")


def _make_conclusion() -> Conclusion:
    return Conclusion(
        id="c1",
        intent_id="i1",
        evidence_set_id="e1",
        domain="career",
        summary="事业结构清晰。",
        overall_confidence=0.8,
        overall_polarity=EvidencePolarity.POSITIVE,
        generated_at=datetime.now(timezone.utc),
    )


def test_runtime_format_response_uses_consult_call_plan(monkeypatch):
    """LLM 转述入口必须消费 canonical ConsultCallPlan，而不是旧 TopicPlan adapter。"""
    resolver = _Resolver()
    captured = {}

    def fake_get_resolver():
        return resolver

    def fake_paraphrase(**kwargs):
        captured.update(kwargs)
        return "LLM answer"

    monkeypatch.setattr("domain.reasoning.consult.get_resolver", fake_get_resolver)
    monkeypatch.setattr("application.conversation.response.paraphrase", fake_paraphrase)

    agent = object.__new__(GardenSpiritAgent)
    agent._llm = _AvailableLLM()
    agent._kb = None
    agent._planet_profiles_for = lambda intent, chart: None

    intent = Intent(id="i1", raw_query="事业怎么样？", domain=IntentDomain.CAREER)
    answer = agent._format_response(
        conclusion=_make_conclusion(),
        intent=intent,
        persona=PersonaType.MOON,
        chart=None,
    )

    assert answer.startswith("LLM answer")
    assert resolver.intent_seen is intent
    assert isinstance(captured["call_plan"], _CallPlan)
    assert captured["call_plan"].intent is intent
    assert captured.get("topic_plan") is None
