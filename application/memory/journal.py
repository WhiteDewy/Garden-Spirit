"""花园日记服务 —— 用户日记 + AI 成长记录。

用户写日记 → AI 生成一句"成长记录"（ai_summary）→ 落库 → 生成成长时间轴事件
（kind=journal）。成长记录可编辑（用户改写后覆盖）。

与 MemoryService 的关系：都喂 GardenStore + 成长时间轴，但职责不同——
MemoryService 管"咨询后写回"，JournalService 管"用户主动记录"。
"""

from __future__ import annotations

from foundation.database.store import GardenStore
from foundation.logger import get_logger
from foundation.utils import new_id, utc_now_aware
from shared.models import JournalEntry, LifeEvent

logger = get_logger("application.memory.journal")

#: LLM 生成成长记录的指令（温暖、具体、不评判、短）
_JOURNAL_SYSTEM = """你是星灵花园的日记陪伴者。读一段用户写的日记，写一句成长记录。

要求：
- 一句，40 字以内。
- 温暖、具体、不评判，不重复用户原话。
- 落到"发生了什么 / 你看见了什么"。
只输出这一句，不要解释。
"""

#: 降级成长记录的最大长度
_FALLBACK_MAX = 120


class JournalSummarizer:
    """用户日记 → 一句成长记录（LLM；无 LLM 时规则截断）。"""

    def __init__(self, llm_client=None):
        self._llm = llm_client

    def summarize(self, content: str) -> str:
        if not content.strip():
            return ""
        if self._llm is not None and self._llm.available:
            try:
                raw = self._llm.complete(
                    prompt=content, system=_JOURNAL_SYSTEM, temperature=0.4, max_tokens=120
                )
                text = raw.strip().strip("「」\"'")
                return text[:200] or ""
            except Exception as exc:  # noqa: BLE001 - 降级不阻断
                logger.warning("日记成长记录 LLM 失败，降级规则: %s", exc)
        return self._fallback(content)

    @staticmethod
    def _fallback(content: str) -> str:
        if len(content) <= _FALLBACK_MAX:
            return content
        # 含省略号控制在 _FALLBACK_MAX 字内
        return content[: _FALLBACK_MAX - 2] + "……"


class JournalService:
    """花园日记的写读改入口。"""

    def __init__(self, store: GardenStore, summarizer: JournalSummarizer | None = None):
        self._store = store
        self._summarizer = summarizer or JournalSummarizer()

    def create(self, person_id: str, content: str, mood: str = "") -> JournalEntry:
        """新建日记：AI 生成成长记录 + 生成时间轴事件（kind=journal）。"""
        now = utc_now_aware()
        entry = JournalEntry(
            id=new_id("journal"),
            person_id=person_id,
            content=content,
            mood=mood,
            ai_summary=self._summarizer.summarize(content),
            created_at=now,
            updated_at=now,
        )
        self._store.save_journal(entry)

        # 成长时间轴：日记也是一种人生事件
        self._store.save_life_event(LifeEvent(
            id=new_id("evt"),
            person_id=person_id,
            occurred_at=now,
            label="写下一篇花园日记",
            kind="journal",
            detail=content[:200],
            related_journal_id=entry.id,
            created_at=now,
        ))
        return entry

    def update(self, entry_id: str, *, content: str | None = None, mood: str | None = None) -> JournalEntry | None:
        """用户编辑日记。ai_summary 只在内容变化时重新生成。"""
        existing = self._store.get_journal(entry_id)
        if existing is None:
            return None
        if content is not None:
            existing.content = content
            existing.ai_summary = self._summarizer.summarize(content)
        if mood is not None:
            existing.mood = mood
        existing.updated_at = utc_now_aware()
        self._store.save_journal(existing)
        return existing

    def list(self, person_id: str, *, page: int = 1, page_size: int = 20) -> tuple[list[JournalEntry], int]:
        """分页列表 → (items, total)。"""
        offset = max(0, page - 1) * page_size
        items = self._store.list_journals(person_id, offset=offset, limit=page_size)
        total = self._store.count_journals(person_id)
        return items, total


__all__ = ["JournalService", "JournalSummarizer"]
