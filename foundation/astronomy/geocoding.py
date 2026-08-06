"""地名 → 经纬度 + 时区。

生产（上线）：高德地图 Geocoding API（国内主流，免费配额够用）。
  配置：环境变量 GS_AMAP_KEY。未配置 → 记 warning 并回退离线静态表。
离线兜底：内置主要城市表 + 手动经纬度回退（仅开发 / 无网场景）。

城市精度对占星是硬约束：经纬度决定宫位，时区决定星盘时刻。
因此"城市解析失败就硬编码上海"是**禁止**的降级——见 API 层的处理。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from foundation.logger import get_logger
from foundation.math import haversine_km

logger = get_logger("astronomy.geocoding")

try:
    import requests  # 可选依赖：未安装时仅静态表可用

    _HAS_REQUESTS = True
except ImportError:  # pragma: no cover
    requests = None  # type: ignore
    _HAS_REQUESTS = False

#: 高德 Geocoding API 配置（环境变量注入，生产必配）
AMAP_KEY_ENV = "GS_AMAP_KEY"
#: 显式离线开关：设 1/true 时跳过高德，仅用静态表（CI/测试/无网环境）
OFFLINE_ENV = "GS_GEOCODE_OFFLINE"
_AMAP_ENDPOINT = "https://restapi.amap.com/v3/geocode/geo"
_AMAP_TIMEOUT = 5


def _amap_enabled() -> bool:
    return os.getenv(OFFLINE_ENV, "").strip().lower() not in ("1", "true", "yes")


@dataclass(frozen=True)
class GeocodeResult:
    place_name: str
    latitude: float
    longitude: float
    timezone_name: str
    source: str          # "amap" | "static_table" | "manual" | "exact"


# ----------------------------------------------------------------------
# 时区推导
# ----------------------------------------------------------------------

#: 中国大陆（Asia/Shanghai 覆盖全国）之外的特例行政区
_CN_SPECIAL_TZ = {
    "台湾": "Asia/Taipei",
    "香港": "Asia/Hong_Kong",
    "澳门": "Asia/Macau",
}


def infer_timezone(country: str = "", province: str = "") -> str:
    """由高德返回的省/国家推导 IANA 时区。

    中国大陆统一 Asia/Shanghai（东八区单一时区）；港澳台各有独立时区。
    海外地区 v1 归 UTC，由精确经纬度输入的时区覆盖（见 manual_location）。
    """
    if country and "中国" in country:
        for key, tz in _CN_SPECIAL_TZ.items():
            if key in province:
                return tz
        return "Asia/Shanghai"
    # 海外：常见国家映射，未命中归 UTC
    overseas = {
        "日本": "Asia/Tokyo",
        "韩国": "Asia/Seoul",
        "新加坡": "Asia/Singapore",
        "美国": "America/New_York",  # 多时区，仅近似——精确值由手动输入覆盖
        "英国": "Europe/London",
        "法国": "Europe/Paris",
        "澳大利亚": "Australia/Sydney",
    }
    for key, tz in overseas.items():
        if country and key in country:
            return tz
    return "UTC"


# ----------------------------------------------------------------------
# 高德 Geocoding（生产路径）
# ----------------------------------------------------------------------


def _amap_geocode(place_name: str) -> GeocodeResult | None:
    """调用高德地理编码。失败/无 key → None（交由静态表兜底）。"""
    if not _HAS_REQUESTS:
        return None
    key = os.getenv(AMAP_KEY_ENV, "").strip()
    if not key:
        logger.warning("未配置 %s——geocoding 走离线静态表（上线前必须配置）", AMAP_KEY_ENV)
        return None
    try:
        resp = requests.get(
            _AMAP_ENDPOINT,
            params={"address": place_name, "key": key},
            timeout=_AMAP_TIMEOUT,
        )
        data = resp.json()
        if data.get("status") != "1":
            logger.warning("高德 geocoding 返回错误: %s %s", data.get("status"), data.get("info"))
            return None
        geocodes = data.get("geocodes") or []
        if not geocodes:
            return None
        first = geocodes[0]
        lon, lat = (first.get("location") or "0,0").split(",")
        province = first.get("province") or ""
        country = first.get("country") or ""
        return GeocodeResult(
            place_name=first.get("formatted_address") or place_name,
            latitude=float(lat),
            longitude=float(lon),
            timezone_name=infer_timezone(country, province),
            source="amap",
        )
    except Exception as exc:  # noqa: BLE001 - 网络/解析失败兜底静态表
        logger.warning("高德 geocoding 失败，回退静态表: %s", exc)
        return None


# ----------------------------------------------------------------------
# 静态城市表（离线兜底）
# ----------------------------------------------------------------------

_STATIC_CITY_TABLE: list[dict] = [
    {"name": "北京", "pinyin": "beijing", "lat": 39.9042, "lon": 116.4074, "tz": "Asia/Shanghai"},
    {"name": "上海", "pinyin": "shanghai", "lat": 31.2304, "lon": 121.4737, "tz": "Asia/Shanghai"},
    {"name": "广州", "pinyin": "guangzhou", "lat": 23.1291, "lon": 113.2644, "tz": "Asia/Shanghai"},
    {"name": "深圳", "pinyin": "shenzhen", "lat": 22.5431, "lon": 114.0579, "tz": "Asia/Shanghai"},
    {"name": "杭州", "pinyin": "hangzhou", "lat": 30.2741, "lon": 120.1551, "tz": "Asia/Shanghai"},
    {"name": "成都", "pinyin": "chengdu", "lat": 30.5728, "lon": 104.0668, "tz": "Asia/Shanghai"},
    {"name": "重庆", "pinyin": "chongqing", "lat": 29.5630, "lon": 106.5516, "tz": "Asia/Shanghai"},
    {"name": "南京", "pinyin": "nanjing", "lat": 32.0603, "lon": 118.7969, "tz": "Asia/Shanghai"},
    {"name": "武汉", "pinyin": "wuhan", "lat": 30.5928, "lon": 114.3055, "tz": "Asia/Shanghai"},
    {"name": "西安", "pinyin": "xian", "lat": 34.3416, "lon": 108.9398, "tz": "Asia/Shanghai"},
    {"name": "天津", "pinyin": "tianjin", "lat": 39.0842, "lon": 117.2009, "tz": "Asia/Shanghai"},
    {"name": "长沙", "pinyin": "changsha", "lat": 28.2282, "lon": 112.9388, "tz": "Asia/Shanghai"},
    {"name": "苏州", "pinyin": "suzhou", "lat": 31.2989, "lon": 120.5853, "tz": "Asia/Shanghai"},
    {"name": "台北", "pinyin": "taipei", "lat": 25.0330, "lon": 121.5654, "tz": "Asia/Taipei"},
    {"name": "香港", "pinyin": "hongkong", "lat": 22.3193, "lon": 114.1694, "tz": "Asia/Hong_Kong"},
    {"name": "新加坡", "pinyin": "singapore", "lat": 1.3521, "lon": 103.8198, "tz": "Asia/Singapore"},
    {"name": "东京", "pinyin": "tokyo", "lat": 35.6762, "lon": 139.6503, "tz": "Asia/Tokyo"},
    {"name": "首尔", "pinyin": "seoul", "lat": 37.5665, "lon": 126.9780, "tz": "Asia/Seoul"},
    {"name": "纽约", "pinyin": "newyork", "lat": 40.7128, "lon": -74.0060, "tz": "America/New_York"},
    {"name": "洛杉矶", "pinyin": "losangeles", "lat": 34.0522, "lon": -118.2437, "tz": "America/Los_Angeles"},
    {"name": "伦敦", "pinyin": "london", "lat": 51.5074, "lon": -0.1278, "tz": "Europe/London"},
    {"name": "巴黎", "pinyin": "paris", "lat": 48.8566, "lon": 2.3522, "tz": "Europe/Paris"},
    {"name": "悉尼", "pinyin": "sydney", "lat": -33.8688, "lon": 151.2093, "tz": "Australia/Sydney"},
]


def _static_geocode(place_name: str) -> GeocodeResult | None:
    """静态表匹配：精确 → 拼音 → 模糊包含。未命中 → None。"""
    if not place_name:
        return None
    name = place_name.strip()
    target = name.lower().replace(" ", "")
    for city in _STATIC_CITY_TABLE:
        if name == city["name"] or target == city["pinyin"]:
            return _to_result(city, "static_table")
    for city in _STATIC_CITY_TABLE:
        if city["name"] in name or target in city["pinyin"]:
            logger.info("模糊匹配城市: %s → %s", place_name, city["name"])
            return _to_result(city, "static_table")
    return None


# ----------------------------------------------------------------------
# 主入口
# ----------------------------------------------------------------------


def geocode(place_name: str, fallback: GeocodeResult | None = None) -> GeocodeResult | None:
    """地名 → 坐标。

    顺序：高德 API（生产）→ 静态表（离线）→ fallback。
    返回 None 仅当 fallback 也为 None 且无法解析——调用方必须处理，
    不得静默用错误坐标。
    """
    if not place_name:
        return fallback
    if _amap_enabled():
        result = _amap_geocode(place_name)
        if result is not None:
            return result
    result = _static_geocode(place_name)
    if result is not None:
        return result
    return fallback


def _to_result(city: dict, source: str) -> GeocodeResult:
    return GeocodeResult(
        place_name=city["name"],
        latitude=city["lat"],
        longitude=city["lon"],
        timezone_name=city["tz"],
        source=source,
    )


def manual_location(latitude: float, longitude: float, timezone_name: str = "UTC") -> GeocodeResult:
    """手动指定经纬度 + 时区（用户精确输入时的回退，时区显式给出）。"""
    return GeocodeResult(
        place_name=f"{latitude:.4f},{longitude:.4f}",
        latitude=latitude,
        longitude=longitude,
        timezone_name=timezone_name,
        source="manual",
    )


__all__ = ["GeocodeResult", "geocode", "manual_location", "infer_timezone", "AMAP_KEY_ENV"]
