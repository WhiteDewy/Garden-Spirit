"""花园日记服务测试（Task 8）。

验证：
- JournalSummarizer 降级路径（无 LLM）产出可读成长记录
- create：落库 + 生成时间轴事件（kind=journal）
- update：内容变则重生成成长记录
- list：按时间倒序
"""

from foundation.database.store import GardenStore
from foundation.utils import new_id

from application.memory.journal import JournalService, JournalSummarizer


def _make_service() -> JournalService:
    store = GardenStore(":memory:")
    return JournalService(store, summarizer=JournalSummarizer(llm_client=None))


def test_summarizer_fallback():
    s = JournalSummarizer(llm_client=None)
    assert s.summarize("今天有点累，但决定把辞职的事想清楚。") == "今天有点累，但决定把辞职的事想清楚。"
    assert s.summarize("") == ""


def test_summarizer_fallback_truncates():
    s = JournalSummarizer(llm_client=None)
    long = "字" * 300
    out = s.summarize(long)
    assert len(out) <= 121
    assert out.endswith("……")


def test_create_saves_journal_and_life_event():
    service = _make_service()
    entry = service.create("p1", "今天认真想了想离职的事，觉得还是要先解决手头项目。", mood="清醒")

    assert entry.mood == "清醒"
    assert entry.ai_summary  # 降级 = 原文截断，非空

    # 落库可读
    assert service.list("p1")[0].content.startswith("今天认真想了想")
    # 生成时间轴事件（kind=journal，关联日记）
    events = service._store.list_life_events("p1")
    assert len(events) == 1
    assert events[0].kind == "journal"
    assert events[0].related_journal_id == entry.id
    assert events[0].label == "写下一篇花园日记"


def test_update_regenerates_summary():
    service = _make_service()
    entry = service.create("p1", "初稿内容", mood="")
    old_summary = entry.ai_summary

    updated = service.update(entry.id, content="改过的新内容")
    assert updated is not None
    assert updated.content == "改过的新内容"
    assert updated.ai_summary != old_summary  # 内容变 → 重生成


def test_update_unknown_returns_none():
    service = _make_service()
    assert service.update(new_id("x"), content="hi") is None


def test_update_mood_only_keeps_content():
    service = _make_service()
    entry = service.create("p1", "内容不变", mood="")
    updated = service.update(entry.id, mood="开心")
    assert updated.mood == "开心"
    assert updated.content == "内容不变"
