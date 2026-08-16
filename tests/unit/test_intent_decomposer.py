"""IntentDecomposer + intent_profiles 测试。

验证：安全网、触发词、LLM 校验、回退、parse_deep 接线。
"""

from unittest import mock

import pytest

from shared.enums import IntentDomain, Priority
from shared.models import Intent
from domain.reasoning.intent import IntentRouter
from domain.reasoning.intent.decomposer import (
    AnalysisTask,
    DecomposedIntent,
    IntentDecomposer,
)
from domain.reasoning.intent.intent_profiles import (
    evaluate_conditional_tasks,
    get_base_tasks,
    load_profiles,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def profiles():
    return load_profiles()


@pytest.fixture(scope="module")
def router():
    return IntentRouter()


@pytest.fixture(scope="module")
def decomposer_no_llm():
    """无 LLM 的 decomposer——纯规则路径。"""
    return IntentDecomposer(llm_client=None)


# ---------------------------------------------------------------------------
# Profile 加载
# ---------------------------------------------------------------------------


def test_all_domains_have_profiles(profiles):
    """11 个 IntentDomain 都有配置（v2 领域引擎：八域 + growth/network/self + daily）。"""
    required = {"career", "relationship", "wealth", "health", "emotion", "family",
                "learning", "growth", "network", "self", "daily"}
    assert set(profiles) == required


def test_base_tasks_not_empty(profiles):
    """每个领域都有必修模块。"""
    for domain, profile in profiles.items():
        assert len(profile.base_tasks) > 0, f"{domain} 缺少 base_tasks"


def test_get_base_tasks_career(profiles):
    """Career 必修：CareerStrength + Timing。"""
    tasks = get_base_tasks(profiles, IntentDomain.CAREER)
    modules = {t.module for t in tasks}
    assert "CareerStrength" in modules
    assert "Timing" in modules


# ---------------------------------------------------------------------------
# Conditional tasks
# ---------------------------------------------------------------------------


def test_burnout_keyword_triggers_psychology(profiles):
    """倦怠触发词 → 自动追加 Psychology + Emotion。"""
    tasks = evaluate_conditional_tasks(profiles, IntentDomain.CAREER, "我上班跟上坟一样累")
    modules = {t.module for t in tasks}
    assert "Psychology" in modules
    assert "Emotion" in modules


def test_change_job_keyword_triggers_opportunity(profiles):
    """换工作触发词 → 追加 Opportunity + Risk + Finance。"""
    tasks = evaluate_conditional_tasks(profiles, IntentDomain.CAREER, "我该换工作吗")
    modules = {t.module for t in tasks}
    assert "Opportunity" in modules
    assert "Risk" in modules
    assert "Finance" in modules


def test_no_trigger_returns_empty(profiles):
    """不匹配触发词 → 无条件任务。"""
    tasks = evaluate_conditional_tasks(profiles, IntentDomain.CAREER, "我想了解一下事业")
    assert len(tasks) == 0


# ---------------------------------------------------------------------------
# Decomposer（无 LLM）
# ---------------------------------------------------------------------------


def test_decomposer_no_llm_returns_base_tasks(decomposer_no_llm, router):
    """无 LLM → 返回 base_tasks + conditional_tasks 合并。"""
    intent = router.route("我上班跟上坟一样，该不该换工作？")
    result = decomposer_no_llm.decompose(intent)
    assert not result.llm_used
    modules = {t.module for t in result.merged_tasks}
    # base: CareerStrength, Timing
    assert "CareerStrength" in modules
    assert "Timing" in modules
    # conditional: Psychology, Emotion, Opportunity, Risk, Finance
    assert "Psychology" in modules
    assert "Opportunity" in modules


def test_decomposer_no_llm_no_trigger(decomposer_no_llm, router):
    """无触发词 → 只有 base_tasks。"""
    intent = router.route("我的事业怎么样")
    result = decomposer_no_llm.decompose(intent)
    assert not result.llm_used
    modules = {t.module for t in result.merged_tasks}
    assert "CareerStrength" in modules
    assert "Timing" in modules
    # 无条件模块
    assert len(result.conditional_tasks) == 0


def test_decomposed_intent_wrap():
    """DecomposedIntent.wrap 创建最小实例。"""
    intent = IntentRouter().route("测试")
    di = DecomposedIntent.wrap(intent)
    assert di.intent is intent
    assert not di.llm_used
    assert di.merged_tasks == []


def test_decomposed_intent_delegates_to_intent():
    """DecomposedIntent 属性委托给 Intent。"""
    intent = IntentRouter().route("换工作")
    di = DecomposedIntent.wrap(intent)
    assert di.domain == intent.domain
    assert di.raw_query == intent.raw_query


def test_decomposer_theme_prompt_uses_domain_signals_not_theme_core_planets():
    """R9：theme_map.core_planets 即使残留，也不能进入 LLM 参考素材。"""
    dec = IntentDecomposer(llm_client=None)
    dec._theme_map["career_psychology"]["core_planets"] = ["moon"]
    text = dec._fmt_themes(IntentDomain.CAREER)
    assert "planets(core)=['sun', 'mars', 'jupiter', 'saturn']" in text
    assert "planets(supporting)=" in text
    assert "planets(core)=['moon']" not in text


def test_decomposer_house_prompt_hides_legacy_governors():
    """R10：LLM 定位素材只给语义场/路由词，不再暴露 YAML 写死 governors。"""
    dec = IntentDecomposer(llm_client=None)
    text = dec._fmt_houses(IntentDomain.RELATIONSHIP)
    assert "governors=" not in text
    assert "伴侣" in text or "婚姻" in text


# ---------------------------------------------------------------------------
# LLM 校验
# ---------------------------------------------------------------------------


class _FakeLLM:
    """模拟 LLM 客户端。"""
    def __init__(self, response_json: dict):
        self._response = response_json

    @property
    def available(self):
        return True

    def complete(self, prompt, system, temperature):
        import json
        return json.dumps(self._response, ensure_ascii=False)


def test_decomposer_llm_invalid_module_filtered(router):
    """LLM 建议未注册模块 → 被过滤。"""
    fake = _FakeLLM({
        "focus_houses": [10, 6],
        "focus_planets": ["sun"],
        "focus_house_lords": [10],
        "focus_aspect_pairs": [],
        "focus_dimensions": ["测试"],
        "reasoning": "test",
        "extra_tasks": [
            {"module": "NotAModule", "priority": "high"},
            {"module": "Emotion", "priority": "medium"},
        ],
    })
    dec = IntentDecomposer(llm_client=fake)
    intent = router.route("我的事业怎么样")
    result = dec.decompose(intent)
    assert result.llm_used
    mods = {t.module for t in result.llm_extra_tasks}
    assert "NotAModule" not in mods
    assert "Emotion" in mods


def test_decomposer_llm_invalid_houses_filtered(router):
    """LLM 返回非法宫位号 → 被过滤。"""
    fake = _FakeLLM({
        "focus_houses": [10, 99, -1, 6],
        "focus_planets": ["sun"],
        "focus_house_lords": [10],
        "focus_aspect_pairs": [],
        "focus_dimensions": [],
        "reasoning": "",
        "extra_tasks": [],
    })
    dec = IntentDecomposer(llm_client=fake)
    result = dec.decompose(router.route("测试"))
    assert result.focus_houses == [10, 6]  # 99 和 -1 被过滤


def test_decomposer_llm_invalid_planets_filtered(router):
    """LLM 返回非法行星 → 被过滤。"""
    fake = _FakeLLM({
        "focus_houses": [10],
        "focus_planets": ["sun", "xyz", "moon", ""],
        "focus_house_lords": [],
        "focus_aspect_pairs": [["sun", "xyz"], ["moon", "saturn"]],
        "focus_dimensions": [],
        "reasoning": "",
        "extra_tasks": [],
    })
    dec = IntentDecomposer(llm_client=fake)
    result = dec.decompose(router.route("测试"))
    assert "xyz" not in result.focus_planets
    assert result.focus_planets == ["sun", "moon"]
    # 非法 pair 被过滤
    assert result.focus_aspect_pairs == [["moon", "saturn"]]


def test_decomposer_llm_failure_graceful(router):
    """LLM 抛异常 → 不回退，base_tasks 仍有效。"""
    class _CrashingLLM:
        available = True
        def complete(self, *a, **kw):
            raise RuntimeError("boom")

    dec = IntentDecomposer(llm_client=_CrashingLLM())
    result = dec.decompose(router.route("我的事业怎么样"))
    assert not result.llm_used
    assert len(result.merged_tasks) >= 2  # base: CareerStrength + Timing


def test_decomposer_json_parsing_markdown():
    """_parse_json 去掉 markdown 代码块。"""
    raw = '```json\n{"focus_houses": [1]}\n```'
    result = IntentDecomposer._parse_json(raw)
    assert result == {"focus_houses": [1]}


def test_decomposer_json_parsing_bare():
    """_parse_json 提取裸 JSON。"""
    raw = '前文...\n{"focus_houses": [10]}\n后文...'
    result = IntentDecomposer._parse_json(raw)
    assert result == {"focus_houses": [10]}


def test_decomposer_json_parsing_failure():
    """_parse_json 无法提取 → ValueError。"""
    with pytest.raises(ValueError):
        IntentDecomposer._parse_json("今天天气不错")


# ---------------------------------------------------------------------------
# parse_deep 接线
# ---------------------------------------------------------------------------


def test_parse_deep_no_decomposer():
    """未配置 decomposer → parse_deep 返回最小 DecomposedIntent。"""
    from application.agent.intent_parser import IntentParser

    parser = IntentParser()
    result = parser.parse_deep("我的事业怎么样")
    assert isinstance(result, DecomposedIntent)
    assert not result.llm_used
    assert result.intent.domain == IntentDomain.CAREER


def test_parse_deep_clarification_short_circuit():
    """需澄清的意图 → parse_deep 不走拆解直接返回。"""
    from application.agent.intent_parser import IntentParser

    parser = IntentParser()
    result = parser.parse_deep("啊")
    assert isinstance(result, DecomposedIntent)
    assert result.intent.requires_clarification
    assert not result.llm_used


def test_parse_deep_with_decomposer(router):
    """有 decomposer → parse_deep 走富化路径。"""
    from application.agent.intent_parser import IntentParser

    dec = IntentDecomposer(llm_client=None)  # 无 LLM，纯规则
    parser = IntentParser(decomposer=dec)
    result = parser.parse_deep("我上班跟上坟一样累")
    assert isinstance(result, DecomposedIntent)
    # 触发词生效
    mods = {t.module for t in result.merged_tasks}
    assert "Psychology" in mods


# ---------------------------------------------------------------------------
# AnalysisTask
# ---------------------------------------------------------------------------


def test_analysis_task_defaults():
    t = AnalysisTask(module="Test")
    assert t.module == "Test"
    assert t.priority == Priority.MEDIUM
    assert t.params == {}
    assert t.reasoning == ""


def test_analysis_task_with_params():
    t = AnalysisTask(module="Timing", priority=Priority.HIGH, params={"window": 6}, reasoning="因为所以")
    assert t.priority == Priority.HIGH
    assert t.params == {"window": 6}
