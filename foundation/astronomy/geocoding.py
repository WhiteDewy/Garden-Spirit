"""地名 → 经纬度。

v1 采用内置静态城市表 + 手动经纬度回退。未来可接外部 geocoding API。
"""

from __future__ import annotations

from dataclasses import dataclass

from foundation.logger import get_logger
from foundation.math import haversine_km

logger = get_logger("astronomy.geocoding")


@dataclass(frozen=True)
class GeocodeResult:
    place_name: str
    latitude: float
    longitude: float
    timezone_name: str
    source: str          # "static_table" | "manual" | "exact"


# 静态主要城市表（拼音 + 中文名），覆盖主要使用场景
_CITY_TABLE: list[dict] = [
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


def geocode(place_name: str, fallback: GeocodeResult | None = None) -> GeocodeResult | None:
    """地名 → 坐标。

    匹配策略：精确匹配 → 拼音匹配 → 模糊匹配（含忽略空格/大小写）→ fallback。
    """
    if not place_name:
        return fallback

    target = place_name.strip().lower().replace(" ", "")

    # 1. 精确匹配（中文名或拼音）
    for city in _CITY_TABLE:
        if place_name.strip() == city["name"] or target == city["pinyin"]:
            return _to_result(city, "static_table")

    # 2. 模糊匹配：目标包含城市名 或 城市名包含目标
    best: dict | None = None
    best_dist = float("inf")
    for city in _CITY_TABLE:
        if city["name"] in place_name or target in city["pinyin"]:
            return _to_result(city, "static_table")
        # 3. 附近城市：用目标中心近似（用于 fallback 提示）
        dist = haversine_km(city["lat"], city["lon"], fallback.latitude, fallback.longitude) if fallback else float("inf")
        if dist < best_dist:
            best_dist, best = dist, city

    if best is not None and best_dist < 1000.0:
        logger.info("模糊匹配城市: %s → %s", place_name, best["name"])
        return _to_result(best, "static_table")

    logger.warning("无法解析地名: %s，使用 fallback", place_name)
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
    """手动指定经纬度（用户精确输入时的回退）。"""
    return GeocodeResult(
        place_name=f"{latitude:.4f},{longitude:.4f}",
        latitude=latitude,
        longitude=longitude,
        timezone_name=timezone_name,
        source="manual",
    )
