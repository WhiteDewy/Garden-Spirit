"""生产化三件套测试：WAL 模式 + 一致性备份脚本。

覆盖：
- 应用连接开 WAL（store 建库后 journal_mode == 'wal'）
- backup_db.py：VACUUM INTO 生成一致性快照，备份可被新 GardenStore 原样读出
- 源库不存在 → 返回 2；目标已存在 → 拒绝覆盖返回 2
"""

import os
import sqlite3
import sys
from datetime import datetime, timezone

import pytest

from foundation.database.encryption import Encryptor, _generate_key
from foundation.database.store import GardenStore
from shared.models import JournalEntry

from scripts import backup_db as bb


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _seed(db_path: str, encryptor: Encryptor) -> None:
    store = GardenStore(db_path=db_path, encryptor=encryptor)
    store.save_journal(JournalEntry(
        id="j1", person_id="p1", content="备份前的日记", created_at=_now(), updated_at=_now(),
    ))
    store.close()


# ----------------------------------------------------------------------
# WAL 模式
# ----------------------------------------------------------------------


def test_store_opens_in_wal_mode(tmp_path):
    db = str(tmp_path / "garden.db")
    _seed(db, Encryptor(key=_generate_key()))
    conn = sqlite3.connect(db)
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    conn.close()


# ----------------------------------------------------------------------
# backup_db.py
# ----------------------------------------------------------------------


def test_backup_db_creates_consistent_snapshot(tmp_path, monkeypatch):
    key = _generate_key()
    db = str(tmp_path / "garden.db")
    out = str(tmp_path / "backups" / "snapshot.db")
    _seed(db, Encryptor(key=key))

    monkeypatch.setattr(sys, "argv", ["backup_db.py", db, "--out", out])
    assert bb.main() == 0

    assert os.path.exists(out)
    # 快照可用同密钥原样读出（加密列可解 + 表结构迁移幂等）
    store = GardenStore(db_path=out, encryptor=Encryptor(key=key))
    assert store.list_journals("p1")[0].content == "备份前的日记"
    store.close()


def test_backup_db_missing_source_returns_error(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["backup_db.py", str(tmp_path / "nope.db")])
    assert bb.main() == 2


def test_backup_db_refuses_overwrite(tmp_path, monkeypatch):
    key = _generate_key()
    db = str(tmp_path / "garden.db")
    out = str(tmp_path / "existing.db")
    _seed(db, Encryptor(key=key))
    # 预置一个目标文件 → 拒绝覆盖
    (tmp_path / "existing.db").write_bytes(b"old")
    monkeypatch.setattr(sys, "argv", ["backup_db.py", db, "--out", out])
    assert bb.main() == 2
    assert (tmp_path / "existing.db").read_bytes() == b"old"


def test_backup_db_default_path_under_backups(tmp_path, monkeypatch):
    """缺省输出：<源库目录>/backups/<库名>.<时间戳>.db"""
    key = _generate_key()
    db = str(tmp_path / "garden.db")
    _seed(db, Encryptor(key=key))

    monkeypatch.setattr(sys, "argv", ["backup_db.py", db])
    assert bb.main() == 0
    backups = (tmp_path / "backups").iterdir()
    files = [p for p in backups if p.name.endswith(".db")]
    assert len(files) == 1
    assert files[0].name.startswith("garden.db.")
