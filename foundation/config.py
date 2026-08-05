"""AppConfig：全局配置。

配置从环境变量 + 可选 .env 加载。所有 v1 冻结决策的默认值集中在此。
"""

from dataclasses import dataclass, field

from shared.enums import HouseSystem, PersonaType, ZodiacType


@dataclass
class EphemerisConfig:
    """天文计算配置。"""

    ephemeris_path: str = "./data/ephemeris"
    zodiac: ZodiacType = ZodiacType.TROPICAL        # v1 决策：回归黄道
    default_house_system: HouseSystem = HouseSystem.PLACIDUS  # v1 决策：象限制
    ayanamsa: str = "lahiri"                        # 仅 SIDEREAL 时使用


@dataclass
class LLMConfig:
    """LLM 配置。LLM 永远只做两件事：意图槽抽取 + 结论转述。"""

    provider: str = "openai"    # "openai" | "anthropic" | "google"
    base_url: str = ""          # 留空 → 用 provider 默认；可覆盖为兼容网关
    model: str = "gpt-4o"
    api_key: str = ""           # 从环境变量加载，不硬编码
    temperature: float = 0.7
    max_tokens: int = 4096
    request_timeout: int = 60


@dataclass
class EvidenceConfig:
    """证据规则（原则三防火墙的默认参数，可被 Strategy YAML 覆盖）。"""

    positive_weight: float = 1.0
    negative_weight: float = 0.8      # 负证据绝对值默认权重
    min_confidence: float = 0.3       # 低于此置信度的证据不进入结论
    conflict_threshold: float = 0.15  # |净分| 低于此值 → NEEDS_MORE_DATA


@dataclass
class StorageConfig:
    """出生数据持久化配置（PRD §8 红线：加密存储）。"""

    db_path: str = "./data/garden_spirit.db"
    #: 加密密钥（Fernet key，base64 url-safe）。留空 → 自动生成随机密钥（仅开发）。
    #: 生产必须通过环境变量 GS_ENCRYPTION_KEY 提供。
    encryption_key: str = ""


@dataclass
class AppConfig:
    """应用级配置。"""

    ephemeris: EphemerisConfig = field(default_factory=EphemerisConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    evidence: EvidenceConfig = field(default_factory=EvidenceConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)

    default_persona: PersonaType = PersonaType.ZIRCON
    cache_ttl_seconds: int = 3600
    max_conversation_turns: int = 50
    debug: bool = False
    log_level: str = "INFO"
    #: 返回盘（日返/月返）默认排盘地点：birth_place（默认出生地）/ current_place
    #: 留作后期可改——宫位随地点变，改这里即可全局切换
    return_chart_location: str = "birth_place"
