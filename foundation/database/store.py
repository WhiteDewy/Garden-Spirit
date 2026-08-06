"""GardenStore：跨会话持久化（第四层记忆的地基）。

管理 5 张表：conversations / memory_items / profiles / journal_entries / life_events。
出生数据仍在 PersonRepository（本模块不碰，避免重复职责）。

隐私红线（PRD §8）：对话正文、画像、日记、事件标签均含 PII，
一律 Fernet 加密后入库；表结构只暴露 id/timestamp/kind 等非敏感字段。

与 PersonRepository 的关系：各自持有独立连接。MVP 阶段数据量小，
跨库可见性问题由"写后即 commit"规避。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from foundation.logger import get_logger
from foundation.utils import utc_now_aware
from shared.enums import PersonaType, Role
from shared.models import (
    ChartProfile,
    Conversation,
    DialogueTurn,
    DomainSummary,
    JournalEntry,
    KeyDate,
    Letter,
    LifeEvent,
    MemoryItem,
    VerifiedFinding,
)
from foundation.database.encryption import Encryptor

logger = get_logger("foundation.database.store")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    persona TEXT DEFAULT '',
    summary_enc TEXT DEFAULT '',
    body_json_enc TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    is_active INTEGER DEFAULT 1,
    metadata_json_enc TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS memory_items (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    person_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content_enc TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    metadata_json_enc TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS profiles (
    person_id TEXT PRIMARY KEY,
    lord_states_json_enc TEXT DEFAULT '',
    verified_findings_json_enc TEXT DEFAULT '',
    key_dates_json_enc TEXT DEFAULT '',
    domain_summaries_json_enc TEXT DEFAULT '',
    trust_score REAL NOT NULL DEFAULT 0,
    trust_signals_json_enc TEXT NOT NULL DEFAULT '',
    preferences_json_enc TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS journal_entries (
    id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    content_enc TEXT NOT NULL,
    mood TEXT DEFAULT '',
    ai_summary_enc TEXT DEFAULT '',
    related_intent_id TEXT,
    related_conclusion_id TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS life_events (
    id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    label_enc TEXT NOT NULL,
    kind TEXT DEFAULT 'life',
    detail_enc TEXT DEFAULT '',
    related_journal_id TEXT,
    related_intent_id TEXT,
    related_conclusion_id TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS letters (
    id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    letter_date TEXT NOT NULL,
    sender TEXT NOT NULL,
    title_enc TEXT DEFAULT '',
    body_enc TEXT NOT NULL,
    kind TEXT DEFAULT 'daily',
    created_at TEXT,
    metadata_json_enc TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_letters_person_date ON letters(person_id, letter_date);
CREATE INDEX IF NOT EXISTS idx_conversations_person ON conversations(person_id);
CREATE INDEX IF NOT EXISTS idx_memory_person ON memory_items(person_id);
CREATE INDEX IF NOT EXISTS idx_memory_session ON memory_items(session_id);
CREATE INDEX IF NOT EXISTS idx_journal_person ON journal_entries(person_id);
CREATE INDEX IF NOT EXISTS idx_life_events_person ON life_events(person_id, occurred_at);
"""


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value else utc_now_aware().isoformat()


def _from_iso(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _json_default(obj: Any) -> Any:
    """JSON 序列化兜底：枚举→值，datetime→ISO，dataclass→dict。"""
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (datetime, timezone)):
        return obj.isoformat()
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return str(obj)


def _dump(obj: Any) -> str:
    return json.dumps(obj, default=_json_default, ensure_ascii=False)


def _load(raw: str | None) -> Any:
    return json.loads(raw) if raw else {}


# ----------------------------------------------------------------------
# 模型 ↔ dict 序列化（显式写出，避免 dataclass 字段漂移时静默丢数据）
# ----------------------------------------------------------------------


def _turn_to_dict(t: DialogueTurn) -> dict:
    return {
        "id": t.id,
        "user_message": t.user_message,
        "assistant_response": t.assistant_response,
        "intent_id": t.intent_id,
        "conclusion_id": t.conclusion_id,
        "persona_used": t.persona_used.value if t.persona_used else None,
        "timestamp": _iso(t.timestamp),
        "latency_ms": t.latency_ms,
        "tokens_used": t.tokens_used,
    }


def _turn_from_dict(d: dict) -> DialogueTurn:
    p = d.get("persona_used")
    return DialogueTurn(
        id=d["id"],
        user_message=d["user_message"],
        assistant_response=d["assistant_response"],
        intent_id=d.get("intent_id"),
        conclusion_id=d.get("conclusion_id"),
        persona_used=PersonaType(p) if p else None,
        timestamp=_from_iso(d.get("timestamp")),
        latency_ms=d.get("latency_ms", 0),
        tokens_used=d.get("tokens_used", 0),
    )


def _conversation_to_dict(conv: Conversation) -> dict:
    return {
        "id": conv.id,
        "person_id": conv.person_id,
        "persona": conv.persona.value if conv.persona else "",
        "turns": [_turn_to_dict(t) for t in conv.turns],
        "started_at": _iso(conv.started_at),
        "ended_at": _iso(conv.ended_at) if conv.ended_at else None,
        "is_active": conv.is_active,
        "metadata": conv.metadata,
    }


def _conversation_from_dict(d: dict) -> Conversation:
    return Conversation(
        id=d["id"],
        person_id=d["person_id"],
        persona=PersonaType(d["persona"]) if d.get("persona") else PersonaType.ZIRCON,
        turns=[_turn_from_dict(t) for t in d.get("turns", [])],
        started_at=_from_iso(d.get("started_at")),
        ended_at=_from_iso(d.get("ended_at")),
        is_active=bool(d.get("is_active", True)),
        metadata=d.get("metadata", {}),
    )


def _summary_to_dict(s: DomainSummary) -> dict:
    return {
        "domain": s.domain,
        "summary": s.summary,
        "confidence": s.confidence,
        "evidence_notes": s.evidence_notes,
        "updated_at": _iso(s.updated_at),
    }


def _summary_from_dict(d: dict) -> DomainSummary:
    return DomainSummary(
        domain=d["domain"],
        summary=d.get("summary", ""),
        confidence=d.get("confidence", 0.0),
        evidence_notes=d.get("evidence_notes", []),
        updated_at=_from_iso(d.get("updated_at")),
    )


def _finding_to_dict(f: VerifiedFinding) -> dict:
    return {
        "id": f.id,
        "statement": f.statement,
        "confidence": f.confidence,
        "source_intent_id": f.source_intent_id,
        "confirmed_at": _iso(f.confirmed_at) if f.confirmed_at else None,
        "user_feedback": f.user_feedback,
        "verification_notes": list(f.verification_notes),
        "domain": f.domain,
    }


def _finding_from_dict(d: dict) -> VerifiedFinding:
    return VerifiedFinding(
        id=d["id"],
        statement=d.get("statement", ""),
        confidence=d.get("confidence", 0.0),
        source_intent_id=d.get("source_intent_id"),
        confirmed_at=_from_iso(d.get("confirmed_at")),
        user_feedback=d.get("user_feedback", ""),
        verification_notes=list(d.get("verification_notes", []) or []),
        domain=d.get("domain", ""),
    )


def _keydate_to_dict(k: KeyDate) -> dict:
    return {
        "id": k.id,
        "date": _iso(k.date),
        "label": k.label,
        "kind": k.kind,
        "related_intent_id": k.related_intent_id,
    }


def _keydate_from_dict(d: dict) -> KeyDate:
    return KeyDate(
        id=d["id"],
        date=_from_iso(d.get("date")),
        label=d.get("label", ""),
        kind=d.get("kind", "event"),
        related_intent_id=d.get("related_intent_id"),
    )


#: profiles 表的增量迁移：CREATE TABLE IF NOT EXISTS 不会改已有表，
#: 这里对已存在的旧库用 ALTER TABLE 补齐新列（A2 trust / B2 preferences）。
_PROFILE_MIGRATIONS = (
    ("trust_score", "REAL NOT NULL DEFAULT 0"),
    ("trust_signals_json_enc", "TEXT NOT NULL DEFAULT ''"),
    ("preferences_json_enc", "TEXT NOT NULL DEFAULT ''"),
)


def _ensure_profile_columns(conn: sqlite3.Connection) -> None:
    """为已存在的 profiles 表补齐缺失列（幂等）。"""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(profiles)")}
    for name, decl in _PROFILE_MIGRATIONS:
        if name not in cols:
            conn.execute(f"ALTER TABLE profiles ADD COLUMN {name} {decl}")
            logger.info("profiles 表迁移：新增列 %s", name)
    conn.commit()


class GardenStore:
    """跨会话数据仓库（SQLite + Fernet）。"""

    def __init__(self, db_path: str = "./data/garden_spirit.db", encryptor: Encryptor | None = None):
        self._db_path = str(db_path)
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._encryptor = encryptor or Encryptor()
        # check_same_thread=False：见 repository.py 同款说明（FastAPI 工作线程）。
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        _ensure_profile_columns(self._conn)  # 旧库补齐 A2 新增列
        self._conn.commit()

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    def save_conversation(
        self,
        conversation: Conversation,
        summary: str = "",
    ) -> None:
        """Upsert 保存完整会话（body 加密）。summary 供"继续昨天"列表展示。"""
        body = _conversation_to_dict(conversation)
        now = _iso(conversation.started_at) or _iso(None)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO conversations
                    (id, person_id, persona, summary_enc, body_json_enc,
                     started_at, ended_at, is_active, metadata_json_enc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    persona = excluded.persona,
                    summary_enc = excluded.summary_enc,
                    body_json_enc = excluded.body_json_enc,
                    ended_at = excluded.ended_at,
                    is_active = excluded.is_active,
                    metadata_json_enc = excluded.metadata_json_enc
                """,
                (
                    conversation.id,
                    conversation.person_id,
                    conversation.persona.value if conversation.persona else "",
                    self._encryptor.encrypt(summary),
                    self._encryptor.encrypt(_dump(body)),
                    now,
                    _iso(conversation.ended_at) if conversation.ended_at else None,
                    int(conversation.is_active),
                    self._encryptor.encrypt(_dump(conversation.metadata)),
                ),
            )

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._conn:
            row = self._conn.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
        if row is None:
            return None
        body = _load(self._encryptor.decrypt(row["body_json_enc"]))
        return _conversation_from_dict(body)

    def list_conversations(self, person_id: str, active_only: bool = False) -> list[Conversation]:
        sql = "SELECT id FROM conversations WHERE person_id = ?"
        params: list[Any] = [person_id]
        if active_only:
            sql += " AND is_active = 1"
        sql += " ORDER BY started_at DESC"
        with self._conn:
            rows = self._conn.execute(sql, params).fetchall()
        out: list[Conversation] = []
        for row in rows:
            conv = self.get_conversation(row["id"])
            if conv is not None:
                out.append(conv)
        return out

    def list_conversation_summaries(self, person_id: str, limit: int = 10) -> list[dict]:
        """轻量列表：id/summary/persona/started_at，不展开 turns。"""
        with self._conn:
            rows = self._conn.execute(
                """
                SELECT id, summary_enc, persona, started_at
                FROM conversations WHERE person_id = ?
                ORDER BY started_at DESC LIMIT ?
                """,
                (person_id, limit),
            ).fetchall()
        out: list[dict] = []
        for row in rows:
            try:
                summary = self._encryptor.decrypt(row["summary_enc"]) if row["summary_enc"] else ""
            except ValueError:
                summary = ""
            out.append({
                "id": row["id"],
                "summary": summary,
                "persona": row["persona"],
                "started_at": row["started_at"],
            })
        return out

    # ------------------------------------------------------------------
    # Memory items
    # ------------------------------------------------------------------

    def save_memory_item(self, item: MemoryItem) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO memory_items
                    (id, session_id, person_id, role, content_enc, timestamp, metadata_json_enc)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.session_id,
                    item.person_id,
                    item.role.value if isinstance(item.role, Role) else str(item.role),
                    self._encryptor.encrypt(item.content),
                    _iso(item.timestamp),
                    self._encryptor.encrypt(_dump(item.metadata)),
                ),
            )

    def list_memory_items(
        self, person_id: str | None = None, session_id: str | None = None, limit: int = 200
    ) -> list[MemoryItem]:
        sql = "SELECT * FROM memory_items WHERE 1=1"
        params: list[Any] = []
        if person_id:
            sql += " AND person_id = ?"
            params.append(person_id)
        if session_id:
            sql += " AND session_id = ?"
            params.append(session_id)
        sql += " ORDER BY timestamp ASC LIMIT ?"
        params.append(limit)
        with self._conn:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._memory_item_from_row(r) for r in rows]

    def _memory_item_from_row(self, row: sqlite3.Row) -> MemoryItem:
        meta_raw = row["metadata_json_enc"]
        return MemoryItem(
            id=row["id"],
            session_id=row["session_id"],
            person_id=row["person_id"],
            role=Role(row["role"]) if row["role"] in Role._value2member_map_ else Role.USER,
            content=self._encryptor.decrypt(row["content_enc"]),
            timestamp=_from_iso(row["timestamp"]),
            metadata=_load(self._encryptor.decrypt(meta_raw)) if meta_raw else {},
        )

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    def get_profile(self, person_id: str) -> ChartProfile | None:
        with self._conn:
            row = self._conn.execute(
                "SELECT * FROM profiles WHERE person_id = ?", (person_id,)
            ).fetchone()
        if row is None:
            return None
        return ChartProfile(
            person_id=person_id,
            lord_states=_load(self._encryptor.decrypt(row["lord_states_json_enc"])) if row["lord_states_json_enc"] else {},
            verified_findings=[
                _finding_from_dict(f) for f in _load(self._encryptor.decrypt(row["verified_findings_json_enc"]))
            ] if row["verified_findings_json_enc"] else [],
            key_dates=[
                _keydate_from_dict(k) for k in _load(self._encryptor.decrypt(row["key_dates_json_enc"]))
            ] if row["key_dates_json_enc"] else [],
            domain_summaries={
                d["domain"]: _summary_from_dict(d)
                for d in _load(self._encryptor.decrypt(row["domain_summaries_json_enc"]))
            } if row["domain_summaries_json_enc"] else {},
            trust_score=float(row["trust_score"] or 0),
            trust_signals=_load(self._encryptor.decrypt(row["trust_signals_json_enc"])) if row["trust_signals_json_enc"] else {},
            preferences=_load(self._encryptor.decrypt(row["preferences_json_enc"])) if row["preferences_json_enc"] else {},
            created_at=_from_iso(row["created_at"]),
            updated_at=_from_iso(row["updated_at"]),
        )

    def save_profile(self, profile: ChartProfile) -> None:
        now = _iso(profile.updated_at) or _iso(None)
        created = _iso(profile.created_at) or now
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO profiles
                    (person_id, lord_states_json_enc, verified_findings_json_enc,
                     key_dates_json_enc, domain_summaries_json_enc,
                     trust_score, trust_signals_json_enc, preferences_json_enc,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(person_id) DO UPDATE SET
                    lord_states_json_enc = excluded.lord_states_json_enc,
                    verified_findings_json_enc = excluded.verified_findings_json_enc,
                    key_dates_json_enc = excluded.key_dates_json_enc,
                    domain_summaries_json_enc = excluded.domain_summaries_json_enc,
                    trust_score = excluded.trust_score,
                    trust_signals_json_enc = excluded.trust_signals_json_enc,
                    preferences_json_enc = excluded.preferences_json_enc,
                    updated_at = excluded.updated_at
                """,
                (
                    profile.person_id,
                    self._encryptor.encrypt(_dump(profile.lord_states)),
                    self._encryptor.encrypt(_dump([_finding_to_dict(f) for f in profile.verified_findings])),
                    self._encryptor.encrypt(_dump([_keydate_to_dict(k) for k in profile.key_dates])),
                    self._encryptor.encrypt(_dump([_summary_to_dict(s) for s in profile.domain_summaries.values()])),
                    float(profile.trust_score or 0),
                    self._encryptor.encrypt(_dump(profile.trust_signals)),
                    self._encryptor.encrypt(_dump(profile.preferences or {})),
                    created,
                    now,
                ),
            )

    # ------------------------------------------------------------------
    # Journal
    # ------------------------------------------------------------------

    def save_journal(self, entry: JournalEntry) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO journal_entries
                    (id, person_id, content_enc, mood, ai_summary_enc,
                     related_intent_id, related_conclusion_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    content_enc = excluded.content_enc,
                    mood = excluded.mood,
                    ai_summary_enc = excluded.ai_summary_enc,
                    related_intent_id = excluded.related_intent_id,
                    related_conclusion_id = excluded.related_conclusion_id,
                    updated_at = excluded.updated_at
                """,
                (
                    entry.id,
                    entry.person_id,
                    self._encryptor.encrypt(entry.content),
                    entry.mood,
                    self._encryptor.encrypt(entry.ai_summary),
                    entry.related_intent_id,
                    entry.related_conclusion_id,
                    _iso(entry.created_at) or _iso(None),
                    _iso(entry.updated_at) or _iso(None),
                ),
            )

    def get_journal(self, entry_id: str) -> JournalEntry | None:
        with self._conn:
            row = self._conn.execute(
                "SELECT * FROM journal_entries WHERE id = ?", (entry_id,)
            ).fetchone()
        if row is None:
            return None
        return JournalEntry(
            id=row["id"],
            person_id=row["person_id"],
            content=self._encryptor.decrypt(row["content_enc"]),
            mood=row["mood"],
            ai_summary=self._encryptor.decrypt(row["ai_summary_enc"]),
            related_intent_id=row["related_intent_id"],
            related_conclusion_id=row["related_conclusion_id"],
            created_at=_from_iso(row["created_at"]),
            updated_at=_from_iso(row["updated_at"]),
        )

    def list_journals(self, person_id: str, limit: int = 200) -> list[JournalEntry]:
        with self._conn:
            rows = self._conn.execute(
                "SELECT id FROM journal_entries WHERE person_id = ? ORDER BY created_at DESC LIMIT ?",
                (person_id, limit),
            ).fetchall()
        out: list[JournalEntry] = []
        for row in rows:
            entry = self.get_journal(row["id"])
            if entry is not None:
                out.append(entry)
        return out

    # ------------------------------------------------------------------
    # Life events
    # ------------------------------------------------------------------

    def save_life_event(self, event: LifeEvent) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO life_events
                    (id, person_id, occurred_at, label_enc, kind, detail_enc,
                     related_journal_id, related_intent_id, related_conclusion_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.person_id,
                    _iso(event.occurred_at),
                    self._encryptor.encrypt(event.label),
                    event.kind,
                    self._encryptor.encrypt(event.detail),
                    event.related_journal_id,
                    event.related_intent_id,
                    event.related_conclusion_id,
                    _iso(event.created_at) or _iso(None),
                ),
            )

    def list_life_events(self, person_id: str, limit: int = 500) -> list[LifeEvent]:
        with self._conn:
            rows = self._conn.execute(
                "SELECT * FROM life_events WHERE person_id = ? ORDER BY occurred_at DESC LIMIT ?",
                (person_id, limit),
            ).fetchall()
        return [self._life_event_from_row(r) for r in rows]

    def get_life_event_by_conclusion(self, conclusion_id: str) -> LifeEvent | None:
        """按关联结论查成长事件（写回去重的依据，保证可重放）。"""
        with self._conn:
            row = self._conn.execute(
                "SELECT * FROM life_events WHERE related_conclusion_id = ? LIMIT 1",
                (conclusion_id,),
            ).fetchone()
        return self._life_event_from_row(row) if row is not None else None

    def _life_event_from_row(self, row: sqlite3.Row) -> LifeEvent:
        return LifeEvent(
            id=row["id"],
            person_id=row["person_id"],
            occurred_at=_from_iso(row["occurred_at"]),
            label=self._encryptor.decrypt(row["label_enc"]),
            kind=row["kind"],
            detail=self._encryptor.decrypt(row["detail_enc"]),
            related_journal_id=row["related_journal_id"],
            related_intent_id=row["related_intent_id"],
            related_conclusion_id=row["related_conclusion_id"],
            created_at=_from_iso(row["created_at"]),
        )

    # ------------------------------------------------------------------
    # Letters（星灵来信）
    # ------------------------------------------------------------------

    def save_letter(self, letter: Letter) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO letters
                    (id, person_id, letter_date, sender, title_enc, body_enc,
                     kind, created_at, metadata_json_enc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    letter.id,
                    letter.person_id,
                    letter.letter_date,
                    letter.sender,
                    self._encryptor.encrypt(letter.title),
                    self._encryptor.encrypt(letter.body),
                    letter.kind,
                    _iso(letter.created_at) or _iso(None),
                    self._encryptor.encrypt(_dump(letter.metadata)),
                ),
            )

    def get_letter(self, person_id: str, letter_date: str, kind: str = "daily") -> Letter | None:
        """按日期取信（每日一封的幂等键）。"""
        with self._conn:
            row = self._conn.execute(
                "SELECT * FROM letters WHERE person_id = ? AND letter_date = ? AND kind = ? LIMIT 1",
                (person_id, letter_date, kind),
            ).fetchone()
        return self._letter_from_row(row) if row is not None else None

    def list_letters(self, person_id: str, limit: int = 60) -> list[Letter]:
        with self._conn:
            rows = self._conn.execute(
                "SELECT * FROM letters WHERE person_id = ? ORDER BY letter_date DESC LIMIT ?",
                (person_id, limit),
            ).fetchall()
        return [self._letter_from_row(r) for r in rows]

    def _letter_from_row(self, row: sqlite3.Row) -> Letter:
        meta_raw = row["metadata_json_enc"]
        return Letter(
            id=row["id"],
            person_id=row["person_id"],
            letter_date=row["letter_date"],
            sender=row["sender"],
            title=self._encryptor.decrypt(row["title_enc"]),
            body=self._encryptor.decrypt(row["body_enc"]),
            kind=row["kind"],
            created_at=_from_iso(row["created_at"]),
            metadata=_load(self._encryptor.decrypt(meta_raw)) if meta_raw else {},
        )

    def close(self) -> None:
        self._conn.close()


__all__ = ["GardenStore"]
