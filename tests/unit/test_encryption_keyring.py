"""密钥轮换测试：Encryptor keyring 逐个尝试解密 + rotate_key.py 重加密脚本。

覆盖：
- 旧密文在新密钥 + 旧密钥 keyring 下照常可解
- 新写入永远用最新密钥（旧密钥单独解不开）
- 全部密钥都解不开 → ValueError
- 旧密钥从环境变量 GS_OLD_ENCRYPTION_KEYS 读取
- rotate_key.py：dry-run 不写库；正式执行全库重加密为最新密钥
"""

import sys
from datetime import datetime, timezone

import pytest

from foundation.database.encryption import Encryptor, _generate_key
from foundation.database.store import GardenStore
from shared.models import JournalEntry, Letter

from scripts import rotate_key as rk


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _seed_db(db_path: str, encryptor: Encryptor) -> None:
    """用指定加密器写一条日记 + 一封来信（跨表验证重加密）。"""
    store = GardenStore(db_path=db_path, encryptor=encryptor)
    store.save_journal(JournalEntry(
        id="j1", person_id="p1", content="轮换前的日记", created_at=_now(), updated_at=_now(),
    ))
    store.save_letter(Letter(
        id="lt1", person_id="p1", letter_date="2026-08-12", sender="moon",
        title="旧信", body="旧钥匙下的来信",
    ))
    store.close()


# ----------------------------------------------------------------------
# Encryptor keyring
# ----------------------------------------------------------------------


def test_keyring_decrypts_old_ciphertext():
    old = _generate_key()
    new = _generate_key()
    old_enc = Encryptor(key=old)
    cipher = old_enc.encrypt("出生数据 1991-03-21 山西陵川")

    # 轮换后：新密钥 + 旧密钥 keyring → 旧密文照常可解
    enc = Encryptor(key=new, old_keys=[old])
    assert enc.decrypt(cipher) == "出生数据 1991-03-21 山西陵川"


def test_keyring_encrypt_uses_latest_key():
    old = _generate_key()
    new = _generate_key()
    enc = Encryptor(key=new, old_keys=[old])

    cipher = enc.encrypt("新数据")
    # 新写入用最新密钥：旧密钥单独解不开（这才是"换钥"的意义）
    old_only = Encryptor(key=old)
    with pytest.raises(ValueError):
        old_only.decrypt(cipher)
    # 新密钥单独可解
    assert Encryptor(key=new).decrypt(cipher) == "新数据"


def test_keyring_all_keys_fail_raises():
    enc = Encryptor(key=_generate_key(), old_keys=[_generate_key(), _generate_key()])
    cipher = enc.encrypt("hello")
    wrong = Encryptor(key=_generate_key(), old_keys=[_generate_key()])
    with pytest.raises(ValueError):
        wrong.decrypt(cipher)


def test_keyring_reads_old_keys_from_env(monkeypatch):
    old = _generate_key()
    new = _generate_key()
    monkeypatch.setenv("GS_ENCRYPTION_KEY", new)
    monkeypatch.setenv("GS_OLD_ENCRYPTION_KEYS", f"{old}, {_generate_key()}, ")  # 剥空白+空项

    cipher = Encryptor(key=old).encrypt("env 迁移")
    enc = Encryptor()  # 只从环境变量取 keyring
    assert enc.decrypt(cipher) == "env 迁移"


# ----------------------------------------------------------------------
# rotate_key.py 脚本
# ----------------------------------------------------------------------


def test_rotate_script_dry_run_does_not_write(tmp_path, monkeypatch):
    old = _generate_key()
    new = _generate_key()
    db = str(tmp_path / "garden.db")
    _seed_db(db, Encryptor(key=old))

    # dry-run：返回 0，库不被改写（旧密钥单独仍可读全表）
    monkeypatch.setattr(sys, "argv", ["rotate_key.py", db, "--current-key", new, "--old-keys", old, "--dry-run"])
    assert rk.main() == 0

    store = GardenStore(db_path=db, encryptor=Encryptor(key=old))
    assert store.list_letters("p1")[0].body == "旧钥匙下的来信"
    assert store.list_journals("p1")[0].content == "轮换前的日记"
    store.close()
    # 新密钥此时还读不出（未重加密）
    new_store = GardenStore(db_path=db, encryptor=Encryptor(key=new))
    with pytest.raises(ValueError):
        new_store.list_letters("p1")
    new_store.close()


def test_rotate_script_real_run_reencrypts(tmp_path, monkeypatch):
    old = _generate_key()
    new = _generate_key()
    db = str(tmp_path / "garden.db")
    _seed_db(db, Encryptor(key=old))

    monkeypatch.setattr(sys, "argv", ["rotate_key.py", db, "--current-key", new, "--old-keys", old])
    assert rk.main() == 0

    # 重加密后：新密钥单独可读全表
    store = GardenStore(db_path=db, encryptor=Encryptor(key=new))
    assert store.list_letters("p1")[0].body == "旧钥匙下的来信"
    assert store.list_letters("p1")[0].title == "旧信"
    assert store.list_journals("p1")[0].content == "轮换前的日记"
    store.close()
    # 旧密钥单独再也读不出（已全部换新）
    old_store = GardenStore(db_path=db, encryptor=Encryptor(key=old))
    with pytest.raises(ValueError):
        old_store.list_letters("p1")
    old_store.close()
    # 备份文件存在
    import glob

    assert glob.glob(f"{db}.bak.*")
