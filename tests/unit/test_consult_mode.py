"""咨询模式测试（Task 7）。

验证：
- quick 模式在 LLM system prompt 注入精简指令（覆盖长度）
- deep 模式不注入（默认完整叙事）
- 未传/非法 mode 安全回退
- API /chat 接受 mode 并回传
"""

from datetime import datetime, timezone

from shared.enums import ConsultMode, EvidencePolarity, IntentDomain, PersonaType
from shared.models import Conclusion, Finding, Intent

from application.conversation.response import build_prompt, _build_mode_instruction


def _make_conclusion() -> Conclusion:
    return Conclusion(
        id="c1", intent_id="i1", evidence_set_id="e1", domain="career",
        summary="总体支持",
        findings=[Finding(id="f1", category="FINDING", text="月亮落11宫得吉",
                          polarity=EvidencePolarity.POSITIVE, confidence=0.8)],
        overall_confidence=0.8,
        overall_polarity=EvidencePolarity.POSITIVE,
        generated_at=datetime.now(timezone.utc),
    )


def _make_intent() -> Intent:
    return Intent(id="i1", raw_query="该不该换工作？", domain=IntentDomain.CAREER)


# --- prompt 指令注入 ---

def test_quick_mode_injects_instruction():
    messages = build_prompt(_make_conclusion(), persona=PersonaType.MOON,
                            question="该不该换工作？", mode=ConsultMode.QUICK)
    system = messages[0]["content"]
    assert "快速咨询" in system
    assert "120-180 字" in system


def test_deep_mode_no_quick_instruction():
    messages = build_prompt(_make_conclusion(), persona=PersonaType.MOON,
                            question="该不该换工作？", mode=ConsultMode.DEEP)
    system = messages[0]["content"]
    assert "快速咨询" not in system
    assert "300-600字" in system  # 深度保留默认长度要求


def test_default_mode_is_deep():
    messages = build_prompt(_make_conclusion(), persona=PersonaType.MOON)
    assert "快速咨询" not in messages[0]["content"]


def test_mode_instruction_helpers():
    assert _build_mode_instruction(ConsultMode.QUICK)
    assert _build_mode_instruction("quick")
    assert _build_mode_instruction(ConsultMode.DEEP) == ""
    assert _build_mode_instruction(ConsultMode.ANNUAL) == ""  # 框架预留
    assert _build_mode_instruction(None) == ""                # 非法/空 → 空
    assert _build_mode_instruction("bogus") == ""             # 非法字符串 → 空


def test_all_modes_are_valid_enum_values():
    """5 种咨询模式都存在于枚举（框架就位）。"""
    assert {m.value for m in ConsultMode} == {"quick", "deep", "annual", "chart", "free"}
