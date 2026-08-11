"""行动回报识别器（触发行动 +20 的前置判断）。

self_map_design §4.2：触发行动（聊完去做了一件事）→ 上一段会话点亮的
34 子类补 +20（kind=action）。本模块判断"这一句是不是在回报'我真的去做了'"
——用户回来了，告诉星灵他跨出去了。

复用 emotion.py / confirmation.py 的 LLM 受控枚举 + 规则兜底模式：
1. LLM 分类：输出 {"action": bool}。
2. 规则兜底：LLM 不可用/失败/返回无效 → 强行动完成词（离线可测）。
3. 拿不准 → False（宁缺毋滥：+20 是稀有分，错发比漏发更伤——"行动"要诚实）。

硬线：本模块不产出任何占星结论，只识别"行动完成时刻"。
"""

from __future__ import annotations

from foundation.llm.client import LLMClient
from foundation.logger import get_logger

logger = get_logger("application.conversation.action")

#: LLM 分类 system prompt（受控枚举：只输出 action 布尔）
_ACTION_SYSTEM = """你是星灵花园的"行动识别器"。判断用户这一句，是不是在**回报"我真的去做了某件事"**——
TA 在上一次对话/咨询后，真的在现实里采取了一个行动，现在回来告诉星灵。

行动回报（action=true）：
- "我做到了 / 我真的去做了 / 我去做了 / 我照着做了 / 我试了 / 我行动了"
- "你说的方法我用了 / 我听你的去做了"
- "我辞职了 / 我去跟老板谈了 / 我申请了 / 我迈出那一步了"（明确完成了一个行动）
- 即使带着情绪（"虽然很难，但我做到了"），只要行动已经完成 → true

不是行动回报（action=false）：
- 还在犹豫 / 没做："我想去 / 我打算 / 我应该去 / 我该不该去 / 准备去 / 还没做"
- 单纯倾诉 / 提问："我该不该换工作"（是困惑，不是已完成）
- 纯疑问句
- 只有情绪，没有行动结果

拿不准 → false（宁缺毋滥，+20 是稀有分）。

只输出 JSON（不要任何解释）：
{"action": true}
"""

#: 未完成先行：命中也算"不是行动回报"（"我还没做到"里含"做到"，必须先查未完成）
_NOT_YET_MARKERS: tuple[str, ...] = (
    "还没", "没做到", "没做", "没去", "打算", "准备去", "该不该", "要不要",
    "应该去", "什么时候", "犹豫", "不敢", "想去做", "还是没", "差点",
)

#: 强行动完成词（规则兜底用，必须够"强"——防止把意图/犹豫当行动）
_STRONG_ACTION: tuple[str, ...] = (
    "我做到了", "我真的去做了", "我去做了", "我照着做了", "我照做了",
    "我去试了", "我试了", "我行动了", "做成了", "成功了", "我辞职了",
    "我去谈了", "我去说了", "我去提了", "我申请了", "我迈出了那一步", "跨出去了",
)

#: 规则兜底：超过该长度的消息大概率是展开描述而非纯行动回报（真回报可带简短补充）
_RULE_MAX_LEN = 80


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1")
    return False


class ActionDetector:
    """"行动完成"识别器。LLM 优先，规则兜底。"""

    def __init__(self, llm_client=None):
        self._llm = llm_client

    def is_action_report(self, message: str) -> bool:
        """这一句是不是"我真的去做了"。空消息 → False。"""
        if not message or not message.strip():
            return False

        if self._llm is not None and getattr(self._llm, "available", True):
            result = self._llm_action(message)
            if result is not None:
                return result

        return self._rule_fallback(message)

    # ------------------------------------------------------------------
    # LLM 路径
    # ------------------------------------------------------------------

    def _llm_action(self, message: str) -> bool | None:
        """LLM 分类。失败/返回无效 → None（规则兜底）。"""
        try:
            if not hasattr(self._llm, "complete"):
                return None
            raw = self._llm.complete(
                prompt=message, system=_ACTION_SYSTEM, temperature=0.0
            )
            data = LLMClient._parse_slots_json(raw)
            if not isinstance(data, dict):
                return None
            val = data.get("action")
            if val is None:
                return None
            return _as_bool(val)
        except Exception:  # noqa: BLE001 - 降级不阻断
            logger.warning("行动回报 LLM 分类失败，规则兜底")
            return None

    # ------------------------------------------------------------------
    # 规则兜底
    # ------------------------------------------------------------------

    def _rule_fallback(self, message: str) -> bool:
        msg = message.strip()
        if any(neg in msg for neg in _NOT_YET_MARKERS):
            return False
        if msg.endswith(("？", "?")):
            return False
        if len(msg) > _RULE_MAX_LEN:
            return False
        return any(k in msg for k in _STRONG_ACTION)


__all__ = ["ActionDetector"]
