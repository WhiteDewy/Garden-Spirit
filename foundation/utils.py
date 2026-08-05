"""通用工具：ID 生成、序列化、时间辅助、出生数据降级。"""

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from shared.constants import BIRTH_UNKNOWN_FALLBACK_HOUR
from shared.models.person import BirthData, GeoLocation


def new_id(prefix: str = "") -> str:
    """生成带前缀的唯一 ID。"""
    uid = uuid.uuid4().hex[:16]
    return f"{prefix}_{uid}" if prefix else uid


def birth_data_fallback(
    datetime_utc: datetime,
    location: GeoLocation,
    time_known: bool,
) -> BirthData:
    """构造 BirthData，时间未知时降级为正午并标记 time_known=False。

    PRD §8 精度降级：未知出生时间 → 默认正午 + 宫位结论精度受限提示。
    若 time_known=False，时分被替换为正午（保留日期与时区），
    由结论管道负责输出"精度不足"提示。

    - datetime_utc: 出生 UTC 时间（可为任意时分——time_known=False 时会被覆盖）
    - location: 出生地点
    - time_known: 用户是否提供了精确到分钟的出生时间
    """
    if time_known:
        return BirthData(datetime_utc=datetime_utc, location=location, time_known=True)

    noon = datetime_utc.replace(
        hour=BIRTH_UNKNOWN_FALLBACK_HOUR, minute=0, second=0, microsecond=0
    )
    return BirthData(datetime_utc=noon, location=location, time_known=False)


def deterministic_id(*parts: str) -> str:
    """由内容生成确定性 ID（用于缓存键 / 幂等）。"""
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def utc_now() -> datetime:
    """当前 UTC 时间（naive，统一约定）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_now_aware() -> datetime:
    return datetime.now(timezone.utc)


def to_json(obj: Any) -> str:
    """dataclass/枚举 安全序列化。"""
    return json.dumps(obj, default=_json_default, ensure_ascii=False)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (datetime, timezone)):
        return obj.isoformat()
    if hasattr(obj, "__dict__"):  # dataclass 等
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    if isinstance(obj, (set, tuple)):
        return list(obj)
    return str(obj)


def monotonic_ms() -> int:
    """单调毫秒，用于性能监控。"""
    return int(time.monotonic() * 1000)
