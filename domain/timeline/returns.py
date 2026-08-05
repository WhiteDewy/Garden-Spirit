"""返回盘（月返/日返）共享求根逻辑。

返回盘 = 某星回到本命黄经的时刻起的盘。
月返 = 月亮；日返 = 太阳。求根逻辑相同，参数化经度函数即可。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

from shared.models import GeoLocation


def classify_return_location(
    birth_location: GeoLocation | None, location: GeoLocation | None
) -> str:
    """返回盘地点类型：出生地 or 当前地（宫位随地点变，必须标注）。"""
    if birth_location is None or location is None:
        return "current_place"
    same = (
        abs(birth_location.latitude - location.latitude) < 0.001
        and abs(birth_location.longitude - location.longitude) < 0.001
    )
    return "birth_place" if same else "current_place"

#: 默认扫描参数
_DEFAULT_STEP = timedelta(hours=1)
_BISECT_STEPS = 20


def find_return_before(
    lon_func: Callable[[datetime], float],
    natal_lon: float,
    before: datetime,
    scan_days: int = 40,
    step: timedelta = _DEFAULT_STEP,
) -> datetime:
    """before 之前最近一次某星回到 natal 黄经的时刻。

    lon_func: 给定时刻返回黄经（0-360）的函数（如月亮/太阳经度）。
    """
    ref = before
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    start = ref - timedelta(days=scan_days)
    crossings = _scan_crossings(lon_func, natal_lon, start, ref, step)
    if not crossings:
        raise ValueError(f"扫描窗口 {scan_days} 天内未找到返回穿越")
    a = crossings[-1]
    return _bisect(lon_func, natal_lon, a, a + step)


def find_return_after(
    lon_func: Callable[[datetime], float],
    natal_lon: float,
    after: datetime,
    scan_days: int = 35,
    step: timedelta = _DEFAULT_STEP,
) -> datetime:
    """after 之后最近一次某星回到 natal 黄经的时刻。"""
    if after.tzinfo is None:
        after = after.replace(tzinfo=timezone.utc)
    start = after + timedelta(hours=1)
    crossings = _scan_crossings(lon_func, natal_lon, start, start + timedelta(days=scan_days), step)
    if not crossings:
        raise ValueError("扫描窗口内未找到下次返回穿越")
    a = crossings[0]
    return _bisect(lon_func, natal_lon, a, a + step)


def _scan_crossings(
    lon_func: Callable[[datetime], float],
    natal_lon: float,
    start: datetime,
    end: datetime,
    step: timedelta,
) -> list[datetime]:
    """正向扫描（经度递增，含 0° 回绕），返回穿越 natal 的区间起点。

    用环形差值 d=(lon-natal)%360 检测：d 从 >180 跳到 <=180 即穿越
    （兼容月亮 359°→0° 的回绕，旧条件 prev<=natal<lon 抓不到 0° 边界）。
    """
    crossings: list[datetime] = []
    prev_dt = start
    prev_d = (lon_func(start) - natal_lon + 360.0) % 360.0
    dt = start + step
    while dt <= end:
        d = (lon_func(dt) - natal_lon + 360.0) % 360.0
        if prev_d > 180.0 and d <= 180.0:
            crossings.append(prev_dt)
        prev_dt, prev_d = dt, d
        dt += step
    return crossings


def _bisect(
    lon_func: Callable[[datetime], float],
    natal_lon: float,
    a: datetime,
    b: datetime,
) -> datetime:
    for _ in range(_BISECT_STEPS):
        mid = a + (b - a) / 2
        if (lon_func(mid) - natal_lon) * (lon_func(a) - natal_lon) < 0:
            b = mid
        else:
            a = mid
    return a + (b - a) / 2
