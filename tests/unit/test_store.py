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
    FragmentLight,
    JournalEntry,
    KeyDate,
    Letter,
    LifeEvent,
    MemoryItem,
    PushSubscription,
    VerifiedFinding,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_conversation(person_id: str = "p1", persona: PersonaType = PersonaType.MOON) -> Conversation:
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
    assert got.turns[0].persona_used == PersonaType.MOON


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


# --- Fragment lights（成长复利账本）---

def test_fragment_lights_roundtrip():
    store = GardenStore(":memory:")
    store.append_fragment_lights("p1", [
        FragmentLight(subtype_id="moon_tide", delta=3, kind="outpouring",
                      source="我最近总是心情不好", lit_at=_now()),
        FragmentLight(subtype_id="sun_core", delta=1, kind="mention",
                      source="", lit_at=_now()),
    ])
    lights = store.list_fragment_lights("p1")
    assert len(lights) == 2
    by_id = {l.subtype_id: l for l in lights}
    assert by_id["moon_tide"].delta == 3
    assert by_id["moon_tide"].kind == "outpouring"
    assert by_id["moon_tide"].source == "我最近总是心情不好"
    assert by_id["sun_core"].source == ""        # 空来源可往返
    assert store.list_fragment_lights("ghost") == []


def test_fragment_lights_filter_since():
    """since 传"某天 00:00" → 只取当天起的账本（今日灵魂碎片的聚合依据）。"""
    store = GardenStore(":memory:")
    store.append_fragment_lights("p1", [
        FragmentLight(subtype_id="moon_tide", delta=3, kind="outpouring", lit_at=_now() - timedelta(days=2)),
        FragmentLight(subtype_id="sun_core", delta=1, kind="mention", lit_at=_now()),
    ])
    today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    lights = store.list_fragment_lights("p1", since=today)
    assert [l.subtype_id for l in lights] == ["sun_core"]


def test_fragment_lights_session_id_stamp_and_filter():
    """账本按会话盖章（conversation.id）：统一盖 + 按会话回溯（§4.2 触发行动的原料）。"""
    store = GardenStore(":memory:")
    store.append_fragment_lights("p1", [
        FragmentLight(subtype_id="moon_tide", delta=3, kind="outpouring", lit_at=_now()),
        FragmentLight(subtype_id="sun_core", delta=1, kind="mention", lit_at=_now()),
    ], session_id="conv_a")
    # 统一盖章：本轮所有点亮都属于当前会话
    assert {l.session_id for l in store.list_fragment_lights("p1")} == {"conv_a"}
    # 按会话精确回溯
    assert len(store.list_fragment_lights("p1", session_id="conv_a")) == 2
    assert store.list_fragment_lights("p1", session_id="conv_b") == []
    # 调用方不传 session_id → 用条目自带的（兼容"预盖章条目"）
    store.append_fragment_lights("p1", [
        FragmentLight(subtype_id="pluto_depth", delta=20, kind="action",
                      session_id="conv_c", lit_at=_now()),
    ])
    assert store.list_fragment_lights("p1", session_id="conv_c")[0].subtype_id == "pluto_depth"
    # 调用方盖的章优先于条目自带
    store.append_fragment_lights("p1", [
        FragmentLight(subtype_id="venus_love", delta=5, kind="seen",
                      session_id="conv_c", lit_at=_now()),
    ], session_id="conv_d")
    assert store.list_fragment_lights("p1", session_id="conv_d")[0].subtype_id == "venus_love"
    assert store.list_fragment_lights("p1", session_id="conv_c")[-1].subtype_id == "pluto_depth"


def test_count_fragment_actions():
    """触发行动计数（§4.2 升顶门槛）：每个子类 kind=action 的次数 → subtype: count。"""
    store = GardenStore(":memory:")
    store.append_fragment_lights("p1", [
        FragmentLight(subtype_id="sun_core", delta=20, kind="action", lit_at=_now()),
        FragmentLight(subtype_id="sun_core", delta=20, kind="action", lit_at=_now()),
        FragmentLight(subtype_id="moon_tide", delta=20, kind="action", lit_at=_now()),
        FragmentLight(subtype_id="moon_tide", delta=3, kind="outpouring", lit_at=_now()),
        FragmentLight(subtype_id="venus_love", delta=5, kind="seen", lit_at=_now()),
    ])
    assert store.count_fragment_actions("p1") == {"sun_core": 2, "moon_tide": 1}
    assert store.count_fragment_actions("ghost") == {}


def test_fragment_lights_migration_adds_session_id(tmp_path):
    """旧库（2A 建的账本，无 session_id 列）→ 迁移补齐列 + 建 session 索引，旧数据兼容。

    这是 §4.2 触发行动的地基：老用户的账本不丢，新列自动 ALTER，旧数据 session_id=''。
    """
    db = str(tmp_path / "old_store.db")
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE fragment_lights (
        id TEXT PRIMARY KEY,
        person_id TEXT NOT NULL,
        subtype_id TEXT NOT NULL,
        delta INTEGER NOT NULL,
        kind TEXT NOT NULL DEFAULT 'mention',
        source_enc TEXT DEFAULT '',
        lit_at TEXT NOT NULL
    )""")
    conn.execute(
        "INSERT INTO fragment_lights VALUES ('lit_old','p1','moon_tide',3,'mention','','2026-08-01T00:00:00+00:00')"
    )
    conn.commit()
    conn.close()

    store = GardenStore(db)
    # 迁移后：旧数据 session_id 归 ''（可回溯 = 无归属会话）
    lights = store.list_fragment_lights("p1")
    assert len(lights) == 1
    assert lights[0].session_id == ""
    # 新写入可带 session_id + session 索引已建（查询不炸）
    store.append_fragment_lights("p1", [
        FragmentLight(subtype_id="sun_core", delta=1, kind="mention", lit_at=_now()),
    ], session_id="conv_x")
    assert store.list_fragment_lights("p1", session_id="conv_x")[0].subtype_id == "sun_core"
    # 触发行动计数正常
    assert store.count_fragment_actions("p1") == {}


# --- 隐私红线：加密落库 ---

def test_store_data_is_encrypted_at_rest(tmp_path):
    db = str(tmp_path / "store.db")
    store = GardenStore(db_path=db, encryptor=Encryptor(key=_generate_key()))
    store.save_profile(_make_profile())
    store.save_journal(JournalEntry(id=new_id("j"), person_id="p1", content="私密日记", created_at=_now(), updated_at=_now()))
    store.save_conversation(_make_conversation(), summary="敏感摘要")
    store.save_life_event(LifeEvent(id=new_id("l"), person_id="p1", occurred_at=_now(), label="辞职细节"))
    store.append_fragment_lights("p1", [
        FragmentLight(subtype_id="moon_tide", delta=3, kind="outpouring",
                      source="我最近总是心情不好", lit_at=_now()),
    ])
    # Web Push：p256dh/auth 是定向加密推送密钥，同样加密落库
    store.save_push_subscription(PushSubscription(
        person_id="p1",
        endpoint="https://fcm.googleapis.com/send/ep_xyz",
        p256dh="BOrc4cONBASE64p256dh==",
        auth="AUTHbase64secret==",
    ))

    conn = sqlite3.connect(db)
    cols = []
    for table in ("profiles", "journal_entries", "conversations", "life_events",
                  "fragment_lights", "push_subscriptions"):
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        for row in rows:
            cols.extend(row)  # 所有值都检查
    conn.close()

    blob = "\n".join(str(c) for c in cols)
    for plaintext in ("考虑离职", "私密日记", "敏感摘要", "辞职细节", "土星落九宫",
                      "我最近总是心情不好", "BOrc4cONBASE64p256dh==", "AUTHbase64secret=="):
        assert plaintext not in blob, f"明文泄露: {plaintext}"
    assert not blob.startswith("{")


# --- Push subscriptions（Web Push 订阅）---

def test_push_subscription_roundtrip():
    """订阅加密落库 → 读回解出明文密钥（p256dh/auth 全程只存 *_enc）。"""
    store = GardenStore(":memory:")
    store.save_push_subscription(PushSubscription(
        person_id="p1",
        endpoint="https://fcm.googleapis.com/send/ep_1",
        p256dh="p256dh_alpha",
        auth="auth_alpha",
    ))
    subs = store.list_push_subscriptions("p1")
    assert len(subs) == 1
    assert subs[0].person_id == "p1"
    assert subs[0].endpoint == "https://fcm.googleapis.com/send/ep_1"
    assert subs[0].p256dh == "p256dh_alpha"      # 明文读回（落库是加密的）
    assert subs[0].auth == "auth_alpha"


def test_push_subscription_upsert_updates_keys():
    """同 person+endpoint 再次保存 = 更新密钥（同设备换钥），不产生重复行。"""
    store = GardenStore(":memory:")
    store.save_push_subscription(PushSubscription(
        person_id="p1", endpoint="ep_x", p256dh="old_key", auth="old_auth",
    ))
    store.save_push_subscription(PushSubscription(
        person_id="p1", endpoint="ep_x", p256dh="new_key", auth="new_auth",
    ))
    subs = store.list_push_subscriptions("p1")
    assert len(subs) == 1
    assert subs[0].p256dh == "new_key"
    assert subs[0].auth == "new_auth"


def test_push_subscription_delete():
    """退订：真的删了 → True；删不存在的 → False。"""
    store = GardenStore(":memory:")
    store.save_push_subscription(PushSubscription(person_id="p1", endpoint="ep_x"))
    assert store.delete_push_subscription("p1", "ep_x") is True
    assert store.list_push_subscriptions("p1") == []
    assert store.delete_push_subscription("p1", "ep_x") is False


def test_push_subscription_list_all():
    """list(None) = 全量（每日推送遍历用）；多设备共存互不覆盖。"""
    store = GardenStore(":memory:")
    store.save_push_subscription(PushSubscription(person_id="p1", endpoint="ep_a"))
    store.save_push_subscription(PushSubscription(person_id="p1", endpoint="ep_b"))
    store.save_push_subscription(PushSubscription(person_id="p2", endpoint="ep_c"))
    assert len(store.list_push_subscriptions("p1")) == 2
    assert len(store.list_push_subscriptions()) == 3


def test_push_subscriptions_migration_creates_table(tmp_path):
    """旧库（无 push_subscriptions 表）→ 打开即自动建表，旧数据不受影响。"""
    db = str(tmp_path / "old_store.db")
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE profiles (
        person_id TEXT PRIMARY KEY, profile_enc TEXT NOT NULL
    )""")
    conn.execute("INSERT INTO profiles VALUES ('p_old', 'enc_old')")
    conn.commit()
    conn.close()

    store = GardenStore(db)
    # 新表自动建好，可正常写入/读取
    store.save_push_subscription(PushSubscription(person_id="p1", endpoint="ep_x"))
    assert len(store.list_push_subscriptions("p1")) == 1
    # 旧表数据仍在
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT profile_enc FROM profiles WHERE person_id='p_old'").fetchone()[0] == "enc_old"
    conn.close()


# --- Letters read_at（首页红点：来信已读追踪）---

def test_letter_read_at_roundtrip():
    """read_at 加密落库 → 读回（未设 = None = 未读）。"""
    store = GardenStore(":memory:")
    now = _now()
    store.save_letter(Letter(id="L1", person_id="p1", letter_date="2026-08-10",
                             body="今日来信", read_at=now))
    got = store.get_letter("p1", "2026-08-10")
    assert got is not None
    assert got.read_at == now
    # 未设 read_at 的信 → None（首页红点逻辑：read_at is None = 未读）
    store.save_letter(Letter(id="L2", person_id="p1", letter_date="2026-08-09", body="旧信"))
    assert store.get_letter("p1", "2026-08-09").read_at is None


def test_mark_letters_read_today():
    """标记某日未读的信为已读（幂等）：只更新 read_at IS NULL 的行。"""
    store = GardenStore(":memory:")
    store.save_letter(Letter(id="L_today", person_id="p1", letter_date="2026-08-10", body="今天的"))
    store.save_letter(Letter(id="L_yesterday", person_id="p1", letter_date="2026-08-09", body="昨天的"))

    marked = store.mark_letters_read_today("p1", "2026-08-10")
    assert marked == 1                       # 只标记了今天的
    assert store.get_letter("p1", "2026-08-10").read_at is not None
    assert store.get_letter("p1", "2026-08-09").read_at is None   # 昨天不受影响

    # 幂等：已读过的行不重复标记
    assert store.mark_letters_read_today("p1", "2026-08-10") == 0
    # 他人/他日不受影响
    store.save_letter(Letter(id="L_p2", person_id="p2", letter_date="2026-08-10", body="别人的"))
    assert store.mark_letters_read_today("p1", "2026-08-10") == 0
    assert store.get_letter("p2", "2026-08-10").read_at is None


def test_letters_migration_adds_read_at(tmp_path):
    """旧库（无 read_at 列）→ 打开即自动补齐，旧数据 read_at=None（未读）。"""
    key = _generate_key()
    enc = Encryptor(key=key)
    db = str(tmp_path / "old_letters.db")
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE letters (
        id TEXT PRIMARY KEY,
        person_id TEXT NOT NULL,
        letter_date TEXT NOT NULL,
        sender TEXT NOT NULL,
        title_enc TEXT DEFAULT '',
        body_enc TEXT NOT NULL,
        kind TEXT DEFAULT 'daily',
        created_at TEXT,
        metadata_json_enc TEXT DEFAULT ''
    )""")
    # 用与 GardenStore 相同的加密器写入旧库（title_enc/body_enc 是 Fernet token，换随机 key 会解密失败）
    conn.execute(
        "INSERT INTO letters VALUES ('L_old','p1','2026-08-01','moon',?,?,'daily',NULL,'')",
        (enc.encrypt(""), enc.encrypt("旧信正文")),
    )
    conn.commit()
    conn.close()

    store = GardenStore(db, encryptor=Encryptor(key=key))
    # 迁移后：旧信 read_at 归 None = 未读（首页红点对旧信亮起，打开信箱后消除）
    old = store.get_letter("p1", "2026-08-01")
    assert old is not None
    assert old.read_at is None
    # 新列可正常写入已读
    marked = store.mark_letters_read_today("p1", "2026-08-01")
    assert marked == 1
    assert store.get_letter("p1", "2026-08-01").read_at is not None
