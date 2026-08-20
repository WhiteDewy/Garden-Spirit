"""天文与占星常量。纯数据，无逻辑。

注意：占星的解释性规则（尊贵、互容、宫位含义等）不在这里，
它们放在 domain/astrology/knowledge/*.yaml（可数据化配置）。
这里只放不可变的基础常量。"""

from shared.enums import AspectType, HouseSystem, Planet, Sign, ZodiacType

# --- 黄道 ---
SIGNS_IN_ORDER: list[Sign] = [
    Sign.ARIES, Sign.TAURUS, Sign.GEMINI, Sign.CANCER,
    Sign.LEO, Sign.VIRGO, Sign.LIBRA, Sign.SCORPIO,
    Sign.SAGITTARIUS, Sign.CAPRICORN, Sign.AQUARIUS, Sign.PISCES,
]

DEGREES_PER_SIGN: float = 30.0
FULL_CIRCLE: float = 360.0

# --- 行星 ---
PLANETS_IN_ORDER: list[Planet] = [
    Planet.SUN, Planet.MOON, Planet.MERCURY, Planet.VENUS, Planet.MARS,
    Planet.JUPITER, Planet.SATURN, Planet.URANUS, Planet.NEPTUNE, Planet.PLUTO,
]

TRADITIONAL_PLANETS: list[Planet] = [
    Planet.SUN, Planet.MOON, Planet.MERCURY, Planet.VENUS, Planet.MARS,
    Planet.JUPITER, Planet.SATURN,
]

OUTER_PLANETS: list[Planet] = [Planet.URANUS, Planet.NEPTUNE, Planet.PLUTO]

PERSONAL_PLANETS: list[Planet] = [
    Planet.SUN, Planet.MOON, Planet.MERCURY, Planet.VENUS, Planet.MARS,
]

SOCIAL_PLANETS: list[Planet] = [Planet.JUPITER, Planet.SATURN]

LUMINARIES: list[Planet] = [Planet.SUN, Planet.MOON]

# --- 庙旺（现代 + 传统两套，knowledge YAML 决定用哪套） ---
DOMICILE_RULER_MODERN: dict[Sign, Planet] = {
    Sign.ARIES: Planet.MARS,
    Sign.TAURUS: Planet.VENUS,
    Sign.GEMINI: Planet.MERCURY,
    Sign.CANCER: Planet.MOON,
    Sign.LEO: Planet.SUN,
    Sign.VIRGO: Planet.MERCURY,
    Sign.LIBRA: Planet.VENUS,
    Sign.SCORPIO: Planet.PLUTO,
    Sign.SAGITTARIUS: Planet.JUPITER,
    Sign.CAPRICORN: Planet.SATURN,
    Sign.AQUARIUS: Planet.URANUS,
    Sign.PISCES: Planet.NEPTUNE,
}

DOMICILE_RULER_TRADITIONAL: dict[Sign, Planet] = {
    Sign.ARIES: Planet.MARS,
    Sign.TAURUS: Planet.VENUS,
    Sign.GEMINI: Planet.MERCURY,
    Sign.CANCER: Planet.MOON,
    Sign.LEO: Planet.SUN,
    Sign.VIRGO: Planet.MERCURY,
    Sign.LIBRA: Planet.VENUS,
    Sign.SCORPIO: Planet.MARS,
    Sign.SAGITTARIUS: Planet.JUPITER,
    Sign.CAPRICORN: Planet.SATURN,
    Sign.AQUARIUS: Planet.SATURN,
    Sign.PISCES: Planet.JUPITER,
}

EXALTATION_SIGN: dict[Planet, Sign] = {
    Planet.SUN: Sign.ARIES,
    Planet.MOON: Sign.TAURUS,
    Planet.MERCURY: Sign.VIRGO,
    Planet.VENUS: Sign.PISCES,
    Planet.MARS: Sign.CAPRICORN,
    Planet.JUPITER: Sign.CANCER,
    Planet.SATURN: Sign.LIBRA,
}

EXALTATION_DEGREE: dict[Planet, float] = {
    Planet.SUN: 19.0,
    Planet.MOON: 3.0,
    Planet.MERCURY: 15.0,
    Planet.VENUS: 27.0,
    Planet.MARS: 28.0,
    Planet.JUPITER: 15.0,
    Planet.SATURN: 21.0,
}

FALL_SIGN: dict[Planet, Sign] = {
    Planet.SUN: Sign.LIBRA,
    Planet.MOON: Sign.SCORPIO,
    Planet.MERCURY: Sign.PISCES,
    Planet.VENUS: Sign.VIRGO,
    Planet.MARS: Sign.CANCER,
    Planet.JUPITER: Sign.CAPRICORN,
    Planet.SATURN: Sign.ARIES,
}

# --- 相位容许度（度） ---
DEFAULT_ORBS: dict[AspectType, float] = {
    AspectType.CONJUNCTION: 8.0,
    AspectType.OPPOSITION: 8.0,
    AspectType.TRINE: 8.0,
    AspectType.SQUARE: 7.0,
    AspectType.SEXTILE: 5.0,
    AspectType.QUINCUNX: 3.0,
    AspectType.SEMISEXTILE: 2.0,
    AspectType.SESQUIQUADRATE: 2.0,
    AspectType.SEMISQUARE: 2.0,
    AspectType.QUINTILE: 1.5,
    AspectType.BIQUINTILE: 1.5,
}

# 曜日（日月）相位可加宽容许度
LUMINARY_ORB_EXTENSION: float = 2.0

# --- pyswisseph 天体 ID ---
SE_PLANET_IDS: dict[Planet, int] = {
    Planet.SUN: 0,
    Planet.MOON: 1,
    Planet.MERCURY: 2,
    Planet.VENUS: 3,
    Planet.MARS: 4,
    Planet.JUPITER: 5,
    Planet.SATURN: 6,
    Planet.URANUS: 7,
    Planet.NEPTUNE: 8,
    Planet.PLUTO: 9,
    Planet.NORTH_NODE: 10,   # 平均北交点
    Planet.SOUTH_NODE: 11,   # 由北交点推导
    Planet.CHIRON: 15,
    Planet.LILITH: 21,       # 摆动黑月（oscillating）
}

# --- 宫位分类 ---
ANGULAR_HOUSES: tuple[int, ...] = (1, 4, 7, 10)
SUCCEDENT_HOUSES: tuple[int, ...] = (2, 5, 8, 11)
CADENT_HOUSES: tuple[int, ...] = (3, 6, 9, 12)

# --- 全局默认（v1 冻结决策） ---
DEFAULT_ZODIAC: ZodiacType = ZodiacType.TROPICAL
DEFAULT_HOUSE_SYSTEM: HouseSystem = HouseSystem.ALCABITIUS

# 出生时间未知时默认用正午
BIRTH_UNKNOWN_FALLBACK_HOUR: int = 12

# 尊贵状态中文名（描述模板用）
DIGNITY_STATE_ZH: dict[str, str] = {
    "domicile": "入庙",
    "exaltation": "曜升",
    "triplicity": "三分主",
    "term": "在界",
    "face": "在面",
    "peregrine": "游走",
    "detriment": "失势",
    "fall": "落陷",
}

# 相位中文名（描述模板用）
ASPECT_ZH: dict[str, str] = {
    "conjunction": "合相",
    "opposition": "对冲",
    "trine": "拱相",
    "square": "刑相",
    "sextile": "六合",
    "quincunx": "梅花相位",
    "semisextile": "半六合",
    "semisquare": "半刑",
    "sesquiquadrate": "补八分相",
    "quintile": "五分相",
    "biquintile": "倍五分相",
}

# 宫位制中文名（解读标注用）
HOUSE_SYSTEM_ZH: dict[str, str] = {
    "placidus": "普拉西度（Placidus）",
    "alcabitius": "阿卡比特（Alcabitius）",
    "koch": "科赫（Koch）",
    "porphyry": "波菲利（Porphyry）",
    "regiomontanus": "雷吉欧蒙塔努斯（Regiomontanus）",
    "campanus": "坎帕努斯（Campanus）",
    "equal": "等宫制（Equal）",
    "whole_sign": "整宫制（Whole Sign）",
}
