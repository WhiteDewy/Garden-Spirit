"""落款推导链测试（self_map_design §6.2）—— 内容 → 情绪需求 → 疗愈名。

验证：
- 10 情绪需求 ↔ 10 星灵一一对应；疗愈名签名表完整
- 映射规则（确定性，无 LLM）：主信号 → 落款星灵；次信号 → 灵魂碎片
- 灵魂碎片去重、限 6 个
- LLM 识别：受控枚举（发明需求丢弃）、次需求限 2
- 规则兜底：关键词命中 → 主/次需求（离线可测）
- 判断不出 → 默认"先接住"（soothed → 月亮）
- explain：显式可解释（§6.2 不能是黑箱）
- LetterService.context_letter：keepsake 来信，正文=完整回复，落款用疗愈名，
  灵魂碎片作脚注（推导碎片 ∪ 当天随聊点亮），metadata 留推导过程
"""

import json

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from shared.enums import Planet
from shared.models import BirthData, GeoLocation, Person

from application.mailbox.letter_service import LetterService
from application.mailbox.signature import (
    HEALING_NAMES,
    MAX_SECONDARY,
    EmotionalNeed,
    LetterSignature,
    NeedClassifier,
)


class FakeNeedLLM:
    """有 complete() 的假 LLM——返回主/次需求 JSON。"""

    available = True

    def __init__(self, primary: str, secondary: list[str]):
        self._primary = primary
        self._secondary = secondary

    def complete(self, prompt, system=None, **kwargs):
        return json.dumps({"primary": self._primary, "secondary": self._secondary})


def _make_person() -> Person:
    return Person(
        id="p_sig",
        name="落款测试",
        birth=BirthData(
            datetime(1990, 6, 15, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
            GeoLocation(31.2304, 121.4737, timezone_name="Asia/Shanghai", place_name="上海"),
        ),
    )


# ---------------------------------------------------------------------------
# 目录：10 需求 ↔ 10 星灵
# ---------------------------------------------------------------------------


def test_ten_needs_map_to_ten_planets():
    """每个情绪需求对应一颗星灵；需求数 = 10。"""
    needs = list(EmotionalNeed)
    assert len(needs) == 10
    sig = LetterSignature.from_needs(needs[0])
    # 每个需求都应有映射（from_needs 会取 _NEED_TO_PLANET）
    for need in needs:
        s = LetterSignature.from_needs(need)
        assert s.planet in Planet and s.healing_name


def test_healing_names_covers_all_ten_planets():
    names = HEALING_NAMES
    ten = {Planet.SUN, Planet.MOON, Planet.MERCURY, Planet.VENUS, Planet.MARS,
           Planet.JUPITER, Planet.SATURN, Planet.URANUS, Planet.NEPTUNE, Planet.PLUTO}
    assert set(names) == ten
    assert names[Planet.MOON] == "想被抱抱的我"
    assert names[Planet.SUN] == "想被看见的我"


# ---------------------------------------------------------------------------
# 映射规则（§6.2 判别规则：主→落款，次→碎片）
# ---------------------------------------------------------------------------


def test_primary_need_sets_signature():
    sig = LetterSignature.from_needs(EmotionalNeed.SOOTHED)
    assert sig.planet == Planet.MOON
    assert sig.healing_name == "想被抱抱的我"
    assert sig.soul_fragments == ()


def test_secondary_needs_become_soul_fragments():
    """次信号不掉落款，掉进灵魂碎片（行星子类 + 星座子类）。"""
    sig = LetterSignature.from_needs(EmotionalNeed.SOOTHED, (EmotionalNeed.DREAM,))
    assert sig.planet == Planet.MOON          # 主信号定落款
    assert sig.soul_fragments == ("neptune_dream", "pisces_sea")


def test_multiple_secondary_needs_union_fragments():
    sig = LetterSignature.from_needs(
        EmotionalNeed.SEEN,
        (EmotionalNeed.DREAM, EmotionalNeed.SOAR),
    )
    assert sig.soul_fragments == (
        "neptune_dream", "pisces_sea", "jupiter_faith", "sagittarius_arrow",
    )


def test_secondary_fragments_deduplicated():
    """两个次需求共享子类 → 去重（不重复点亮）。"""
    sig = LetterSignature.from_needs(
        EmotionalNeed.ACT,
        (EmotionalNeed.DREAM, EmotionalNeed.DIG),
    )
    assert len(sig.soul_fragments) == len(set(sig.soul_fragments))


# ---------------------------------------------------------------------------
# LLM 识别（受控枚举）
# ---------------------------------------------------------------------------


def test_llm_classify_primary_and_secondary():
    c = NeedClassifier(FakeNeedLLM("soothed", ["soar"]))
    sig = c.classify("内容")
    assert sig.primary_need == EmotionalNeed.SOOTHED
    assert sig.secondary_needs == (EmotionalNeed.SOAR,)
    assert sig.planet == Planet.MOON
    assert sig.healing_name == "想被抱抱的我"


def test_llm_classify_drops_invented_primary():
    """LLM 发明主需求 → 不信它，规则兜底。"""
    c = NeedClassifier(FakeNeedLLM("bogus_need", []))
    sig = c.classify("今天好累，撑不住了")
    assert sig.primary_need == EmotionalNeed.SOOTHED   # 规则兜底结果


def test_llm_classify_drops_invented_secondary():
    """发明/重复的次需求 → 丢弃；次需求与主需求同值 → 丢弃。"""
    c = NeedClassifier(FakeNeedLLM("soothed", ["bogus", "soothed", "soar", "dream"]))
    sig = c.classify("内容")
    assert sig.secondary_needs == (EmotionalNeed.SOAR, EmotionalNeed.DREAM)
    assert len(sig.secondary_needs) <= MAX_SECONDARY


def test_llm_classify_empty_secondary():
    c = NeedClassifier(FakeNeedLLM("seen", []))
    sig = c.classify("内容")
    assert sig.secondary_needs == ()
    assert sig.planet == Planet.SUN


def test_llm_classify_failure_falls_back():
    class BrokenLLM:
        available = True

        def complete(self, prompt, system=None, **kwargs):
            return "not json at all"

    c = NeedClassifier(BrokenLLM())
    sig = c.classify("今天好难过，想哭")
    assert sig.primary_need == EmotionalNeed.SOOTHED


# ---------------------------------------------------------------------------
# 规则兜底（无 LLM）
# ---------------------------------------------------------------------------


def test_rule_fallback_content_to_need():
    """§6.2 示例主线：在找能被温柔抱一下的东西 → 想被抱抱 → 月亮。"""
    c = NeedClassifier()
    sig = c.classify("所有人都靠我撑着，我好累")
    assert sig.primary_need == EmotionalNeed.SOOTHED
    assert sig.healing_name == "想被抱抱的我"


def test_rule_fallback_primary_and_secondary():
    """委屈（主：想被抱抱）+ 旅行（次：想飞）→ 月亮落款 + 木星碎片。"""
    c = NeedClassifier()
    sig = c.classify("被老板骂了好委屈，想辞职去旅行")
    assert sig.primary_need == EmotionalNeed.SOOTHED
    assert sig.secondary_needs == (EmotionalNeed.SOAR,)
    assert "jupiter_faith" in sig.soul_fragments
    assert "sagittarius_arrow" in sig.soul_fragments


def test_rule_fallback_unknown_content_defaults_to_soothed():
    """判断不出 → 默认"先接住"（soothed → 月亮），显式可解释。"""
    c = NeedClassifier()
    sig = c.classify("嗯嗯，好的")
    assert sig.primary_need == EmotionalNeed.SOOTHED
    assert sig.planet == Planet.MOON


def test_rule_fallback_empty_content():
    c = NeedClassifier()
    assert c.classify("").primary_need == EmotionalNeed.SOOTHED
    assert c.classify(None).primary_need == EmotionalNeed.SOOTHED


# ---------------------------------------------------------------------------
# 显式可解释（§6.2：不能是黑箱）
# ---------------------------------------------------------------------------


def test_explain_trace_is_human_readable():
    sig = LetterSignature.from_needs(EmotionalNeed.SOOTHED, (EmotionalNeed.SOAR,))
    trace = sig.explain
    assert "想被抱抱" in trace
    assert "月亮" in trace
    assert "想被抱抱的我" in trace
    assert "jupiter_faith" in trace


# ---------------------------------------------------------------------------
# LetterService.context_letter（§6.1 来信式日记）
# ---------------------------------------------------------------------------


def _make_service() -> LetterService:
    from foundation.database.store import GardenStore

    store = GardenStore(":memory:")
    return LetterService(store=store, llm_client=None, chart_provider=None)


def test_context_letter_keepsake_with_signature():
    svc = _make_service()
    letter = svc.context_letter(
        _make_person(),
        content="今天好难过，想哭",
        reply="嗯，我听见了。想哭就哭一会儿，我在。",
    )
    assert letter.kind == "keepsake"
    assert letter.sender == "moon"
    assert letter.title == "「想被抱抱的我」来信"
    # 正文 = 那段完整回复（不是摘要），落款用疗愈名
    assert "想哭就哭一会儿，我在。" in letter.body
    assert "—— 想被抱抱的我" in letter.body
    assert "◈ 今日灵魂碎片" in letter.body
    # metadata 留推导过程（显式可解释）
    assert "explain" in letter.metadata
    assert "想被抱抱" in letter.metadata["explain"]


def test_context_letter_unions_lit_fragments_footnote():
    """灵魂碎片脚注 = 推导碎片 ∪ 当天随聊点亮（去重保序）。"""
    svc = _make_service()
    letter = svc.context_letter(
        _make_person(),
        content="被老板骂了好委屈，想辞职去旅行",
        reply="辛苦了，先停一下。",
        lit_fragments=("mars_action", "jupiter_faith"),
    )
    # 委屈→SOOTHED(主) 旅行→SOAR(次)；次需求碎片 jupiter_faith/sagittarius_arrow
    # + 随聊点亮 mars_action/jupiter_faith → 去重后 4 个
    assert letter.metadata["soul_fragments"] == ["jupiter_faith", "sagittarius_arrow"]
    assert letter.metadata["lit_fragments"] == ["mars_action", "jupiter_faith"]
    assert "火星·行动引擎" in letter.body      # 随聊点亮进了脚注
    assert "木星·信念高塔" in letter.body      # 次需求碎片进了脚注


def test_record_keepsake_saves_and_returns_signature():
    """§6.1/§6.2 接线：一次倾诉时刻 → keepsake 来信落库 + 返回推导链签名。"""
    svc = _make_service()
    p = _make_person()
    letter, sig = svc.record_keepsake(
        p,
        content="被老板骂了好委屈，想辞职去旅行",
        reply="辛苦了，先停一下。",
        lit_fragments=("mars_action", "jupiter_faith"),
    )
    assert letter.kind == "keepsake"
    assert letter.id
    assert sig.planet is not None
    # 已落库（信箱能取到）
    assert any(l.id == letter.id for l in svc.list(p.id))
    # metadata 完整（供前端"为什么点亮它"）：推导链显式可解释
    assert letter.metadata["primary_need"] == "soothed"
    assert letter.metadata["healing_name"] == "想被抱抱的我"
    assert letter.metadata["soul_fragments"] == ["jupiter_faith", "sagittarius_arrow"]
    assert "想被抱抱" in letter.metadata["explain"]


class FakeEntryLLM:
    """按 system prompt 分发：需求识别 → JSON；词条蒸馏 → 诗化一句。"""

    available = True

    def __init__(self, entry: str):
        self._entry = entry

    def complete(self, prompt, system=None, **kwargs):
        if system and "情绪需求识别器" in system:
            return json.dumps({"primary": "dream", "secondary": []})
        return self._entry


def test_record_memorable_creates_entry_keepsake():
    """§6.1 词条式来信：日常/正面分享 → LLM 诗化词条成信，落款推导链完整。"""
    from foundation.database.store import GardenStore  # noqa: PLC0415

    svc = LetterService(
        store=GardenStore(":memory:"),
        llm_client=FakeEntryLLM("在九门的世界里，你找到了暂时栖息的梦境。"),
        chart_provider=None,
    )
    p = _make_person()
    letter, sig = svc.record_memorable(
        p,
        content="最近在看九门",
        reply="是不是盗墓题材那部？我也看过，太带感了。",
        lit_fragments=("moon_tide",),
    )
    assert letter.kind == "keepsake"            # 同一收件箱
    assert letter.metadata["entry"] is True     # 词条标记（前端区分样式）
    # 正文 = 诗化词条（不是整段回复的搬运）
    assert "在九门的世界里" in letter.body
    assert "是不是盗墓题材那部" not in letter.body
    # 落款推导链完整（显式可解释，§6.2）
    assert sig.planet is not None
    assert letter.metadata["primary_need"] == "dream"
    assert letter.metadata["healing_name"] == "想做梦的我"
    assert "想做梦" in letter.metadata["explain"]
    # 已落库（信箱能取到）
    assert any(l.id == letter.id for l in svc.list(p.id))


def test_record_memorable_falls_back_to_reply():
    """LLM 不可用 → 词条降级为星灵回复原样（仍是"记忆存档"，服务不断）。"""
    from foundation.database.store import GardenStore  # noqa: PLC0415

    svc = LetterService(store=GardenStore(":memory:"), llm_client=None, chart_provider=None)
    p = _make_person()
    letter, _ = svc.record_memorable(
        p,
        content="最近在看九门",
        reply="是不是盗墓题材那部？我也看过，太带感了。",
    )
    assert letter.kind == "keepsake"
    assert letter.metadata["entry"] is True
    assert "是不是盗墓题材那部" in letter.body   # 回复原样兜底


def test_context_letter_signature_explicit():
    """显式传入 signature → 不重新推导（可复现）。"""
    svc = _make_service()
    sig = LetterSignature.from_needs(EmotionalNeed.SEEN)
    letter = svc.context_letter(
        _make_person(),
        content="随便什么内容",
        reply="你很棒。",
        signature=sig,
    )
    assert letter.sender == "sun"
    assert letter.title == "「想被看见的我」来信"


def test_context_letter_sender_uses_healing_name_not_fragment():
    """落款是疗愈名（§6.1）：收信人读到"我自己的一部分写给其余的我"。"""
    svc = _make_service()
    letter = svc.context_letter(
        _make_person(),
        content="我想去看很远的远方",
        reply="去看看吧，世界比你想的大。",
    )
    assert "想飞的我" in letter.title
    assert letter.sender == "jupiter"
