"""宫位咨询意图流（领域引擎 v2）：裸宫反问 → 切片锁定 → 跨轮消解 → 宫位解读。

用户语：
    "我的3宫怎么样" → 反问该宫涵盖的方面（house_significations.yaml = 唯一事实源）
    "我想问表达"   → 确定性意图判断 → 锁 3宫 + self 域 → 宫位语义场解读

硬线：占星结论全由 Domain 的 HouseSignificationEngine 出，LLM 只叙事。
测试环境 GS_LLM_DISABLE=1（conftest）→ 走降级模板，全链路无 LLM。
"""

from datetime import datetime
import zoneinfo

import pytest

from application.agent import GardenSpiritAgent
from application.conversation.companion import should_use_companion
from domain.reasoning.intent import IntentRouter
from shared.enums import HouseSystem, IntentDomain, PersonaType
from shared.models import BirthData, GeoLocation, Person


@pytest.fixture(scope="module")
def person() -> Person:
    return Person(
        id="p_house_intent",
        name="夏天",
        gender="女",
        birth=BirthData(
            datetime(1991, 3, 21, 9, 25, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(35.7, 113.35, timezone_name="Asia/Shanghai", place_name="山西陵川"),
        ),
        house_system=HouseSystem.ALCABITIUS,
    )


@pytest.fixture(scope="module")
def agent() -> GardenSpiritAgent:
    return GardenSpiritAgent()


def _fh(intent) -> int | None:
    s = intent.get_slot("focus_house")
    return int(s.normalized_value) if s else None


def _fd(intent) -> str | None:
    s = intent.get_slot("focus_domain")
    return s.normalized_value if s else None


def _slot(intent, name: str) -> str | None:
    s = intent.get_slot(name)
    return s.normalized_value if s else None


# -- 路由层：裸宫反问 / 切片锁定 / 领域词 / 别名 / 中文数字 -----------------

def test_bare_house_asks_clarification():
    intent = IntentRouter().route("我的3宫怎么样")
    assert intent.requires_clarification
    assert _fh(intent) == 3
    # 反问列出该宫语义场切片（唯一事实源），由用户自选
    assert "沟通/表达/写作" in intent.clarification_question
    assert "学习/短途/走动" in intent.clarification_question


def test_house_cn_numerals():
    intent = IntentRouter().route("第三宫怎么样")
    assert _fh(intent) == 3
    assert intent.requires_clarification


def test_slice_answer_locks_domain_via_followup():
    """轮1 反问暂存 active_house=3；轮2 回答切片 → 锁域 + 继承宫位。"""
    intent = IntentRouter().route("我想问表达", context={"active_house": 3})
    assert not intent.requires_clarification
    assert _fh(intent) == 3
    assert _fd(intent) == "self"   # 歧义切片优先序：self → learning


def test_rule_plus_house_no_clarification():
    """领域词 + 宫位（"12宫财运"）：规则锁域，宫位作 focus，不反问。"""
    intent = IntentRouter().route("帮我看看12宫财运")
    assert not intent.requires_clarification
    assert _fh(intent) == 12
    assert _fd(intent) == "wealth"


def test_planet_in_house_is_complete_astrology_material():
    """完整配置（行星+落宫）不是裸宫位，不能追问“8宫哪一块”。"""
    intent = IntentRouter().route("月亮在8宫什么意思啊")
    assert not intent.requires_clarification
    assert _slot(intent, "astrology_material") == "planet_in_house"
    assert _slot(intent, "focus_planet") == "moon"
    assert _fh(intent) == 8


def test_planet_in_house_friend_chart_subject():
    """朋友/对方星盘里的行星落宫，是他盘材料上下文，不是用户本盘裸宫。"""
    intent = IntentRouter().route("我有一个朋友的星盘，月亮在8宫")
    assert not intent.requires_clarification
    assert _slot(intent, "astrology_material") == "planet_in_house"
    assert _slot(intent, "focus_planet") == "moon"
    assert _fh(intent) == 8
    assert _slot(intent, "subject") == "friend_chart"


def test_house_slice_alias_taohua():
    """桃花别名 → 5宫恋爱切片 → relationship（不反问恋爱还是创作）。"""
    intent = IntentRouter().route("第五宫桃花")
    assert not intent.requires_clarification
    assert _fh(intent) == 5
    assert intent.domain == IntentDomain.RELATIONSHIP


def test_followup_non_slice_pivots_to_normal_routing():
    """反问后用户转话题（不匹配切片）→ 常规路由，不锁宫位。"""
    intent = IntentRouter().route("我感情怎么样", context={"active_house": 3})
    assert intent.domain == IntentDomain.RELATIONSHIP
    assert _fh(intent) is None


def test_house_intent_not_swallowed_by_companion():
    """宫位引用（focus_house 槽位）→ 走澄清/咨询，不进陪伴兜底。"""
    intent = IntentRouter().route("我的3宫怎么样")
    assert should_use_companion(intent, None) is False


# -- 端到端：澄清 → 切片 → 宫位解读（无 LLM 降级模板） ---------------------

def test_house_clarification_end_to_end(agent, person):
    sid = "house_e2e"
    r1 = agent.handle_message(sid, "我的3宫怎么样", person, PersonaType.MOON)
    assert "你想问的是哪一块" in r1
    ctx = agent.context_builder._sessions[sid]
    assert ctx.pending_focus_house == 3
    assert ctx.to_intent_context()["active_house"] == 3

    r2 = agent.handle_message(sid, "我想问表达", person, PersonaType.MOON)
    assert "沟通/表达" in r2          # 3宫表达切片已出
    assert ctx.latest_conclusion is not None
    assert ctx.latest_conclusion.domain == "self"
    assert ctx.pending_focus_house is None   # 闭环后清理暂存
    assert "不构成医疗" in r2                 # 合规红线


def test_house_reading_is_domain_not_llm(agent, person):
    """硬线：12宫财运的解读来自 HouseSignificationEngine（玄学/暗财切片）。"""
    answer = agent.handle_message("house_dom", "帮我看看12宫财运", person, PersonaType.MOON)
    assert "玄学" in answer or "暗财" in answer


def test_house_reads_each_slice_independently(agent, person):
    """同一个3宫，问"表达"与"出行"各出各的切片，不串味。"""
    a1 = agent.handle_message("hs1", "我是想问3宫的表达", person, PersonaType.MOON)
    a2 = agent.handle_message("hs2", "我是想问3宫的出行", person, PersonaType.MOON)
    assert "沟通/表达" in a1
    assert "学习/短途" in a2
    # self 域只激活表达切片，不甩学习/出行（语义场域过滤）
    assert "学习/短途" not in a1
