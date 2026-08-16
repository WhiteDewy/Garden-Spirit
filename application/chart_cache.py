"""本命盘静态缓存服务（R4）。

原则：出生数据确定后，本命盘只需计算一次；缓存属于出生数据的敏感派生数据，
由 PersonRepository 加密落库。Application 层只通过本服务读写缓存，不把缓存逻辑散到 API/Agent。
"""

from __future__ import annotations

from collections.abc import Callable

from foundation.database import PersonRepository
from shared.enums import HouseSystem, ZodiacType
from shared.models import Chart, Person
from shared.models.chart_codec import chart_from_json, chart_to_json

from domain.astrology.calculation import NatalChartCalculator


NATAL_CACHE_SCHEMA_VERSION = "v1"


def natal_cache_key(
    house_system: HouseSystem,
    zodiac: ZodiacType = ZodiacType.TROPICAL,
) -> str:
    """本命盘缓存 key：含版本/宫位制/黄道，避免算法或制式升级后串图。"""
    return f"natal:{NATAL_CACHE_SCHEMA_VERSION}:{house_system.value}:{zodiac.value}"


def legacy_natal_cache_key(house_system: HouseSystem) -> str:
    """旧版本命盘缓存 key；仅用于懒迁移，不作为当前命中标准。"""
    return f"natal:{house_system.value}"


class NatalChartCache:
    """Person.chart_cache 的唯一读写入口。"""

    def __init__(
        self,
        person_repo: PersonRepository,
        calculator: NatalChartCalculator | None = None,
    ):
        self._person_repo = person_repo
        self._calculator = calculator or NatalChartCalculator()

    def get_or_compute(
        self,
        person: Person,
        house_system: HouseSystem | None = None,
    ) -> Chart:
        """读取缓存；缺失/损坏则重算并加密回写。"""
        effective_house_system = self._effective_house_system(person, house_system)
        zodiac = self._calculator.config.zodiac
        key = natal_cache_key(effective_house_system, zodiac)
        raw = (person.chart_cache or {}).get(key)
        chart = self._load_valid_chart(raw, person, effective_house_system, zodiac)
        if chart:
            return chart

        legacy_key = legacy_natal_cache_key(effective_house_system)
        legacy_raw = (person.chart_cache or {}).get(legacy_key)
        chart = self._load_valid_chart(legacy_raw, person, effective_house_system, zodiac)
        if chart:
            person.chart_cache = {**(person.chart_cache or {}), key: chart_to_json(chart)}
            self._person_repo.save(person)
            return chart

        chart = self._calculator.compute(person, house_system=effective_house_system)
        person.chart_cache = {**(person.chart_cache or {}), key: chart_to_json(chart)}
        self._person_repo.save(person)
        return chart

    def _load_valid_chart(
        self,
        raw: str | None,
        person: Person,
        house_system: HouseSystem,
        zodiac: ZodiacType,
    ) -> Chart | None:
        if not raw:
            return None
        try:
            chart = chart_from_json(raw)
        except (KeyError, TypeError, ValueError):
            # 旧实验缓存或损坏缓存不阻断用户，重算并覆盖当前 key。
            return None
        if (
            chart.person_id == person.id
            and chart.house_system == house_system
            and chart.zodiac == zodiac
        ):
            return chart
        return None

    def _effective_house_system(
        self,
        person: Person,
        override: HouseSystem | None,
    ) -> HouseSystem:
        return override or person.house_system or self._calculator.config.default_house_system


ChartProvider = Callable[[Person, HouseSystem | None], Chart]


__all__ = [
    "NatalChartCache",
    "ChartProvider",
    "NATAL_CACHE_SCHEMA_VERSION",
    "legacy_natal_cache_key",
    "natal_cache_key",
]
