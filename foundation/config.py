"""AppConfig：全局配置。

配置从环境变量 + 可选 .env 加载。所有 v1 冻结决策的默认值集中在此。

.env 从项目根目录加载（gitignored），真实环境变量优先于 .env。
密钥类配置（GS_AMAP_KEY / GS_ENCRYPTION_KEY / LLM api_key）见 .env.example。
"""

from dataclasses import dataclass, field

from dotenv import load_dotenv

from shared.enums import HouseSystem, PersonaType, ZodiacType

load_dotenv()  # 项目根 .env；不覆盖已存在的环境变量


@dataclass
class EphemerisConfig:
    """天文计算配置。"""

    ephemeris_path: str = "./data/ephemeris"
    zodiac: ZodiacType = ZodiacType.TROPICAL        # v1 决策：回归黄道
    default_house_system: HouseSystem = HouseSystem.ALCABITIUS  # 产品默认：阿卡比特
    ayanamsa: str = "lahiri"                        # 仅 SIDEREAL 时使用


@dataclass
class LLMConfig:
    """LLM 配置。LLM 永远只做两件事：意图槽抽取 + 结论转述。

    从环境变量加载（.env 或系统环境），不硬编码：
      LLM_PROVIDER / LLM_BASE_URL / LLM_MODEL / LLM_API_KEY
    """

    provider: str = "openai"    # "openai" | "anthropic" | "google"
    base_url: str = ""          # 留空 → 用 provider 默认；可覆盖为兼容网关
    model: str = "gpt-4o"
    api_key: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    request_timeout: int = 60

    def __post_init__(self) -> None:
        import os

        # 原则：显式传入的字段（非默认值）优先于环境变量——测试注入 fake/key 不被覆盖。
        # GS_LLM_DISABLE=1：跳过从环境读 key（CI/测试/无网环境），应用默认即不可用。
        if os.getenv("GS_LLM_DISABLE", "").strip().lower() in ("1", "true", "yes"):
            return
        if self.provider == "openai":
            self.provider = os.getenv("LLM_PROVIDER", self.provider)
        if not self.base_url:
            self.base_url = os.getenv("LLM_BASE_URL", self.base_url)
        if self.model == "gpt-4o":
            self.model = os.getenv("LLM_MODEL", self.model)
        if not self.api_key:
            self.api_key = os.getenv("LLM_API_KEY", self.api_key)


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
    #: 加密密钥（Fernet key，base64 url-safe）。生产必须通过环境变量 GS_ENCRYPTION_KEY 提供。
    #: create_app 对持久化文件库会 fail-fast；仅 :memory: 测试允许底层随机开发密钥。
    encryption_key: str = ""

    def __post_init__(self) -> None:
        import os

        if not self.encryption_key:
            self.encryption_key = os.getenv("GS_ENCRYPTION_KEY", "")


@dataclass
class PushConfig:
    """Web Push 通知配置（VAPID 密钥对）。

    从环境变量加载（.env 或系统环境），不硬编码：
      GS_VAPID_PRIVATE_KEY / GS_VAPID_PUBLIC_KEY / GS_VAPID_SUBJECT
    VAPID 密钥对生成见 .env.example。
    """

    vapid_private_key: str = ""
    vapid_public_key: str = ""
    vapid_subject: str = "mailto:admin@garden-spirit.app"

    def __post_init__(self) -> None:
        import os

        if not self.vapid_private_key:
            self.vapid_private_key = os.getenv("GS_VAPID_PRIVATE_KEY", "")
        if not self.vapid_public_key:
            self.vapid_public_key = os.getenv("GS_VAPID_PUBLIC_KEY", "")
        if self.vapid_subject == "mailto:admin@garden-spirit.app":
            self.vapid_subject = os.getenv("GS_VAPID_SUBJECT", self.vapid_subject)


@dataclass
class AppConfig:
    """应用级配置。"""

    ephemeris: EphemerisConfig = field(default_factory=EphemerisConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    evidence: EvidenceConfig = field(default_factory=EvidenceConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    push: PushConfig = field(default_factory=PushConfig)

    default_persona: PersonaType = PersonaType.MOON  # 产品默认星灵 = 月亮（mascot）
    cache_ttl_seconds: int = 3600
    max_conversation_turns: int = 50
    debug: bool = False
    log_level: str = "INFO"
    #: 返回盘（日返/月返）默认排盘地点：birth_place（默认出生地）/ current_place
    #: 留作后期可改——宫位随地点变，改这里即可全局切换
    return_chart_location: str = "birth_place"

    def __post_init__(self) -> None:
        import os

        if not self.debug:
            self.debug = os.getenv("GS_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")
