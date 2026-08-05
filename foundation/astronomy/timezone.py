"""时区工具：本地时间 ↔ UTC 转换、夏令时检测。

出生时间处理的正确性依赖这里——这是占星计算最易出错的环节。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from foundation.logger import get_logger

logger = get_logger("astronomy.timezone")


def to_utc(
    local_dt: datetime, timezone_name: str | None = None, force_offset_hours: float | None = None
) -> datetime:
    """本地时间 → UTC。

    - 提供 IANA 时区名：用 zoneinfo 精确转换（含夏令时）。
    - 提供 force_offset_hours：用固定偏移（用户手动指定）。
    - 均无：假定输入已是 UTC。
    """
    if local_dt.tzinfo is not None:
        return local_dt.astimezone(timezone.utc).replace(tzinfo=None)

    if force_offset_hours is not None:
        return local_dt - timedelta(hours=force_offset_hours)

    if timezone_name:
        try:
            tz = ZoneInfo(timezone_name)
            aware = local_dt.replace(tzinfo=tz)
            return aware.astimezone(timezone.utc).replace(tzinfo=None)
        except (ZoneInfoNotFoundError, ValueError):
            logger.warning("未知时区 %s，按 UTC 处理", timezone_name)

    return local_dt


def from_utc(utc_dt: datetime, timezone_name: str | None = None) -> datetime:
    """UTC → 本地时间。"""
    if not timezone_name:
        return utc_dt
    try:
        tz = ZoneInfo(timezone_name)
        return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz).replace(tzinfo=None)
    except (ZoneInfoNotFoundError, ValueError):
        return utc_dt


def is_dst(local_dt: datetime, timezone_name: str) -> bool | None:
    """判断某时刻是否处于夏令时。无法判断返回 None。"""
    try:
        tz = ZoneInfo(timezone_name)
        aware = local_dt.replace(tzinfo=tz)
        return bool(aware.dst() and aware.dst() != timedelta(0))
    except (ZoneInfoNotFoundError, ValueError):
        return None


def utc_offset_hours(local_dt: datetime, timezone_name: str | None) -> float | None:
    """某时刻的 UTC 偏移（小时）。无法确定返回 None。"""
    try:
        tz = ZoneInfo(timezone_name) if timezone_name else timezone.utc
        aware = local_dt.replace(tzinfo=tz)
        offset = aware.utcoffset()
        return offset.total_seconds() / 3600.0 if offset else 0.0
    except (ZoneInfoNotFoundError, ValueError):
        return None
