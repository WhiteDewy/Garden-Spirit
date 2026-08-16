"""Safety 模块测试：免责声明 + 情绪危机检测。

纯关键词检测，无 LLM。验证：
- 自伤/自杀信号 → blocked，返回专业求助引导
- 情绪低落信号 → caution（不阻断）
- 正常问题 → safe
- 免责声明非空
"""

import re
from pathlib import Path

import pytest

from application.conversation.safety import (
    MEDICAL_BOUNDARY_CODA,
    SafetyResult,
    check_safety,
    disclaimer_text,
    medical_boundary_check,
    medical_boundary_instruction,
)


# --- 阻断级：自伤/自杀信号 ---

@pytest.mark.parametrize(
    "msg",
    [
        "我不想活了",
        "我想自杀",
        "想死",
        "活不下去了",
        "我割腕了",
        "想跳楼",
        "活着没意思",
        "我想结束生命",
        "撑不住了",
    ],
)
def test_block_on_crisis_keyword(msg):
    r = check_safety(msg)
    assert r.level == "blocked"
    assert "心理援助" in r.message or "急救" in r.message


def test_block_message_contains_disclaimer():
    """阻断话术也带免责声明尾部。"""
    r = check_safety("我想自杀")
    assert "仅供自我探索参考" in r.message


# --- 警告级：情绪低落信号（不阻断） ---

@pytest.mark.parametrize("msg", ["我很抑郁", "好绝望", "崩溃了", "走不出来"])
def test_caution_on_distress(msg):
    r = check_safety(msg)
    assert r.level == "caution"


@pytest.mark.parametrize(
    "msg",
    [
        "星盘能看我是不是得了癌症吗",
        "我该不该停药",
        "医生这个诊断是不是准",
        "我还能活多久",
    ],
)
def test_medical_boundary_caution_not_blocked(msg):
    """医疗诊断/用药/寿命问题不走占星阻断，但标记 caution 供输出边界兜底。"""
    r = check_safety(msg)
    assert r.level == "caution"
    assert r.message == ""


def test_medical_boundary_check_adds_coda():
    coda = medical_boundary_check("星盘能看我该不该停药吗")
    assert coda == MEDICAL_BOUNDARY_CODA
    assert "医生诊断为准" in coda
    assert "不能判断疾病" in coda
    assert "用药" in coda


def test_medical_boundary_check_idempotent():
    assert medical_boundary_check("我想问停药。" + MEDICAL_BOUNDARY_CODA) is None


def test_medical_boundary_instruction_for_prompt():
    text = medical_boundary_instruction()
    assert "不能诊断疾病" in text
    assert "预测寿命" in text
    assert "指导用药" in text


# --- 安全级：正常问题 ---

def test_safe_on_normal_query():
    r = check_safety("看下事业运，最近要不要换工作？")
    assert r.level == "safe"
    assert r.message == ""


def test_safe_on_relationship_query():
    r = check_safety("和男朋友的关系怎么样？")
    assert r.level == "safe"


def test_safe_on_empty_message():
    r = check_safety("")
    assert r.level == "safe"


def test_no_false_positive_containing_substring():
    """'想死' 是信号，但普通语境不含这些词的不能误报。"""
    assert check_safety("最近在学习上怎么突破？").level == "safe"


# --- 免责声明 ---

def test_disclaimer_not_empty():
    d = disclaimer_text()
    assert d
    assert "不构成医疗" in d
    assert "仅供自我探索参考" in d


def test_product_facing_knowledge_avoids_fatalistic_medical_predictions():
    """确定性知识文本会绕过 LLM 改写，不能直接输出宿命化/医疗诊断式断语。"""
    root = Path(__file__).resolve().parents[2]
    targets = sorted((root / "domain/astrology/knowledge").rglob("*.yaml"))
    forbidden = re.compile(
        r"注定|一定会|肯定会|逃不掉|无法改变|"
        r"患重病|重疾|癌|诊断|职业病|精神疾病|住院|手术(?!刀)|医疗事故|指导用药|"
        r"短寿|短命|早逝|死于非命|客死他乡|飞来横祸|大凶|克死|死亡|自我毁灭|"
        r"多灾多难|灾祸|厄运缠身|致命打击|牢狱之灾|空难|"
        r"破产|无法修成正果|婚姻不太幸福|躲债|灰产|灰色收入|不正当生意"
    )

    offenders: list[str] = []
    for path in targets:
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.lstrip()
            # Only scan surfaced copy; YAML comments and negative prompt examples are not product output.
            if stripped.startswith("#") or stripped.startswith("never_say:") or stripped.startswith("- never_say:"):
                continue
            if forbidden.search(line):
                offenders.append(f"{path.relative_to(root)}:{line_no}: {line.strip()}")

    assert offenders == []


# --- 端到端：handle_message 短路 ---

def test_handle_message_crisis_short_circuits():
    """危机消息 → 直接返回求助话术，不进入占星管道。"""
    from datetime import datetime, timezone

    from application.agent.runtime import GardenSpiritAgent
    from shared.models import BirthData, GeoLocation, Person

    agent = GardenSpiritAgent()
    person = Person(
        id="p_crisis",
        name="测试",
        birth=BirthData(
            datetime(1990, 6, 15, 9, 30, tzinfo=timezone.utc),
            GeoLocation(31.23, 121.47, timezone_name="Asia/Shanghai", place_name="上海"),
        ),
    )
    answer = agent.handle_message("s1", "我不想活了", person)
    assert "心理援助" in answer
    assert "宫位" not in answer  # 没走占星解读
