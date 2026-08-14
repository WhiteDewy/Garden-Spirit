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
    """十一大意图领域（领域引擎 v2）。

    在原有八域基础上：感情加宽（收 12 宫暗面）、新增 growth 远方·信念、
    新增 network 人际·社群、新增 self 自我。daily 保留为跨域行运视图。
    词汇与 planet_nature/house_significations 语义场标签对齐（docs/domain_engine_v2.md）。
    """

    CAREER = "career"            # 事业：10/6/2/1
    RELATIONSHIP = "relationship"  # 感情（宽）：5/7/8/12 整条光谱
    WEALTH = "wealth"            # 财富：2/8/11
    HEALTH = "health"            # 健康：1/6/12
    EMOTION = "emotion"          # 情绪：4/8/12
    FAMILY = "family"            # 家庭：4/5(亲子)/10
    LEARNING = "learning"        # 学习：3/6
    GROWTH = "growth"            # 远方·信念：9/12（留学/深造/信仰/人生意义）
    NETWORK = "network"          # 人际·社群：11/3/7（朋友/人脉/圈子/团队）
    SELF = "self"                # 自我：1/9/12（我是谁/人格/内在成长）
    DAILY = "daily"              # 每日运势（跨域行运视图，非语义场域）


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


class EmotionState(str, Enum):
    """用户情绪状态（情绪感知层——陪伴协议第 1 步）。

    只描述"此刻的情绪"，不描述用户人格（对应 self_map_design §7.1：
    按 情绪状态 × 诉求类型 判断，而非按领域分类）。
    """

    CALM = "calm"            # 平静/日常
    HAPPY = "happy"          # 开心/满足
    LOW = "low"              # 低落/难过/伤心
    ANXIOUS = "anxious"      # 焦虑/担心/不安
    ANGRY = "angry"          # 生气/烦躁
    TIRED = "tired"          # 疲惫/无力
    LONELY = "lonely"        # 孤独/想被陪伴
    CONFUSED = "confused"    # 迷茫/纠结/想不通
    PRESSURED = "pressured"  # 压力大/紧绷
    FEARFUL = "fearful"      # 害怕/恐惧


class RequestType(str, Enum):
    """诉求类型（情绪感知层）——用户此刻最想要的回应方式。

    self_map_design §7.1 定稿四选一：被听见 / 被安慰 / 被梳理 / 被推动。
    软牵引门控（§7.3）据此决定"递盘 or 继续陪"。
    """

    HEARD = "heard"        # 被听见：分享/倾诉，想要认真听
    SOOTHED = "soothed"    # 被安慰：难过/累，想要安抚
    SORTED = "sorted"      # 被梳理：一团乱/纠结/要决策，想要理清
    PUSHED = "pushed"      # 被推动：没动力/犹豫，想要方向推一把


class ConsultMode(str, Enum):
    """咨询模式——影响分析深度与叙事长度（产品层"今天想怎么聊"）。

    MVP 实现 quick/deep；annual/chart/free 框架预留（当前映射到默认深度）。
    """

    QUICK = "quick"    # 快速咨询：简洁回答（共情+核心判断+一句出路）
    DEEP = "deep"      # 深度咨询：完整叙事（现状默认）
    ANNUAL = "annual"  # 年度主题（框架预留）
    CHART = "chart"    # 星盘解析（框架预留）
    FREE = "free"      # 自由聊天（框架预留）


class TrustLevel(str, Enum):
    """信任等级（A2 关系层）——由 trust_score 推导，等级只读不存。

    陌生 → 认识 → 信任 → 深交。深度优先：一次深聊 > 十次闲聊。
    """

    STRANGER = "stranger"           # 陌生
    ACQUAINTANCE = "acquaintance"   # 认识
    TRUSTED = "trusted"             # 信任
    INTIMATE = "intimate"           # 深交


class PersonaType(str, Enum):
    """十大星灵人格（self_map_design §1.1 回归行星）——人格只改变语言风格，不改结论。

    值 = 行星名（与 Planet 值一致），疗愈名（想被看见的我…）见
    application/mailbox/signature.py HEALING_NAMES（单一来源）。
    默认人格 = 月亮（产品 mascot：每日来信默认 sender moon / 聊天占位 🌙）。
    """

    SUN = "sun"          # 太阳 · 想被看见的我
    MOON = "moon"        # 月亮 · 想被抱抱的我
    MERCURY = "mercury"  # 水星 · 想说话的我
    VENUS = "venus"      # 金星 · 想爱与被爱的我
    MARS = "mars"        # 火星 · 想要就冲的我
    JUPITER = "jupiter"  # 木星 · 想飞的我
    SATURN = "saturn"    # 土星 · 想负责的我
    URANUS = "uranus"    # 天王星 · 想挣脱的我
    NEPTUNE = "neptune"  # 海王星 · 想做梦的我
    PLUTO = "pluto"      # 冥王星 · 想深挖的我
