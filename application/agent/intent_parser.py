"""IntentParser —— 自然语言 → Intent。

LLM 边界之一（原则三）：若配置了 LLM，用它抽取原始槽位（slots）；
领域归属永远由 Domain 规则（IntentRouter）判定。
v1 无 LLM 时退化为纯规则解析，保证离线可测。
"""

from __future__ import annotations

from domain.reasoning.intent import IntentRouter
from shared.models import Intent, IntentSlot

# LLM 抽取提示词（未来接 LLM 时使用）
_LLM_SLOT_PROMPT = (
    "从用户的占星提问中抽取结构化槽位，返回 JSON："
    '{"person": "...", "related_person": "...", '
    '"timeframe": "...", "specific_event": "..."}'
    "只抽取，不做任何占星判断。"
)


class IntentParser:
    """规则优先的意图解析器。"""

    def __init__(self, router: IntentRouter | None = None, llm_client=None, decomposer=None):
        self._router = router or IntentRouter()
        self._llm = llm_client  # 可选；None 时纯规则
        self._decomposer = decomposer  # 可选；None 时 parse_deep() 退化为空壳

    def parse(self, message: str, context: dict | None = None) -> Intent:
        """解析用户消息为 Intent。

        1. 若配置 LLM：抽取原始槽位（LLM 不判断领域）。
        2. 领域规则路由（Domain 判定领域/子领域）。
        context 为会话蒸馏上下文，用于追问消解（继承活跃话题）。
        """
        slots: dict[str, IntentSlot] = {}
        if self._llm is not None:
            raw = self._llm_extract_slots(message, context)
            # LLM 返回原始字符串 → 包装为 IntentSlot
            for name, value in raw.items():
                if isinstance(value, str) and value.strip():
                    slots[name] = IntentSlot(
                        name=name, raw_value=value, normalized_value=value,
                    )
        return self._router.route(message, slots, context)

    def parse_deep(self, message: str, context: dict | None = None):
        """深度解析：LLM 拆解 → DecomposedIntent。

        先走 parse() 获取 Intent（领域/子领域），再用 IntentDecomposer
        做占星结构映射 + 分析任务富化。
        若 decomposer 未配置或 LLM 不可用，返回最小 DecomposedIntent。
        """
        from domain.reasoning.intent.decomposer import DecomposedIntent

        intent = self.parse(message, context)
        if intent.requires_clarification:
            return DecomposedIntent.wrap(intent)

        if self._decomposer is not None:
            return self._decomposer.decompose(intent)

        return DecomposedIntent.wrap(intent)

    def _llm_extract_slots(self, message: str, context: dict | None = None) -> dict:
        """调用 LLM 抽取槽位。失败时返回空槽（规则兜底）。

        context 为会话蒸馏上下文（active_domain 等），v1 暂不注入 LLM prompt；
        保留参数供后续增强（如注入活跃话题以提升抽取精度）。
        """
        try:
            return self._llm.extract_slots(_LLM_SLOT_PROMPT, message)
        except Exception:  # noqa: BLE001
            return {}
