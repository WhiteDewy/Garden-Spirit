"""Consult Resolver 单元测试 —— 话题解析 + 转宫推导 + prompt 生成。"""

import pytest

from domain.reasoning.consult import ConsultResolver, TopicPlan


@pytest.fixture(scope="module")
def resolver():
    return ConsultResolver()


# =============================================================================
# 话题匹配
# =============================================================================

class TestTopicMatching:
    def test_marriage(self, resolver):
        plan = resolver.resolve_topic("我能和他结婚吗")
        assert plan.topic_id == "marriage"
        assert plan.primary_house == 7
        assert 5 in plan.supplementary_houses

    def test_dating(self, resolver):
        plan = resolver.resolve_topic("我什么时候才能谈恋爱")
        assert plan.topic_id == "dating"
        assert plan.primary_house == 5

    def test_career(self, resolver):
        plan = resolver.resolve_topic("我今年事业怎么样")
        assert plan.topic_id == "career"
        assert plan.primary_house == 10

    def test_career_change(self, resolver):
        plan = resolver.resolve_topic("我能换工作吗")
        assert plan.topic_id == "career_change"

    def test_wealth(self, resolver):
        plan = resolver.resolve_topic("我财运好吗")
        assert plan.topic_id == "wealth"
        assert plan.primary_house == 2

    def test_villain(self, resolver):
        plan = resolver.resolve_topic("最近犯小人怎么办")
        assert plan.topic_id == "villain"
        assert plan.primary_house == 12

    def test_advanced_study(self, resolver):
        plan = resolver.resolve_topic("我该不该考研深造")
        assert plan.topic_id == "advanced_study"
        assert plan.primary_house == 9

    def test_study(self, resolver):
        plan = resolver.resolve_topic("我学习运怎么样")
        assert plan.topic_id == "study"
        assert plan.primary_house == 3

    def test_health(self, resolver):
        plan = resolver.resolve_topic("我身体怎么样")
        assert plan.topic_id == "health"
        assert plan.primary_house == 6

    def test_marriage_planets(self, resolver):
        """婚姻话题应包含金火月土木等核心星。"""
        plan = resolver.resolve_topic("我能结婚吗")
        assert "venus" in plan.primary_planets
        assert "mars" in plan.primary_planets
        assert "moon" in plan.primary_planets

    def test_career_planets(self, resolver):
        """事业话题应包含火星、木星、土星等核心星。"""
        plan = resolver.resolve_topic("我事业怎么样")
        assert "mars" in plan.primary_planets
        assert "jupiter" in plan.primary_planets
        assert "saturn" in plan.primary_planets


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


# =============================================================================
# Prompt 生成
# =============================================================================

class TestPromptGeneration:
    def test_marriage_prompt_has_sections(self, resolver):
        plan = resolver.resolve_topic("我能结婚吗")
        prompt = resolver.build_topic_prompt(plan)
        assert "输出结构" in prompt or "回答结构" in prompt
        assert "婚姻" in prompt

    def test_dating_prompt(self, resolver):
        plan = resolver.resolve_topic("我什么时候脱单")
        prompt = resolver.build_topic_prompt(plan)
        assert len(prompt) > 0

    def test_career_prompt(self, resolver):
        plan = resolver.resolve_topic("我事业怎么样")
        prompt = resolver.build_topic_prompt(plan)
        assert len(prompt) > 0

    def test_guardrails_in_prompt(self, resolver):
        plan = resolver.resolve_topic("我能结婚吗")
        prompt = resolver.build_topic_prompt(plan)
        assert "不能说" in prompt or "结不了婚" in prompt


# =============================================================================
# TopicPlan 序列化
# =============================================================================

class TestTopicPlanSerialization:
    def test_to_dict(self, resolver):
        plan = resolver.resolve_topic("我能结婚吗")
        d = plan.to_dict()
        assert d["topic_id"] == "marriage"
        assert d["primary_house"] == 7
        assert "supplementary_houses" in d
        assert "primary_planets" in d
        assert "output_structure" in d
        assert "guardrails" in d
