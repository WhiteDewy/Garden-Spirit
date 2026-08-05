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

    def __init__(self):
        self.available = True
        self.captured = None

    def chat(self, messages):
        self.captured = messages
        return "转述内容"


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
        _make_conclusion(), intent, PersonaType.ZIRCON, chart
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
        _make_conclusion(), intent, PersonaType.ZIRCON, chart
    )

    user = fake.captured[1]["content"]
    profiles_sec = user.split("行星档案")[1]
    # 截到下一个块标题
    for next_marker in ("盘主本命概要", "飞星证据卡", "领域分析结论"):
        if next_marker in profiles_sec:
            profiles_sec = profiles_sec.split(next_marker)[0]
            break
    assert "- " in profiles_sec, "行星档案块应有条目"


def test_llm_unavailable_falls_back():
    """LLM 不可用 → 降级模板，不崩（chart 可选后仍安全）。"""
    agent = GardenSpiritAgent()

    class _Off:
        available = False

    agent._llm = _Off()

    intent = Intent(id="i", raw_query="我适合换工作吗", domain=IntentDomain.CAREER)
    answer = agent._format_response(
        _make_conclusion(), intent, PersonaType.ZIRCON, None
    )
    assert isinstance(answer, str)
    assert len(answer) > 0
