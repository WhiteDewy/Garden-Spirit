"""PlanetActivation —— 语境定刻（self_map_design §1.1.1）。

「写给」是动态的：**星盘定底 × 语境定刻**。
- 星盘定底：本命相位/落宫 → 每颗星的长期课题端（Domain 出，硬线内）。
- 语境定刻：**此刻哪一面被激活**。LLM 只报"哪颗星被触动"，不判方向。
- 方向由 Domain 相位表出（硬线：占星结论全由 Domain 出，LLM 自由度只在"怎么疗愈"）。

本模块 = 语境定刻的一半：
- `PlanetActivationClassifier.classify()`：消息 → 被触动的 10 星灵（受控枚举），
  LLM 优先、规则兜底。**只报激活，不产生任何占星解读、不判方向**。
- 情绪×诉求由 EmotionPerception 出（§7.1），抓手=用户原话——两部分在此组装成
  `PlanetActivation`（"哪颗星被触动 + 当下情绪/诉求 + 抓手"），供软牵引共振星灵（§7.3）、
  落款推导链（§6.2）、10 星灵回归（§1.1）消费。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from foundation.logger import get_logger
from shared.enums import EmotionState, Planet, RequestType

logger = get_logger("application.conversation.planet_activation")

#: 10 星灵（回归行星）：古典十大，不含南北交点/凯龙/莉莉丝
ACTIVATABLE_PLANETS: tuple[Planet, ...] = (
    Planet.SUN, Planet.MOON, Planet.MERCURY, Planet.VENUS, Planet.MARS,
    Planet.JUPITER, Planet.SATURN, Planet.URANUS, Planet.NEPTUNE, Planet.PLUTO,
)

#: 一条消息最多激活几颗星（主信号在前；落款取第一颗）
MAX_ACTIVATED = 3


@dataclass
class PlanetActivation:
    """一次"语境定刻"的结果。

    planets：被触动的星灵（主信号在前）。trigger：抓手（用户原话）。
    emotion / request：当下情绪×诉求（来自 EmotionPerception，非本模块判）。
    """

    planets: list[Planet] = field(default_factory=list)
    trigger: str = ""
    emotion: EmotionState | None = None
    request: RequestType | None = None

    @property
    def primary(self) -> Planet | None:
        """共振星灵（主信号）：落款 / 软牵引取第一颗。"""
        return self.planets[0] if self.planets else None


#: 规则兜底关键词（每颗星被什么话题触动——与 34 子类触发语义对齐）
_PLANET_KEYWORDS: dict[Planet, tuple[str, ...]] = {
    Planet.SUN:     ("成就感", "人生目标", "想成为", "抱负", "使命", "自我价值", "我是谁"),
    Planet.MOON:    ("心情", "难过", "委屈", "想哭", "安全感", "原生家庭", "情绪"),
    Planet.MERCURY: ("学习", "沟通", "逻辑", "分析", "写作", "想不通", "考试"),
    Planet.VENUS:   ("恋爱", "爱情", "喜欢的人", "浪漫", "审美", "美食"),
    Planet.MARS:    ("生气", "愤怒", "竞争", "解压", "冲动", "行动力", "运动"),
    Planet.JUPITER: ("旅行", "远方", "哲学", "人生意义", "乐观", "希望"),
    Planet.SATURN:  ("压力", "责任", "自律", "纪律", "边界", "背负", "恐惧", "工作"),
    Planet.URANUS:  ("打破常规", "特立独行", "叛逆", "革新", "变化"),
    Planet.NEPTUNE: ("做梦", "梦到", "发呆", "灵感", "迷茫", "梦幻"),
    Planet.PLUTO:   ("秘密", "创伤", "至暗", "重生", "深藏", "阴影", "控制"),
}

#: LLM 分类 system prompt（受控枚举：只能从 10 星灵里选，不发明）
_PLANET_ACTIVATE_SYSTEM = """你是星灵花园的"星灵激活器"。读用户的一句话，判断此刻哪颗星灵被触动了。

可选星灵（只从这些里选，不要发明）：
- sun = 太阳（成就感、人生目标、想成为的人）
- moon = 月亮（心情起伏、安全感、想被安慰）
- mercury = 水星（学习、沟通、思考）
- venus = 金星（爱与被爱、审美、浪漫）
- mars = 火星（行动、愤怒、解压、想冲一把）
- jupiter = 木星（远方、信念、乐观）
- saturn = 土星（责任、压力、边界）
- uranus = 天王星（挣脱、打破常规）
- neptune = 海王星（做梦、迷茫、灵感）
- pluto = 冥王星（深藏、创伤、深刻转变）

规则：
- 只报"哪颗星被触动"，最多 3 颗，主信号在前。
- 绝不解释含义、不判方向、不写任何占星判断。
- 没被触动的 → 空数组。

只输出 JSON（不要任何解释）：
{"planets": ["moon"]}
"""


class PlanetActivationClassifier:
    """消息 → 被触动的星灵列表（LLM 优先，规则兜底）。"""

    def __init__(self, llm_client=None):
        self._llm = llm_client

    def classify(self, message: str) -> list[Planet]:
        """分类一条消息 → 被触动的星灵（去重、限 3 个、只含 10 星灵）。"""
        if not message or not message.strip():
            return []

        if self._llm is not None and getattr(self._llm, "available", True):
            result = self._llm_classify(message)
            if result is not None:
                return result

        return self._rule_fallback(message)

    # ------------------------------------------------------------------

    def _llm_classify(self, message: str) -> list[Planet] | None:
        """LLM 分类。失败/返回无效 → None（规则兜底）。返回 [] 也算合法。"""
        try:
            if not hasattr(self._llm, "complete"):
                return None
            from foundation.llm.client import LLMClient

            raw = self._llm.complete(
                prompt=message,
                system=_PLANET_ACTIVATE_SYSTEM,
                temperature=0.0,
            )
            data = LLMClient._parse_slots_json(raw)
            if not isinstance(data, dict):
                return None
            raw_planets = data.get("planets")
            if not isinstance(raw_planets, list):
                return None
            planets: list[Planet] = []
            for raw_planet in raw_planets:
                try:
                    planet = Planet(str(raw_planet).strip().lower())
                except ValueError:
                    continue  # LLM 发明了星灵 → 不信它，丢弃
                if planet in ACTIVATABLE_PLANETS and planet not in planets:
                    planets.append(planet)
            return planets[:MAX_ACTIVATED]
        except Exception:  # noqa: BLE001 - 降级不阻断
            logger.warning("星灵激活 LLM 分类失败，规则兜底")
            return None

    def _rule_fallback(self, message: str) -> list[Planet]:
        """关键词兜底：按命中数降序取前 3。同分按目录顺序（sun 在前）。"""
        scored: list[tuple[int, int, Planet]] = []
        for i, planet in enumerate(ACTIVATABLE_PLANETS):
            hits = sum(1 for kw in _PLANET_KEYWORDS.get(planet, ()) if kw in message)
            if hits > 0:
                scored.append((hits, -i, planet))  # 命中数降序，同分目录顺序升序
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [planet for _, _, planet in scored[:MAX_ACTIVATED]]


__all__ = [
    "PlanetActivation",
    "PlanetActivationClassifier",
    "ACTIVATABLE_PLANETS",
    "MAX_ACTIVATED",
]
