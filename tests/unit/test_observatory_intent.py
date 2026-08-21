"""主题观星台报告型入口上下文的意图层防回归测试。"""

from application.agent.intent_parser import IntentParser, _build_context_block
from shared.enums import ConsultMode, IntentDomain


class _CapturingLLM:
    available = True

    def __init__(self, result: dict):
        self.result = result
        self.system = ""
        self.message = ""

    def classify_intent(self, system: str, message: str) -> dict:
        self.system = system
        self.message = message
        return self.result


def _career_family_context() -> dict:
    return {
        "report_intent": {
            "entry_source": "observatory",
            "entry_topic_key": "career",
            "primary_topic": "career",
            "secondary_topics": ["family"],
            "intent_shape": "cross_topic_influence",
            "report_type": "theme",
            "user_focus_text": "我想看和母亲的关系对我事业的影响",
        },
    }


def test_report_intent_context_marks_entry_as_non_conclusion():
    block = _build_context_block(_career_family_context())

    assert "入口上下文（主题观星台）" in block
    assert "入口主题：career" in block
    assert "入口建议主主题：career" in block
    assert "入口建议次主题：family" in block
    assert "入口意图形态：cross_topic_influence" in block
    assert "入口报告类型：theme" in block
    assert "用户原始关注：我想看和母亲的关系对我事业的影响" in block
    assert "不是占星结论" in block
    assert "不能强行锁死领域" in block
    assert "不要因为入口主题而忽略跨主题影响" in block


def test_report_intent_reaches_llm_without_hard_locking_domain():
    llm = _CapturingLLM({
        "intent_type": "new_question",
        "domain": "family",
        "subdomain": "",
        "focus_house": None,
        "focus_slice": None,
        "deep_dive": False,
        "confirmed": None,
        "confidence": 0.9,
        "needs_clarification": False,
        "reasoning": "用户询问母亲关系这一跨主题来源",
    })
    parser = IntentParser(llm_client=llm)

    intent = parser.parse(
        "我想看和母亲的关系对我事业的影响",
        context=_career_family_context(),
        mode=ConsultMode.DEEP,
    )

    assert llm.message == "我想看和母亲的关系对我事业的影响"
    assert "入口主题：career" in llm.system
    assert "入口建议次主题：family" in llm.system
    assert intent.domain is IntentDomain.FAMILY
    assert intent.entry_source == "observatory"
    assert intent.entry_topic_key == "career"
    assert intent.entry_primary_topic == "career"
    assert intent.entry_secondary_topics == ["family"]
    assert intent.entry_intent_shape == "cross_topic_influence"
    assert intent.entry_report_type == "theme"
    assert intent.entry_user_focus_text == "我想看和母亲的关系对我事业的影响"


def test_report_intent_attaches_on_rule_fallback_without_changing_domain():
    parser = IntentParser()

    intent = parser.parse(
        "我想看和母亲的关系对我事业的影响",
        context=_career_family_context(),
        mode=ConsultMode.DEEP,
    )

    assert intent.entry_topic_key == "career"
    assert intent.entry_secondary_topics == ["family"]
    assert intent.entry_intent_shape == "cross_topic_influence"
    assert intent.raw_query == "我想看和母亲的关系对我事业的影响"


def test_free_mode_receives_report_intent_context_for_continuation():
    """FREE 模式也要看到观星台入口，避免"继续看这个"类省略表达被误当闲聊。"""
    llm = _CapturingLLM({
        "is_astrology_question": False,
        "topic": "continuation",
        "reasoning": "fake result only; this test asserts prompt context",
    })
    parser = IntentParser(llm_client=llm)

    intent = parser.parse(
        "继续看这个会不会影响收入",
        context=_career_family_context(),
        mode=ConsultMode.FREE,
    )

    assert intent.domain is IntentDomain.DAILY
    assert intent.subdomain == "Chat"
    assert "入口上下文（主题观星台）" in llm.system
    assert "入口主题：career" in llm.system
    assert "入口建议次主题：family" in llm.system
    assert "继续占星咨询" in llm.system
    assert "不能据此生成吉凶判断" in llm.system
    assert intent.entry_topic_key == "career"
    assert intent.entry_secondary_topics == ["family"]


def test_no_report_intent_does_not_add_observatory_context():
    block = _build_context_block({"report_intent": None})

    assert block == "（这是对话的第一轮，无上文）"
    assert "主题观星台" not in block
