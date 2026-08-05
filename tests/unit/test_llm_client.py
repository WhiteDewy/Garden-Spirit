"""LLM 客户端测试：mock API，验证请求/响应格式与降级行为。"""

import json
from unittest import mock

import pytest

from foundation.config import LLMConfig
from foundation.llm.client import LLMClient, LLMError


def _make_client(**overrides):
    cfg = LLMConfig(api_key="test-key", **overrides)
    return LLMClient(cfg)


class _FakeResponse:
    def __init__(self, status_code=200, text="", data=None):
        self.status_code = status_code
        self.text = text or json.dumps(data or {})
        self._data = data

    def json(self):
        if self._data is not None:
            return self._data
        return json.loads(self.text)


def test_available_false_without_key():
    """无 api_key → available=False。"""
    assert LLMClient(LLMConfig(api_key="")).available is False


def test_chat_sends_correct_payload():
    """验证发送的 payload 结构（model/messages/temperature）。"""
    cfg = LLMConfig(api_key="k", model="test-model", temperature=0.3)
    client = LLMClient(cfg)
    messages = [{"role": "user", "content": "你好"}]

    fake = _FakeResponse(data={"choices": [{"message": {"content": "我回来了"}}]})
    with mock.patch("foundation.llm.client.requests.post", return_value=fake) as m:
        out = client.chat(messages)

    assert out == "我回来了"
    # 验证请求
    call = m.call_args
    assert call.kwargs["json"]["model"] == "test-model"
    assert call.kwargs["json"]["messages"] == messages
    assert call.kwargs["json"]["temperature"] == 0.3
    assert call.kwargs["headers"]["Authorization"] == "Bearer k"


def test_chat_raises_on_non_200():
    """非 200 → LLMError。"""
    client = _make_client()
    fake = _FakeResponse(status_code=429, text="rate limited")
    with mock.patch("foundation.llm.client.requests.post", return_value=fake):
        with pytest.raises(LLMError):
            client.chat([{"role": "user", "content": "hi"}])


def test_chat_raises_on_missing_key():
    """无 key 直接报错，不发请求。"""
    client = LLMClient(LLMConfig(api_key=""))
    with pytest.raises(LLMError):
        client.chat([{"role": "user", "content": "hi"}])


# ---------------------------------------------------------------------------
# extract_slots —— LLM 意图槽抽取
# ---------------------------------------------------------------------------


def test_extract_slots_returns_parsed_dict():
    """extract_slots 调用 complete 并解析返回 JSON。"""
    client = _make_client()
    slot_json = '{"person": "我", "timeframe": "明年"}'
    fake = _FakeResponse(data={"choices": [{"message": {"content": slot_json}}]})
    with mock.patch("foundation.llm.client.requests.post", return_value=fake):
        result = client.extract_slots("抽槽", "我明年能换工作吗？")
    assert result == {"person": "我", "timeframe": "明年"}


def test_extract_slots_strips_markdown_code_block():
    """extract_slots 去掉 markdown ```json ... ``` 包裹。"""
    client = _make_client()
    raw = '```json\n{"person": "我"}\n```'
    fake = _FakeResponse(data={"choices": [{"message": {"content": raw}}]})
    with mock.patch("foundation.llm.client.requests.post", return_value=fake):
        result = client.extract_slots("抽槽", "我的事业怎么样？")
    assert result == {"person": "我"}


def test_extract_slots_handles_null_values():
    """JSON 中 null 值的 key 被过滤掉。"""
    client = _make_client()
    raw = '{"person": "我", "related_person": null, "timeframe": "今年"}'
    fake = _FakeResponse(data={"choices": [{"message": {"content": raw}}]})
    with mock.patch("foundation.llm.client.requests.post", return_value=fake):
        result = client.extract_slots("抽槽", "测试")
    assert result == {"person": "我", "timeframe": "今年"}
    assert "related_person" not in result


def test_extract_slots_returns_empty_on_invalid_json():
    """LLM 返回非 JSON 文本 → 返回 {}。"""
    client = _make_client()
    fake = _FakeResponse(data={"choices": [{"message": {"content": "嗯，好的..."}}]})
    with mock.patch("foundation.llm.client.requests.post", return_value=fake):
        result = client.extract_slots("抽槽", "测试")
    assert result == {}


def test_extract_slots_returns_empty_on_llm_error():
    """LLM 调用异常 → 返回 {}（规则兜底）。"""
    client = _make_client()
    with mock.patch("foundation.llm.client.requests.post", side_effect=Exception("timeout")):
        result = client.extract_slots("抽槽", "测试")
    assert result == {}


def test_extract_slots_returns_empty_when_unavailable():
    """LLM 不可用（无 key）→ extract_slots 返回 {}。"""
    client = LLMClient(LLMConfig(api_key=""))
    result = client.extract_slots("抽槽", "测试")
    assert result == {}


def test_parse_slots_json_extracts_first_braces():
    """_parse_slots_json 从杂文本中抓取第一个 {...}。"""
    from foundation.llm.client import LLMClient as LC

    result = LC._parse_slots_json('前文...\n{"timeframe": "下个月"}\n后文...')
    assert result == {"timeframe": "下个月"}


def test_parse_slots_json_empty_string():
    """空字符串 → {}。"""
    from foundation.llm.client import LLMClient as LC

    assert LC._parse_slots_json("") == {}


def test_intent_parser_with_llm_client():
    """IntentParser 带 LLM 客户端：LLM 抽槽 + 规则路由协作。"""
    from application.agent.intent_parser import IntentParser
    from shared.models import Intent

    # 模拟 LLM 客户端
    class FakeLLM:
        def extract_slots(self, system_prompt, message):
            return {"timeframe": "明年", "person": "我"}

    parser = IntentParser(llm_client=FakeLLM())
    intent = parser.parse("我明年能换工作吗？")
    # LLM 抽了槽，规则路由命中 career/ChangeJob
    assert intent.domain.value == "career"
    assert intent.subdomain == "ChangeJob"
    # LLM 槽位被吸收进 Intent.slots
    assert intent.get_slot("timeframe") is not None or intent.domain_confidence > 0


def test_intent_parser_llm_failure_falls_back_to_rules():
    """LLM 槽抽取异常 → 规则仍然工作（不阻断）。"""
    from application.agent.intent_parser import IntentParser

    class FailingLLM:
        def extract_slots(self, system_prompt, message):
            raise RuntimeError("boom")

    parser = IntentParser(llm_client=FailingLLM())
    intent = parser.parse("我该换工作吗？")
    # LLM 失败但规则仍命中 career/ChangeJob
    assert intent.domain.value == "career"
    assert intent.subdomain == "ChangeJob"
    assert not intent.requires_clarification
