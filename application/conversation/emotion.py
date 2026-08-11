"""情绪感知层（陪伴协议 · 第 1 步"感知"）。

self_map_design §7.1：按 情绪状态 × 诉求类型 判断，而非按领域分类。
诉求四选一（定稿）：被听见 heard / 被安慰 soothed / 被梳理 sorted / 被推动 pushed。

三层落地（复用 intent_parser 的 LLM 优先 + 规则兜底模式）：
1. LLM 分类：输出 {emotion, request, confidence}（受控枚举，不能发明情绪/诉求）。
2. 规则兜底：LLM 不可用/失败/返回无效值 → 确定性关键词（离线可测、服务不断）。
3. 都拿不准 → 默认 {calm, heard}（宁可中性，不误判方向）。

原则三：本模块不产出任何占星结论，只感知"此刻的情绪 × 想要的回应方式"。

后续（Phase 1 扩展）：§1.1.1 计划把 planet_activation（哪颗星被触动 + 当下情绪/诉求）
并入意图 LLM 调用，一次请求同时输出。届时本模块的 LLM 路径可被合并，
规则兜底保留（离线/降级仍要能感知）。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from foundation.llm.client import LLMClient
from foundation.logger import get_logger
from shared.enums import EmotionState, RequestType

logger = get_logger("application.conversation.emotion")

#: LLM 情绪分类 system prompt（受控枚举）
_EMOTION_CLASSIFY_SYSTEM = """你是星灵花园的情绪感知器。读用户的一句话，判断 TA 此刻的情绪状态和 TA 最想要的回应方式。

只输出 JSON（不要任何解释）：
{
  "emotion": "low",
  "request": "soothed",
  "confidence": 0.9,
  "memorable": true
}

可选情绪（只从这些里选，不要发明新词）：
- calm = 平静/日常
- happy = 开心/满足
- low = 低落/难过/伤心
- anxious = 焦虑/担心/不安
- angry = 生气/烦躁
- tired = 疲惫/无力
- lonely = 孤独/想被陪伴
- confused = 迷茫/纠结/想不通
- pressured = 压力大/紧绷
- fearful = 害怕/恐惧

可选诉求（只从这些里选，不要发明新词）：
- heard = 被听见：在分享/倾诉，想让 TA 认真听
- soothed = 被安慰：在难过/累，想要安抚
- sorted = 被梳理：一团乱/纠结/要决策，想要理清
- pushed = 被推动：没动力/犹豫，想要方向推一把

规则：
- 判断"此刻最想要的"，不是最强烈的。例："今天被老板骂了好难过，但我想知道该不该辞职" → emotion=low, request=sorted（TA 要先理清该不该）。
- 纯分享见闻（无负面情绪）→ emotion=calm, request=heard。
- 用户说得太含糊/完全判断不出 → emotion=calm, request=heard。
- confidence 0~1，越确定越高。

memorable = 这是不是一个"值得记住的分享时刻"——TA 说了一件具体的、TA 在意的事（剧/书/歌/游戏/人/事/想法/经历）。
- 具体分享 → true（例："最近在看九门""今天去爬山了""我养了只猫"）。
- 功能性短句/纯问候/确认 → false（"好的""嗯""谢谢""在吗"）。
- 即使情绪是 calm，只要分享了具体的在意之事 → true。
- 拿不准 → false（宁缺毋滥，别给每句话都打 memorable）。
"""

#: 规则兜底：情绪关键词表（受控枚举 → 关键词组）
_EMOTION_RULES: dict[EmotionState, tuple[str, ...]] = {
    EmotionState.HAPPY: ("开心", "高兴", "太好了", "好棒", "幸福", "满足", "爽", "满意"),
    EmotionState.LOW: ("难过", "伤心", "想哭", "低落", "沮丧", "不开心", "失望", "委屈", "心痛", "难受", "心情不好"),
    EmotionState.ANXIOUS: ("焦虑", "担心", "不安", "紧张", "心慌", "忐忑", "发愁"),
    EmotionState.ANGRY: ("生气", "愤怒", "烦躁", "恼火", "气死", "火大", "烦死"),
    EmotionState.TIRED: ("累", "疲惫", "没力气", "精疲力竭", "撑不住", "困", "筋疲力尽"),
    EmotionState.LONELY: ("孤独", "孤单", "寂寞", "没人懂", "一个人"),
    EmotionState.CONFUSED: ("迷茫", "困惑", "纠结", "想不通", "一团乱", "怎么办"),
    EmotionState.PRESSURED: ("压力", "压得", "透不过气", "紧绷", "喘不过气"),
    EmotionState.FEARFUL: ("害怕", "恐惧", "好怕", "吓"),
}

#: 规则兜底：诉求关键词表（受控枚举 → 关键词组）
_REQUEST_RULES: dict[RequestType, tuple[str, ...]] = {
    RequestType.SOOTHED: ("安慰", "抱抱", "好累", "难过", "想哭", "心情不好", "撑不住", "委屈", "累"),
    RequestType.SORTED: ("该不该", "要不要", "怎么办", "纠结", "理不清", "想不通", "怎么选", "一团乱", "如何"),
    RequestType.PUSHED: ("没动力", "想动起来", "怎么开始", "推我一把", "拖延", "敢不敢", "要不要去"),
    RequestType.HEARD: (),
}

#: 负面情绪集合——命中意味着"需要先接住，不适合一上来就递盘"（§7.3）
_NEGATIVE_EMOTIONS = frozenset({
    EmotionState.LOW, EmotionState.ANXIOUS, EmotionState.ANGRY,
    EmotionState.TIRED, EmotionState.LONELY, EmotionState.CONFUSED,
    EmotionState.PRESSURED, EmotionState.FEARFUL,
})


@dataclass(frozen=True)
class EmotionResult:
    """情绪感知结果。"""

    emotion: EmotionState
    request: RequestType
    confidence: float = 0.0
    source: str = "rule"   # "llm" | "rule"
    #: 是否"值得记住的分享时刻"（§6.1 日常/正面时刻 → 词条式 keepsake）
    memorable: bool = False

    @property
    def needs_care(self) -> bool:
        """负面情绪 → 需要先接住（软牵引门控的前置判断）。"""
        return self.emotion in _NEGATIVE_EMOTIONS


def _as_bool(value: object) -> bool:
    """把 LLM 返回的 memorable 归一成 bool：True/"true"/"True"/1 → True，其余 → False。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1")
    return False


class EmotionPerception:
    """情绪 × 诉求感知器。LLM 分类优先，规则兜底。"""

    def __init__(self, llm_client=None):
        self._llm = llm_client

    def perceive(self, message: str) -> EmotionResult:
        """感知用户消息 → 情绪 × 诉求。空消息 → 中性默认。"""
        if not message or not message.strip():
            return EmotionResult(
                emotion=EmotionState.CALM,
                request=RequestType.HEARD,
                confidence=0.0,
            )

        if self._llm is not None and getattr(self._llm, "available", True):
            classified = self._llm_classify(message)
            result = self._from_classification(classified)
            if result is not None:
                return result

        return self._rule_fallback(message)

    # ------------------------------------------------------------------
    # LLM 路径
    # ------------------------------------------------------------------

    def _llm_classify(self, message: str) -> dict:
        """LLM 分类情绪/诉求。失败/异常 → {}（规则兜底）。"""
        try:
            if not hasattr(self._llm, "complete"):
                return {}
            raw = self._llm.complete(
                prompt=message, system=_EMOTION_CLASSIFY_SYSTEM, temperature=0.0
            )
            return LLMClient._parse_slots_json(raw)
        except Exception:  # noqa: BLE001 - 降级不阻断
            logger.warning("情绪感知 LLM 分类失败，规则兜底")
            return {}

    def _from_classification(self, classified: dict) -> EmotionResult | None:
        """LLM 分类结果 → EmotionResult。无效枚举 → None（规则兜底）。"""
        if not isinstance(classified, dict):
            return None

        emotion_raw = str(classified.get("emotion") or "").strip().lower()
        request_raw = str(classified.get("request") or "").strip().lower()

        try:
            emotion = EmotionState(emotion_raw)
        except ValueError:
            return None  # LLM 发明了情绪 → 不信它

        request = RequestType.HEARD
        if request_raw:
            try:
                request = RequestType(request_raw)
            except ValueError:
                request = RequestType.HEARD

        try:
            conf = float(classified.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0

        memorable = _as_bool(classified.get("memorable"))

        return EmotionResult(
            emotion=emotion, request=request,
            confidence=conf, source="llm", memorable=memorable,
        )

    # ------------------------------------------------------------------
    # 规则兜底
    # ------------------------------------------------------------------

    def _rule_fallback(self, message: str) -> EmotionResult:
        emotion, emotion_hits = self._best_rule(message, _EMOTION_RULES)
        request, request_hits = self._best_rule(message, _REQUEST_RULES)
        confidence = min(0.7, 0.2 + 0.1 * (emotion_hits + request_hits))
        return EmotionResult(
            emotion=emotion,
            request=request,
            confidence=confidence,
            source="rule",
        )

    @staticmethod
    def _best_rule(
        message: str, rules: dict[Enum, tuple[str, ...]]
    ) -> tuple[Enum, int]:
        """关键词命中数最高的规则 → (状态, 命中数)。全不命中 → 表类型的默认值。

        规则表是 EmotionState 表 → 默认 CALM；RequestType 表 → 默认 HEARD。
        """
        default = (
            EmotionState.CALM
            if any(isinstance(k, EmotionState) for k in rules)
            else RequestType.HEARD
        )
        best: Enum = default
        best_hits = 0
        for state, keywords in rules.items():
            hits = sum(1 for kw in keywords if kw in message)
            if hits > best_hits:
                best_hits = hits
                best = state
        return best, best_hits


__all__ = [
    "EmotionResult",
    "EmotionPerception",
    "_EMOTION_CLASSIFY_SYSTEM",
]
