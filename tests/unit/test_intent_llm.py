"""LLM 意图理解测试（A1 对话大脑）。

验证：
- LLM 分类"这个月运势" → daily（修掉关键词翻车）
- LLM 分类"随便聊聊" → Chat 子领域
- LLM 返回无效领域 → 回退规则（LLM 不能发明领域）
- LLM 判定需要澄清 → 澄清
- FakeLLM 没有 classify_intent → 回退规则（旧测试兼容）
- LLMClient.classify_intent 解析结构化 JSON
"""

import json
from unittest import mock

import pytest

from application.agent.intent_parser import IntentParser
from foundation.config import LLMConfig
from foundation.llm.client import LLMClient
from shared.enums import IntentDomain


class FakeClassifyLLM:
    """有 classify_intent 的假 LLM。"""

    available = True

    def __init__(self, result):
        self._result = result

    def classify_intent(self, system_prompt, message):
        return self._result

    def extract_slots(self, system_prompt, message):
        return {}


class FakeOldLLM:
    """只有 extract_slots 的旧假 LLM（兼容测试）。"""

    available = True

    def extract_slots(self, system_prompt, message):
        return {"timeframe": "明年"}


def test_llm_classifies_fortune_to_daily():
    """"这个月运势"LLM 分类 → daily，不再靠关键词。"""
    parser = IntentParser(llm_client=FakeClassifyLLM(
        {"domain": "daily", "subdomain": "", "confidence": 0.9, "needs_clarification": False}
    ))
    intent = parser.parse("我这个月运势怎么样")
    assert intent.domain == IntentDomain.DAILY
    assert not intent.requires_clarification


def test_llm_classifies_chat():
    parser = IntentParser(llm_client=FakeClassifyLLM(
        {"domain": "chat", "confidence": 0.9, "needs_clarification": False}
    ))
    intent = parser.parse("随便聊聊")
    assert intent.subdomain == "Chat"
    assert not intent.requires_clarification


def test_llm_classifies_meta():
    """问星灵自己/产品能力 → LLM 分类 meta → Daily.Meta（能力介绍）。"""
    parser = IntentParser(llm_client=FakeClassifyLLM(
        {"domain": "meta", "confidence": 0.9, "needs_clarification": False}
    ))
    intent = parser.parse("你是做什么的，能学到什么")
    assert intent.domain == IntentDomain.DAILY
    assert intent.subdomain == "Meta"
    assert not intent.requires_clarification


def test_llm_invalid_domain_falls_back_to_rules():
    """LLM 发明领域 → 不信它，回退规则。"""
    parser = IntentParser(llm_client=FakeClassifyLLM(
        {"domain": "fortune_telling", "confidence": 0.99}
    ))
    intent = parser.parse("我这个月运势怎么样")
    # 回退规则：运势 → DAILY
    assert intent.domain == IntentDomain.DAILY


def test_llm_needs_clarification():
    parser = IntentParser(llm_client=FakeClassifyLLM(
        {"domain": "career", "subdomain": "", "confidence": 0.4, "needs_clarification": True}
    ))
    intent = parser.parse("嗯……就是有点烦")
    assert intent.requires_clarification


def test_llm_low_confidence_clarifies():
    parser = IntentParser(llm_client=FakeClassifyLLM(
        {"domain": "career", "subdomain": "", "confidence": 0.2, "needs_clarification": False}
    ))
    intent = parser.parse("我想问点事")
    assert intent.requires_clarification


def test_old_llm_without_classify_falls_back():
    """旧 FakeLLM（只有 extract_slots）→ 规则兜底，不崩。"""
    parser = IntentParser(llm_client=FakeOldLLM())
    intent = parser.parse("我该不该换工作？")
    assert intent.domain == IntentDomain.CAREER
    assert intent.subdomain == "ChangeJob"


def test_llm_none_falls_back():
    parser = IntentParser(llm_client=None)
    intent = parser.parse("我该不该换工作？")
    assert intent.domain == IntentDomain.CAREER


def test_llmclassify_parses_json():
    """LLMClient.classify_intent：结构化 JSON 解析。"""
    client = LLMClient(LLMConfig(api_key="k", model="m"))

    class _FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": json.dumps(
                {"domain": "relationship", "subdomain": "Status", "confidence": 0.85,
                 "needs_clarification": False}
            )}}]}

    with mock.patch("foundation.llm.client.requests.post", return_value=_FakeResponse()):
        result = client.classify_intent("system", "我们感情怎么样")
    assert result["domain"] == "relationship"
    assert result["subdomain"] == "Status"
