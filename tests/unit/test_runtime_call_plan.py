"""Runtime consult call-plan contract tests."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from application.agent.runtime import GardenSpiritAgent
from application.agent.context_builder import ContextBuilder
from domain.reasoning.intent.decomposer import DecomposedIntent
from shared.enums import EvidencePolarity, HouseSystem, IntentDomain, PersonaType, Priority
from shared.models import (
    BirthData,
    Conclusion,
    ExecutionPlan,
    ExecutionStep,
    FactSet,
    GeoLocation,
    Intent,
    Person,
    Strategy,
    StrategyStep,
)


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
        self.chart_seen = None

    def resolve_call_plan(self, intent: Intent, chart=None):
        self.intent_seen = intent
        self.chart_seen = chart
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
    assert resolver.chart_seen is None
    assert isinstance(captured["call_plan"], _CallPlan)
    assert captured["call_plan"].intent is intent
    assert captured.get("topic_plan") is None


def test_runtime_enrichment_merges_consult_call_plan_carriers():
    """定位层承载者必须进入执行 enrichment，不能只注入 LLM prompt。"""
    intent = Intent(id="i2", raw_query="事业怎么样？", domain=IntentDomain.CAREER)
    decomposed = DecomposedIntent(
        intent=intent,
        focus_houses=[6],
        focus_planets=["mercury"],
        focus_house_lords=[6],
        focus_aspect_pairs=[["sun", "saturn"]],
        focus_dimensions=["career"],
    )

    class _ExecutionCallPlan:
        def to_dict(self) -> dict:
            return {
                "focus_house": 10,
                "primary_house": 10,
                "core_houses": [10, 2],
                "supplementary_houses": [11],
                "house_lords": [10, 2],
                "natural_significators": ["sun", "saturn"],
                "supporting_planets": ["jupiter"],
                "house_lord_planets": ["saturn", "venus"],
                "house_lord_placements": [
                    {"house": 10, "cusp_sign": "capricorn", "lord": "saturn", "lord_house": 10},
                ],
                "house_occupants": ["moon"],
                "aspect_pairs": [["mars", "saturn"]],
                "source": "consult_resolver_v2",
            }

    enrichment = GardenSpiritAgent._build_enrichment(
        decomposed, call_plan=_ExecutionCallPlan()
    )

    assert enrichment["focus_houses"] == [6, 10, 2, 11]
    assert enrichment["focus_house_lords"] == [6, 10, 2]
    assert enrichment["focus_planets"] == [
        "mercury", "sun", "saturn", "jupiter", "venus", "moon",
    ]
    assert enrichment["focus_aspect_pairs"] == [["sun", "saturn"], ["mars", "saturn"]]
    assert enrichment["house_lord_placements"][0]["lord"] == "saturn"
    assert enrichment["house_occupants"] == ["moon"]
    assert enrichment["consult_call_plan_source"] == "consult_resolver_v2"


def test_handle_message_passes_consult_call_plan_carriers_into_plan_params(monkeypatch):
    """常规咨询主链必须把定位层承载者注入真实 ExecutionStep.params。"""
    intent = Intent(id="i3", raw_query="事业怎么样？", domain=IntentDomain.CAREER)
    decomposed = DecomposedIntent(
        intent=intent,
        focus_houses=[6],
        focus_planets=["mercury"],
        focus_house_lords=[6],
        focus_aspect_pairs=[["sun", "saturn"]],
        focus_dimensions=["career"],
    )
    chart = SimpleNamespace(id="chart1", house_system=HouseSystem.PLACIDUS)
    strategy = Strategy(
        id="s1",
        name="career",
        description="career strategy",
        intent_domains=[IntentDomain.CAREER],
        steps=[
            StrategyStep(
                id="timing",
                name="Timing",
                analysis_module="Timing",
                required_facts=[],
                priority=Priority.MEDIUM,
            )
        ],
    )
    captured: dict[str, object] = {}

    class _ExecutionCallPlan:
        def to_dict(self) -> dict:
            return {
                "focus_house": 10,
                "primary_house": 10,
                "core_houses": [10, 2],
                "supplementary_houses": [11],
                "house_lords": [10, 2],
                "natural_significators": ["sun", "saturn"],
                "supporting_planets": ["jupiter"],
                "house_lord_planets": ["saturn", "venus"],
                "house_lord_placements": [
                    {"house": 10, "cusp_sign": "capricorn", "lord": "saturn", "lord_house": 10},
                ],
                "house_occupants": ["moon"],
                "aspect_pairs": [["mars", "saturn"]],
                "source": "consult_resolver_v2",
                "topic_id": "career",
                "topic_label": "事业",
                "output_structure": None,
                "cross_readings": [],
                "guardrails": [],
            }

    class _Parser:
        def parse_deep(self, message, context, mode):
            captured["intent_context"] = context
            return decomposed

    class _Planner:
        def create_plan(self, got_intent, got_strategy, got_person, chart=None, enrichment=None):
            captured["planner_intent"] = got_intent
            captured["planner_strategy"] = got_strategy
            captured["planner_person"] = got_person
            captured["planner_chart"] = chart
            captured["planner_enrichment"] = enrichment
            step = ExecutionStep(
                id="step1",
                strategy_step_id="timing",
                module="Timing",
                params={"_enrichment": enrichment},
                priority=Priority.MEDIUM,
            )
            plan = ExecutionPlan(
                id="plan1",
                strategy_id=got_strategy.id,
                intent_id=got_intent.id,
                chart_ids=[chart.id],
                steps=[step],
            )
            captured["plan_step_params"] = step.params
            return plan, chart

    class _Executor:
        def execute(self, plan, got_chart, got_person):
            captured["executor_plan_params"] = plan.steps[0].params
            return FactSet(id="facts1", chart_ids=[got_chart.id], intent_domain=intent.domain.value)

    class _Composer:
        def compose(self, fact_set, got_strategy, got_intent):
            return SimpleNamespace(id="evidence1", domain=got_intent.domain.value)

    class _Reasoner:
        def reason(self, evidence_set, got_intent, failed_core):
            captured["failed_core"] = failed_core
            return _make_conclusion()

    class _Resolver:
        def resolve_call_plan(self, got_intent, chart=None):
            captured["resolver_intent"] = got_intent
            captured["resolver_chart"] = chart
            return _ExecutionCallPlan()

    def fake_get_resolver():
        return _Resolver()

    monkeypatch.setattr("domain.reasoning.consult.get_resolver", fake_get_resolver)

    agent = object.__new__(GardenSpiritAgent)
    agent.config = SimpleNamespace(default_persona=PersonaType.MOON)
    agent.context_builder = ContextBuilder()
    agent.intent_parser = _Parser()
    agent._emotion = SimpleNamespace(perceive=lambda message: SimpleNamespace(needs_care=False))
    agent._select_strategy = lambda got_decomposed, mode: strategy
    agent._chart_provider = lambda got_person, house_system: chart
    agent.planner = _Planner()
    agent.executor = _Executor()
    agent.composer = _Composer()
    agent.reasoner = _Reasoner()
    agent._format_response = lambda conclusion, got_intent, persona, got_chart, mode, call_plan=None: "ok"

    person = Person(
        id="p1",
        name="测试用户",
        birth=BirthData(
            datetime.now(timezone.utc),
            GeoLocation(31.2, 121.5, timezone_name="Asia/Shanghai", place_name="上海"),
        ),
    )

    assert agent.handle_message("s1", "事业怎么样？", person, PersonaType.MOON) == "ok"

    enrichment = captured["executor_plan_params"]["_enrichment"]
    assert captured["resolver_chart"] is chart
    assert captured["planner_chart"] is chart
    assert captured["planner_enrichment"] is enrichment
    assert enrichment["focus_houses"] == [6, 10, 2, 11]
    assert enrichment["focus_house_lords"] == [6, 10, 2]
    assert enrichment["focus_planets"] == [
        "mercury", "sun", "saturn", "jupiter", "venus", "moon",
    ]
    assert enrichment["focus_aspect_pairs"] == [["sun", "saturn"], ["mars", "saturn"]]
    assert enrichment["house_lord_placements"][0]["lord"] == "saturn"
    assert enrichment["house_occupants"] == ["moon"]
    assert enrichment["consult_call_plan_source"] == "consult_resolver_v2"


def test_direct_house_consult_passes_call_plan_carriers(monkeypatch):
    """宫位直读路径也必须复用 ConsultCallPlan carriers，不能绕过动态承载者。"""
    from shared.models import IntentSlot

    intent = Intent(
        id="i4",
        raw_query="我的12宫财运怎么样？",
        domain=IntentDomain.WEALTH,
        slots={
            "focus_house": IntentSlot(
                name="focus_house",
                raw_value="12宫",
                normalized_value="12",
            )
        },
    )
    decomposed = DecomposedIntent(
        intent=intent,
        focus_houses=[12],
        focus_planets=["mercury"],
        focus_house_lords=[12],
        focus_dimensions=["wealth"],
    )
    chart = SimpleNamespace(id="chart-house", house_system=HouseSystem.PLACIDUS)
    captured: dict[str, object] = {}

    class _ExecutionCallPlan:
        def to_dict(self) -> dict:
            return {
                "focus_house": 12,
                "primary_house": 12,
                "core_houses": [12, 2],
                "house_lords": [12, 2],
                "natural_significators": ["jupiter"],
                "supporting_planets": ["venus"],
                "house_lord_planets": ["mars"],
                "house_lord_placements": [
                    {"house": 12, "cusp_sign": "aries", "lord": "mars", "lord_house": 2},
                ],
                "house_occupants": ["moon"],
                "aspect_pairs": [["mars", "jupiter"]],
                "source": "consult_resolver_v2",
            }

    class _Parser:
        def parse_deep(self, message, context, mode):
            return decomposed

    class _Resolver:
        def resolve_call_plan(self, got_intent, chart=None):
            captured["resolver_intent"] = got_intent
            captured["resolver_chart"] = chart
            return _ExecutionCallPlan()

    def fake_get_resolver():
        return _Resolver()

    def fake_house_conclusion(chart, got_intent, house_slot, *, deep=False, confirmed=None, enrichment=None):
        captured["house_chart"] = chart
        captured["house_intent"] = got_intent
        captured["house_slot"] = house_slot
        captured["house_deep"] = deep
        captured["house_enrichment"] = enrichment
        return _make_conclusion()

    def fake_format_response(conclusion, got_intent, persona, chart=None, mode=None, house_focus=None, confirmed=None, call_plan=None):
        captured["format_call_plan"] = call_plan
        captured["format_house_focus"] = house_focus
        return "house ok"

    monkeypatch.setattr("domain.reasoning.consult.get_resolver", fake_get_resolver)

    agent = object.__new__(GardenSpiritAgent)
    agent.config = SimpleNamespace(default_persona=PersonaType.MOON)
    agent.context_builder = ContextBuilder()
    agent.intent_parser = _Parser()
    agent._emotion = SimpleNamespace(perceive=lambda message: SimpleNamespace(needs_care=False))
    agent._chart_provider = lambda got_person, house_system: chart
    agent._house_conclusion = fake_house_conclusion
    agent._format_response = fake_format_response

    person = Person(
        id="p1",
        name="测试用户",
        birth=BirthData(
            datetime.now(timezone.utc),
            GeoLocation(31.2, 121.5, timezone_name="Asia/Shanghai", place_name="上海"),
        ),
    )

    assert agent.handle_message("s-house", "我的12宫财运怎么样？", person, PersonaType.MOON) == "house ok"

    enrichment = captured["house_enrichment"]
    assert captured["resolver_chart"] is chart
    assert captured["house_chart"] is chart
    assert captured["format_house_focus"] == 12
    assert captured["format_call_plan"].to_dict()["source"] == "consult_resolver_v2"
    assert enrichment["focus_houses"] == [12, 2]
    assert enrichment["focus_house_lords"] == [12, 2]
    assert enrichment["focus_planets"] == ["mercury", "jupiter", "venus", "mars", "moon"]
    assert enrichment["focus_aspect_pairs"] == [["mars", "jupiter"]]
    assert enrichment["house_lord_placements"][0]["lord"] == "mars"
    assert enrichment["house_occupants"] == ["moon"]
    assert enrichment["consult_call_plan_source"] == "consult_resolver_v2"
