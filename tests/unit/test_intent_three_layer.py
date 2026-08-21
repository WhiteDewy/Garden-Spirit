"""三层意图 prompt 测试（对话模式感知，领域引擎 v2 意图层升级）。

验证：
- DEEP：上下文注入（对话历史 + 活跃宫位）+ 富输出解析
  （intent_type/focus_house/focus_slice/deep_dive）+ 切片→领域由 Domain 权威化
  （LLM 猜领域被 signification 表覆盖）。
- QUICK：收敛规则 prompt（不深挖、不宫位反问）。
- FREE：非占星 → Daily.Chat（陪伴管线）；占星 → DEEP 继续分类。
- 宫位优先：有宫位引用时确定性路由永远先于 LLM（硬线：语义场=唯一事实源）。
- 端到端：深挖追问（"怎么个暗财"）→ 证据链展开 + 验证问句；确认轮收敛。

测试环境 GS_LLM_DISABLE=1（conftest），注入 fake LLM 单独覆盖 LLM 路径。
"""

from datetime import datetime
import zoneinfo

import pytest

from application.agent import GardenSpiritAgent
from application.agent.intent_parser import IntentParser, _build_context_block
from shared.enums import ConsultMode, HouseSystem, IntentDomain, PersonaType
from shared.models import BirthData, GeoLocation, Person


@pytest.fixture(scope="module")
def person() -> Person:
    return Person(
        id="p_three_layer",
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


class FakeClassifyLLM:
    """有 classify_intent 的假 LLM（可捕获 system prompt / 按队列返回）。"""

    available = True

    def __init__(self, results=None):
        self._results = list(results or [{}])
        self.calls: list[str] = []  # 每次调用的 system prompt

    def classify_intent(self, system_prompt, message):
        self.calls.append(system_prompt)
        return self._results[min(len(self._results) - 1, len(self.calls) - 1)]

    def extract_slots(self, system_prompt, message):
        return {}


def _build_agent() -> GardenSpiritAgent:
    return GardenSpiritAgent()


# ---------------------------------------------------------------------------
# 上下文块注入
# ---------------------------------------------------------------------------

def test_context_block_mentions_history_and_house():
    block = _build_context_block({
        "recent_turns": [
            {"user": "帮我看看12宫财运", "assistant": "你12宫最醒目的是「暗财/偏财/隐性收入」…"},
        ],
        "active_house": 12,
        "active_domain": "wealth",
    })
    assert "对话历史" in block
    assert "帮我看看12宫财运" in block
    assert "活跃宫位：第12宫" in block
    assert "活跃领域：wealth" in block


def test_context_block_empty():
    block = _build_context_block({})
    assert "第一轮" in block


# ---------------------------------------------------------------------------
# DEEP：富输出解析 + 领域权威化
# ---------------------------------------------------------------------------

def test_deep_rich_output_parsed():
    """深挖追问富输出 → intent 新字段全部挂载 + focus_house 槽位。"""
    parser = IntentParser(llm_client=FakeClassifyLLM([{
        "intent_type": "follow_up_deep_dive",
        "domain": "wealth",
        "subdomain": "",
        "focus_house": 12,
        "focus_slice": "暗财/偏财/隐性收入",
        "deep_dive": True,
        "confirmed": None,
        "confidence": 0.9,
        "needs_clarification": False,
    }]))
    intent = parser.parse("怎么个暗财")
    assert intent.intent_type == "follow_up_deep_dive"
    assert intent.deep_dive is True
    assert intent.focus_slice is not None
    assert int(intent.get_slot("focus_house").normalized_value) == 12


def test_slice_domain_overrides_llm_guess():
    """LLM 猜 learning，但 3宫"表达"切片的领域由 signification 表权威化为 self。"""
    parser = IntentParser(llm_client=FakeClassifyLLM([{
        "intent_type": "clarification_response",
        "domain": "learning",          # LLM 猜错了
        "focus_house": 3,
        "focus_slice": "表达",
        "deep_dive": False,
        "confidence": 0.8,
        "needs_clarification": False,
    }]))
    intent = parser.parse("我是想问3宫的表达")
    assert intent.domain == IntentDomain.SELF   # 切片优先序 self → learning
    fd = intent.get_slot("focus_domain")
    assert fd is not None and fd.normalized_value == "self"


def test_deep_prompt_injects_context_and_house_table():
    """DEEP 模式 system prompt 含对话上下文 + 12 宫语义场表。"""
    fake = FakeClassifyLLM([{"domain": "career", "confidence": 0.9}])
    parser = IntentParser(llm_client=fake)
    parser.parse("我想表达一下", context={"active_house": 12, "recent_turns": []})
    sys = fake.calls[0]
    assert "对话上下文" in sys
    assert "第12宫" in sys          # 宫位语义场表已注入
    assert "follow_up_deep_dive" in sys   # 意图模式定义
    assert "intent_type" in sys


# ---------------------------------------------------------------------------
# QUICK：收敛规则
# ---------------------------------------------------------------------------

def test_quick_prompt_has_convergence_rules():
    fake = FakeClassifyLLM([{"domain": "career", "confidence": 0.9}])
    parser = IntentParser(llm_client=fake)
    parser.parse("怎么个换法", mode=ConsultMode.QUICK)
    sys = fake.calls[0]
    assert "快速咨询模式特殊规则" in sys
    assert "deep_dive 始终为 false" in sys


def test_quick_bare_house_still_rules_first():
    """快速模式也不推翻确定性宫位路由：裸宫 → 反问，LLM 不接管。"""
    parser = IntentParser(llm_client=FakeClassifyLLM([{"domain": "daily"}]))
    intent = parser.parse("我的3宫怎么样", mode=ConsultMode.QUICK)
    assert intent.requires_clarification
    assert int(intent.get_slot("focus_house").normalized_value) == 3


# ---------------------------------------------------------------------------
# FREE：是否聊占星
# ---------------------------------------------------------------------------

def test_free_non_astrology_goes_chat():
    """FREE 模式非占星 → Daily.Chat（陪伴管线）。"""
    fake = FakeClassifyLLM([{
        "is_astrology_question": False, "topic": "电影",
        "emotion_hint": "calm", "reasoning": "分享电影",
    }])
    parser = IntentParser(llm_client=fake)
    intent = parser.parse("刚看了一部电影", mode=ConsultMode.FREE)
    assert intent.domain == IntentDomain.DAILY
    assert intent.subdomain == "Chat"
    assert intent.intent_type == "chat"


def test_free_astrology_delegates_to_deep():
    """FREE 模式聊占星 → 用 DEEP 模板二次分类。"""
    fake = FakeClassifyLLM([
        {"is_astrology_question": True, "reasoning": "想解盘"},
        {"intent_type": "new_question", "domain": "wealth",
         "focus_house": 2, "confidence": 0.85, "needs_clarification": False},
    ])
    parser = IntentParser(llm_client=fake)
    intent = parser.parse("对了帮我看看财运", mode=ConsultMode.FREE)
    assert intent.domain == IntentDomain.WEALTH
    assert len(fake.calls) == 2          # FREE 判定 + DEEP 分类各一次
    assert "2宫" in fake.calls[1]        # 第二次用 DEEP 模板（含宫位表）


# ---------------------------------------------------------------------------
# 宫位优先：确定性路由永远先于 LLM
# ---------------------------------------------------------------------------

def test_house_always_routes_deterministically():
    """即使 LLM 会误判，"我的3宫怎么样"也走规则反问，不吞进 LLM 分类。"""
    parser = IntentParser(llm_client=FakeClassifyLLM([{"domain": "daily"}]))
    intent = parser.parse("我的3宫怎么样")
    assert intent.requires_clarification
    assert int(intent.get_slot("focus_house").normalized_value) == 3
    assert "你想问的是哪一块" in intent.clarification_question


def test_planet_in_house_routes_as_complete_material_before_llm():
    """行星落宫是完整占星材料，不应被“X宫”裸宫反问截走。"""
    llm = FakeClassifyLLM([{"domain": "daily"}])
    parser = IntentParser(llm_client=llm)
    intent = parser.parse("月亮在8宫什么意思啊")
    assert not intent.requires_clarification
    assert intent.get_slot("astrology_material").normalized_value == "planet_in_house"
    assert intent.get_slot("focus_planet").normalized_value == "moon"
    assert int(intent.get_slot("focus_house").normalized_value) == 8
    assert llm.calls == []


# ---------------------------------------------------------------------------
# 端到端：深挖证据链 → 验证问句 → 确认收敛（离线 + fake LLM 驱动富输出）
# ---------------------------------------------------------------------------

def _deep_fake():
    """深挖轮：识别"怎么个暗财"为 follow_up_deep_dive。"""
    return FakeClassifyLLM([{
        "intent_type": "follow_up_deep_dive",
        "domain": "wealth",
        "focus_house": 12,
        "focus_slice": "暗财/偏财/隐性收入",
        "deep_dive": True,
        "confidence": 0.9,
        "needs_clarification": False,
    }])


def test_deep_dive_expands_mechanism_and_asks_verification(agent, person):
    """轮1 12宫财运浅读 → 轮2"怎么个暗财"深挖：证据链展开 + 验证问句。"""
    # 轮1：离线规则出 12宫财运浅读
    r1 = agent.handle_message("dive_e2e", "帮我看看12宫财运", person, PersonaType.MOON)
    assert "玄学" in r1 or "暗财" in r1

    # 轮2：注入 fake LLM 驱动深挖富输出
    agent.intent_parser._llm = _deep_fake()
    r2 = agent.handle_message("dive_e2e", "怎么个暗财", person, PersonaType.MOON)
    ctx = agent.context_builder._sessions["dive_e2e"]
    # 验证问句被追加（机制验证，引导用户确认）
    assert "验证一下" in r2 or "副业" in r2 or "玄学" in r2
    # 深挖暂存已写入（下一轮确认收敛用）
    assert ctx.pending_house_verify is not None
    assert ctx.pending_house_verify[0] == 12
    assert ctx.pending_house_verify[1] == "wealth"


def test_confirmation_converges_mechanism(agent, person):
    """轮3 用户确认 → 收敛机制结论（坐实），不再重复展开。"""
    agent.handle_message("conf_e2e", "帮我看看12宫财运", person, PersonaType.MOON)
    agent.intent_parser._llm = _deep_fake()
    agent.handle_message("conf_e2e", "怎么个暗财", person, PersonaType.MOON)

    # 确认轮：fake LLM 只认 confirmation + confirmed=true，不重复宫位
    agent.intent_parser._llm = FakeClassifyLLM([{
        "intent_type": "confirmation", "confirmed": True,
        "confidence": 0.9, "needs_clarification": False,
    }])
    r3 = agent.handle_message("conf_e2e", "对，就是有副业", person, PersonaType.MOON)
    ctx = agent.context_builder._sessions["conf_e2e"]
    assert "确认了" in r3
    assert "坐实" in r3
    assert ctx.pending_house_verify is None   # 收敛后清理暂存


def test_confirmation_denial_turns_to_tendency(agent, person):
    """用户否认 → 收敛为"倾向"而非坐实。"""
    agent.handle_message("deny_e2e", "帮我看看12宫财运", person, PersonaType.MOON)
    agent.intent_parser._llm = _deep_fake()
    agent.handle_message("deny_e2e", "怎么个暗财", person, PersonaType.MOON)
    agent.intent_parser._llm = FakeClassifyLLM([{
        "intent_type": "confirmation", "confirmed": False,
        "confidence": 0.9, "needs_clarification": False,
    }])
    r3 = agent.handle_message("deny_e2e", "没有，我没这些", person, PersonaType.MOON)
    assert "否了" in r3
    assert "倾向" in r3


def test_confirmation_offline_rules_fallback(agent, person):
    """LLM 关闭时确认轮也走通：验证问句后"对，就是有副业"→ 坐实收敛，不再重读。"""
    agent.handle_message("off_conf", "帮我看看12宫财运", person, PersonaType.MOON)
    agent.intent_parser._llm = _deep_fake()
    agent.handle_message("off_conf", "怎么个暗财", person, PersonaType.MOON)
    # 恢复离线（LLM 不可用）→ 确认走规则兜底（pending_house_verify + 短句命中）
    agent.intent_parser._llm = None
    r3 = agent.handle_message("off_conf", "对，就是有副业", person, PersonaType.MOON)
    assert "确认了" in r3
    assert "坐实" in r3
    ctx = agent.context_builder._sessions["off_conf"]
    assert ctx.pending_house_verify is None   # 收敛后清理


def test_non_confirm_not_swallowed_offline(agent, person):
    """验证问句后用户没接确认话头（正常追问）→ 不被误判为 confirmation。"""
    agent.handle_message("nc_e2e", "帮我看看12宫财运", person, PersonaType.MOON)
    agent.intent_parser._llm = _deep_fake()
    agent.handle_message("nc_e2e", "怎么个暗财", person, PersonaType.MOON)
    agent.intent_parser._llm = None
    # 超过 20 字的正常句子 + 无确认词 → 走常规路由，不收敛
    r3 = agent.handle_message("nc_e2e", "那这个暗财和我今年学玄学有关系吗", person, PersonaType.MOON)
    assert "确认了" not in r3
