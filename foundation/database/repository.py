"""Person 持久化仓库（出生数据加密存储，PRD §8 红线）。

- 出生数据（BirthData）整体 Fernet 加密后入库
- name/gender/notes 属于 PII，一并加密
- 表结构暴露给外界的只有 id/house_system 等非敏感字段
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from foundation.logger import get_logger
from foundation.utils import utc_now_aware
from shared.enums import HouseSystem
from shared.models.person import BirthData, GeoLocation, Person

from foundation.database.encryption import Encryptor

logger = get_logger("foundation.database.repository")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS persons (
    id TEXT PRIMARY KEY,
    name_encrypted TEXT NOT NULL,
    gender_encrypted TEXT DEFAULT '',
    notes_encrypted TEXT DEFAULT '',
    birth_data_encrypted TEXT NOT NULL,
    house_system TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value else utc_now_aware().isoformat()


def _birth_to_json(birth: BirthData) -> str:
    """BirthData → JSON 字符串（datetime → ISO8601）。"""
    data = asdict(birth)
    data["datetime_utc"] = birth.datetime_utc.isoformat()
    return json.dumps(data, ensure_ascii=False)


def _birth_from_json(raw: str) -> BirthData:
    """JSON 字符串 → BirthData（ISO8601 → datetime）。"""
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


class PersonRepository:
    """Person 持久化（SQLite + Fernet 加密出生数据）。"""

    def __init__(self, db_path: str = "./data/garden_spirit.db", encryptor: Encryptor | None = None):
        self._db_path = str(db_path)
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._encryptor = encryptor or Encryptor()
        # 单条持久连接：对 :memory: 必须复用同一连接，否则每次 _connect 都是新空库
        # check_same_thread=False：FastAPI/TestClient 会在工作线程执行请求，
        # 单连接跨线程访问依赖 SQLite 自身锁 + 即时 commit 保证一致性。
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def _connect(self) -> sqlite3.Connection:
        return self._conn

    # ------------------------------------------------------------------

    def save(self, person: Person) -> None:
        """Upsert 保存 Person（出生数据加密）。"""
        now = _iso(person.updated_at)
        birth_enc = self._encryptor.encrypt(_birth_to_json(person.birth))
        name_enc = self._encryptor.encrypt(person.name)
        gender_enc = self._encryptor.encrypt(person.gender or "")
        notes_enc = self._encryptor.encrypt(person.notes)
        created_at = _iso(person.created_at)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO persons
                    (id, name_encrypted, gender_encrypted, notes_encrypted,
                     birth_data_encrypted, house_system, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name_encrypted = excluded.name_encrypted,
                    gender_encrypted = excluded.gender_encrypted,
                    notes_encrypted = excluded.notes_encrypted,
                    birth_data_encrypted = excluded.birth_data_encrypted,
                    house_system = excluded.house_system,
                    updated_at = excluded.updated_at
                """,
                (
                    person.id,
                    name_enc,
                    gender_enc,
                    notes_enc,
                    birth_enc,
                    person.house_system.value if person.house_system else "",
                    created_at,
                    now,
                ),
            )
            conn.commit()

    def get(self, person_id: str) -> Person | None:
        """按 id 读取并解密 Person。不存在 → None。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM persons WHERE id = ?", (person_id,)
            ).fetchone()
        if row is None:
            return None

        birth = _birth_from_json(self._encryptor.decrypt(row["birth_data_encrypted"]))
        name = self._encryptor.decrypt(row["name_encrypted"])
        gender = self._encryptor.decrypt(row["gender_encrypted"]) or None
        notes = self._encryptor.decrypt(row["notes_encrypted"])

        return Person(
            id=row["id"],
            name=name,
            birth=birth,
            gender=gender,
            notes=notes,
            house_system=HouseSystem(row["house_system"]) if row["house_system"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def delete(self, person_id: str) -> bool:
        """删除 Person。删除成功 → True；不存在 → False。"""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM persons WHERE id = ?", (person_id,))
            conn.commit()
        return cur.rowcount > 0

    def list_all(self) -> list[Person]:
        """列出全部 Person（全量解密。数据量小，v1 够用）。"""
        with self._connect() as conn:
            rows = conn.execute("SELECT id FROM persons ORDER BY created_at").fetchall()
        out: list[Person] = []
        for row in rows:
            p = self.get(row["id"])
            if p is not None:
                out.append(p)
        return out


__all__ = ["PersonRepository"]
