"""无 LLM 降级模板测试——回答必须人话，不堆评分/术语。

验证：
- 技术性评分/时机项被过滤（综合评分/净分/时间窗口 不再直出）
- 温暖开场（按判定极性）
- 人文观察保留、时机单独成节
- 免责声明保留（合规红线）
"""

from datetime import datetime, timezone

from shared.enums import ConclusionCategory, EvidencePolarity, IntentDomain, PersonaType
from shared.models import Conclusion, Finding, Intent, TimePeriod

from application.agent.runtime import GardenSpiritAgent


def _make_intent() -> Intent:
    return Intent(id="i1", raw_query="工作压力很大", domain=IntentDomain.CAREER)


def _make_conclusion() -> Conclusion:
    now = datetime.now(timezone.utc)
    return Conclusion(
        id="c1",
        intent_id="i1",
        evidence_set_id="e1",
        domain="career",
        summary="关于career的询问：盘面总体支持，条件有利。",
        findings=[
            Finding(id="f1", category=ConclusionCategory.FINDING,
                    text="职业强度综合评分 20（十宫主土星尊贵分8）",
                    polarity=EvidencePolarity.POSITIVE, confidence=0.9),
            Finding(id="f2", category=ConclusionCategory.FINDING,
                    text="你的情绪有分寸感——冷静、可靠，能扛事也懂得什么时候该收起情绪",
                    polarity=EvidencePolarity.POSITIVE, confidence=0.8),
            Finding(id="f3", category=ConclusionCategory.FINDING,
                    text="时间窗口 2026-09 至 2027-01：行运对年主星火星总体有利（净分+9.4）",
                    polarity=EvidencePolarity.POSITIVE, confidence=0.7),
        ],
        overall_confidence=0.9,
        overall_polarity=EvidencePolarity.POSITIVE,
        time_periods=[
            TimePeriod(label="2026-09 至 2027-01", start=now, end=now,
                       quality=EvidencePolarity.POSITIVE),
        ],
        recommendations=["可积极推进，但仍需结合现实条件做决定。"],
        metadata={"house_system": "placidus", "verdict": "favorable"},
    )


def test_fallback_is_human_not_scoring_report():
    out = GardenSpiritAgent._fallback_template(_make_conclusion(), _make_intent(), PersonaType.MOON)

    # 生硬的评分报告残留不得出现
    assert "总体判断：" not in out
    assert "置信度" not in out
    assert "综合评分" not in out
    assert "净分" not in out
    assert "尊贵分" not in out
    assert "✓" not in out

    # 人话要素
    assert "站在你这边" in out              # 温暖开场（favorable）
    assert "你的情绪有分寸感" in out          # 人文观察保留
    assert "关于时机" in out                # 时机单独成节
    assert "2026-09 至 2027-01" in out
    assert "建议" in out

    # 合规红线
    assert "不构成医疗" in out


def test_fallback_filters_all_scoring_no_raw_dump():
    """全部 finding 都是评分时，不展示观察节、不直出评分文本（宁可没有）。"""
    c = _make_conclusion()
    c.findings = [
        Finding(id="f1", category=ConclusionCategory.FINDING, text="职业强度综合评分 20（尊贵分8）",
                polarity=EvidencePolarity.POSITIVE, confidence=0.9),
        Finding(id="f2", category=ConclusionCategory.FINDING, text="职业风险综合评分 -0.7（凶星相位）",
                polarity=EvidencePolarity.NEGATIVE, confidence=0.8),
    ]
    out = GardenSpiritAgent._fallback_template(c, _make_intent(), PersonaType.MOON)
    assert "综合评分" not in out
    assert "想先和你分享几个观察" not in out
    assert "站在你这边" in out  # 判定开场仍在


def test_fallback_descriptive():
    c = _make_conclusion()
    c.metadata["descriptive"] = True
    out = GardenSpiritAgent._fallback_template(c, _make_intent(), PersonaType.MOON)
    assert "关于时机" not in out  # 描述性解读不展开时机
    assert "不构成医疗" in out


def test_fallback_no_recommendations_gives_way_out():
    """A3 护栏：没有建议也不能留下绝路——兜底一句通用出路。"""
    c = _make_conclusion()
    c.recommendations = []
    out = GardenSpiritAgent._fallback_template(c, _make_intent(), PersonaType.MOON)
    assert "不是死路" in out          # 通用出路
    assert "给出路" not in out        # 不出露"方案元语言"
    assert "不构成医疗" in out


def test_fallback_fatalistic_gets_coda():
    """A3 硬护栏：Domain 产出了致命判决词 → coda 补在免责声明前。"""
    c = _make_conclusion()
    c.summary = "你注定单身，感情这条路没有结果"
    out = GardenSpiritAgent._fallback_template(c, _make_intent(), PersonaType.MOON)
    # 出路收尾在正文，位于免责声明之前
    assert "不过，这都不是判决" in out
    assert out.index("不过，这都不是判决") < out.index("不构成医疗")
    assert "不是绝路" in out
