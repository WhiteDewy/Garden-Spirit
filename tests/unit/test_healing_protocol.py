"""A3 疗愈协议测试：叙事 5 步 + 输出护栏。

验证：
- HEALING_STEPS 是规范弧线（共情→本命基调→交叉判断→时机→给出路）
- build_healing_instruction() 编译出含 5 步 + 护栏的 system prompt 块
- build_prompt() 已注入该指令（wiring）
- healing_guardrail_check() 命中致命判决词 → 返回"给出路"收尾
- 幂等：已含出路 marker → 不重复追加
- 干净文本/合理上下文 → 不误伤
- WAY_OUT_CODA 本身是建设性的（给出路）
"""

from shared.enums import PersonaType
from shared.models import Conclusion

from application.conversation.healing import (
    GENERIC_WAY_OUT,
    GUARDRAIL_PATTERNS,
    HEALING_STEPS,
    WAY_OUT_CODA,
    build_healing_instruction,
    healing_guardrail_check,
)
from application.conversation.response import build_prompt


# --- 5 步弧线 ---


def test_healing_steps_order():
    titles = [s[1] for s in HEALING_STEPS]
    assert titles == ["共情", "本命基调", "交叉判断", "时机", "给出路"]


def test_healing_steps_unique_ids():
    ids = [s[0] for s in HEALING_STEPS]
    assert len(ids) == len(set(ids)) == 5


def test_build_instruction_has_all_steps():
    text = build_healing_instruction()
    for title in ("共情", "本命基调", "交叉判断", "时机", "给出路"):
        assert title in text


def test_build_instruction_has_guardrails():
    text = build_healing_instruction()
    assert "判决书" in text
    assert "给出路" in text
    assert "压力不等于垮台" in text
    assert "不能诊断疾病" in text
    assert "指导用药" in text


# --- 输出护栏检测 ---


def test_guardrail_detects_zhu_ding():
    assert healing_guardrail_check("你注定单身") is not None


def test_guardrail_detects_divorce():
    assert healing_guardrail_check("你们的婚姻一定离婚") is not None


def test_guardrail_detects_ming_li():
    assert healing_guardrail_check("你命里没有财运") is not None


def test_guardrail_clean_passes():
    assert healing_guardrail_check("星盘显示有挑战，但可以经营出结果") is None


def test_guardrail_no_false_on_negative_star():
    """受克、压力等词不是致命判决——正常解读不误伤。"""
    text = "这段感情有结构性压力，火星受克，需要额外经营，但盘上有木星在帮它"
    assert healing_guardrail_check(text) is None


def test_guardrail_idempotent_marker():
    """已含"给出路" marker → 不再重复追加（幂等，防双 coda）。"""
    assert healing_guardrail_check("你注定单身。" + WAY_OUT_CODA) is None


def test_guardrail_empty_text():
    assert healing_guardrail_check("") is None
    assert healing_guardrail_check(None) is None


def test_way_out_coda_is_constructive():
    assert "不是绝路" in WAY_OUT_CODA
    assert "发力" in WAY_OUT_CODA
    assert "地图是死的，走路的是你" in WAY_OUT_CODA


def test_generic_way_out_is_constructive():
    assert "不是死路" in GENERIC_WAY_OUT
    assert "发力" in GENERIC_WAY_OUT


# --- 接线：build_prompt 已注入疗愈指令 ---


def test_build_prompt_injects_healing_instruction():
    conclusion = Conclusion(
        id="c1", intent_id="i1", evidence_set_id="e1",
        domain="career", summary="总体判断",
    )
    messages = build_prompt(conclusion=conclusion, persona=PersonaType.MOON)
    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    assert "疗愈叙事协议" in system
    assert "5 步节奏" in system


def test_guardrail_patterns_all_present_in_patterns_list():
    """护栏词表非空、且都是致命判决类（不混入正常词汇）。"""
    assert len(GUARDRAIL_PATTERNS) >= 10
    assert "注定" in GUARDRAIL_PATTERNS
