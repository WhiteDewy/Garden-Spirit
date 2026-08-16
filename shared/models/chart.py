"""Chart 模型：统一星盘数据结构。

**这是唯一跨越 foundation → domain 的模型。**
- 所有计算器（NatalChart/Transit/Synastry...）都产出 Chart。
- 所有分析模块只消费 FactSet（由 Chart 派生），不直接消费 Chart。
- Application 层永远看不到 Chart。

Chart 是一张"可测试的图（graph）"：行星位置 + 宫位 + 相位 + 尊贵 + 特殊点。
"""

from dataclasses import dataclass, field
from datetime import datetime

from shared.enums import (
    AspectApplication,
    AspectType,
    ChartType,
    DignityState,
    HouseSystem,
    Planet,
    PlanetSpeed,
    Sect,
    Sign,
    ZodiacType,
)
from shared.types import Degree, EntityId, JulianDay


# --------------------------------------------------------------------------
# 位置原语
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class EclipticPosition:
    """天体在黄道上的位置。"""

    longitude: Degree          # 黄道经度 0-360
    latitude: Degree = 0.0     # 黄纬 -90..+90
    declination: Degree = 0.0  # 赤纬
    right_ascension: Degree = 0.0
    distance_au: float = 0.0   # 距地距离（AU）


@dataclass(frozen=True)
class SignPosition:
    """以星座表述的位置。"""

    sign: Sign
    degree_absolute: Degree   # 绝对黄道经度
    degree_in_sign: float     # 星座内度数 0-30
    minutes: int = 0
    seconds: int = 0


@dataclass(frozen=True)
class HousePosition:
    """宫位落点。"""

    house: int                # 1-12
    cusp_degree: Degree       # 该宫宫头度数
    distance_from_cusp: float # 距宫头度数


# --------------------------------------------------------------------------
# 星盘内天体
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ChartPlanet:
    """一颗行星在星盘中的完整状态。"""

    planet: Planet
    ecliptic: EclipticPosition
    sign: SignPosition
    house: HousePosition
    speed: PlanetSpeed
    speed_deg_per_day: float        # 每日运行度（含正负号）
    is_combust: bool = False        # 距太阳 8.5° 内
    is_cazimi: bool = False         # 距太阳 17 角分内（受日）
    is_under_beams: bool = False    # 距太阳 17° 内（日光下）


@dataclass(frozen=True)
class HouseCusp:
    """宫头。"""

    house: int
    degree: Degree
    sign: Sign


# --------------------------------------------------------------------------
# 相位 / 尊贵 / 特殊点
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Aspect:
    """两星体之间的相位。"""

    body1: Planet
    body2: Planet
    aspect_type: AspectType
    exact_angle: float       # 精确相位角（如 90.0）
    orb: float               # 偏差度数
    application: AspectApplication


@dataclass(frozen=True)
class EssentialDignity:
    """行星在某星座的先天尊贵。"""

    planet: Planet
    sign: Sign
    dignity_state: DignityState
    score: int               # 庙=5 旺=4 三分=3 界=2 面=1 游走=0 陷=-5 弱=-4


@dataclass(frozen=True)
class Lot:
    """阿拉伯点（Fortune/Spirit 等）。"""

    name: str
    formula: str            # 如 "Asc + Moon - Sun"（福点）
    degree: Degree
    sign: Sign
    house: int


@dataclass(frozen=True)
class FixedStarConjunction:
    """行星与恒星合相。"""

    star_name: str
    star_magnitude: float
    planet: Planet
    orb: float
    star_degree: Degree
    star_sign: Sign


@dataclass(frozen=True)
class ChartReception:
    """本命盘互溶快照（出生即定，随 Chart 缓存）。"""

    planet_a: Planet
    planet_b: Planet
    dignities_of_a_at_b: tuple[DignityState, ...]
    dignities_of_b_at_a: tuple[DignityState, ...]
    dignity_type: DignityState
    score: int
    aspect_type: AspectType | None = None
    aspect_nature: str | None = None
    description_zh: str = ""


@dataclass(frozen=True)
class ChartAcceptance:
    """本命盘激活接纳快照（单向尊严 + 相位）。"""

    acceptor: Planet
    accepted: Planet
    dignities: tuple[DignityState, ...]
    dignity_type: DignityState
    score: int
    aspect_type: AspectType
    aspect_nature: str
    description_zh: str = ""


# --------------------------------------------------------------------------
# 星盘本体
# --------------------------------------------------------------------------

@dataclass
class Chart:
    """统一星盘。唯一的跨层模型。"""

    id: EntityId
    person_id: EntityId
    chart_type: ChartType
    calculated_at_utc: datetime        # 计算执行时间

    # 时间与地点
    julian_day: JulianDay
    epoch_utc: datetime                # 该星盘代表的时间点
    location: str                      # 人类可读地点

    # 配置
    zodiac: ZodiacType
    house_system: HouseSystem

    # 核心数据
    planets: dict[Planet, ChartPlanet] = field(default_factory=dict)
    house_cusps: dict[int, HouseCusp] = field(default_factory=dict)  # 1-12
    ascendant: SignPosition | None = None
    midheaven: SignPosition | None = None

    # 派生数据（计算时填充，不现场算）
    aspects: list[Aspect] = field(default_factory=list)
    dignities: dict[Planet, list[EssentialDignity]] = field(default_factory=dict)
    receptions: list[ChartReception] = field(default_factory=list)
    acceptances: list[ChartAcceptance] = field(default_factory=list)
    lots: list[Lot] = field(default_factory=list)
    fixed_star_conjunctions: list[FixedStarConjunction] = field(default_factory=list)

    # 全局状态
    sect: Sect | None = None
    moon_phase: float | None = None    # 0=新月, 0.5=满月

    # 计算层缓存（运行时 memo，非序列化数据）
    planet_assessments: dict = field(default_factory=dict, repr=False, compare=False)

    # 合盘 / 行运：引用其他图表
    reference_chart_id: EntityId | None = None
    reference_chart_type: ChartType | None = None
