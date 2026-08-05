"""出生数据加密存储测试（PRD §8 红线）。

验证：
- Encryptor 加密/解密往返
- 错误密钥解密失败（不静默）
- PersonRepository CRUD 往返无损
- 空库查询返回 None
"""

from datetime import datetime, timezone

import pytest

from foundation.database import Encryptor, PersonRepository
from foundation.database.encryption import _generate_key
from shared.models.person import BirthData, GeoLocation, Person


def _make_person(person_id: str = "p1", *, time_known: bool = True) -> Person:
    loc = GeoLocation(31.23, 121.47, timezone_name="Asia/Shanghai", place_name="上海")
    src = datetime(1990, 6, 15, 9, 30, tzinfo=timezone.utc)
    if not time_known:
        src = src.replace(hour=12, minute=0)
    birth = BirthData(src, loc, time_known=time_known)
    return Person(id=person_id, name="测试用户", gender="F", birth=birth, notes="备注")


# --- Encryptor ---

def test_encryptor_roundtrip():
    enc = Encryptor(key=_generate_key())
    secret = "出生数据 1990-06-15 09:30 UTC 上海"
    cipher = enc.encrypt(secret)
    assert cipher != secret
    assert enc.decrypt(cipher) == secret


def test_encryptor_wrong_key_fails():
    enc = Encryptor(key=_generate_key())
    cipher = enc.encrypt("secret data")
    enc2 = Encryptor(key=_generate_key())  # 不同密钥
    with pytest.raises(ValueError):
        enc2.decrypt(cipher)


def test_encryptor_env_key_priority(monkeypatch):
    """环境变量 GS_ENCRYPTION_KEY 优先于空参数。"""
    key = _generate_key()
    monkeypatch.setenv("GS_ENCRYPTION_KEY", key)
    enc = Encryptor(key="")
    cipher = enc.encrypt("hello")
    assert enc.decrypt(cipher) == "hello"


# --- PersonRepository ---

def test_repository_roundtrip():
    repo = PersonRepository(db_path=":memory:")
    p = _make_person()
    repo.save(p)
    got = repo.get("p1")
    assert got is not None
    assert got.id == p.id
    assert got.name == p.name
    assert got.gender == p.gender
    assert got.notes == p.notes
    assert got.birth.time_known is True
    assert got.birth.datetime_utc == p.birth.datetime_utc
    assert got.birth.location.place_name == "上海"


def test_repository_roundtrip_time_unknown():
    """time_known=False 出生数据也必须无损往返。"""
    repo = PersonRepository(db_path=":memory:")
    p = _make_person("p2", time_known=False)
    repo.save(p)
    got = repo.get("p2")
    assert got is not None
    assert got.birth.time_known is False
    assert got.birth.datetime_utc.hour == 12


def test_repository_get_nonexistent():
    repo = PersonRepository(db_path=":memory:")
    assert repo.get("ghost") is None


def test_repository_delete():
    repo = PersonRepository(db_path=":memory:")
    repo.save(_make_person("p3"))
    assert repo.delete("p3") is True
    assert repo.get("p3") is None


def test_repository_delete_nonexistent():
    repo = PersonRepository(db_path=":memory:")
    assert repo.delete("ghost") is False


def test_repository_list_all():
    repo = PersonRepository(db_path=":memory:")
    repo.save(_make_person("a"))
    repo.save(_make_person("b"))
    repo.save(_make_person("c"))
    assert {p.id for p in repo.list_all()} == {"a", "b", "c"}


def test_repository_upsert_updates():
    repo = PersonRepository(db_path=":memory:")
    repo.save(_make_person("p5"))
    p = _make_person("p5")
    p.name = "改名了"
    repo.save(p)
    got = repo.get("p5")
    assert got.name == "改名了"


def test_repository_data_is_encrypted_at_rest(tmp_path):
    """DB 里的出生数据必须加密——明文内容不可见。"""
    import sqlite3

    db = str(tmp_path / "test.db")
    repo = PersonRepository(db_path=db)
    p = _make_person("p6")
    repo.save(p)

    conn = sqlite3.connect(db)
    row = conn.execute("SELECT birth_data_encrypted, name_encrypted FROM persons WHERE id='p6'").fetchone()
    conn.close()
    assert row is not None
    # 明文出生数据/名字不能直接出现在库里
    assert "上海" not in row[0]
    assert "测试用户" not in row[1]
    # 也不能是合法的可读 JSON
    assert not row[0].startswith("{")
