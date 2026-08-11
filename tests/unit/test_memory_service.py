"""记忆写回管线测试（第四层记忆：咨询后写回）。

验证：
- MemorySummarizer 降级路径（无 LLM）产出可读摘要
- MemoryService.apply_writeback 端到端：摘要 + 画像 + 成长事件全部落库
- 重放不产生重复成长事件（按 conclusion 去重）
- _merge_profile 对 LLM 结构化更新的合并规则（去重/覆盖/上限）
- LLM 摘要可用时的结构化路径
"""

from datetime import datetime, timezone
from unittest.mock import Mock

from foundation.database.store import GardenStore
from foundation.utils import new_id
from shared.enums import EvidencePolarity, IntentDomain
from shared.models import (
    Conclusion,
    Conversation,
    DialogueTurn,
    Intent,
)

from application.memory.service import MemoryService
from application.memory.summarizer import MemorySummarizer

from tests.unit.test_store import _make_conversation  # 复用会话构造


def _make_intent(domain: IntentDomain = IntentDomain.CAREER) -> Intent:
    return Intent(id=new_id("intent"), raw_query="我该不该离职？", domain=domain, subdomain="career_change")


def _make_conclusion(intent: Intent) -> Conclusion:
    return Conclusion(
        id=new_id("concl"),
        intent_id=intent.id,
        evidence_set_id=new_id("evid"),
        domain=intent.domain.value,
        summary="土星落九宫：深造是职业跃迁的必经之路",
        overall_confidence=0.7,
        overall_polarity=EvidencePolarity.NEUTRAL,
        generated_at=datetime.now(timezone.utc),
    )


# --- MemorySummarizer 降级路径 ---

def test_summarizer_fallback_without_llm():
    summarizer = MemorySummarizer(llm_client=None)
    conv = _make_conversation()
    summary, updates = summarizer.summarize(conv, "career")
    assert summary
    assert "你好" in summary or "事业" in summary
    assert updates == {}  # 降级：不产结构化更新


def test_summarizer_fallback_is_topic_not_transcript():
    """降级摘要 = 最后一条用户消息作话题，不 dump「用户:/星灵:」转写（回访开场丑）。"""
    summarizer = MemorySummarizer(llm_client=None)
    conv = _make_conversation()
    conv.add_turn(DialogueTurn(
        id=new_id("t"), user_message="我该不该离职？",
        assistant_response="土星落九宫，深造是跃迁之路", persona_used=None,
        timestamp=datetime.now(timezone.utc),
    ))
    summary, updates = summarizer.summarize(conv, "career")
    assert summary == "我该不该离职？"
    assert "用户:" not in summary and "星灵:" not in summary


def test_summarizer_empty_conversation():
    conv = Conversation(id=new_id("conv"), person_id="p1", persona=None)
    summary, updates = MemorySummarizer(None).summarize(conv, "career")
    assert summary == "" and updates == {}


# --- MemoryService 端到端 ---

def test_writeback_end_to_end():
    store = GardenStore(":memory:")
    service = MemoryService(store)  # 无 LLM → 降级路径
    conv = _make_conversation()
    intent = _make_intent()
    conclusion = _make_conclusion(intent)

    result = service.apply_writeback(
        person_id="p1", conversation=conv, intent=intent, conclusion=conclusion,
        need="sorted",
    )
    assert result["conversation_id"] == conv.id
    assert result["summary"]  # 摘要已生成
    assert result["profile_updated"] is True  # conclusion.summary 已并入画像
    assert result["life_event_id"] is not None

    # 画像落库：领域理解来自 Domain 的 conclusion.summary，非 LLM
    profile = store.get_profile("p1")
    assert profile is not None
    assert profile.domain_summaries["career"].summary == "土星落九宫：深造是职业跃迁的必经之路"
    assert profile.domain_summaries["career"].confidence == 0.7

    # 会话落库（含摘要，"继续昨天"可读）
    summaries = store.list_conversation_summaries("p1")
    assert len(summaries) == 1
    assert summaries[0]["summary"]

    # 成长事件落库（kind=consult，关联结论）
    events = store.list_life_events("p1")
    assert len(events) == 1
    assert events[0].kind == "consult"
    assert events[0].related_conclusion_id == conclusion.id
    # 咨询记录补意图/需求（喂记忆写回）：domain=八大领域，need=诉求类型
    assert events[0].domain == "career"
    assert events[0].need == "sorted"


def test_writeback_replay_no_duplicate_life_event():
    store = GardenStore(":memory:")
    service = MemoryService(store)
    conv = _make_conversation()
    intent = _make_intent()
    conclusion = _make_conclusion(intent)

    first = service.apply_writeback(person_id="p1", conversation=conv, intent=intent, conclusion=conclusion)
    second = service.apply_writeback(person_id="p1", conversation=conv, intent=intent, conclusion=conclusion)

    assert first["life_event_id"] == second["life_event_id"]  # 同结论 → 同一事件
    assert len(store.list_life_events("p1")) == 1
    # 画像/会话 upsert：不重复、不丢字段
    assert store.get_profile("p1").domain_summaries["career"].summary == conclusion.summary


def test_writeback_without_conclusion_still_persists():
    """没有 Conclusion（如纯闲聊）也写回会话与摘要，只是不生成成长事件。"""
    store = GardenStore(":memory:")
    service = MemoryService(store)
    conv = _make_conversation()
    result = service.apply_writeback(person_id="p1", conversation=conv)
    assert result["life_event_id"] is None
    assert store.list_conversation_summaries("p1")[0]["summary"]
    assert store.get_profile("p1") is not None  # 空画像已创建


# --- _merge_profile 结构化更新（用假 summarizer 注入 LLM 结果）---

class _FakeSummarizer:
    """固定返回结构化更新的假 LLM 摘要器。"""

    def __init__(self, updates: dict):
        self._updates = updates

    def summarize(self, conversation, domain: str = ""):
        return "fake summary", self._updates


def test_merge_profile_structured_updates():
    store = GardenStore(":memory:")
    updates = {
        "domain_summary": "最近三个月你越来越相信自己的判断",
        "key_dates": [{"label": "考虑离职", "date": "2026-08-01"}],
        "lord_states": {"moon_in_7": "观察中"},
        "verified_findings": ["土星落九宫：深造是职业跃迁的必经之路"],
    }
    service = MemoryService(store, summarizer=_FakeSummarizer(updates))
    conv = _make_conversation()
    intent = _make_intent()
    result = service.apply_writeback(person_id="p1", conversation=conv, intent=intent)

    assert result["profile_updated"] is True
    profile = store.get_profile("p1")
    assert profile.domain_summaries["career"].summary == "最近三个月你越来越相信自己的判断"
    assert profile.key_dates[0].label == "考虑离职"
    assert profile.lord_states["moon_in_7"] == "观察中"
    assert profile.verified_findings[0].statement == "土星落九宫：深造是职业跃迁的必经之路"


def test_merge_profile_dedupes():
    """重复的 label/statement 只保留一条。"""
    store = GardenStore(":memory:")
    updates = {
        "key_dates": [{"label": "考虑离职", "date": "2026-08-01"}, {"label": "考虑离职", "date": "2026-09-01"}],
        "verified_findings": ["土星落九宫：深造", "土星落九宫：深造"],
    }
    service = MemoryService(store, summarizer=_FakeSummarizer(updates))
    conv = _make_conversation()
    service.apply_writeback(person_id="p1", conversation=conv, intent=_make_intent())
    service.apply_writeback(person_id="p1", conversation=conv, intent=_make_intent())

    profile = store.get_profile("p1")
    assert len(profile.key_dates) == 1          # 跨两次写回也只一条
    assert len(profile.verified_findings) == 1


def test_merge_profile_empty_updates_is_safe():
    """LLM 返回空更新（降级/失败）不破坏画像。"""
    store = GardenStore(":memory:")
    service = MemoryService(store, summarizer=_FakeSummarizer({}))
    conv = _make_conversation()
    service.apply_writeback(person_id="p1", conversation=conv, intent=_make_intent())
    profile = store.get_profile("p1")
    assert profile is not None
    assert profile.verified_findings == [] and profile.key_dates == []
