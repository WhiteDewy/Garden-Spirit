"""触发行动识别器测试（self_map_design §4.2 +20 的前置判断）。

触发行动：用户回来了，告诉星灵"我真的去做了"——不是又要聊，是行动完成回报。
识别宁缺毋滥（+20 是稀有分，错发比漏发更伤）：只有明确"完成"才算，犹豫/意图不算。

覆盖：
- 空消息 / 空白 → False
- 规则兜底：强行动完成词 → True（离线可测）
- 规则兜底：未完成先行（"还没做到" 里含"做到"）、意图、疑问、超长 → False
- LLM 路径：available 时走 LLM 分类（{"action": bool}）
- LLM 失败/返回无效 → 规则兜底（服务不炸）
"""

import json

import pytest

from application.conversation.action import ActionDetector


# ---------------------------------------------------------------------------
# 规则兜底（离线确定性）
# ---------------------------------------------------------------------------


def test_empty_message_false():
    assert ActionDetector().is_action_report("") is False
    assert ActionDetector().is_action_report("   ") is False
    assert ActionDetector(None).is_action_report(None) is False


def test_strong_action_words_true():
    """规则兜底只认强完成词（保守：宁缺毋滥）。

    更口语的完成回报（"我去跟老板谈了"）由 LLM 覆盖——规则兜底故意不接。
    """
    det = ActionDetector()
    for msg in (
        "我做到了",
        "我真的去做了",
        "我去做了",
        "我照着做了",
        "我去试了",
        "我行动了",
        "我辞职了",
        "我迈出了那一步",
        "虽然很难，但我做到了",
    ):
        assert det.is_action_report(msg) is True, msg


def test_not_yet_blocks_action_words():
    """未完成先行：含"做到"但其实是"还没做到" → 不算行动回报。"""
    det = ActionDetector()
    for msg in (
        "我还没做到",
        "我还没做",
        "我打算去做",
        "我想去做了",
        "我准备去了",
        "该不该去做",
        "要不要去做",
        "还是没去做",
    ):
        assert det.is_action_report(msg) is False, msg


def test_question_false():
    assert ActionDetector().is_action_report("我做到了吗？") is False
    assert ActionDetector().is_action_report("我去做了?") is False


def test_long_message_false():
    """超长消息大概率是展开描述而非纯行动回报，宁缺毋滥。"""
    long = "我真的去做了" + "然后……" * 30
    assert len(long) > 80
    assert ActionDetector().is_action_report(long) is False


def test_mere_intention_false():
    det = ActionDetector()
    for msg in ("我该不该换工作", "我有点想去做", "我什么时候去做"):
        assert det.is_action_report(msg) is False, msg


# ---------------------------------------------------------------------------
# LLM 路径
# ---------------------------------------------------------------------------


class FakeActionLLM:
    """有 complete() 的假 LLM：可注入返回体。"""

    available = True

    def __init__(self, raw: str):
        self._raw = raw

    def complete(self, prompt, system=None, **kwargs):
        return self._raw


def test_llm_action_true():
    llm = FakeActionLLM(json.dumps({"action": True}))
    assert ActionDetector(llm).is_action_report("我去做了") is True


def test_llm_action_false():
    llm = FakeActionLLM(json.dumps({"action": False}))
    assert ActionDetector(llm).is_action_report("我还没做") is False


def test_llm_markdown_block_ok():
    llm = FakeActionLLM("```json\n{\"action\": true}\n```")
    assert ActionDetector(llm).is_action_report("我做到了") is True


def test_llm_invalid_falls_back_to_rules():
    """LLM 返回无效 JSON → 规则兜底（服务不炸，离线仍可测）。"""
    llm = FakeActionLLM("不好意思，我无法判断")
    det = ActionDetector(llm)
    assert det.is_action_report("我去做了") is True      # 规则兜底命中
    assert det.is_action_report("我该不该去") is False   # 规则兜底拒绝


def test_llm_missing_key_falls_back():
    llm = FakeActionLLM(json.dumps({"something_else": 1}))
    det = ActionDetector(llm)
    assert det.is_action_report("我做到了") is True  # key 缺失 → 规则兜底


def test_llm_without_complete_uses_rules():
    """没有 complete() 的客户端 → 直接规则兜底。"""
    llm = object()  # 无 complete 方法
    det = ActionDetector(llm)
    assert det.is_action_report("我去做了") is True
    assert det.is_action_report("我还在犹豫") is False
