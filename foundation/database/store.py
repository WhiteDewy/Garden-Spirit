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
from foundation.utils import new_id, utc_now_aware
from shared.enums import PersonaType, Role
from shared.models import (
    ChartProfile,
    Conversation,
    DialogueTurn,
    DomainSummary,
    FragmentLight,
    JournalEntry,
    KeyDate,
    Letter,
    LifeEvent,
    MemoryItem,
    PushSubscription,
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
    fragments_json_enc TEXT NOT NULL DEFAULT '',
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
    domain TEXT DEFAULT '',
    need TEXT DEFAULT '',
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
CREATE TABLE IF NOT EXISTS fragment_lights (
    id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    subtype_id TEXT NOT NULL,
    delta INTEGER NOT NULL,
    kind TEXT NOT NULL DEFAULT 'mention',
    source_enc TEXT DEFAULT '',
    lit_at TEXT NOT NULL,
    session_id TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS push_subscriptions (
    person_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    p256dh_enc TEXT NOT NULL DEFAULT '',
    auth_enc TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    PRIMARY KEY (person_id, endpoint)
);
CREATE TABLE IF NOT EXISTS related_persons (
    id TEXT PRIMARY KEY,
    person_id TEXT NOT NULL,
    name_enc TEXT NOT NULL,
    birth_data_enc TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_letters_person_date ON letters(person_id, letter_date);
CREATE INDEX IF NOT EXISTS idx_related_persons_owner ON related_persons(person_id);
CREATE INDEX IF NOT EXISTS idx_fragment_lights_person_time ON fragment_lights(person_id, lit_at);
CREATE INDEX IF NOT EXISTS idx_conversations_person ON conversations(person_id);
CREATE INDEX IF NOT EXISTS idx_memory_person ON memory_items(person_id);
CREATE INDEX IF NOT EXISTS idx_memory_session ON memory_items(session_id);
CREATE INDEX IF NOT EXISTS idx_journal_person ON journal_entries(person_id);
CREATE INDEX IF NOT EXISTS idx_life_events_person ON life_events(person_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_push_subscriptions_person ON push_subscriptions(person_id);
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


def _birth_to_json(birth) -> str:
    """BirthData → JSON 字符串（datetime → ISO8601）。与 repository.py 同格式。"""
    from dataclasses import asdict

    data = asdict(birth)
    data["datetime_utc"] = birth.datetime_utc.isoformat()
    return json.dumps(data, ensure_ascii=False)


def _birth_from_json(raw: str) -> Any:
    """JSON 字符串 → BirthData（ISO8601 → datetime）。"""
    from shared.models.person import BirthData, GeoLocation

    data: dict[str, Any] = json.loads(raw)
    loc_data = data["location"]
    location = GeoLocation(
        latitude=loc_data["latitude"],
        longitude=loc_data["longitude"],
        altitude=loc_data.get("altitude", 0.0),
        timezone_name=loc_data.get("timezone_name", "UTC"),
        place_name=loc_data.get("place_name", ""),
    )
    return BirthData(
        datetime_utc=datetime.fromisoformat(data["datetime_utc"]),
        location=location,
        time_known=bool(data.get("time_known", True)),
    )


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
    # 旧库可能存宝石人格值（zircon/rose_quartz…）——10 星灵回归后非法，兜底默认月亮。
    persona = PersonaType.MOON
    if d.get("persona"):
        try:
            persona = PersonaType(d["persona"])
        except ValueError:
            persona = PersonaType.MOON
    return Conversation(
        id=d["id"],
        person_id=d["person_id"],
        persona=persona,
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


# ----------------------------------------------------------------------
# 合规导出：各表 → 明文 dict（datetime 转 ISO，可直接 JSON 序列化）
# ----------------------------------------------------------------------


def _memory_item_to_dict(m: MemoryItem) -> dict:
    return {
        "id": m.id,
        "session_id": m.session_id,
        "person_id": m.person_id,
        "role": m.role.value,
        "content": m.content,
        "timestamp": _iso(m.timestamp),
        "metadata": m.metadata,
    }


def _journal_to_dict(j: JournalEntry) -> dict:
    return {
        "id": j.id,
        "person_id": j.person_id,
        "content": j.content,
        "mood": j.mood,
        "ai_summary": j.ai_summary,
        "related_intent_id": j.related_intent_id,
        "related_conclusion_id": j.related_conclusion_id,
        "created_at": _iso(j.created_at),
        "updated_at": _iso(j.updated_at),
    }


def _life_event_to_dict(e: LifeEvent) -> dict:
    return {
        "id": e.id,
        "person_id": e.person_id,
        "occurred_at": _iso(e.occurred_at),
        "label": e.label,
        "kind": e.kind,
        "detail": e.detail,
        "related_journal_id": e.related_journal_id,
        "related_intent_id": e.related_intent_id,
        "related_conclusion_id": e.related_conclusion_id,
        "domain": e.domain,
        "need": e.need,
        "created_at": _iso(e.created_at),
    }


def _letter_to_dict(l: Letter) -> dict:
    return {
        "id": l.id,
        "person_id": l.person_id,
        "letter_date": l.letter_date,
        "sender": l.sender,
        "title": l.title,
        "body": l.body,
        "kind": l.kind,
        "created_at": _iso(l.created_at),
        "read_at": _iso(l.read_at) if l.read_at else None,
        "metadata": l.metadata,
    }


def _fragment_light_to_dict(f: FragmentLight) -> dict:
    return {
        "subtype_id": f.subtype_id,
        "delta": f.delta,
        "kind": f.kind,
        "source": f.source,
        "lit_at": _iso(f.lit_at),
        "session_id": f.session_id,
    }


def _push_subscription_to_dict(s: PushSubscription) -> dict:
    return {
        "person_id": s.person_id,
        "endpoint": s.endpoint,
        "p256dh": s.p256dh,
        "auth": s.auth,
        "created_at": _iso(s.created_at),
    }


def _birth_to_dict(birth) -> dict:
    """BirthData → 明文 dict（datetime → ISO，导出 JSON 友好）。"""
    from dataclasses import asdict

    data = asdict(birth)
    data["datetime_utc"] = birth.datetime_utc.isoformat()
    return data


#: profiles 表的增量迁移：CREATE TABLE IF NOT EXISTS 不会改已有表，
#: 这里对已存在的旧库用 ALTER TABLE 补齐新列（A2 trust / B2 preferences）。
_PROFILE_MIGRATIONS = (
    ("trust_score", "REAL NOT NULL DEFAULT 0"),
    ("trust_signals_json_enc", "TEXT NOT NULL DEFAULT ''"),
    ("preferences_json_enc", "TEXT NOT NULL DEFAULT ''"),
    ("fragments_json_enc", "TEXT NOT NULL DEFAULT ''"),
)

#: life_events 表的增量迁移（咨询记录补 intent/need，喂记忆写回）。
_LIFE_EVENT_MIGRATIONS = (
    ("domain", "TEXT DEFAULT ''"),
    ("need", "TEXT DEFAULT ''"),
)

#: fragment_lights 表的增量迁移（触发行动 +20：账本标所属会话，精确回溯"上一段会话点亮"）。
_FRAGMENT_LIGHT_MIGRATIONS = (
    ("session_id", "TEXT DEFAULT ''"),
)

#: letters 表的增量迁移（首页红点：追踪来信是否已读）。
_LETTER_MIGRATIONS = (
    ("read_at", "TEXT DEFAULT NULL"),
)


def _ensure_profile_columns(conn: sqlite3.Connection) -> None:
    """为已存在的 profiles 表补齐缺失列（幂等）。"""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(profiles)")}
    for name, decl in _PROFILE_MIGRATIONS:
        if name not in cols:
            conn.execute(f"ALTER TABLE profiles ADD COLUMN {name} {decl}")
            logger.info("profiles 表迁移：新增列 %s", name)
    conn.commit()


def _ensure_life_event_columns(conn: sqlite3.Connection) -> None:
    """为已存在的 life_events 表补齐缺失列（幂等，同 _ensure_profile_columns）。"""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(life_events)")}
    for name, decl in _LIFE_EVENT_MIGRATIONS:
        if name not in cols:
            conn.execute(f"ALTER TABLE life_events ADD COLUMN {name} {decl}")
            logger.info("life_events 表迁移：新增列 %s", name)
    conn.commit()


def _ensure_fragment_light_columns(conn: sqlite3.Connection) -> None:
    """为已存在的 fragment_lights 表补齐缺失列（幂等，同 _ensure_profile_columns）。

    旧库（2A 建的账本）无 session_id 列 → ALTER 补齐，旧数据 session_id=''。
    session 索引也在迁移后建（_SCHEMA 里的旧表在补列前建索引会炸，必须后置）。
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(fragment_lights)")}
    for name, decl in _FRAGMENT_LIGHT_MIGRATIONS:
        if name not in cols:
            conn.execute(f"ALTER TABLE fragment_lights ADD COLUMN {name} {decl}")
            logger.info("fragment_lights 表迁移：新增列 %s", name)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_fragment_lights_session "
        "ON fragment_lights(person_id, session_id)"
    )
    conn.commit()


def _ensure_letter_columns(conn: sqlite3.Connection) -> None:
    """为已存在的 letters 表补齐缺失列（幂等，同 _ensure_profile_columns）。

    首页红点：旧信 read_at=NULL（未读），打开信箱标记已读后才有值。
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(letters)")}
    for name, decl in _LETTER_MIGRATIONS:
        if name not in cols:
            conn.execute(f"ALTER TABLE letters ADD COLUMN {name} {decl}")
            logger.info("letters 表迁移：新增列 %s", name)
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
        # 生产并发：WAL（多读一写 + 崩溃恢复稳）+ busy_timeout（锁时等待，不立刻报错）。
        # 推送 cron（scripts/push_daily.py 外部进程）与用户请求可能同时写——WAL 是关键。
        self._conn.execute("PRAGMA journal_mode=WAL").fetchone()  # 消费返回行，避免残留游标
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_SCHEMA)
        _ensure_profile_columns(self._conn)   # 旧库补齐 A2 新增列
        _ensure_life_event_columns(self._conn)  # 旧库补齐 life_events 新增列
        _ensure_fragment_light_columns(self._conn)  # 旧库补齐 fragment_lights 新增列
        _ensure_letter_columns(self._conn)    # 旧库补齐 letters 新增列（首页红点 read_at）
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
            fragments={
                str(k): int(v) for k, v in (
                    _load(self._encryptor.decrypt(row["fragments_json_enc"])) if row["fragments_json_enc"] else {}
                ).items()
            },
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
                     fragments_json_enc,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(person_id) DO UPDATE SET
                    lord_states_json_enc = excluded.lord_states_json_enc,
                    verified_findings_json_enc = excluded.verified_findings_json_enc,
                    key_dates_json_enc = excluded.key_dates_json_enc,
                    domain_summaries_json_enc = excluded.domain_summaries_json_enc,
                    trust_score = excluded.trust_score,
                    trust_signals_json_enc = excluded.trust_signals_json_enc,
                    preferences_json_enc = excluded.preferences_json_enc,
                    fragments_json_enc = excluded.fragments_json_enc,
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
                    self._encryptor.encrypt(_dump(profile.fragments or {})),
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
                     related_journal_id, related_intent_id, related_conclusion_id,
                     domain, need, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    event.domain,
                    event.need,
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
            domain=row["domain"] or "",
            need=row["need"] or "",
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
                     kind, created_at, read_at, metadata_json_enc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    _iso(letter.read_at) if letter.read_at else None,
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
            read_at=_from_iso(row["read_at"]) if row["read_at"] else None,
            metadata=_load(self._encryptor.decrypt(meta_raw)) if meta_raw else {},
        )

    def mark_letters_read_today(self, person_id: str, letter_date: str) -> int:
        """把该人某日（letter_date=YYYY-MM-DD）未读的信标记为已读。返回标记数。

        首页红点 = 今日来信未读；打开信箱时调这个，红点即刻消除。
        只更新 read_at IS NULL 的行（已读过的幂等跳过）。
        """
        now = _iso(None)  # 当前 UTC，统一时戳
        with self._conn:
            cur = self._conn.execute(
                "UPDATE letters SET read_at = ? WHERE person_id = ? AND letter_date = ? AND read_at IS NULL",
                (now, person_id, letter_date),
            )
        return cur.rowcount

    # ------------------------------------------------------------------
    # Fragment lights（34 子类点亮账本，成长复利层地基）
    # ------------------------------------------------------------------

    def append_fragment_lights(
        self,
        person_id: str,
        lights: list[FragmentLight],
        session_id: str = "",
    ) -> None:
        """追加账本记录。累计深度仍走 profiles.fragments（单一事实源），
        本账本是追加式事件日志，供今日碎片/报告/反转/行运按时间聚合。

        session_id：本轮所有点亮所属会话（conversation.id），统一盖章落库——
        触发行动（§4.2 +20）靠它精确回溯"上一段会话点亮的子类"。

        隐私红线：subtype_id/delta/kind/lit_at 非敏感明文，source（消息片段）加密。
        """
        if not lights:
            return
        now = _iso(None)
        with self._conn:
            self._conn.executemany(
                """
                INSERT INTO fragment_lights
                    (id, person_id, subtype_id, delta, kind, source_enc, lit_at, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        new_id("lit"),
                        person_id,
                        l.subtype_id,
                        int(l.delta),
                        l.kind,
                        self._encryptor.encrypt(l.source),
                        _iso(l.lit_at) or now,
                        session_id or l.session_id,
                    )
                    for l in lights
                ],
            )

    def list_fragment_lights(
        self,
        person_id: str,
        since: datetime | None = None,
        session_id: str | None = None,
        limit: int = 500,
    ) -> list[FragmentLight]:
        """查账本（新的在前）。since 传"某天 00:00"即可做"今日碎片"按日聚合；
        session_id 传某段会话（conversation.id）即可回溯"那段会话点亮过哪些子类"。
        """
        sql = "SELECT * FROM fragment_lights WHERE person_id = ?"
        params: list[Any] = [person_id]
        if since is not None:
            sql += " AND lit_at >= ?"
            params.append(since.isoformat())
        if session_id:
            sql += " AND session_id = ?"
            params.append(session_id)
        sql += " ORDER BY lit_at DESC LIMIT ?"
        params.append(limit)
        with self._conn:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._fragment_light_from_row(r) for r in rows]

    def count_fragment_actions(self, person_id: str) -> dict[str, int]:
        """每个子类被"触发行动"（kind=action）点亮过几次 → subtype_id: count。

        升顶门槛（§4.2）：4 级需 ≥1 次行动，5 级需 ≥2 次行动——按账本真做过的次数算。
        """
        with self._conn:
            rows = self._conn.execute(
                """
                SELECT subtype_id, COUNT(*) AS n
                FROM fragment_lights
                WHERE person_id = ? AND kind = 'action'
                GROUP BY subtype_id
                """,
                (person_id,),
            ).fetchall()
        return {r["subtype_id"]: int(r["n"]) for r in rows}

    def _fragment_light_from_row(self, row: sqlite3.Row) -> FragmentLight:
        return FragmentLight(
            subtype_id=row["subtype_id"],
            delta=row["delta"],
            kind=row["kind"],
            source=self._encryptor.decrypt(row["source_enc"]) if row["source_enc"] else "",
            lit_at=_from_iso(row["lit_at"]),
            session_id=row["session_id"] if "session_id" in row.keys() else "",
        )

    # --- Push subscriptions（Web Push 订阅）---

    def save_push_subscription(self, sub: PushSubscription) -> None:
        """Upsert 一条推送订阅（复合主键 person_id + endpoint，同人多设备共存）。

        p256dh/auth 是定向加密推送的密钥，属于敏感数据，加密落库（*_enc 列）。
        """
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO push_subscriptions
                    (person_id, endpoint, p256dh_enc, auth_enc, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(person_id, endpoint) DO UPDATE SET
                    p256dh_enc = excluded.p256dh_enc,
                    auth_enc = excluded.auth_enc,
                    created_at = excluded.created_at
                """,
                (
                    sub.person_id,
                    sub.endpoint,
                    self._encryptor.encrypt(sub.p256dh or ""),
                    self._encryptor.encrypt(sub.auth or ""),
                    _iso(sub.created_at),
                ),
            )

    def delete_push_subscription(self, person_id: str, endpoint: str) -> bool:
        """删一条订阅（该 endpoint 失效/用户退订）。真的删了 → True。"""
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM push_subscriptions WHERE person_id = ? AND endpoint = ?",
                (person_id, endpoint),
            )
        return cur.rowcount > 0

    def list_push_subscriptions(
        self, person_id: str | None = None
    ) -> list[PushSubscription]:
        """列订阅。person_id=None → 全部（每日推送遍历用）。"""
        if person_id is not None:
            sql = "SELECT * FROM push_subscriptions WHERE person_id = ?"
            params: list[Any] = [person_id]
        else:
            sql = "SELECT * FROM push_subscriptions"
            params = []
        with self._conn:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._push_subscription_from_row(r) for r in rows]

    def _push_subscription_from_row(self, row: sqlite3.Row) -> PushSubscription:
        return PushSubscription(
            person_id=row["person_id"],
            endpoint=row["endpoint"],
            p256dh=self._encryptor.decrypt(row["p256dh_enc"]) if row["p256dh_enc"] else "",
            auth=self._encryptor.decrypt(row["auth_enc"]) if row["auth_enc"] else "",
            created_at=_from_iso(row["created_at"]),
        )

    # --- Related persons（合盘对象，多轮持久化）---

    def save_related_person(
        self,
        related_id: str,
        person_id: str,
        name: str,
        birth_data_json: str,
        gender: str = "",
        notes: str = "",
    ) -> str:
        """Upsert 保存一个合盘对象（出生数据 Fernet 加密）。

        birth_data_json = `_birth_to_json(birth)` 的输出（与 persons 表同格式）。
        返回 related_id（调用方生成，跨层复用同一 id）。
        """
        now = _iso(None)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO related_persons
                    (id, person_id, name_enc, birth_data_enc, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    person_id = excluded.person_id,
                    name_enc = excluded.name_enc,
                    birth_data_enc = excluded.birth_data_enc,
                    updated_at = excluded.updated_at
                """,
                (
                    related_id,
                    person_id,
                    self._encryptor.encrypt(name),
                    self._encryptor.encrypt(birth_data_json),
                    now,
                    now,
                ),
            )
        return related_id

    def list_related_persons(self, person_id: str) -> list[dict]:
        """列某用户保存的合盘对象（只解密 name，不碰出生数据——列表视图够用）。"""
        with self._conn:
            rows = self._conn.execute(
                "SELECT * FROM related_persons WHERE person_id = ? ORDER BY created_at DESC",
                (person_id,),
            ).fetchall()
        out: list[dict] = []
        for row in rows:
            data = self._related_person_to_dict(row, include_birth=False)
            if data is not None:
                out.append(data)
        return out

    def get_related_person(self, related_id: str) -> dict | None:
        """按 id 取完整合盘对象（含解密出生数据）。不存在 → None。"""
        with self._conn:
            row = self._conn.execute(
                "SELECT * FROM related_persons WHERE id = ?", (related_id,)
            ).fetchone()
        if row is None:
            return None
        return self._related_person_to_dict(row, include_birth=True)

    def delete_related_person(self, related_id: str) -> bool:
        """删合盘对象（合规：用户可随时删除数据）。真的删了 → True。"""
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM related_persons WHERE id = ?", (related_id,)
            )
        return cur.rowcount > 0

    def _related_person_to_dict(
        self, row: sqlite3.Row, include_birth: bool
    ) -> dict | None:
        """SQLite 行 → 解密 dict。birth 字段按需解析（列表视图不碰加密出生数据）。"""
        try:
            d: dict = {
                "id": row["id"],
                "person_id": row["person_id"],
                "name": self._encryptor.decrypt(row["name_enc"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            if include_birth:
                birth_json = self._encryptor.decrypt(row["birth_data_enc"])
                d["birth_data"] = _birth_from_json(birth_json)
            return d
        except Exception:  # noqa: BLE001 - 解密失败不炸整列表，跳过该行
            logger.warning("合盘对象解密失败，跳过: %s", row["id"])
            return None

    # ------------------------------------------------------------------
    # 合规：全量删除 + 数据导出（PRD §8「可随时删除数据」）
    # ------------------------------------------------------------------

    def purge_person(self, person_id: str) -> dict[str, int]:
        """合规全量删除：清空该人所有业务表数据（级联）。返回各表删除行数。

        幂等：无数据 → 全 0，不炸。persons 表不在本类职责
        （属 PersonRepository，由 API 层调 repo.delete 一并删）。
        """
        tables = (
            "conversations", "memory_items", "profiles", "journal_entries",
            "life_events", "letters", "fragment_lights", "push_subscriptions",
            "related_persons",
        )
        counts: dict[str, int] = {}
        with self._conn:
            for table in tables:
                cur = self._conn.execute(
                    f"DELETE FROM {table} WHERE person_id = ?", (person_id,)
                )
                counts[table] = cur.rowcount
        return counts

    def export_person(self, person_id: str) -> dict:
        """合规全量导出：聚合该人所有表的解密数据（供下载/迁移/删除前存档）。

        所有 datetime 已转 ISO 字符串（可直接 JSON 序列化）；PII 全部解密。
        出生数据（persons 表）在 PersonRepository，由 API 层合并进 PersonOut。
        """
        profile = self.get_profile(person_id)
        out: dict[str, Any] = {
            "profile": None,
            "conversations": [
                _conversation_to_dict(c) for c in self.list_conversations(person_id)
            ],
            "memory_items": [
                _memory_item_to_dict(m) for m in self.list_memory_items(person_id=person_id)
            ],
            "journal_entries": [_journal_to_dict(j) for j in self.list_journals(person_id)],
            "life_events": [_life_event_to_dict(e) for e in self.list_life_events(person_id)],
            "letters": [_letter_to_dict(l) for l in self.list_letters(person_id)],
            "fragment_lights": [
                _fragment_light_to_dict(f) for f in self.list_fragment_lights(person_id)
            ],
            "push_subscriptions": [
                _push_subscription_to_dict(s)
                for s in self.list_push_subscriptions(person_id)
            ],
            "related_persons": [],
        }
        if profile is not None:
            out["profile"] = {
                "person_id": profile.person_id,
                "lord_states": profile.lord_states,
                "verified_findings": [_finding_to_dict(f) for f in profile.verified_findings],
                "key_dates": [_keydate_to_dict(k) for k in profile.key_dates],
                "domain_summaries": {
                    d: _summary_to_dict(s) for d, s in profile.domain_summaries.items()
                },
                "trust_score": profile.trust_score,
                "trust_signals": profile.trust_signals,
                "preferences": profile.preferences,
                "fragments": profile.fragments,
                "created_at": _iso(profile.created_at),
                "updated_at": _iso(profile.updated_at),
            }
        # 合盘对象：列表只含名字，导出需补出生数据（明文 dict）
        for d in self.list_related_persons(person_id):
            full = self.get_related_person(d["id"])
            if full is None:
                continue
            full["birth_data"] = _birth_to_dict(full["birth_data"])
            out["related_persons"].append(full)
        return out

    def get_recall_data(self, person_id: str) -> dict:
        """记忆召回素材豆荚：聚合画像 + 点亮账本 + 会话摘要（"我记得你"）。

        返回全是明文 dict（PII 已解密）。API 层据此组装 RecallItem：
        - key_dates: 画像关键日期，≤5
        - confirmed_findings: 用户确认过的沉淀判断，≤3
        - domain_summaries: 有摘要的领域，≤3（confidence 降序）
        - top_fragments: 账本聚合累计深度 top 3
        - recent_topics: 最近 3 次会话摘要（naturalize 由 API 层做，store 保持纯净）
        """
        out: dict[str, Any] = {
            "key_dates": [],
            "confirmed_findings": [],
            "domain_summaries": [],
            "top_fragments": [],
            "recent_topics": [],
        }
        profile = self.get_profile(person_id)
        if profile is not None:
            out["key_dates"] = [
                {"label": k.label, "at": _iso(k.date)} for k in profile.key_dates[:5]
            ]
            out["confirmed_findings"] = [
                {"statement": f.statement, "at": _iso(f.confirmed_at)}
                for f in profile.verified_findings
                if f.user_feedback == "confirmed"
            ][:3]
            summaries = [
                {"domain": d, "summary": s.summary, "confidence": s.confidence}
                for d, s in profile.domain_summaries.items()
                if s.summary
            ]
            out["domain_summaries"] = sorted(
                summaries, key=lambda x: x.get("confidence", 0.0), reverse=True
            )[:3]
        # 账本聚合：子类 → 累计深度（跨天全量，供"越走越亮"的长期共振叙事）
        agg: dict[str, int] = {}
        for light in self.list_fragment_lights(person_id):
            agg[light.subtype_id] = agg.get(light.subtype_id, 0) + int(light.delta)
        out["top_fragments"] = [
            {"subtype_id": fid, "depth": depth}
            for fid, depth in sorted(agg.items(), key=lambda kv: kv[1], reverse=True)[:3]
        ]
        out["recent_topics"] = self.list_conversation_summaries(person_id, limit=3)
        return out

    def close(self) -> None:
        self._conn.close()


__all__ = ["GardenStore"]
