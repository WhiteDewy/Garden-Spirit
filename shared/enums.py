"""Garden-Spirit 全系统共享枚举。

这是整个系统唯一的数据契约之一：所有模块引用这里的枚举，不允许各自发明字符串常量。
"""

from enum import Enum


class Planet(str, Enum):
    """天体。值统一小写 snake_case。"""

    SUN = "sun"
    MOON = "moon"
    MERCURY = "mercury"
    VENUS = "venus"
    MARS = "mars"
    JUPITER = "jupiter"
    SATURN = "saturn"
    URANUS = "uranus"
    NEPTUNE = "neptune"
    PLUTO = "pluto"
    NORTH_NODE = "north_node"
    SOUTH_NODE = "south_node"
    CHIRON = "chiron"
    LILITH = "lilith"


class Sign(str, Enum):
    """黄道十二星座。"""

    ARIES = "aries"
    TAURUS = "taurus"
    GEMINI = "gemini"
    CANCER = "cancer"
    LEO = "leo"
    VIRGO = "virgo"
    LIBRA = "libra"
    SCORPIO = "scorpio"
    SAGITTARIUS = "sagittarius"
    CAPRICORN = "capricorn"
    AQUARIUS = "aquarius"
    PISCES = "pisces"


class Element(str, Enum):
    """四大元素。"""

    FIRE = "fire"
    EARTH = "earth"
    AIR = "air"
    WATER = "water"


class Modality(str, Enum):
    """星座模式。"""

    CARDINAL = "cardinal"
    FIXED = "fixed"
    MUTABLE = "mutable"


class Gender(str, Enum):
    """星体性别（传统占星概念，非生物学性别）。"""

    MASCULINE = "masculine"
    FEMININE = "feminine"


class ChartType(str, Enum):
    """图表类型。"""

    NATAL = "natal"
    TRANSIT = "transit"
    SOLAR_RETURN = "solar_return"
    LUNAR_RETURN = "lunar_return"
    ANNUAL_PROFECTION = "annual_profection"
    FIRDARIA = "firdaria"
    SECONDARY_PROGRESSION = "secondary_progression"
    SYNASTRY = "synastry"
    COMPOSITE = "composite"


class ZodiacType(str, Enum):
    """黄道类型：回归 / 恒星。"""

    TROPICAL = "tropical"
    SIDEREAL = "sidereal"


class HouseSystem(str, Enum):
    """宫位制。值为 pyswisseph 的 House system 单字母代码。"""

    PLACIDUS = "P"
    KOCH = "K"
    PORPHYRY = "O"
    REGIOMONTANUS = "R"
    CAMPANUS = "C"
    EQUAL = "E"
    WHOLE_SIGN = "W"
    ALCABITIUS = "B"


class AspectType(str, Enum):
    """相位类型。"""

    CONJUNCTION = "conjunction"        # 0°
    OPPOSITION = "opposition"          # 180°
    TRINE = "trine"                    # 120°
    SQUARE = "square"                  # 90°
    SEXTILE = "sextile"                # 60°
    QUINCUNX = "quincunx"              # 150°
    SEMISEXTILE = "semisextile"        # 30°
    SEMISQUARE = "semisquare"          # 45°
    SESQUIQUADRATE = "sesquiquadrate"  # 135°
    QUINTILE = "quintile"              # 72°
    BIQUINTILE = "biquintile"          # 144°


class AspectApplication(str, Enum):
    """相位入相/出相状态。入相 = 正在接近精确，对时机更有意义。"""

    APPLYING = "applying"
    SEPARATING = "separating"
    EXACT = "exact"


class PlanetSpeed(str, Enum):
    """行星运行方向/状态。"""

    DIRECT = "direct"
    RETROGRADE = "retrograde"
    STATIONARY_DIRECT = "stationary_direct"
    STATIONARY_RETROGRADE = "stationary_retrograde"


class DignityState(str, Enum):
    """先天尊贵（Essential Dignity）状态。"""

    DOMICILE = "domicile"
    EXALTATION = "exaltation"
    TRIPLICITY = "triplicity"
    TERM = "term"
    FACE = "face"
    PEREGRINE = "peregrine"
    DETRIMENT = "detriment"
    FALL = "fall"


class Sect(str, Enum):
    """昼/夜 sect。"""

    DAY = "day"
    NIGHT = "night"


class IntentDomain(str, Enum):
    """八大意图领域。"""

    CAREER = "career"
    RELATIONSHIP = "relationship"
    WEALTH = "wealth"
    HEALTH = "health"
    EMOTION = "emotion"
    FAMILY = "family"
    LEARNING = "learning"
    DAILY = "daily"


class EvidencePolarity(str, Enum):
    """证据极性。"""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class EvidenceConfidence(str, Enum):
    """证据置信度（分档）。"""

    VERY_HIGH = "very_high"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    SPECULATIVE = "speculative"


class FactCategory(str, Enum):
    """事实类别。用于按类过滤 FactSet。"""

    POSITION = "position"
    ASPECT = "aspect"
    DIGNITY = "dignity"
    RECEPTION = "reception"
    LORDSHIP = "lordship"
    STRENGTH = "strength"
    PATTERN = "pattern"
    TIMING = "timing"
    SPECIAL_POINT = "special_point"
    THEME = "theme"          # 分析模块直接写主题倾向的事实


class ConclusionCategory(str, Enum):
    """结论条目类别。"""

    FINDING = "finding"
    WARNING = "warning"
    RECOMMENDATION = "recommendation"
    TIMING_ADVICE = "timing_advice"
    SUMMARY = "summary"


class Verdict(str, Enum):
    """结论判定。"""

    FAVORABLE = "favorable"
    UNFAVORABLE = "unfavorable"
    NEUTRAL = "neutral"
    NEEDS_MORE_DATA = "needs_more_data"


class Priority(str, Enum):
    """优先级。"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Role(str, Enum):
    """对话角色。"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class PersonaType(str, Enum):
    """十大星灵人格（占位名，产品阶段可改）。"""

    ZIRCON = "zircon"          # 锆石
    OBSIDIAN = "obsidian"      # 黑曜石
    AMETHYST = "amethyst"      # 紫水晶
    CITRINE = "citrine"        # 黄水晶
    ROSE_QUARTZ = "rose_quartz"  # 粉晶
    TURQUOISE = "turquoise"    # 绿松石
    MOONSTONE = "moonstone"    # 月光石
    JADE = "jade"              # 翡翠
    GARNET = "garnet"          # 石榴石
    LAPIS = "lapis"            # 青金石
