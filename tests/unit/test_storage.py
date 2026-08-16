"""出生数据加密存储测试（PRD §8 红线）。

验证：
- Encryptor 加密/解密往返
- 错误密钥解密失败（不静默）
- PersonRepository CRUD 往返无损
- 空库查询返回 None
"""

from datetime import datetime, timezone

import pytest

from foundation.config import EphemerisConfig
from foundation.database import Encryptor, PersonRepository
from foundation.database.encryption import _generate_key
from shared.enums import HouseSystem, ZodiacType
from shared.models.chart_codec import chart_from_json, chart_to_json
from shared.models.person import BirthData, GeoLocation, Person

from application.chart_cache import NatalChartCache, legacy_natal_cache_key, natal_cache_key
from domain.astrology.calculation import NatalChartCalculator


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


def test_chart_codec_roundtrip_natal_chart():
    """Chart codec 能完整往返本命盘核心结构，且不持久化运行时 memo。"""
    p = _make_person("chart_codec")
    p.house_system = HouseSystem.ALCABITIUS
    chart = NatalChartCalculator().compute(p)
    chart.planet_assessments["memo"] = {"runtime_only": True}

    restored = chart_from_json(chart_to_json(chart))

    assert restored.id == chart.id
    assert restored.person_id == chart.person_id
    assert restored.chart_type == chart.chart_type
    assert restored.house_system == HouseSystem.ALCABITIUS
    assert restored.epoch_utc == chart.epoch_utc
    assert restored.ascendant == chart.ascendant
    assert restored.midheaven == chart.midheaven
    assert set(restored.planets) == set(chart.planets)
    assert restored.planets.keys() == chart.planets.keys()
    assert restored.house_cusps.keys() == chart.house_cusps.keys()
    assert restored.aspects[0].aspect_type == chart.aspects[0].aspect_type
    assert [r.planet_a for r in restored.receptions] == [r.planet_a for r in chart.receptions]
    assert [a.acceptor for a in restored.acceptances] == [a.acceptor for a in chart.acceptances]
    assert restored.planet_assessments == {}


def test_repository_chart_cache_roundtrip_and_encrypted(tmp_path):
    """chart_cache 属于出生数据派生信息：可往返，但库里不可见明文星盘。"""
    import sqlite3

    db = str(tmp_path / "cache.db")
    repo = PersonRepository(db_path=db)
    p = _make_person("p_cache")
    chart = NatalChartCalculator().compute(p, house_system=HouseSystem.PLACIDUS)
    key = natal_cache_key(HouseSystem.PLACIDUS)
    p.chart_cache[key] = chart_to_json(chart)
    repo.save(p)

    got = repo.get("p_cache")
    assert got is not None
    assert key in got.chart_cache
    restored = chart_from_json(got.chart_cache[key])
    assert restored.person_id == "p_cache"
    assert restored.house_system == HouseSystem.PLACIDUS
    assert [r.planet_b for r in restored.receptions] == [r.planet_b for r in chart.receptions]
    assert [a.accepted for a in restored.acceptances] == [a.accepted for a in chart.acceptances]

    conn = sqlite3.connect(db)
    row = conn.execute("SELECT chart_cache_encrypted FROM persons WHERE id='p_cache'").fetchone()
    conn.close()
    assert row is not None
    encrypted = row[0]
    assert "natal:v1:P:tropical" not in encrypted
    assert "planets" not in encrypted
    assert "p_cache" not in encrypted
    assert not encrypted.startswith("{")


def test_natal_chart_cache_key_includes_schema_house_system_and_zodiac():
    """缓存 key 必须含 schema/宫位制/黄道，避免升级或 sidereal 切换误复用。"""
    assert natal_cache_key(HouseSystem.PLACIDUS) == "natal:v1:P:tropical"
    assert (
        natal_cache_key(HouseSystem.ALCABITIUS, ZodiacType.SIDEREAL)
        == "natal:v1:B:sidereal"
    )


def test_natal_chart_cache_computes_once_then_reads_repository_cache(tmp_path):
    """缓存服务首次计算并回填；后续读缓存，不重复调用排盘。"""
    db = str(tmp_path / "chart_cache.db")
    repo = PersonRepository(db_path=db)
    p = _make_person("p_once")
    repo.save(p)

    class CountingCalculator(NatalChartCalculator):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def compute(self, person, house_system=None):
            self.calls += 1
            return super().compute(person, house_system=house_system)

    calc = CountingCalculator()
    cache = NatalChartCache(repo, calc)

    chart1 = cache.get_or_compute(repo.get("p_once"))
    chart2 = cache.get_or_compute(repo.get("p_once"))

    assert calc.calls == 1
    assert chart2.id == chart1.id
    stored = repo.get("p_once")
    assert stored is not None
    assert natal_cache_key(chart1.house_system, chart1.zodiac) in stored.chart_cache


def test_natal_chart_cache_key_separates_house_systems(tmp_path):
    """同一人不同宫位制必须分 key 缓存，不能串图。"""
    repo = PersonRepository(db_path=str(tmp_path / "house_systems.db"))
    p = _make_person("p_houses")
    repo.save(p)
    cache = NatalChartCache(repo)

    placidus = cache.get_or_compute(repo.get("p_houses"), HouseSystem.PLACIDUS)
    alcabitius = cache.get_or_compute(repo.get("p_houses"), HouseSystem.ALCABITIUS)

    assert placidus.house_system == HouseSystem.PLACIDUS
    assert alcabitius.house_system == HouseSystem.ALCABITIUS
    assert placidus.id != alcabitius.id
    stored = repo.get("p_houses")
    assert stored is not None
    assert natal_cache_key(HouseSystem.PLACIDUS, ZodiacType.TROPICAL) in stored.chart_cache
    assert natal_cache_key(HouseSystem.ALCABITIUS, ZodiacType.TROPICAL) in stored.chart_cache


def test_natal_chart_cache_migrates_valid_legacy_key_without_recompute(tmp_path):
    """旧 natal:{house_system} key 只在内容匹配当前版本口径时懒迁移。"""
    repo = PersonRepository(db_path=str(tmp_path / "legacy_cache.db"))
    p = _make_person("p_legacy")
    chart = NatalChartCalculator().compute(p, house_system=HouseSystem.PLACIDUS)
    p.chart_cache[legacy_natal_cache_key(HouseSystem.PLACIDUS)] = chart_to_json(chart)
    repo.save(p)

    class CountingCalculator(NatalChartCalculator):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def compute(self, person, house_system=None):
            self.calls += 1
            return super().compute(person, house_system=house_system)

    calc = CountingCalculator()
    cache = NatalChartCache(repo, calc)
    migrated = cache.get_or_compute(repo.get("p_legacy"), HouseSystem.PLACIDUS)

    assert calc.calls == 0
    assert migrated.id == chart.id
    stored = repo.get("p_legacy")
    assert stored is not None
    assert legacy_natal_cache_key(HouseSystem.PLACIDUS) in stored.chart_cache
    assert natal_cache_key(HouseSystem.PLACIDUS, ZodiacType.TROPICAL) in stored.chart_cache


def test_natal_chart_cache_recomputes_legacy_key_when_zodiac_mismatches(tmp_path):
    """旧 key 若来自不同黄道，不能被迁移成当前本命盘。"""
    repo = PersonRepository(db_path=str(tmp_path / "legacy_zodiac.db"))
    p = _make_person("p_legacy_zodiac")
    sidereal_calc = NatalChartCalculator(EphemerisConfig(zodiac=ZodiacType.SIDEREAL))
    sidereal_chart = sidereal_calc.compute(p, house_system=HouseSystem.PLACIDUS)
    p.chart_cache[legacy_natal_cache_key(HouseSystem.PLACIDUS)] = chart_to_json(sidereal_chart)
    repo.save(p)

    class CountingCalculator(NatalChartCalculator):
        def __init__(self):
            super().__init__(EphemerisConfig(zodiac=ZodiacType.TROPICAL))
            self.calls = 0

        def compute(self, person, house_system=None):
            self.calls += 1
            return super().compute(person, house_system=house_system)

    calc = CountingCalculator()
    cache = NatalChartCache(repo, calc)
    chart = cache.get_or_compute(repo.get("p_legacy_zodiac"), HouseSystem.PLACIDUS)

    assert calc.calls == 1
    assert chart.zodiac == ZodiacType.TROPICAL
    stored = repo.get("p_legacy_zodiac")
    assert stored is not None
    restored = chart_from_json(
        stored.chart_cache[natal_cache_key(HouseSystem.PLACIDUS, ZodiacType.TROPICAL)]
    )
    assert restored.id == chart.id
    assert restored.zodiac == ZodiacType.TROPICAL


def test_natal_chart_cache_recovers_from_corrupted_entry(tmp_path):
    """损坏/旧实验缓存不阻断运行，重算后覆盖当前 key。"""
    repo = PersonRepository(db_path=str(tmp_path / "bad_cache.db"))
    p = _make_person("p_bad")
    key = natal_cache_key(HouseSystem.PLACIDUS)
    p.chart_cache[key] = "not-json"
    repo.save(p)

    cache = NatalChartCache(repo)
    chart = cache.get_or_compute(repo.get("p_bad"), HouseSystem.PLACIDUS)

    assert chart.house_system == HouseSystem.PLACIDUS
    stored = repo.get("p_bad")
    assert stored is not None
    restored = chart_from_json(stored.chart_cache[key])
    assert restored.id == chart.id
    assert restored.house_system == HouseSystem.PLACIDUS
