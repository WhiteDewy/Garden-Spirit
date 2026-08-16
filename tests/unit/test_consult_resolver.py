"""Consult Resolver 单元测试 —— 话题解析 + 转宫推导 + prompt 生成。"""

from datetime import datetime, timezone

import pytest

from shared.enums import (
    AspectType,
    ChartType,
    DignityState,
    HouseSystem,
    IntentDomain,
    Planet,
    PlanetSpeed,
    Sign,
    ZodiacType,
)
from shared.models import (
    Chart,
    ChartAcceptance,
    ChartPlanet,
    EclipticPosition,
    HouseCusp,
    HousePosition,
    SignPosition,
)
from shared.models.intent import Intent, IntentSlot

from domain.reasoning.consult import (
    ConsultCallPlan,
    ConsultResolver,
    TopicPlan,
    resolve_call_plan,
    resolve_question,
)


@pytest.fixture(scope="module")
def resolver():
    return ConsultResolver()


def _planet(planet: Planet, sign: Sign, house: int, lon: float) -> ChartPlanet:
    return ChartPlanet(
        planet=planet,
        ecliptic=EclipticPosition(longitude=lon),
        sign=SignPosition(sign=sign, degree_absolute=lon, degree_in_sign=lon % 30.0),
        house=HousePosition(house=house, cusp_degree=0.0, distance_from_cusp=0.0),
        speed=PlanetSpeed.DIRECT,
        speed_deg_per_day=1.0,
    )

def _carrier_chart() -> Chart:
    now = datetime(2026, 8, 15, tzinfo=timezone.utc)
    return Chart(
        id="carrier_chart",
        person_id="p_carrier",
        chart_type=ChartType.NATAL,
        calculated_at_utc=now,
        julian_day=0.0,
        epoch_utc=now,
        location="test",
        zodiac=ZodiacType.TROPICAL,
        house_system=HouseSystem.WHOLE_SIGN,
        house_cusps={
            1: HouseCusp(1, 0.0, Sign.ARIES),
            5: HouseCusp(5, 120.0, Sign.LEO),
            7: HouseCusp(7, 180.0, Sign.LIBRA),
            10: HouseCusp(10, 270.0, Sign.CAPRICORN),
        },
        planets={
            Planet.SUN: _planet(Planet.SUN, Sign.LEO, 5, 125.0),
            Planet.MOON: _planet(Planet.MOON, Sign.LIBRA, 7, 185.0),
            Planet.VENUS: _planet(Planet.VENUS, Sign.SAGITTARIUS, 9, 250.0),
            Planet.MARS: _planet(Planet.MARS, Sign.ARIES, 1, 10.0),
            Planet.SATURN: _planet(Planet.SATURN, Sign.CAPRICORN, 10, 275.0),
            Planet.PLUTO: _planet(Planet.PLUTO, Sign.LIBRA, 7, 190.0),
        },
    )

def _marriage_ally_chart(*, with_ally: bool) -> Chart:
    """7宫宫头白羊 → 7R 火星；火星落天秤失势，用显式接纳快照模拟援军。"""
    now = datetime(2026, 8, 15, tzinfo=timezone.utc)
    chart = Chart(
        id="marriage_ally_chart",
        person_id="p_marriage_ally",
        chart_type=ChartType.NATAL,
        calculated_at_utc=now,
        julian_day=0.0,
        epoch_utc=now,
        location="test",
        zodiac=ZodiacType.TROPICAL,
        house_system=HouseSystem.WHOLE_SIGN,
        house_cusps={
            1: HouseCusp(1, 180.0, Sign.LIBRA),
            5: HouseCusp(5, 300.0, Sign.AQUARIUS),
            7: HouseCusp(7, 0.0, Sign.ARIES),
            10: HouseCusp(10, 90.0, Sign.CANCER),
        },
        planets={
            Planet.MARS: _planet(Planet.MARS, Sign.LIBRA, 1, 190.0),
            Planet.VENUS: _planet(Planet.VENUS, Sign.LIBRA, 1, 195.0),
            Planet.MOON: _planet(Planet.MOON, Sign.CANCER, 10, 95.0),
            Planet.SUN: _planet(Planet.SUN, Sign.LEO, 11, 125.0),
        },
    )
    if with_ally:
        chart.acceptances = [
            ChartAcceptance(
                acceptor=Planet.VENUS,
                accepted=Planet.MARS,
                dignities=(DignityState.DOMICILE,),
                dignity_type=DignityState.DOMICILE,
                score=5,
                aspect_type=AspectType.CONJUNCTION,
                aspect_nature="HARMONIOUS",
                description_zh="金星接纳火星",
            )
        ]
    return chart


class TestConsultCallPlan:
    def test_call_plan_is_canonical_trunk(self, resolver):
        plan = resolver.resolve_call_plan("我能和他结婚吗")
        assert isinstance(plan, ConsultCallPlan)
        assert plan.domain == "relationship"
        assert plan.domain_label == "感情"
        assert plan.focus_house == 7
        assert plan.topic_id == "marriage"
        assert 7 in plan.core_houses
        assert "venus" in plan.natural_significators
        assert 7 in plan.house_lords
        assert plan.source == "consult_resolver_v2"

    def test_resolve_topic_is_legacy_adapter(self, resolver):
        plan = resolver.resolve_topic("我能和他结婚吗")
        assert isinstance(plan, TopicPlan)
        assert plan.topic_id == "marriage"
        assert plan.primary_house == 7
        assert "venus" in plan.primary_planets

    def test_call_plan_to_dict_keeps_prompt_payload(self, resolver):
        d = resolver.resolve_call_plan("我事业怎么样").to_dict()
        assert d["domain"] == "career"
        assert d["focus_house"] == 10
        assert d["primary_house"] == 10
        assert d["primary_planets"] == d["natural_significators"]
        assert "output_structure" in d
        assert "cross_readings" in d
        assert "guardrails" in d

    def test_module_resolve_call_plan_is_canonical_helper(self):
        plan = resolve_call_plan("我事业怎么样")
        assert isinstance(plan, ConsultCallPlan)
        assert plan.domain == "career"
        assert plan.focus_house == 10
        assert plan.topic_id == "career"

    def test_module_resolve_question_remains_legacy_helper(self):
        plan = resolve_question("我能和他结婚吗")
        assert isinstance(plan, TopicPlan)
        assert plan.topic_id == "marriage"
        assert plan.primary_house == 7

    def test_call_plan_label_uses_system_two_sources(self):
        """话题展示名不再依赖旧 house_nature.label。"""
        resolver = ConsultResolver()
        assert not hasattr(resolver, "_house_nature")
        plan = resolver.resolve_call_plan("我能和他结婚吗")
        assert plan.focus_house == 7
        assert plan.topic_label == "伴侣/婚姻/一对一"
        assert plan.topic_label != "婚姻/合作"

    def test_call_plan_preserves_intent_context(self, resolver):
        intent = Intent(
            id="i_house",
            raw_query="我的3宫表达怎么样",
            domain=IntentDomain.SELF,
            slots={"focus_house": IntentSlot("focus_house", "3宫", "3")},
            focus_slice="表达",
        )
        plan = resolver.resolve_call_plan(intent)
        assert isinstance(plan, ConsultCallPlan)
        assert plan.domain == "self"
        assert plan.focus_house == 3
        assert plan.focus_slice == "表达"

    def test_call_plan_derives_actual_house_lord_from_chart(self, resolver):
        """R10：7R 来自实盘 7 宫宫头星座，而不是 YAML 写死 governors。"""
        plan = resolver.resolve_call_plan("我能和他结婚吗", chart=_carrier_chart())
        assert 7 in plan.house_lords                         # 兼容：仍是要追踪的宫号
        assert "venus" in plan.house_lord_planets           # Libra cusp → traditional Venus
        assert {
            "house": 7,
            "cusp_sign": "libra",
            "lord": "venus",
            "lord_house": 9,
            "lord_sign": "sagittarius",
        } in plan.house_lord_placements

    def test_call_plan_derives_core_house_occupants_from_chart(self, resolver):
        """R10：核心宫内星来自实盘行星落宫，非静态配置。"""
        plan = resolver.resolve_call_plan("我能和他结婚吗", chart=_carrier_chart())
        assert plan.house_occupants == ["sun", "moon", "pluto"]
        assert "venus" in plan.natural_significators

    def test_call_plan_serializes_dynamic_carriers(self, resolver):
        d = resolver.resolve_call_plan("我能和他结婚吗", chart=_carrier_chart()).to_dict()
        assert 7 in d["house_lords"]
        assert "venus" in d["house_lord_planets"]
        assert any(item["house"] == 7 and item["lord_house"] == 9 for item in d["house_lord_placements"])
        assert d["house_occupants"] == ["sun", "moon", "pluto"]

    def test_scenario_map_triggers_debilitated_lord_with_ally(self, resolver):
        """阶段4：scenario_maps 的 has_ally 必须由真实 Chart 接纳链触发。"""
        plan = resolver.resolve_call_plan("我能和他结婚吗", chart=_marriage_ally_chart(with_ally=True))

        matched = [
            s for s in plan.scenarios
            if s.get("condition") == "7R debilitated + has_ally"
        ]
        assert len(matched) == 1
        scenario = matched[0]
        assert scenario["matched"] is True
        assert scenario["target_house"] == 7
        assert scenario["target_lord"] == "mars"
        assert scenario["target_planet_name"] == "火星"
        assert scenario["essential_neg"] > 0
        assert scenario["ally_planet"] == "venus"
        assert scenario["ally_name"] == "金星"
        assert scenario["ally_kind"] == "acceptance"
        assert scenario["ally_aspect"] == "conjunction"
        assert scenario["ally_domain"] == "1宫领域"
        assert scenario["ally_timeline"][0]["helper"] == "venus"
        assert "金星" in scenario["say"]
        assert "1宫领域" in scenario["say"]
        assert "{al ally_name}" not in scenario["say"]

    def test_scenario_map_keeps_no_ally_when_chain_absent(self, resolver):
        """阶段4：没有接纳/互溶帮手时，has_ally 不应误命中。"""
        plan = resolver.resolve_call_plan("我能和他结婚吗", chart=_marriage_ally_chart(with_ally=False))

        conditions = [s.get("condition") for s in plan.scenarios if s.get("type") == "topic"]
        assert "7R debilitated + has_ally" not in conditions
        assert "7R afflicted + ally_timeline_exists" not in conditions
        assert "7R debilitated + no_ally" in conditions
        no_ally = next(s for s in plan.scenarios if s.get("condition") == "7R debilitated + no_ally")
        assert no_ally["matched"] is True
        assert no_ally["target_lord"] == "mars"
        assert "ally_planet" not in no_ally

    def test_scenario_map_without_chart_preserves_template_layer(self, resolver):
        """兼容层：无 Chart 时仍把 YAML 场景模板交给 prompt，不做伪判断。"""
        plan = resolver.resolve_call_plan("我能和他结婚吗")

        conditions = [s.get("condition") for s in plan.scenarios if s.get("type") == "topic"]
        assert "7R debilitated + has_ally" in conditions
        assert "7R debilitated + no_ally" in conditions
        template = next(s for s in plan.scenarios if s.get("condition") == "7R debilitated + has_ally")
        assert "matched" not in template
        assert "{al ally_name}" in template["say"]


# =============================================================================
# 话题匹配
# =============================================================================

class TestCallPlanMatching:
    def test_marriage(self, resolver):
        plan = resolver.resolve_call_plan("我能和他结婚吗")
        assert plan.topic_id == "marriage"
        assert plan.focus_house == 7
        assert 5 in plan.supplementary_houses

    def test_dating(self, resolver):
        plan = resolver.resolve_call_plan("我什么时候才能谈恋爱")
        assert plan.topic_id == "dating"
        assert plan.focus_house == 5

    def test_career(self, resolver):
        plan = resolver.resolve_call_plan("我今年事业怎么样")
        assert plan.topic_id == "career"
        assert plan.focus_house == 10

    def test_career_change(self, resolver):
        plan = resolver.resolve_call_plan("我能换工作吗")
        assert plan.topic_id == "career_change"

    def test_wealth(self, resolver):
        plan = resolver.resolve_call_plan("我财运好吗")
        assert plan.topic_id == "wealth"
        assert plan.focus_house == 2

    def test_villain(self, resolver):
        plan = resolver.resolve_call_plan("最近犯小人怎么办")
        assert plan.topic_id == "villain"
        assert plan.focus_house == 12

    def test_advanced_study(self, resolver):
        plan = resolver.resolve_call_plan("我该不该考研深造")
        assert plan.topic_id == "advanced_study"
        assert plan.focus_house == 9

    def test_study(self, resolver):
        plan = resolver.resolve_call_plan("我学习运怎么样")
        assert plan.topic_id == "study"
        assert plan.focus_house == 3

    def test_semantic_route_keywords_are_primary_source(self):
        """路由关键词已迁入 house_significations，旧 house_nature 不再参与定位。"""
        resolver = ConsultResolver()
        assert not hasattr(resolver, "_house_nature")
        cases = [
            ("我能和他结婚吗", "marriage", 7),
            ("我什么时候才能谈恋爱", "dating", 5),
            ("我今年事业怎么样", "career", 10),
            ("我财运好吗", "wealth", 2),
            ("最近犯小人怎么办", "villain", 12),
            ("我该不该考研深造", "advanced_study", 9),
            ("我学习运怎么样", "study", 3),
            ("我身体怎么样", "health", 6),
        ]
        for question, topic_id, house in cases:
            plan = resolver.resolve_call_plan(question)
            assert plan.topic_id == topic_id
            assert plan.focus_house == house

    def test_marriage_planets(self, resolver):
        """婚姻话题应包含金火月土木等核心星。"""
        plan = resolver.resolve_call_plan("我能结婚吗")
        assert "venus" in plan.natural_significators
        assert "mars" in plan.natural_significators
        assert "moon" in plan.natural_significators

    def test_career_planets_use_domain_signals_not_profile_core_planets(self):
        """R9：intent_profiles.core_planets 即使残留，也不能覆盖 canonical domain_signals。"""
        resolver = ConsultResolver()
        resolver._intent_profiles["career"]["core_planets"] = ["moon"]
        plan = resolver.resolve_call_plan("我事业怎么样")
        assert plan.natural_significators == ["sun", "mars", "jupiter", "saturn"]
        assert "moon" not in plan.natural_significators


# =============================================================================
# 转宫推导
# =============================================================================

class TestDerivedHouse:
    def test_7R_in_9_is_7_of_3(self, resolver):
        assert resolver.derived_house(7, 9) == 3

    def test_7R_in_7_is_7_of_1(self, resolver):
        assert resolver.derived_house(7, 7) == 1

    def test_7R_in_1_is_7_of_7(self, resolver):
        assert resolver.derived_house(7, 1) == 7

    def test_7R_in_12_is_7_of_6(self, resolver):
        assert resolver.derived_house(7, 12) == 6

    def test_10R_in_6_is_10_of_9(self, resolver):
        assert resolver.derived_house(10, 6) == 9

    def test_10R_in_10_is_10_of_1(self, resolver):
        assert resolver.derived_house(10, 10) == 1

    def test_5R_in_7_is_5_of_3(self, resolver):
        assert resolver.derived_house(5, 7) == 3

    def test_2R_in_11_is_2_of_10(self, resolver):
        assert resolver.derived_house(2, 11) == 10

    def test_wraps_past_12(self, resolver):
        """3R in 1 = 3之11 ——验证 12 之后回到 1 的取模。"""
        assert resolver.derived_house(3, 1) == 11


# =============================================================================
# 宫主落宫含义
# =============================================================================

class TestLordPlacement:
    def test_7R_in_7_handwritten(self, resolver):
        result = resolver.get_lord_placement_meaning(7, 7, "7R")
        assert result is not None
        assert result["derived"] == "7之1"
        assert "直达" in result["meaning"]

    def test_7R_in_9_handwritten(self, resolver):
        result = resolver.get_lord_placement_meaning(7, 9, "7R")
        assert result is not None
        assert result["derived"] == "7之3"
        assert len(result["tell_user"]) >= 2

    def test_fallback_for_unknown_lord(self, resolver):
        """未手写的宫主应 fallback 到转宫公式。"""
        result = resolver.get_lord_placement_meaning(11, 5, None)  # 11R in 5 = 11之7
        assert result is not None
        # 11之7 = (5-11+1) % 12 = (-5) % 12 = 7
        assert "11之7" in result["derived"]

    def test_derived_house_meanings_are_primary_source(self):
        """转宫语义来自 house_derived，resolver 不再持有旧 house_nature。"""
        resolver = ConsultResolver()
        assert not hasattr(resolver, "_house_nature")
        result = resolver.get_lord_placement_meaning(11, 5, None)  # 11R in 5 = 11之7
        assert result is not None
        assert result["derived"] == "11之7"
        assert "社群之伴侣" in result["meaning"]
        assert result["meaning"] in result["tell_user"][0]


# =============================================================================
# Prompt 生成
# =============================================================================

class TestCallPlanPromptGeneration:
    def test_marriage_prompt_has_sections(self, resolver):
        plan = resolver.resolve_call_plan("我能结婚吗")
        prompt = resolver.build_call_plan_prompt(plan)
        assert "输出结构" in prompt or "回答结构" in prompt
        assert "婚姻" in prompt

    def test_dating_prompt(self, resolver):
        plan = resolver.resolve_call_plan("我什么时候脱单")
        prompt = resolver.build_call_plan_prompt(plan)
        assert len(prompt) > 0

    def test_career_prompt(self, resolver):
        plan = resolver.resolve_call_plan("我事业怎么样")
        prompt = resolver.build_call_plan_prompt(plan)
        assert len(prompt) > 0

    def test_guardrails_in_prompt(self, resolver):
        plan = resolver.resolve_call_plan("我能结婚吗")
        prompt = resolver.build_call_plan_prompt(plan)
        assert "不能说" in prompt or "结不了婚" in prompt

    def test_build_topic_prompt_remains_legacy_alias(self, resolver):
        plan = resolver.resolve_topic("我能结婚吗")
        assert resolver.build_topic_prompt(plan) == resolver.build_call_plan_prompt(plan)


# =============================================================================
# ConsultCallPlan 序列化
# =============================================================================

class TestCallPlanSerialization:
    def test_to_dict(self, resolver):
        plan = resolver.resolve_call_plan("我能结婚吗")
        d = plan.to_dict()
        assert d["domain"] == "relationship"
        assert d["topic_id"] == "marriage"
        assert d["focus_house"] == 7
        assert d["primary_house"] == 7
        assert "core_houses" in d
        assert "natural_significators" in d
        assert "primary_planets" in d
        assert d["primary_planets"] == d["natural_significators"]
        assert "output_structure" in d
        assert "guardrails" in d

    def test_to_topic_plan_legacy_adapter(self, resolver):
        plan = resolver.resolve_call_plan("我能结婚吗").to_topic_plan()
        assert isinstance(plan, TopicPlan)
        assert plan.topic_id == "marriage"
        assert plan.primary_house == 7
        assert "primary_planets" in plan.to_dict()
