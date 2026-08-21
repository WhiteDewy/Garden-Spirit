"""P3 护栏回归：LLM/前端不得越过 Domain 占星权威。"""

from datetime import datetime, timezone

from application.conversation.response import build_prompt
from shared.enums import EvidencePolarity, PersonaType
from shared.models import Conclusion, Finding


def _guardrail_conclusion() -> Conclusion:
    return Conclusion(
        id="c_guardrail",
        intent_id="i_guardrail",
        evidence_set_id="es_guardrail",
        domain="career",
        summary="事业主题以法达章节和本命承载者为主，年度小限只提供年度辅助观察。",
        findings=[
            Finding(
                id="f_guardrail",
                category="FINDING",
                text="十宫主土星入庙，事业根基有稳定承载",
                polarity=EvidencePolarity.POSITIVE,
                confidence=0.86,
            )
        ],
        overall_confidence=0.86,
        overall_polarity=EvidencePolarity.POSITIVE,
        generated_at=datetime.now(timezone.utc),
        metadata={
            "timing_authority": "firdaria",
            "annual_activation": {
                "role": "auxiliary",
                "primary_timing_authority": "firdaria",
                "activation_house": 12,
                "activation_lord": "mars",
            },
        },
    )


def test_llm_prompt_states_domain_only_astrology_authority():
    """LLM 只可转述 Domain 素材，不能发明/改写占星事实与权威。"""
    messages = build_prompt(
        _guardrail_conclusion(),
        persona=PersonaType.MOON,
        question="我今年事业会怎样？",
    )

    system = messages[0]["content"]
    user = messages[1]["content"]
    assert "系统提供，你只转述" in system
    assert "你只能转述下面提供的数据" in system
    assert "绝不能发明任何占星事实" in system
    assert "极性（得吉/受克）一个字都不能改" in system
    assert "证据链不能删减" in system
    assert "内容只能来自上面的数据，语气是你的" in user


def test_conclusion_contract_keeps_timing_authority_in_domain_metadata_only():
    """Conclusion 可携带 Domain 审计元数据；LLM/前端不从中自行推断新权威。"""
    conclusion = _guardrail_conclusion()

    assert conclusion.metadata["timing_authority"] == "firdaria"
    annual = conclusion.metadata["annual_activation"]
    assert annual["role"] == "auxiliary"
    assert annual["primary_timing_authority"] == "firdaria"
    assert "year_lord" not in conclusion.metadata
    assert "year_lord" not in annual


def test_observatory_frontend_copy_declares_no_fake_reports():
    """主题观星台只能发起上下文与展示证据状态，不能前端伪造报告结论。"""
    path = "frontend/src/pages/universe/consult.vue"
    with open(path, encoding="utf-8") as f:
        source = f.read()

    assert "这里不前端生成预测结论" in source
    assert "入口主题只作上下文" in source
    assert "后端会重新识别" in source
    assert "不会前端伪造结论" in source
    assert "net_score" not in source
    assert "年主星" not in source
