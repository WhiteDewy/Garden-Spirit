"""IntentParser —— 自然语言 → Intent。

LLM 意图理解（A1，对话大脑基础）：
- 配置 LLM 时：LLM 分类用户意图（domain/subdomain/confidence/needs_clarification）。
  这是"人话→占星概念"映射（原则三允许的 LLM 职责），但**领域必须落在
  IntentDomain 受控枚举内**——LLM 不能发明领域，占星结论仍全由 Domain 出。
- LLM 不可用/失败/返回无效领域 → 回退确定性规则（离线可测、服务不断）。

闲聊（domain=chat）映射为 Daily.Chat，由 runtime 温暖回应。
"""

from __future__ import annotations

from datetime import datetime, timezone

from domain.reasoning.intent import IntentRouter
from foundation.utils import new_id
from shared.enums import IntentDomain
from shared.models import Intent, IntentSlot

_INTENT_CLASSIFY_SYSTEM = """你是星灵花园的意图理解器。读用户的一句话，判断 TA 想问什么。

可选领域（只从这些里选，不要发明新领域）：
- career = 职业/工作（换工作、升职、创业、压力、方向）
- relationship = 感情/关系（对象、分手、复合、结婚、伴侣）
- wealth = 财富/财运（投资、赚钱、理财、收入）
- health = 健康/身体（生病、失眠、精力）
- emotion = 情绪/心情（低落、焦虑、迷茫、累但说不清）
- family = 家庭/原生家庭/亲子
- learning = 学习/学业/考试
- daily = 运势/每日/近期状态/最近怎么样
- chat = 纯闲聊/问候/不想聊具体领域（如"你好""随便聊聊""最近好累想找人说说话"）
- meta = 问星灵自己/产品能力/能学到什么（如"你是谁""你能做什么""能学到什么""你有什么专业""这个app有什么用"）——注意：这是问产品本身，不是用户自己的学习/职业

只输出 JSON（不要任何解释或 markdown）：
{
  "domain": "career",
  "subdomain": "ChangeJob",
  "confidence": 0.9,
  "needs_clarification": false,
  "question_intent": "用户真正想问的一句话"
}

规则：
- subdomain 是领域内细分（如 ChangeJob/Promotion/Status），不确定就给空字符串 ""。
- 用户说得太含糊、完全判断不出 → needs_clarification=true。
- "这个月运势""最近怎么样""今天怎么样" → daily。
- confidence 0~1，越确定越高。
"""

_MIN_LLM_CONFIDENCE = 0.5


class IntentParser:
    """LLM 意图理解优先，规则兜底的意图解析器。"""

    def __init__(self, router: IntentRouter | None = None, llm_client=None, decomposer=None):
        self._router = router or IntentRouter()
        self._llm = llm_client  # 可选；None 时纯规则
        self._decomposer = decomposer  # 可选；None 时 parse_deep() 退化为空壳

    def parse(self, message: str, context: dict | None = None) -> Intent:
        """解析用户消息为 Intent。

        1. LLM 可用 → 意图分类（领域受限枚举）+ 确定性槽抽取。
        2. LLM 不可用/失败 → 规则路由（含 LLM 槽抽取降级）。
        """
        if self._llm is not None and getattr(self._llm, "available", True):
            classified = self._llm_classify(message)
            intent = self._from_classification(message, classified, context)
            if intent is not None:
                return intent

        # 兜底：规则路由（可含 LLM 槽抽取，领域仍由规则定）
        slots: dict[str, IntentSlot] = {}
        if self._llm is not None:
            raw = self._llm_extract_slots(message, context)
            for name, value in raw.items():
                if isinstance(value, str) and value.strip():
                    slots[name] = IntentSlot(
                        name=name, raw_value=value, normalized_value=value,
                    )
        return self._router.route(message, slots, context)

    def parse_deep(self, message: str, context: dict | None = None):
        """深度解析：LLM 拆解 → DecomposedIntent。"""
        from domain.reasoning.intent.decomposer import DecomposedIntent

        intent = self.parse(message, context)
        if intent.requires_clarification:
            return DecomposedIntent.wrap(intent)
        if self._decomposer is not None:
            return self._decomposer.decompose(intent)
        return DecomposedIntent.wrap(intent)

    # ------------------------------------------------------------------
    # LLM 意图分类
    # ------------------------------------------------------------------

    def _llm_classify(self, message: str) -> dict:
        """调用 LLM 分类意图。失败/异常 → {}（规则兜底）。"""
        if self._llm is None:
            return {}
        try:
            if not hasattr(self._llm, "classify_intent"):
                return {}
            raw = self._llm.classify_intent(_INTENT_CLASSIFY_SYSTEM, message)
            return raw if isinstance(raw, dict) else {}
        except Exception:  # noqa: BLE001
            return {}

    def _from_classification(
        self, message: str, classified: dict, context: dict | None
    ) -> Intent | None:
        """把 LLM 分类结果转为 Intent。无效领域 → None（回退规则）。

        LLM 只能从 IntentDomain 里选领域（受控枚举）；闲聊映射为 Daily.Chat。
        """
        if not isinstance(classified, dict):
            return None
        domain_raw = classified.get("domain")
        if not isinstance(domain_raw, str) or not domain_raw.strip():
            return None
        domain_raw = domain_raw.strip().lower()

        # 闲聊 → Daily.Chat（runtime 温暖回应，不进占星管线）
        if domain_raw == "chat":
            return self._build_intent(message, IntentDomain.DAILY, "Chat",
                                      confidence=0.8, needs_clarification=False)

        # 问星灵自己/产品能力 → Daily.Meta（runtime 答能力介绍，不进占星管线）
        if domain_raw == "meta":
            return self._build_intent(message, IntentDomain.DAILY, "Meta",
                                      confidence=0.9, needs_clarification=False)

        try:
            domain = IntentDomain(domain_raw)
        except ValueError:
            return None  # LLM 发明了领域 → 不信它，回退规则

        try:
            conf = float(classified.get("confidence", 0))
        except (TypeError, ValueError):
            conf = 0.0

        needs = bool(classified.get("needs_clarification")) or conf < _MIN_LLM_CONFIDENCE
        subdomain = classified.get("subdomain") or ""
        return self._build_intent(message, domain, str(subdomain) if isinstance(subdomain, str) else "",
                                  confidence=conf, needs_clarification=needs)

    def _build_intent(self, message, domain, subdomain, *, confidence, needs_clarification) -> Intent:
        slots: dict[str, IntentSlot] = {}
        # 合盘对象识别（确定性，合盘需要对方出生数据）
        related = IntentRouter._extract_related_person(message)
        if related is not None:
            slots[related.name] = related
        return Intent(
            id=new_id("intent"),
            raw_query=message,
            domain=domain,
            subdomain=subdomain,
            slots=slots,
            domain_confidence=confidence,
            parsed_at=datetime.now(timezone.utc),
            requires_clarification=needs_clarification,
            clarification_question=(
                "我还不确定你想问哪方面，可以具体说说吗？比如职业、感情、财运、健康、学习…"
                if needs_clarification else ""
            ),
        )

    # ------------------------------------------------------------------
    # 降级：规则路由用到的 LLM 槽抽取
    # ------------------------------------------------------------------

    def _llm_extract_slots(self, message: str, context: dict | None = None) -> dict:
        """调用 LLM 抽取槽位。失败时返回空槽（规则兜底）。"""
        try:
            return self._llm.extract_slots(_LLM_SLOT_PROMPT, message)
        except Exception:  # noqa: BLE001
            return {}


_LLM_SLOT_PROMPT = (
    "从用户的占星提问中抽取结构化槽位，返回 JSON："
    '{"person": "...", "related_person": "...", '
    '"timeframe": "...", "specific_event": "..."}'
    "只抽取，不做任何占星判断。"
)
