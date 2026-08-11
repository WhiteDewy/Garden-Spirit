"""照见确认识别器（被照见 +5 的前置判断）。

self_map_design §4.2：被照见（用户说"对，就是这样"）→ 上一轮镜映/解读点亮的
34 子类补 +5（kind=seen）。本模块判断"这一句是不是在确认'你理解对了 TA'"。

复用 emotion.py 的 LLM 受控枚举 + 规则兜底模式：
1. LLM 分类：输出 {"confirmed": bool}。
2. 规则兜底：LLM 不可用/失败/返回无效 → 强确认关键词（离线可测）。
3. 拿不准 → False（宁缺毋滥：错发 +5 比漏发更伤——照见分应当诚实）。

硬线：本模块不产出任何占星结论，只识别"确认时刻"。
"""

from __future__ import annotations

from foundation.llm.client import LLMClient
from foundation.logger import get_logger

logger = get_logger("application.conversation.confirmation")

#: LLM 分类 system prompt（受控枚举：只输出 confirmed 布尔）
_CONFIRMATION_SYSTEM = """你是星灵花园的"照见识别器"。判断用户这一句，是不是在**确认"你理解对了 TA"**——
TA 在回应你上一句的镜映/解读，表示"对，就是这样，你懂我"。

确认时刻（confirmed=true）：
- "对，就是这样 / 就是这个感觉 / 你懂我 / 说到我心里了 / 完全被你说中了"
- "你说得对，我确实是…"（承接你的话，明确同意）
- 即使后面跟着补充说明，只要开头是明确确认 → true

不是确认（confirmed=false）：
- "嗯" "哈哈" "谢谢" "好的" 等礼貌敷衍（太弱，不算真确认）
- 提出新话题 / 新问题 / 转移话题
- "不对 / 不是这样 / 没那么严重"（否定你的解读）
- 纯疑问句

拿不准 → false（宁缺毋滥，照见分要诚实）。

只输出 JSON（不要任何解释）：
{"confirmed": true}
"""

#: 否定先行：命中也算"不是确认"（"不对"里含"对"，必须先查否定）
_NEGATION_MARKERS: tuple[str, ...] = (
    "不对", "不是", "没说到", "没对上", "才不是", "并不是", "没那么", "有点不", "不太对",
)

#: 强确认关键词（规则兜底用，必须够"强"——防止把敷衍/弱认同当照见）
_STRONG_CONFIRM: tuple[str, ...] = (
    "就是这样", "就是这个感觉", "这种感觉", "你懂我", "说到我心里", "说到心坎",
    "完全说中", "被你说中", "说中了", "太准了", "好准", "说得对", "说得太对",
    "对对对", "没错", "对对",
)

#: 规则兜底：超过该长度的消息大概率是新内容而非纯确认（真确认可带短补充）
_RULE_MAX_LEN = 60


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1")
    return False


class ConfirmationDetector:
    """"照见确认"识别器。LLM 优先，规则兜底。"""

    def __init__(self, llm_client=None):
        self._llm = llm_client

    def is_confirmation(self, message: str) -> bool:
        """这一句是不是"对，就是这样"式的确认。空消息 → False。"""
        if not message or not message.strip():
            return False

        if self._llm is not None and getattr(self._llm, "available", True):
            result = self._llm_confirm(message)
            if result is not None:
                return result

        return self._rule_fallback(message)

    # ------------------------------------------------------------------
    # LLM 路径
    # ------------------------------------------------------------------

    def _llm_confirm(self, message: str) -> bool | None:
        """LLM 分类。失败/返回无效 → None（规则兜底）。"""
        try:
            if not hasattr(self._llm, "complete"):
                return None
            raw = self._llm.complete(
                prompt=message, system=_CONFIRMATION_SYSTEM, temperature=0.0
            )
            data = LLMClient._parse_slots_json(raw)
            if not isinstance(data, dict):
                return None
            val = data.get("confirmed")
            if val is None:
                return None
            return _as_bool(val)
        except Exception:  # noqa: BLE001 - 降级不阻断
            logger.warning("照见确认 LLM 分类失败，规则兜底")
            return None

    # ------------------------------------------------------------------
    # 规则兜底
    # ------------------------------------------------------------------

    def _rule_fallback(self, message: str) -> bool:
        msg = message.strip()
        if any(neg in msg for neg in _NEGATION_MARKERS):
            return False
        if msg.endswith(("？", "?")):
            return False
        if len(msg) > _RULE_MAX_LEN:
            return False
        return any(k in msg for k in _STRONG_CONFIRM)


__all__ = ["ConfirmationDetector"]
