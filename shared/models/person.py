"""Person 模型：用户身份与出生数据。

出生数据是敏感信息，本模型只承载数据，不承载存储/加密逻辑
（存储与加密在 foundation/database）。
"""

from dataclasses import dataclass, field
from datetime import datetime

from shared.enums import HouseSystem
from shared.types import Altitude, EntityId, Latitude, Longitude


@dataclass(frozen=True)
class GeoLocation:
    """地理坐标（不可变）。"""

    latitude: Latitude
    longitude: Longitude
    altitude: Altitude = 0.0
    timezone_name: str = "UTC"        # IANA 时区名，如 "Asia/Shanghai"
    place_name: str = ""              # 人类可读地名，如 "上海"

    def __post_init__(self) -> None:
        if not (-90.0 <= self.latitude <= 90.0):
            raise ValueError(f"纬度越界: {self.latitude}")
        if not (-180.0 <= self.longitude <= 180.0):
            raise ValueError(f"经度越界: {self.longitude}")


@dataclass(frozen=True)
class BirthData:
    """出生数据（不可变）。datetime_utc 是唯一权威时间。

    time_known: 用户是否提供了精确到分钟的出生时间。
        若为 False，datetime_utc 的时分由 foundation 层的降级策略
        （默认正午 12:00）填充，结论应提示"出生时间精度不足"。
    """

    datetime_utc: datetime
    location: GeoLocation
    time_known: bool = True

    def __post_init__(self) -> None:
        if self.datetime_utc.tzinfo is None:
            raise ValueError("datetime_utc 必须带时区信息（UTC）")


@dataclass
class Person:
    """用户档案。只有非身份字段可变。"""

    id: EntityId
    name: str
    birth: BirthData
    gender: str | None = None
    notes: str = ""
    #: 用户偏好的宫位制；None = 用全局默认（EphemerisConfig.default_house_system）
    house_system: HouseSystem | None = None
    #: 图表缓存。key 需含宫位制（如 "natal:placidus"），避免跨系统串图
    chart_cache: dict[str, str] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __hash__(self) -> int:
        return hash(self.id)
