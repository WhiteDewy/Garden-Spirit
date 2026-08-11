"""照见确认识别器测试（被照见 +5 的前置判断，§4.2）。

验证：
- 强确认短语（对/就是这样/你懂我）→ True
- 弱认同/敷衍（嗯/哈哈/谢谢）→ False（宁缺毋滥）
- 否定解读（不对/不是）→ False
- 新话题/疑问句 → False
- LLM 返回非法结构 → 规则兜底
"""

import json

from application.conversation.confirmation import ConfirmationDetector


def test_rule_positive_confirmation():
    d = ConfirmationDetector()
    assert d.is_confirmation("对，就是这样") is True
    assert d.is_confirmation("对，就是这样，我最近总是这样") is True   # 确认 + 短补充
    assert d.is_confirmation("你懂我，说到我心里了") is True
    assert d.is_confirmation("完全被你说中了") is True
    assert d.is_confirmation("你说得对") is True


def test_rule_weak_ack_is_not_confirmation():
    """礼貌敷衍太弱，不算真确认（照见分要诚实，宁缺毋滥）。"""
    d = ConfirmationDetector()
    assert d.is_confirmation("嗯嗯") is False
    assert d.is_confirmation("哈哈") is False
    assert d.is_confirmation("谢谢") is False
    assert d.is_confirmation("好的") is False
    assert d.is_confirmation("对") is False          # 单个"对"太弱（可能接"但是"）


def test_rule_negation_not_confirmation():
    d = ConfirmationDetector()
    assert d.is_confirmation("不对，我不是这个意思") is False
    assert d.is_confirmation("不是这样") is False
    assert d.is_confirmation("没那么严重") is False


def test_rule_new_topic_or_question_not_confirmation():
    d = ConfirmationDetector()
    assert d.is_confirmation("我最近在考虑换工作，你怎么看？") is False
    assert d.is_confirmation("那明年呢？") is False
    assert d.is_confirmation("最近看了一部电影叫九门") is False   # 新话题
    assert d.is_confirmation("") is False


def test_llm_result_respected():
    """LLM 返回 confirmed=false → 不认（即使含关键词）。"""

    class FakeLLM:
        available = True

        def complete(self, prompt, system=None, **kwargs):
            return json.dumps({"confirmed": False})

    d = ConfirmationDetector(FakeLLM())
    assert d.is_confirmation("对，就是这样") is False


def test_llm_failure_falls_back_to_rule():
    """LLM 返回非法结构 → 规则兜底。"""

    class BrokenLLM:
        available = True

        def complete(self, prompt, system=None, **kwargs):
            return "not json"

    d = ConfirmationDetector(BrokenLLM())
    assert d.is_confirmation("对，就是这样") is True
