"""对话质量评测集 · pytest 入口。

跑全部场景，逐条打标，全绿才通过（回归门禁）。
失败时会打印每个场景哪条质量检查坏了——改对话行为时用它当罗盘。

直接跑：pytest tests/quality/test_dialogue_quality.py -v
只看报告不 gate：python tests/quality/dialogue_cases.py
"""

import sys

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Windows 默认 GBK 控制台打不出 ✔/✗ → 统一换行输出，避免报错掩盖真正的断言失败
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):  # pragma: no cover - 非 UTF-8 环境/无 reconfigure
    pass

import pytest

from shared.models import BirthData, GeoLocation, Person

from application.agent import GardenSpiritAgent

from tests.quality.dialogue_cases import DIALOGUE_CASES, evaluate_case


def _make_person() -> Person:
    return Person(
        id="p_eval",
        name="评测用户",
        birth=BirthData(
            datetime(1990, 6, 15, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
            GeoLocation(31.2304, 121.4737, timezone_name="Asia/Shanghai", place_name="上海"),
        ),
    )


def test_all_dialogue_cases_pass():
    """质量契约：所有场景必须通过（一条失败 = 一个对话质量标准被破坏）。"""
    agent = GardenSpiritAgent()
    failures = []

    for i, case in enumerate(DIALOGUE_CASES):
        result = evaluate_case(agent, _make_person(), case, session_id=f"eval_{i}")
        if not result.passed:
            failures.append(result)
            detail = "\n".join(
                f"    [FAIL] {c.name}: {c.detail}" for c in result.failed_checks()
            )
            print(f"\n场景「{result.name}」未通过：\n{detail}")

    passed = len(DIALOGUE_CASES) - len(failures)
    print(f"\n对话质量评测：{passed}/{len(DIALOGUE_CASES)} 场景通过")
    assert not failures, f"{len(failures)} 个场景未通过质量契约"


def test_eval_cases_are_wellformed():
    """评测集自身的完整性：场景有名字、有意图说明、轨道合法。"""
    valid_tracks = {"companion", "consult", "greeting", "safety", "meta"}
    for case in DIALOGUE_CASES:
        assert case.name, "场景必须有名字"
        assert case.turns, f"场景 {case.name} 必须有消息"
        assert case.expect.track in valid_tracks, (
            f"场景 {case.name} 的轨道 {case.expect.track} 不合法"
        )
