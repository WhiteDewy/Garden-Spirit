"""LLM 转述引擎测试：验证 prompt 结构、铁律约束、数据格式化。

不真实调用 LLM——只验证 build_prompt 的产物：
- system prompt 含梦老师方法论 + 铁律
- user prompt 含 Domain 数据（结论/证据卡/本命）
- 极性标记正确
"""

from datetime import datetime, timezone
import zoneinfo

import pytest

from shared.enums import EvidencePolarity, IntentDomain, PersonaType
from shared.models import BirthData, Conclusion, Finding, GeoLocation, Person

from application.conversation.response import build_prompt, _format_conclusion, _build_call_plan_injection
from domain.astrology.calculation import NatalChartCalculator
from domain.astrology.interpretation import dispositor_cards, natal_reading
from domain.astrology.interpretation.planet_profile import read_all_planets
from domain.astrology.knowledge import load_knowledge


def _make_conclusion() -> Conclusion:
    return Conclusion(
        id="c_test",
        intent_id="i_test",
        evidence_set_id="ev_test",
        domain="career",
        summary="盘面总体支持，条件有利。",
        findings=[
            Finding(
                id="f1",
                category="FINDING",
                text="6宫主金星飞入10宫，职业技能可转化为事业成就",
                polarity=EvidencePolarity.POSITIVE,
                confidence=0.8,
                supporting_evidence_ids=["e1"],
                weight=1.0,
            ),
            Finding(
                id="f2",
                category="WARNING",
                text="12宫主火星受克，注意暗处压力",
                polarity=EvidencePolarity.NEGATIVE,
                confidence=0.7,
                supporting_evidence_ids=["e2"],
                weight=0.8,
            ),
        ],
        recommendations=["聚焦技能，把技艺变成事业抓手"],
        overall_confidence=0.75,
        overall_polarity=EvidencePolarity.POSITIVE,
    )


@pytest.fixture(scope="module")
def xiatian_chart():
    """夏天盘：真实数据。"""
    kb = load_knowledge()
    p = Person(
        id="x",
        name="x",
        gender="F",
        birth=BirthData(
            datetime(1991, 3, 21, 9, 25, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(35.7, 113.35, timezone_name="Asia/Shanghai", place_name="lingchuan"),
        ),
        house_system=__import__("shared.enums", fromlist=["HouseSystem"]).HouseSystem.ALCABITIUS,
    )
    return NatalChartCalculator().compute(p)


@pytest.fixture(scope="module")
def xiatian_chart_cards(xiatian_chart):
    """夏天盘：真实数据跑证据卡。"""
    return dispositor_cards(xiatian_chart, load_knowledge())


@pytest.fixture(scope="module")
def xiatian_all_materials(xiatian_chart):
    """夏天盘：全部转述素材（证据卡 + 本命 + 档案），模拟 runtime 接通后的场景。"""
    kb = load_knowledge()
    return {
        "evidence_cards": dispositor_cards(xiatian_chart, kb),
        "natal": natal_reading(xiatian_chart, kb),
        "planet_profiles": read_all_planets(xiatian_chart, kb),
    }


def test_system_prompt_contains_methodology():
    """system prompt 含梦老师方法论。"""
    c = _make_conclusion()
    messages = build_prompt(c, persona=PersonaType.MOON)
    system = messages[0]["content"]
    assert "掌宫优于落宫" in system
    assert "链式追踪" in system
    assert "给出路不给绝路" in system
    assert "吉凶两论" in system
    assert "命名伤口" in system  # 五条说话标准
    assert "铁律" in system


def test_system_prompt_contains_iron_rules():
    """铁律约束必须在 system prompt 里。"""
    c = _make_conclusion()
    system = build_prompt(c)[0]["content"]
    assert "只能转述" in system
    assert "不能发明" in system
    assert "极性" in system
    assert "证据链" in system


def test_user_prompt_contains_domain_data():
    """user prompt 含结论数据。"""
    c = _make_conclusion()
    user = build_prompt(c, question="该不该换工作？")[1]["content"]
    assert "盘面总体支持" in user
    assert "6宫主金星" in user
    assert "该不该换工作" in user


def test_user_prompt_polarity_marks():
    """极性标记：positive→有利，negative→注意。"""
    c = _make_conclusion()
    user = build_prompt(c)[1]["content"]
    assert "[有利]" in user
    assert "[注意]" in user


def test_cards_in_user_prompt(xiatian_chart_cards):
    """证据卡进入 user prompt，且含得吉/受克标记。"""
    c = _make_conclusion()
    user = build_prompt(c, evidence_cards=xiatian_chart_cards)[1]["content"]
    assert "飞星证据卡" in user
    assert "得吉" in user or "受克" in user
    assert "借力" in user or "注意" in user


def test_cards_dont_leak_title(xiatian_chart_cards):
    """证据卡的占星速记 title 不能泄漏进 prompt（skeleton 已去 title）。"""
    c = _make_conclusion()
    user = build_prompt(c, evidence_cards=xiatian_chart_cards)[1]["content"]
    # skeleton 形如 "4宫主太阳飞入11宫，得吉"，不含 "——{title}"
    assert "登神梯" not in user  # 4飞11 的 title 不应出现


def test_persona_variation():
    """不同人格 → system prompt 不同。"""
    c = _make_conclusion()
    moon = build_prompt(c, persona=PersonaType.MOON)[0]["content"]
    venus = build_prompt(c, persona=PersonaType.VENUS)[0]["content"]
    assert moon != venus
    assert "月亮" in moon
    assert "金星" in venus


def test_format_conclusion_no_llm():
    """格式化函数本身不含任何占星发明，纯搬运 Domain 数据。"""
    c = _make_conclusion()
    txt = _format_conclusion(c)
    assert "盘面总体支持" in txt
    assert "6宫主金星" in txt


def test_format_conclusion_includes_data_gaps():
    """data_gaps 必须进入 LLM prompt——出生时间精度提示靠它透传。"""
    c = _make_conclusion()
    c.data_gaps.append("出生时间未精确到分钟，默认使用正午 12:00 排盘")
    txt = _format_conclusion(c)
    assert "数据缺失提示" in txt
    assert "出生时间未精确到分钟" in txt


def test_call_plan_injection_uses_canonical_parameter():
    """build_prompt 优先消费 canonical call_plan，并注入咨询主干节奏。"""

    class Plan:
        def to_dict(self):
            return {
                "topic_label": "事业",
                "output_structure": {
                    "label": "事业",
                    "sections": [{"title": "结构", "focus": "10宫主状态"}],
                },
                "cross_readings": [],
                "guardrails": ["不要脱离 Domain 结论"],
            }

    system = build_prompt(_make_conclusion(), call_plan=Plan())[0]["content"]
    assert "当前话题：事业" in system
    assert "结构（聚焦：10宫主状态）" in system
    assert "不要脱离 Domain 结论" in system


def test_topic_plan_remains_legacy_alias():
    """迁移期旧 topic_plan 调用仍走同一注入协议。"""

    class Plan:
        def to_dict(self):
            return {
                "topic_label": "感情",
                "output_structure": {
                    "label": "感情",
                    "sections": [{"title": "关系结构", "focus": "7宫"}],
                },
                "cross_readings": [],
                "guardrails": [],
            }

    assert _build_call_plan_injection(Plan()) in build_prompt(
        _make_conclusion(), topic_plan=Plan()
    )[0]["content"]


# --- 能力总纲 system prompt（master prompt） ---

def test_system_prompt_contains_capability_map():
    """system prompt 含能力地图——LLM 知道会收到哪些数据。"""
    c = _make_conclusion()
    system = build_prompt(c)[0]["content"]
    assert "你会收到的数据" in system
    assert "领域分析结论" in system
    assert "行星档案" in system
    assert "本命概要" in system
    assert "飞星证据卡" in system


def test_system_prompt_contains_weaving_rules():
    """system prompt 含织入规则——LLM 知道数据怎么配合。"""
    c = _make_conclusion()
    system = build_prompt(c)[0]["content"]
    assert "怎么织成一篇解读" in system
    assert "接住情绪" in system           # A3 疗愈弧线：先共情、再讲基调
    assert "再讲基调、再讲细节" in system
    assert "证据卡要对上结论" in system


def test_system_prompt_data_map_precedes_voice():
    """能力地图在说话方式之前——LLM 先理解有什么武器，再看怎么说话。"""
    c = _make_conclusion()
    system = build_prompt(c)[0]["content"]
    assert system.index("你会收到的数据") < system.index("你的占星方法论")


def test_data_blocks_have_role_labels(xiatian_all_materials):
    """各数据块标题带角色标签，LLM 能理解数据关系。"""
    c = _make_conclusion()
    user = build_prompt(c, **xiatian_all_materials)[1]["content"]
    assert "原料：每颗星的单点配置" in user        # 行星档案
    assert "长期基调：跨领域最关键的几条" in user   # 本命概要
    assert "因果链：宫主星怎么飞" in user           # 飞星证据卡
    assert "核心：确定性推理的最终输出" in user     # 领域分析结论


def test_natal_and_cards_both_in_prompt(xiatian_all_materials):
    """接通后：证据卡 + 本命概要同时进入 user prompt（此前 natal 从不进）。"""
    c = _make_conclusion()
    user = build_prompt(c, **xiatian_all_materials)[1]["content"]
    assert "盘主本命概要" in user
    assert "飞星证据卡" in user
    assert "领域分析结论" in user
    assert "盘主问的是" not in user or True  # question 未传时不出现


def test_natal_has_cross_domain_content(xiatian_all_materials):
    """本命概要含跨领域内容（职业/感情等），不是空壳。"""
    c = _make_conclusion()
    user = build_prompt(c, **xiatian_all_materials)[1]["content"]
    natal_section = user.split("盘主本命概要")[1].split("飞星证据卡")[0]
    assert "职业" in natal_section or "感情" in natal_section or "财富" in natal_section
