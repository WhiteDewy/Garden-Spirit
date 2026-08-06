"""意图路由修复测试——"这个月运势"接住 + 闲聊不循环澄清。

背景：用户实测"我这个月运势怎么样"和"随便聊聊"都被反复要求澄清。
根因：Daily 规则只有"今天运势/运势如何"，没接住"运势/这个月运势"；
      闲聊没有任何处理，落入澄清循环。
"""

import pytest

from domain.reasoning.intent import IntentRouter
from shared.enums import IntentDomain


def test_daily_fortune_routing():
    """"这个月运势"必须路由到 Daily，不要求澄清。"""
    intent = IntentRouter().route("我这个月运势怎么样")
    assert intent.domain == IntentDomain.DAILY
    assert not intent.requires_clarification


@pytest.mark.parametrize("q", [
    "今天运势", "今日运势", "最近运势怎么样", "本月运势如何",
    "这个月运势", "这周运势", "流年运势", "运势",
])
def test_daily_variants(q):
    intent = IntentRouter().route(q)
    assert intent.domain == IntentDomain.DAILY, q
    assert not intent.requires_clarification


def test_meta_routes_capability_questions():
    """问星灵自己/产品能力 → Daily.Meta（离线兜底路由）。"""
    for q in ("你是谁", "你能做什么", "我能从你这里学到什么",
              "你有什么专业", "你的专业是什么", "这有什么用"):
        intent = IntentRouter().route(q)
        assert intent.domain == IntentDomain.DAILY, q
        assert intent.subdomain == "Meta", q


def test_meta_does_not_swallow_real_questions():
    """真实提问（学习/职业）不能被 Meta 吞掉。"""
    for q in ("我适合学什么专业方向", "考研还是直接工作", "我在工作里能学到什么"):
        intent = IntentRouter().route(q)
        assert intent.subdomain != "Meta", q


def test_chat_routing_not_clarification():
    """"随便聊聊" → Chat 子领域，不要求澄清。"""
    intent = IntentRouter().route("相随便聊聊")
    assert intent.subdomain == "Chat"
    assert not intent.requires_clarification


def test_greeting_does_not_steal_real_question():
    """"你好"开头的真问题：领域信号（事业）必须压过问候。"""
    intent = IntentRouter().route("你好，我想问下事业")
    assert intent.domain == IntentDomain.CAREER


def test_greeting_does_not_steal_fortune():
    intent = IntentRouter().route("你好，我最近运势怎么样")
    assert intent.domain == IntentDomain.DAILY


def test_runtime_detect_chat():
    """纯问候短句 → 温暖回应；长句/真问题 → None（交给路由）。"""
    from application.agent.runtime import GardenSpiritAgent

    assert GardenSpiritAgent._detect_chat("你好") is not None
    assert GardenSpiritAgent._detect_chat("相随便聊聊") is not None
    assert GardenSpiritAgent._detect_chat("在吗") is not None
    assert GardenSpiritAgent._detect_chat("我该不该离职？") is None
    assert GardenSpiritAgent._detect_chat("聊聊感情") is None      # 交给路由 → 感情
    assert GardenSpiritAgent._detect_chat("你好，我最近运势怎么样") is None  # 长句 → 路由
