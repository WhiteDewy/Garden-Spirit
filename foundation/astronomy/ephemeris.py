"""Swiss Ephemeris 封装。

这是 foundation 层唯一的星历入口。所有占星计算从这里拿原始天文数据，
再在 domain/astrology 层转化为 Chart 模型。

注意：本模块只做"天文计算"，不含任何占星解释。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import swisseph as swe  # pyswisseph

from foundation.config import EphemerisConfig
from foundation.logger import get_logger
from shared.constants import SE_PLANET_IDS
from shared.enums import Planet, PlanetSpeed
from shared.types import JulianDay

logger = get_logger("astronomy.ephemeris")

# 是否加载了完整瑞士星历文件（.se1）。若否，回退内置 Moshier 星历。
_EPHEMERIS_AVAILABLE: bool | None = None
_EPHE_PATH: str | None = None

# 需要获取的黄道外天体（月交点/凯龙/莉莉丝）
_EXTRA_BODIES: dict[str, int] = {
    "north_node": 10,
    "chiron": 15,
    "lilith": 21,
}

# 速度阈值：判定逆行/顺行（度/天）
# 绝对值低于此阈值视为停滞（stationary）
_STATIONARY_THRESHOLD_DEG_PER_DAY = 0.0005


def _require_initialized(func):
    """确保 ephemeris 路径已设置。"""
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        initialize_ephemeris()
        return func(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# 初始化
# ---------------------------------------------------------------------------

def initialize_ephemeris(path: str | None = None) -> None:
    """设置星历文件路径。

    - 提供路径且目录含 .se1 文件 → 使用完整瑞士星历（最精确）。
    - 否则 → 自动回退内置 Moshier 星历（精度足以日常占星，无需下载）。
    """
    global _EPHEMERIS_AVAILABLE, _EPHE_PATH
    _EPHE_PATH = path or _EPHE_PATH
    if _EPHE_PATH:
        swe.set_ephe_path(_EPHE_PATH)
    _EPHEMERIS_AVAILABLE = _has_se_files(_EPHE_PATH)
    if not _EPHEMERIS_AVAILABLE:
        logger.info(
            "未找到瑞士星历文件（%s），回退内置 Moshier 星历。"
            "如需更高精度，请下载 Swiss Ephemeris 数据到 data/ephemeris/",
            _EPHE_PATH,
        )


def _has_se_files(path: str | None) -> bool:
    if not path:
        return False
    p = Path(path)
    if not p.is_dir():
        return False
    return any(p.glob("*.se1"))


def ephemeris_available() -> bool:
    """完整瑞士星历文件是否可用（决定 Chiron 等是否需要独立星历的天体）。"""
    if _EPHEMERIS_AVAILABLE is None:
        initialize_ephemeris()
    return bool(_EPHEMERIS_AVAILABLE)


def _flags() -> int:
    """计算用标志：有瑞士星历文件则 SWIEPH，否则 MOSEPH。"""
    if _EPHEMERIS_AVAILABLE is None:
        initialize_ephemeris()
    base = swe.FLG_SPEED
    return (swe.FLG_SWIEPH if _EPHEMERIS_AVAILABLE else swe.FLG_MOSEPH) | base


# ---------------------------------------------------------------------------
# 时间换算
# ---------------------------------------------------------------------------

def to_julian_day(dt: datetime) -> JulianDay:
    """Python datetime (UTC) → 儒略日。"""
    if dt.tzinfo is not None:
        dt = dt.astimezone(tz_utc()).replace(tzinfo=None)
    jd = swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute / 60.0 + dt.second / 3600.0)
    # julday 默认用公历（Gregorian），无需额外参数
    return jd


def from_julian_day(jd: JulianDay) -> datetime:
    """儒略日 → Python datetime (UTC)。"""
    year, month, day, hour_f = swe.revjul(jd)
    hour = int(hour_f)
    minute_f = (hour_f - hour) * 60.0
    minute = int(minute_f)
    second = (minute_f - minute) * 60.0
    return datetime(int(year), int(month), int(day), hour, minute, int(second))


def tz_utc():
    from datetime import timezone

    return timezone.utc


# ---------------------------------------------------------------------------
# 行星位置
# ---------------------------------------------------------------------------

@_require_initialized
def planet_longitude(jd: JulianDay, planet: Planet) -> float:
    """行星黄经（度）。"""
    lon = swe.calc_ut(jd, SE_PLANET_IDS[planet], _flags())[0][0]
    return lon % 360.0


def _planet_speed_category(speed_deg_per_day: float) -> PlanetSpeed:
    """速度 → 运行方向类别。"""
    if abs(speed_deg_per_day) < _STATIONARY_THRESHOLD_DEG_PER_DAY:
        return PlanetSpeed.STATIONARY_DIRECT
    return (
        PlanetSpeed.DIRECT
        if speed_deg_per_day > 0
        else PlanetSpeed.RETROGRADE
    )


@_require_initialized
def planet_full(jd: JulianDay, planet: Planet) -> dict:
    """行星完整数据：黄经/黄纬/赤经/赤纬/距地/速度。

    - 南交点由北交点 +180° 推导（pyswisseph 的 ID 11 是真交点，非南交点）。
    - Chiron 需要完整瑞士星历文件；Moshier 星历下不可用，由调用方跳过。

    Returns:
        {
            "longitude": float, "latitude": float,
            "right_ascension": float, "declination": float,
            "distance_au": float, "speed_deg_per_day": float,
            "speed_category": PlanetSpeed,
        }
    """
    if planet == Planet.SOUTH_NODE:
        north = planet_full(jd, Planet.NORTH_NODE)
        return {
            **north,
            "longitude": (north["longitude"] + 180.0) % 360.0,
            "speed_deg_per_day": north["speed_deg_per_day"],
            "speed_category": north["speed_category"],
        }
    arr = swe.calc_ut(jd, SE_PLANET_IDS[planet], _flags())[0]
    lon, lat, dist, speed_lon = arr[0], arr[1], arr[2], arr[3]
    # 赤经/赤纬需要额外标志
    try:
        arr_eq = swe.calc_ut(jd, SE_PLANET_IDS[planet], _flags() | swe.FLG_EQUATORIAL)[0]
        ra, dec = arr_eq[0], arr_eq[1]
    except Exception:  # pragma: no cover
        ra, dec = 0.0, 0.0
    return {
        "longitude": lon % 360.0,
        "latitude": lat,
        "right_ascension": ra,
        "declination": dec,
        "distance_au": dist,
        "speed_deg_per_day": speed_lon,
        "speed_category": _planet_speed_category(speed_lon),
    }


# ---------------------------------------------------------------------------
# 宫位
# ---------------------------------------------------------------------------

@_require_initialized
def house_cusps(jd: JulianDay, latitude: float, longitude: float, house_system: str) -> dict:
    """计算宫头与角点。

    Returns:
        {"cusps": {1..12: float}, "ascendant": float, "midheaven": float}
    """
    house_code = house_system.encode() if isinstance(house_system, str) else house_system
    cusps_raw, ascmc_raw = swe.houses_ex(jd, latitude, longitude, house_code, _flags())
    cusps = {i + 1: cusps_raw[i] % 360.0 for i in range(12)}
    return {
        "cusps": cusps,
        "ascendant": ascmc_raw[0] % 360.0,
        "midheaven": ascmc_raw[1] % 360.0,
        # ascmc[2..9] 包含天底/下降/天顶等的补充点
        "_raw_ascmc": list(ascmc_raw),
    }


# ---------------------------------------------------------------------------
# 特殊点
# ---------------------------------------------------------------------------

@_require_initialized
def moon_phase_angle(jd: JulianDay) -> float:
    """月相角（0-360）。0=新月，180=满月。

    由日月黄经差计算（pyswisseph 无 moon_phase 接口）。
    """
    sun_lon = planet_longitude(jd, Planet.SUN)
    moon_lon = planet_longitude(jd, Planet.MOON)
    return (moon_lon - sun_lon) % 360.0


# ---------------------------------------------------------------------------
# 行运辅助：判断精确相位时间（用于时间窗口）
# ---------------------------------------------------------------------------

@_require_initialized
def aspect_event_times(
    start_jd: JulianDay,
    end_jd: JulianDay,
    body1: Planet,
    body2: Planet,
    aspect_angle: float,
    orb: float,
    steps: int = 200,
) -> list[JulianDay]:
    """在时间区间内扫描两星体逼近指定相位的时刻（粗粒度）。

    用于时间窗口聚合：找出行运行星与本命行星形成关键相位的时段。
    v1 采用均匀采样 + 线性插值逼近，精度足够日常使用。
    """
    times: list[JulianDay] = []
    sample_interval = (end_jd - start_jd) / steps
    prev = None
    for i in range(steps + 1):
        jd = start_jd + sample_interval * i
        lon1 = planet_longitude(jd, body1)
        lon2 = planet_longitude(jd, body2)
        diff = abs((lon1 - lon2 + 540.0) % 360.0 - 180.0)  # 0-180
        distance = abs(diff - aspect_angle)
        if distance <= orb:
            # 粗略：采样点落入容许度即为事件期
            times.append(jd)
    return times


def guess_timezone_offset(
    dt: datetime, timezone_name: str | None
) -> timedelta:
    """获取某时刻的 UTC 偏移（IANA 时区）。

    若 timezone_name 缺失，返回 None（由调用方决定如何降级）。
    """
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    if not timezone_name:
        return timedelta(0)
    try:
        tz = ZoneInfo(timezone_name)
        if dt.tzinfo is None:
            aware = dt.replace(tzinfo=tz)
        else:
            aware = dt.astimezone(tz)
        return aware.utcoffset() or timedelta(0)
    except (ZoneInfoNotFoundError, ValueError):
        return timedelta(0)
