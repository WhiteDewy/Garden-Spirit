"""GardenStore 跨会话持久化测试（第四层记忆的地基）。

验证：
- Conversation 保存/读取/摘要列表
- ChartProfile 全结构往返（lord_states / verified_findings / key_dates / domain_summaries）
- JournalEntry 增改查
- LifeEvent 增查 + 时间排序
- MemoryItem 按 person/session 过滤
- 隐私字段加密落库（明文不可见）
"""

import sqlite3
from datetime import datetime, timedelta, timezone

from foundation.database import Encryptor
from foundation.database.encryption import _generate_key
from foundation.database.store import GardenStore
from foundation.utils import new_id
from shared.enums import PersonaType, Role
from shared.models import (
    ChartProfile,
    Conversation,
    DialogueTurn,
    DomainSummary,
    JournalEntry,
    KeyDate,
    LifeEvent,
    MemoryItem,
    VerifiedFinding,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_conversation(person_id: str = "p1", persona: PersonaType = PersonaType.ZIRCON) -> Conversation:
    conv = Conversation(
        id=new_id("conv"),
        person_id=person_id,
        persona=persona,
        started_at=_now(),
        is_active=True,
    )
    conv.add_turn(DialogueTurn(
        id=new_id("t"),
        user_message="你好，我想问事业",
        assistant_response="正在看你的星图……",
        persona_used=persona,
        timestamp=_now(),
    ))
    return conv


def _make_profile(person_id: str = "p1") -> ChartProfile:
    now = _now()
    prof = ChartProfile(person_id=person_id, created_at=now, updated_at=now)
    prof.lord_states["moon_in_7"] = "观察中"
    prof.verified_findings.append(VerifiedFinding(
        id=new_id("f"), statement="土星落九宫：深造是职业跃迁的必经之路", confidence=0.8,
    ))
    prof.key_dates.append(KeyDate(id=new_id("k"), date=now, label="考虑离职", kind="event"))
    prof.domain_summaries["career"] = DomainSummary(
        domain="career", summary="最近三个月你越来越相信自己的判断", confidence=0.6, updated_at=now,
    )
    return prof


# --- Conversation ---

def test_conversation_roundtrip():
    store = GardenStore(":memory:")
    conv = _make_conversation()
    store.save_conversation(conv, summary="开场寒暄")
    got = store.get_conversation(conv.id)
    assert got is not None
    assert got.person_id == "p1"
    assert got.turns[0].user_message == "你好，我想问事业"
    assert got.turns[0].persona_used == PersonaType.ZIRCON


def test_conversation_get_nonexistent():
    store = GardenStore(":memory:")
    assert store.get_conversation("ghost") is None


def test_conversation_summaries():
    store = GardenStore(":memory:")
    store.save_conversation(_make_conversation(), summary="第一次")
    store.save_conversation(_make_conversation(), summary="第二次")
    sums = store.list_conversation_summaries("p1")
    assert len(sums) == 2
    assert {s["summary"] for s in sums} == {"第一次", "第二次"}
    # 摘要列表不泄露 turns 正文
    assert all("user_message" not in s for s in sums)


def test_conversation_active_filter():
    store = GardenStore(":memory:")
    conv = _make_conversation()
    store.save_conversation(conv, summary="active")
    done = _make_conversation()
    done.is_active = False
    store.save_conversation(done, summary="done")
    active = store.list_conversations("p1", active_only=True)
    assert len(active) == 1
    assert active[0].id == conv.id


# --- Profile ---

def test_profile_roundtrip_all_structures():
    store = GardenStore(":memory:")
    store.save_profile(_make_profile())
    got = store.get_profile("p1")
    assert got is not None
    assert got.lord_states["moon_in_7"] == "观察中"
    assert got.verified_findings[0].statement == "土星落九宫：深造是职业跃迁的必经之路"
    assert got.key_dates[0].label == "考虑离职"
    assert got.domain_summaries["career"].summary == "最近三个月你越来越相信自己的判断"


def test_profile_get_nonexistent():
    store = GardenStore(":memory:")
    assert store.get_profile("ghost") is None


def test_profile_upsert_updates():
    store = GardenStore(":memory:")
    store.save_profile(_make_profile())
    prof = _make_profile()
    prof.lord_states["saturn_in_9"] = "追加观察"
    store.save_profile(prof)
    got = store.get_profile("p1")
    assert got.lord_states["moon_in_7"] == "观察中"      # 旧字段不丢
    assert got.lord_states["saturn_in_9"] == "追加观察"   # 新字段写入


def test_profile_trust_fields_roundtrip():
    """A2 关系层：信任分与信号计数跨存储往返不丢。"""
    store = GardenStore(":memory:")
    prof = _make_profile()
    prof.trust_score = 12.5
    prof.trust_signals = {"deep_consult": 2, "journal": 1, "finding_confirmed": 1}
    store.save_profile(prof)

    got = store.get_profile("p1")
    assert got.trust_score == 12.5
    assert got.trust_signals == {"deep_consult": 2, "journal": 1, "finding_confirmed": 1}
    # 非信任字段不受影响
    assert got.domain_summaries["career"].summary == "最近三个月你越来越相信自己的判断"


def test_profile_trust_defaults_zero():
    store = GardenStore(":memory:")
    store.save_profile(_make_profile())  # 未设置信任字段 → 默认
    got = store.get_profile("p1")
    assert got.trust_score == 0.0
    assert got.trust_signals == {}


# --- Journal ---

def test_journal_roundtrip():
    store = GardenStore(":memory:")
    now = _now()
    entry = JournalEntry(
        id=new_id("j"), person_id="p1", content="今天有点迷茫",
        mood="迷茫", ai_summary="AI 生成的成长记录",
        created_at=now, updated_at=now,
    )
    store.save_journal(entry)
    got = store.get_journal(entry.id)
    assert got.content == "今天有点迷茫"
    assert got.mood == "迷茫"
    assert got.ai_summary == "AI 生成的成长记录"


def test_journal_update_after_edit():
    """用户编辑后覆盖 content，ai_summary 保留。"""
    store = GardenStore(":memory:")
    now = _now()
    entry = JournalEntry(id=new_id("j"), person_id="p1", content="初稿", created_at=now, updated_at=now)
    store.save_journal(entry)
    entry.content = "编辑后的正文"
    store.save_journal(entry)
    got = store.get_journal(entry.id)
    assert got.content == "编辑后的正文"


def test_journal_list_orders_by_created_desc():
    store = GardenStore(":memory:")
    t1, t2, t3 = _now(), _now() + timedelta(hours=1), _now() + timedelta(hours=2)
    store.save_journal(JournalEntry(id=new_id("j"), person_id="p1", content="一", created_at=t1, updated_at=t1))
    store.save_journal(JournalEntry(id=new_id("j"), person_id="p1", content="二", created_at=t2, updated_at=t2))
    store.save_journal(JournalEntry(id=new_id("j"), person_id="p1", content="三", created_at=t3, updated_at=t3))
    entries = store.list_journals("p1")
    assert [e.content for e in entries] == ["三", "二", "一"]


# --- LifeEvent ---

def test_life_event_roundtrip():
    store = GardenStore(":memory:")
    event = LifeEvent(
        id=new_id("l"), person_id="p1", occurred_at=_now(),
        label="真正辞职", kind="life", detail="已提交离职",
    )
    store.save_life_event(event)
    got = store.list_life_events("p1")
    assert len(got) == 1
    assert got[0].label == "真正辞职"
    assert got[0].kind == "life"


def test_life_event_orders_desc():
    store = GardenStore(":memory:")
    t1, t2 = _now() - timedelta(days=10), _now()
    store.save_life_event(LifeEvent(id=new_id("l"), person_id="p1", occurred_at=t1, label="旧"))
    store.save_life_event(LifeEvent(id=new_id("l"), person_id="p1", occurred_at=t2, label="新"))
    got = store.list_life_events("p1")
    assert [e.label for e in got] == ["新", "旧"]


# --- MemoryItem ---

def test_memory_item_roundtrip_and_filter():
    store = GardenStore(":memory:")
    now = _now()
    item = MemoryItem(
        id=new_id("mem"), session_id="s1", person_id="p1", role=Role.USER,
        content="敏感对话内容", timestamp=now, metadata={"intent_id": "i1"},
    )
    store.save_memory_item(item)
    assert store.list_memory_items(person_id="p1")[0].content == "敏感对话内容"
    assert store.list_memory_items(session_id="s1")[0].metadata["intent_id"] == "i1"
    assert store.list_memory_items(person_id="ghost") == []


# --- 隐私红线：加密落库 ---

def test_store_data_is_encrypted_at_rest(tmp_path):
    db = str(tmp_path / "store.db")
    store = GardenStore(db_path=db, encryptor=Encryptor(key=_generate_key()))
    store.save_profile(_make_profile())
    store.save_journal(JournalEntry(id=new_id("j"), person_id="p1", content="私密日记", created_at=_now(), updated_at=_now()))
    store.save_conversation(_make_conversation(), summary="敏感摘要")
    store.save_life_event(LifeEvent(id=new_id("l"), person_id="p1", occurred_at=_now(), label="辞职细节"))

    conn = sqlite3.connect(db)
    cols = []
    for table in ("profiles", "journal_entries", "conversations", "life_events"):
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        for row in rows:
            cols.extend(row)  # 所有值都检查
    conn.close()

    blob = "\n".join(str(c) for c in cols)
    for plaintext in ("考虑离职", "私密日记", "敏感摘要", "辞职细节", "土星落九宫"):
        assert plaintext not in blob, f"明文泄露: {plaintext}"
    assert not blob.startswith("{")
