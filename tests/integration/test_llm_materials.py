"""集成测试：LLM 转述素材全链路接通。

验证 runtime._format_response 在 LLM 可用时，把四块数据都传给 LLM：
结论（永远有）+ 行星档案 + 本命概要 + 飞星证据卡。

背景：evidence_cards/natal/planet_profiles 此前已建成但 runtime 从未接通，
且 _planet_profiles_for 曾以无参方式调用 read_all_planets() 导致档案静默丢失。
本测试锁定这些断线点。
"""

from datetime import datetime
import zoneinfo

from application.agent.runtime import GardenSpiritAgent
from domain.astrology.calculation import NatalChartCalculator
from shared.enums import HouseSystem, IntentDomain, PersonaType
from shared.models import BirthData, Conclusion, Finding, GeoLocation, Person
from shared.models.intent import Intent
from shared.enums import EvidencePolarity


class _FakeLLM:
    """捕获实际发给 LLM 的 messages。"""

    def __init__(self, reply: str = "转述内容"):
        self.available = True
        self.captured = None
        self._reply = reply

    def chat(self, messages):
        self.captured = messages
        return self._reply


def _make_person() -> Person:
    return Person(
        id="x",
        name="x",
        gender="F",
        birth=BirthData(
            datetime(1991, 3, 21, 9, 25, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(35.7, 113.35, timezone_name="Asia/Shanghai", place_name="lingchuan"),
        ),
        house_system=HouseSystem.ALCABITIUS,
    )


def _make_conclusion() -> Conclusion:
    return Conclusion(
        id="c",
        intent_id="i",
        evidence_set_id="e",
        domain="career",
        summary="盘面总体支持，条件有利。",
        overall_confidence=0.8,
        overall_polarity=EvidencePolarity.POSITIVE,
        findings=[
            Finding(
                id="f1",
                category="FINDING",
                text="6宫主金星飞入10宫，职业技能可转化为事业成就",
                polarity=EvidencePolarity.POSITIVE,
                confidence=0.8,
            )
        ],
    )


def test_llm_receives_all_four_materials():
    """接通后：结论 + 行星档案 + 本命概要 + 飞星证据卡全部进 LLM 消息。"""
    agent = GardenSpiritAgent()
    fake = _FakeLLM()
    agent._llm = fake

    chart = NatalChartCalculator().compute(_make_person())
    intent = Intent(id="i", raw_query="我适合换工作吗", domain=IntentDomain.CAREER)
    agent._format_response(
        _make_conclusion(), intent, PersonaType.MOON, chart
    )

    assert fake.captured is not None, "LLM 应被调用"
    user = fake.captured[1]["content"]

    # 四块素材都在
    assert "行星档案" in user
    assert "盘主本命概要" in user
    assert "飞星证据卡" in user
    assert "领域分析结论" in user


def test_planet_profiles_actually_present():
    """行星档案块非空（曾因无参调用 read_all_planets 而静默丢失）。"""
    agent = GardenSpiritAgent()
    fake = _FakeLLM()
    agent._llm = fake

    chart = NatalChartCalculator().compute(_make_person())
    intent = Intent(id="i", raw_query="我适合换工作吗", domain=IntentDomain.CAREER)
    agent._format_response(
        _make_conclusion(), intent, PersonaType.MOON, chart
    )

    user = fake.captured[1]["content"]
    profiles_sec = user.split("行星档案")[1]
    # 截到下一个块标题
    for next_marker in ("盘主本命概要", "飞星证据卡", "领域分析结论"):
        if next_marker in profiles_sec:
            profiles_sec = profiles_sec.split(next_marker)[0]
            break
    assert "- " in profiles_sec, "行星档案块应有条目"


def test_llm_receives_report_entry_context_as_non_conclusion():
    """runtime 把 Intent.entry_* 入口上下文传进 LLM prompt，且不把它当结论。"""
    agent = GardenSpiritAgent()
    fake = _FakeLLM()
    agent._llm = fake

    chart = NatalChartCalculator().compute(_make_person())
    intent = Intent(id="i", raw_query="从报告继续看事业", domain=IntentDomain.CAREER)
    intent.entry_source = "observatory"
    intent.entry_topic_key = "career"
    intent.entry_primary_topic = "career"
    intent.entry_secondary_topics = ["wealth", "growth"]
    intent.entry_intent_shape = "cross_topic_influence"
    intent.entry_report_type = "annual"
    intent.entry_user_focus_text = "想知道事业变化会不会影响收入。"

    agent._format_response(
        _make_conclusion(), intent, PersonaType.MOON, chart
    )

    user = fake.captured[1]["content"]
    assert "报告入口上下文" in user
    assert "来源：observatory" in user
    assert "入口主题：career" in user
    assert "次主题：wealth、growth" in user
    assert "不是占星结论" in user
    assert "领域分析结论" in user


def test_llm_unavailable_falls_back():
    """LLM 不可用 → 降级模板，不崩（chart 可选后仍安全）。"""
    agent = GardenSpiritAgent()

    class _Off:
        available = False

    agent._llm = _Off()

    intent = Intent(id="i", raw_query="我适合换工作吗", domain=IntentDomain.CAREER)
    answer = agent._format_response(
        _make_conclusion(), intent, PersonaType.MOON, None
    )
    assert isinstance(answer, str)
    assert len(answer) > 0


def test_format_response_llm_path_adds_medical_boundary_once():
    """LLM 路径：用户问题触及医疗红线时，wrapper 统一补专业边界且只补一次。"""
    agent = GardenSpiritAgent()
    fake = _FakeLLM("星盘可以看压力节奏，但不能替你决定停药。")
    agent._llm = fake

    intent = Intent(id="i", raw_query="我该不该停药？", domain=IntentDomain.HEALTH)
    answer = agent._format_response(_make_conclusion(), intent, PersonaType.MOON, None)

    assert "健康和身体问题要以医生诊断为准" in answer
    assert answer.count("健康和身体问题要以医生诊断为准") == 1


def test_format_response_fallback_medical_boundary_is_idempotent():
    """fallback 已在免责声明前补 coda；外层 wrapper 不得再因 raw_query 追加第二次。"""
    agent = GardenSpiritAgent()

    class _Off:
        available = False

    agent._llm = _Off()
    intent = Intent(id="i", raw_query="星盘能看我该不该停药吗？", domain=IntentDomain.HEALTH)
    conclusion = _make_conclusion()
    conclusion.summary = "星盘显示你需要重新评估吃药和治疗方案"

    answer = agent._format_response(conclusion, intent, PersonaType.MOON, None)

    assert "健康和身体问题要以医生诊断为准" in answer
    assert answer.count("健康和身体问题要以医生诊断为准") == 1
    assert answer.index("健康和身体问题要以医生诊断为准") < answer.index("不构成医疗")
