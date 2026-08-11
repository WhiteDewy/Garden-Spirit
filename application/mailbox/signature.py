"""落款推导链（self_map_design §6.2）—— 内容 → 情绪需求 → 疗愈名。

来信式日记的落款不是拍脑袋选的，也不是"聊了什么话题就亮哪颗星"——
是识别内容背后的**情绪需求**，映射到对应的疗愈名（§1.1 签名表）。

推导链**显式可解释**（§6.2 实现要求）：
1. LLM 只输出情绪需求（主 / 次）——受控枚举，从 10 个需求里选，不发明。
2. **映射规则**（确定性，无 LLM）决定落款与灵魂碎片：
   - 主信号 → 落款星灵（最强情绪需求定落款）。
   - 次信号 → 灵魂碎片（次需求不浪费，掉进行星子类 + 星座子类）。
3. 每步可回答"为什么是这个落款"——`LetterSignature.explain` 输出完整推导过程。

硬线：本模块不产生占星结论，不判方向。情绪需求是"想要什么"，不是星盘判断。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from foundation.logger import get_logger
from shared.enums import Planet

logger = get_logger("application.mailbox.signature")

#: 一条内容最多认几个次需求（§6.2：次信号掉进灵魂碎片）
MAX_SECONDARY = 2


class EmotionalNeed(str, Enum):
    """情绪需求（= 疗愈名里"想要的部分"，与 §1.1 10 星灵一一对应）。"""

    SEEN = "seen"        # 想被看见 → 太阳
    SOOTHED = "soothed"  # 想被抱抱 → 月亮
    HEARD = "heard"      # 想说话 → 水星
    LOVED = "loved"      # 想爱与被爱 → 金星
    ACT = "act"          # 想要就冲 → 火星
    SOAR = "soar"        # 想飞 → 木星
    RELIEF = "relief"    # 想负责 / 想放下一点 → 土星
    BREAK = "break"      # 想挣脱 → 天王星
    DREAM = "dream"      # 想做梦 → 海王星
    DIG = "dig"          # 想深挖 → 冥王星


#: 需求 → 落款星灵（映射规则：主信号 → 星灵）
_NEED_TO_PLANET: dict[EmotionalNeed, Planet] = {
    EmotionalNeed.SEEN: Planet.SUN,
    EmotionalNeed.SOOTHED: Planet.MOON,
    EmotionalNeed.HEARD: Planet.MERCURY,
    EmotionalNeed.LOVED: Planet.VENUS,
    EmotionalNeed.ACT: Planet.MARS,
    EmotionalNeed.SOAR: Planet.JUPITER,
    EmotionalNeed.RELIEF: Planet.SATURN,
    EmotionalNeed.BREAK: Planet.URANUS,
    EmotionalNeed.DREAM: Planet.NEPTUNE,
    EmotionalNeed.DIG: Planet.PLUTO,
}

#: 落款疗愈名（§1.1 签名表——每颗星既是人格，也是信件的落款）
HEALING_NAMES: dict[Planet, str] = {
    Planet.SUN: "想被看见的我",
    Planet.MOON: "想被抱抱的我",
    Planet.MERCURY: "想说话的我",
    Planet.VENUS: "想爱与被爱的我",
    Planet.MARS: "想要就冲的我",
    Planet.JUPITER: "想飞的我",
    Planet.SATURN: "想负责的我",
    Planet.URANUS: "想挣脱的我",
    Planet.NEPTUNE: "想做梦的我",
    Planet.PLUTO: "想深挖的我",
}

#: 需求 → 灵魂碎片（映射规则：次信号 → 行星子类 + 星座子类）
_NEED_TO_FRAGMENTS: dict[EmotionalNeed, list[str]] = {
    EmotionalNeed.SEEN:    ["sun_core", "leo_glory"],
    EmotionalNeed.SOOTHED: ["moon_tide", "cancer_shell"],
    EmotionalNeed.HEARD:   ["mercury_maze", "gemini_wind"],
    EmotionalNeed.LOVED:   ["venus_love", "libra_balance"],
    EmotionalNeed.ACT:     ["mars_action", "aries_fire"],
    EmotionalNeed.SOAR:    ["jupiter_faith", "sagittarius_arrow"],
    EmotionalNeed.RELIEF:  ["saturn_order", "capricorn_peak"],
    EmotionalNeed.BREAK:   ["uranus_awake", "aquarius_star"],
    EmotionalNeed.DREAM:   ["neptune_dream", "pisces_sea"],
    EmotionalNeed.DIG:     ["pluto_depth", "scorpio_eye"],
}

#: 需求 → 中文名（explain / LLM 指令共用）
_NEED_ZH: dict[EmotionalNeed, str] = {
    EmotionalNeed.SEEN: "想被看见",
    EmotionalNeed.SOOTHED: "想被抱抱",
    EmotionalNeed.HEARD: "想说话",
    EmotionalNeed.LOVED: "想爱与被爱",
    EmotionalNeed.ACT: "想要就冲",
    EmotionalNeed.SOAR: "想飞",
    EmotionalNeed.RELIEF: "想负责/想放下一点",
    EmotionalNeed.BREAK: "想挣脱",
    EmotionalNeed.DREAM: "想做梦",
    EmotionalNeed.DIG: "想深挖",
}

#: 规则兜底：需求关键词（从内容里识别"想要什么"）
_NEED_RULES: dict[EmotionalNeed, tuple[str, ...]] = {
    EmotionalNeed.SEEN:    ("成就", "被看见", "认可", "证明", "发光", "厉害", "自信", "价值"),
    EmotionalNeed.SOOTHED: ("难过", "委屈", "想哭", "好累", "撑不住", "抱抱", "安慰", "脆弱", "孤独", "疲惫"),
    EmotionalNeed.HEARD:   ("想说", "没人听", "话到嘴边", "倾诉", "表达", "憋着", "说不出口"),
    EmotionalNeed.LOVED:   ("恋爱", "被爱", "喜欢的人", "配不上", "不值得", "心动"),
    EmotionalNeed.ACT:     ("行动", "想冲", "犹豫", "不敢", "迈出", "第一步", "拖延", "开始"),
    EmotionalNeed.SOAR:    ("远方", "旅行", "自由", "逃离", "出去", "向往", "开阔", "世界"),
    EmotionalNeed.RELIEF:  ("压力", "责任", "扛", "放下", "背负", "喘口气", "太累", "紧绷"),
    EmotionalNeed.BREAK:   ("挣脱", "打破", "不一样", "束缚", "应该", "叛逆", "框架"),
    EmotionalNeed.DREAM:   ("梦", "幻想", "发呆", "灵感", "浪漫", "沉浸", "想象", "治愈"),
    EmotionalNeed.DIG:     ("秘密", "创伤", "根源", "深处", "直面", "阴影", "疗愈", "为什么"),
}

#: LLM 识别 system prompt（受控枚举：只从 10 个需求里选，不发明）
_NEED_CLASSIFY_SYSTEM = """你是星灵花园的情绪需求识别器。读用户的一段话，判断它背后最想要的"情绪需求"（主）和次要需求（次）。

可选需求（只从这些里选，不要发明）：
- seen = 想被看见（成就感、被认可、想证明自己）
- soothed = 想被抱抱（难过、累、脆弱、想要安慰）
- heard = 想说话（话到嘴边、没人听、想倾诉）
- loved = 想爱与被爱（恋爱、觉得自己不配被爱）
- act = 想要就冲（想行动、犹豫不敢开始）
- soar = 想飞（想逃离、去远方、要自由）
- relief = 想负责/想放下一点（压力大、扛太多、想松一口气）
- break = 想挣脱（困在"应该"里、想不一样）
- dream = 想做梦（想沉浸、幻想、灵感）
- dig = 想深挖（面对创伤、想懂自己为什么这样）

规则：
- 主需求 = 这段话最想满足的那一个；次需求 = 0-2 个被压住的次要声音。
- 只判断"想要什么"，不做任何占星解读、不判方向。
- 完全判断不出 → primary=soothed（默认：先接住），secondary=[]。

只输出 JSON（不要任何解释）：
{"primary": "soothed", "secondary": ["soar"]}
"""


# ---------------------------------------------------------------------------
# 推导结果
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LetterSignature:
    """一次"内容 → 情绪需求 → 疗愈名"的推导结果。"""

    primary_need: EmotionalNeed
    secondary_needs: tuple[EmotionalNeed, ...] = ()
    planet: Planet | None = None        # 落款星灵（主信号 → 星灵）
    healing_name: str = ""              # 疗愈名（落款签名）
    soul_fragments: tuple[str, ...] = ()  # 灵魂碎片（次信号 → 34 子类）

    @classmethod
    def from_needs(
        cls,
        primary: EmotionalNeed,
        secondary: tuple[EmotionalNeed, ...] = (),
    ) -> "LetterSignature":
        """映射规则（§6.2 判别规则）——确定性，无 LLM。"""
        planet = _NEED_TO_PLANET[primary]
        fragments: list[str] = []
        for need in secondary:
            fragments.extend(_NEED_TO_FRAGMENTS.get(need, ()))
        # 去重、保序（次信号不浪费，也不重复点亮）
        seen: set[str] = set()
        deduped = [fid for fid in fragments if not (fid in seen or seen.add(fid))]
        return cls(
            primary_need=primary,
            secondary_needs=tuple(secondary),
            planet=planet,
            healing_name=HEALING_NAMES[planet],
            soul_fragments=tuple(deduped[:6]),
        )

    @property
    def explain(self) -> str:
        """显式可解释的推导过程（§6.2：不能是黑箱）。"""
        secondary = "、".join(_NEED_ZH.get(n, n.value) for n in self.secondary_needs) or "无"
        fragments = "、".join(self.soul_fragments) or "无"
        return (
            f"内容 → 主需求「{_NEED_ZH.get(self.primary_need, self.primary_need.value)}」"
            f" → 落款 {_planet_zh(self.planet)}·「{self.healing_name}」；"
            f"次需求「{secondary}」 → 灵魂碎片 {fragments}"
        )


def _planet_zh(planet: Planet | None) -> str:
    from application.mailbox.letter_service import SENDER_ZH  # noqa: PLC0415

    if planet is None:
        return "星灵"
    return SENDER_ZH.get(planet.value, planet.value)


# ---------------------------------------------------------------------------
# 情绪需求识别（LLM 受控枚举 + 规则兜底）
# ---------------------------------------------------------------------------


class NeedClassifier:
    """内容 → LetterSignature（LLM 识别需求，映射规则定落款与碎片）。"""

    def __init__(self, llm_client=None):
        self._llm = llm_client

    def classify(self, content: str) -> LetterSignature:
        """识别一段内容 → 落款推导结果。"""
        if not content or not content.strip():
            return LetterSignature.from_needs(EmotionalNeed.SOOTHED)

        if self._llm is not None and getattr(self._llm, "available", True):
            result = self._llm_classify(content)
            if result is not None:
                return result

        return self._rule_fallback(content)

    # ------------------------------------------------------------------

    def _llm_classify(self, content: str) -> LetterSignature | None:
        """LLM 识别主/次需求。失败/返回无效 → None（规则兜底）。"""
        try:
            if not hasattr(self._llm, "complete"):
                return None
            from foundation.llm.client import LLMClient

            raw = self._llm.complete(
                prompt=content,
                system=_NEED_CLASSIFY_SYSTEM,
                temperature=0.0,
            )
            data = LLMClient._parse_slots_json(raw)
            if not isinstance(data, dict):
                return None
            try:
                primary = EmotionalNeed(str(data.get("primary") or "").strip().lower())
            except ValueError:
                return None  # LLM 发明了需求 → 不信它，规则兜底

            secondary: list[EmotionalNeed] = []
            raw_secondary = data.get("secondary")
            if isinstance(raw_secondary, list):
                for raw_need in raw_secondary:
                    try:
                        need = EmotionalNeed(str(raw_need).strip().lower())
                    except ValueError:
                        continue  # 发明的次需求 → 丢弃
                    if need != primary and need not in secondary:
                        secondary.append(need)
                secondary = secondary[:MAX_SECONDARY]
            return LetterSignature.from_needs(primary, tuple(secondary))
        except Exception:  # noqa: BLE001 - 降级不阻断
            logger.warning("落款需求 LLM 识别失败，规则兜底")
            return None

    def _rule_fallback(self, content: str) -> LetterSignature:
        """关键词兜底：按命中数定主/次需求（同分按目录顺序）。"""
        scored: list[tuple[int, int, EmotionalNeed]] = []
        for i, need in enumerate(EmotionalNeed):
            hits = sum(1 for kw in _NEED_RULES.get(need, ()) if kw in content)
            if hits > 0:
                scored.append((hits, -i, need))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

        if not scored:
            # 判断不出 → 默认"先接住"（soothed → 月亮），显式可解释
            return LetterSignature.from_needs(EmotionalNeed.SOOTHED)

        primary = scored[0][2]
        secondary = tuple(need for _, _, need in scored[1 : 1 + MAX_SECONDARY])
        return LetterSignature.from_needs(primary, secondary)


__all__ = [
    "EmotionalNeed",
    "LetterSignature",
    "NeedClassifier",
    "HEALING_NAMES",
    "MAX_SECONDARY",
]
