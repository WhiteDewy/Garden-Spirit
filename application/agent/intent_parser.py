"""IntentParser —— 自然语言 → Intent（三层意图 prompt，对话模式感知）。

架构（v2）：
1. **宫位优先**：宫位是精确占星词汇——确定性抽取永远优先于 LLM
   （"3宫"/"第十二宫"/"12宫财运"，语义场=唯一事实源）。有宫位 → 直接走规则路由，
   LLM 只在非宫位消息上分类。
2. **FREE / 随聊**：LLM 只判断「是否在聊占星」。非占星 → Daily.Chat（陪伴管线）；
   占星 → 用 DEEP 模板继续分类。
3. **QUICK / 快速**：DEEP 骨架 + 收敛规则（不深挖、高澄清门槛、不宫位反问）。
4. **DEEP / 深度（默认）**：完整上下文注入 + intent_type（用户此刻在做什么）
   + 12 宫语义场表 + 富输出（focus_house/focus_slice/deep_dive/confirmed）。

硬线不变（原则三）：
- 领域是受控枚举，LLM 输出非法领域 → 规则兜底不信。
- 宫位切片 → 领域的映射由 Domain（rules.signification 表）定，LLM 不能发明。
- LLM 的新能力（intent_type/focus_slice/deep_dive/confirmed）只影响**路由方向**，
  不影响占星结论内容——结论仍全由 Domain 的引擎出。
"""

from __future__ import annotations

from datetime import datetime, timezone

from domain.reasoning.intent import IntentRouter
from foundation.utils import new_id
from shared.enums import ConsultMode, IntentDomain
from shared.models import Intent, IntentSlot

_MIN_LLM_CONFIDENCE = 0.5

#: 允许的 intent_type（LLM 只能从这里选；非法 → 默认 new_question，不阻断路由）
_INTENT_TYPES = frozenset({
    "new_question", "follow_up_deep_dive", "clarification_response",
    "topic_switch", "confirmation", "chat", "meta",
})

#: 确认词（规则兜底：上轮刚发过验证问句 + 短句命中 → 确认/否认，收敛机制结论）。
#: 判定保守：只在 pending_house_verify 非空且消息 ≤ 20 字时生效，避免误吞闲聊。
_CONFIRM_POSITIVE = ("对，", "对 ", "对呀", "对啊", "对的", "是的", "没错",
                     "确实是", "确实", "嗯嗯", "嗯，", "就是这样", "就是有")
_CONFIRM_NEGATIVE = ("不是", "没有", "并没有", "不对", "没", "不")


def _build_context_block(context: dict | None) -> str:
    """从蒸馏上下文拼「对话历史 + 活跃状态」块（python 侧注入，不写死在模板里）。

    只读 context 里的字段，不含任何占星含义（Application 蒸馏边界，原则一）。
    """
    if not context:
        return "（这是对话的第一轮，无上文）"
    lines: list[str] = []
    turns = context.get("recent_turns") or []
    if turns:
        lines.append("## 对话历史")
        for i, t in enumerate(turns, 1):
            user = str(t.get("user", "")).replace("\n", " ")
            asst = str(t.get("assistant", "")).replace("\n", " ")
            lines.append(f"轮{i} 用户：{user}")
            lines.append(f"轮{i} 系统：{asst}…")

    active_domain = context.get("active_domain")
    active_house = context.get("active_house")
    if active_domain or active_house:
        lines.append("\n## 活跃上下文（上一轮未完结）")
        if active_domain:
            lines.append(f"- 活跃领域：{active_domain}")
        if active_house:
            lines.append(f"- 活跃宫位：第{active_house}宫（上轮就此宫位做了反问/解读）")
    return "\n".join(lines) if lines else "（这是对话的第一轮，无上文）"


# ---------------------------------------------------------------------------
# 三层 prompt 模板
# ---------------------------------------------------------------------------

#: DEEP —— 深度咨询（默认）：上下文注入 + intent_type + 12 宫语义场 + 富输出。
_DEEP_INTENT_PROMPT = """你是星灵花园的对话大脑。你的任务不是简单分类领域——而是理解「用户此刻在这个对话里在做什么」，然后给出精确的路由判断。

## 对话上下文

__CONVERSATION_CONTEXT__

（上方的对话上下文包含：前几轮用户说了什么、系统回复了什么、当前的活跃领域/宫位。
 如果活跃领域/宫位非空，说明上一轮还没完结——本轮大概率是追问或切换话题。）

## 意图模式

先判断 intent_type（用户此刻在做什么），再填领域/宫位/切片：

### new_question
用户发起一个与上文无关的新问题。
- 例（上文在聊感情，本轮）："我事业最近怎么样" → 新话题
- 例（无上文）："帮我看看财运" → 新话题

### follow_up_deep_dive
用户对上一轮结论的深挖追问——不换话题，往里钻。
- 例（上轮系统说了12宫有暗财）→ "怎么个暗财"、"具体是怎么来的"
- 例（上轮说了3宫表达强）→ "为什么说我有表达天赋"、"展开讲讲"
- 关键信号：追问词（怎么/为什么/展开/具体/说说）+ 用词指向上轮切片
- 这种时候不要重复整段结论——填 focus_house/focus_slice，标记 deep_dive=true，
  让下游把该切片的证据链展开。

### clarification_response
用户正在回答系统上一轮的反问。
- 例（系统反问"3宫涵盖表达、学习、出行……你想问哪块？"）→ "我想问表达"
- 取上轮 active_house + 本轮用户指定的切片词 → 填 focus_house + focus_slice

### topic_switch
用户在上一个话题中间转向新话题。
- 例（刚在聊3宫表达，本轮）→ "那感情怎么样"
- 这种时候清理上文的宫位暂存，走新领域的路由（focus_house 留空）。

### confirmation
用户在对系统的验证式提问做确认/否认。
- 例："对，就是做占星写作"、"不是这样"、"嗯嗯对"
- confirmed=true/false

### chat
纯闲聊/问候/情绪倾诉——不进入占星管线。
- 例："你好"、"最近好累啊想找人说说话"

### meta
用户问的是星灵/产品自身——"你是谁"、"你能做什么"

## 领域分类

从以下领域中选择（只从这些里选，不要发明新领域）：

| domain | 含义 | 典型用户话术 |
|--------|------|------------|
| career | 职业/工作 | 换工作、升职、创业、工作压力、方向 |
| relationship | 感情/关系 | 对象、暧昧、分手、复合、结婚、伴侣 |
| wealth | 财富/财运 | 投资、赚钱、理财、收入、偏财 |
| health | 健康/身体 | 生病、失眠、精力 |
| emotion | 情绪/心情 | 低落、焦虑、迷茫、心烦 |
| family | 家庭/亲子 | 原生家庭、和父母、和孩子 |
| learning | 学习/学业 | 考试、考研、学业、学什么 |
| growth | 远方/信念 | 留学、深造、信仰、人生意义、旅行 |
| network | 人际/社群 | 朋友、人脉、圈子、同事关系、社交、粉丝 |
| self | 自我/人格 | 我是谁、性格、内在成长 |
| daily | 运势/日常 | 今天运势、最近怎么样、流年 |

## 宫位语义场（用户可能用口语引用宫位）

| 宫位 | 涵盖的方面 |
|------|----------|
| 1宫 | 自我/个性/存在感、生命力/精力、外观/第一印象/气场 |
| 2宫 | 正财/收入/价值观、物质资源/金钱观、自尊/自我价值 |
| 3宫 | 沟通/表达/写作、学习/短途/走动、内容/传播/表达影响力、兄弟姐妹/邻里/熟人群 |
| 4宫 | 家庭根基/原生家庭/父亲、房产/居住/安全感、内心深处的情绪地基 |
| 5宫 | 恋爱/浪漫/心动、创造力/才华/兴趣、子女/亲子、投机/博弈/风险投入 |
| 6宫 | 日常工作/技能/服务、身体健康/养生、同事/下属/日常事务 |
| 7宫 | 伴侣/婚姻/一对一、合作/合伙/签约/客户、公开对手/竞争/诉讼 |
| 8宫 | 偏财/他人资源/投资、亲密/信任/性、死亡/危机/转化 |
| 9宫 | 高等学问/深造/信仰、远行/异国/外派、观点/出版/传播 |
| 10宫 | 事业/名望/社会地位、权威/上司/体制、人生方向/使命 |
| 11宫 | 人际网络/社群/粉丝、理想/愿景/新技术、进账/社会资源 |
| 12宫 | 玄学/灵性/幕后专业、暗财/偏财/隐性收入、小人/暗中敌人/背叛、潜意识/梦境/灵感、医院/失眠/自我消耗 |

**重要**：用户说"第3宫"、"三宫"、"3宫"都是在指宫位。如果宫位引用明确但没说明是哪个方面，
标记 needs_clarification=true，让系统去反问用户。**但若你从对话上下文能看出用户问的是哪块
（如 context.active_house 对应的切片），直接填 focus_slice，不需要反问。**

## 子领域细分（部分）

| domain | subdomain | 含义 |
|--------|-----------|------|
| career | ChangeJob | 换工作/跳槽/离职 |
| career | Promotion | 升职/加薪/晋升 |
| career | Entrepreneurship | 创业/自己干 |
| career | Burnout | 工作倦怠/压力大 |
| relationship | PartnerTraits | 未来对象特征 |
| relationship | Status | 感情状态/关系怎么样 |
| relationship | Start | 恋爱/表白/心动/合适吗 |
| relationship | Reconcile | 复合/和好/挽回 |
| relationship | Commitment | 结婚/婚姻/订婚 |
| relationship | Synastry | 合盘（有伴侣数据） |
| daily | Fortune | 运势 |
| daily | Chat | 闲聊/问候 |

不确定 subdomain 时给空字符串 ""。

## 输出格式

只输出 JSON（不要任何解释或 markdown）：

{
  "intent_type": "new_question",
  "domain": "career",
  "subdomain": "ChangeJob",
  "focus_house": null,
  "focus_slice": null,
  "deep_dive": false,
  "confirmed": null,
  "confidence": 0.9,
  "needs_clarification": false,
  "reasoning": "用户第一次问换工作，无上文关联"
}

字段说明：
- intent_type: new_question | follow_up_deep_dive | clarification_response | topic_switch | confirmation | chat | meta
- domain: 领域枚举值（必须在上方的领域表中，否则系统会拒绝）
- subdomain: 细分（可选）
- focus_house: 宫位号 1-12（用户提到宫位时填写）
- focus_slice: 切片词（如"暗财/偏财/隐性收入"，从宫位语义场表中匹配；不确定可空）
- deep_dive: true 表示这是对上一轮某条切片的深挖追问
- confirmed: true/false/null（仅 intent_type=confirmation 时使用）
- confidence: 0~1，越确定越高
- needs_clarification: true 表示需要反问用户（意图不明确 or 宫位引用但方向不明确）
- reasoning: 一句话说明判断依据（内部使用，不展示给用户）
"""

#: QUICK —— 快速咨询：DEEP 骨架 + 收敛规则（不深挖/高澄清门槛/不宫位反问）。
_QUICK_INTENT_PROMPT = _DEEP_INTENT_PROMPT.replace(
    "## 输出格式",
    """## 快速咨询模式特殊规则

用户在快速咨询模式——想要简洁、快速的回答。

1. **直接收敛**：如果你能判断出意图、领域、宫位，就直接锁定，不要标记 follow_up_deep_dive。
   deep_dive 始终为 false —— 在快速模式下，用户追问"怎么个暗财"也当作 new_question 处理，
   直接输出该切片结论，简短即可。

2. **高阈值澄清**：只有真正完全无法判断时才 needs_clarification=true。稍微含糊但能推断的，
   给推断结果 + confidence 0.6-0.7，让下游走默认策略。

3. **不要宫位反问**：即使用户说"3宫怎么样"这种裸宫位，也不反问切片——直接选该宫最常见的切片
   （3宫→沟通/表达，12宫→玄学/灵性），给快速结论。用户想要的是速度，不是精细度。

## 输出格式""",
)

#: FREE —— 自由聊天：不分类领域，只判断「是否在聊占星」。
_FREE_INTENT_PROMPT = """你是星灵花园的星灵——住在用户星盘里的陪伴者。现在是「自由聊天」模式。

用户可能在：
1. 倾诉情绪（累、迷茫、不开心）→ 陪伴 + 情绪接住
2. 闲聊日常（电影、书、工作、生活）→ 自然回应 + 可以轻轻联想星盘
3. 突然想聊占星（"对了帮我看看事业"）→ 交给咨询管线
4. 问你是谁/能做什么 → 能力介绍

你的任务：判断用户是要「聊占星」还是「纯粹聊天」。

## 占星信号（下列情况 → is_astrology_question=true）
- 提到具体占星术语：宫位（"3宫"/"第12宫"）、行星、星座、运势、本命盘、合盘
- 明确要求解读或分析："帮我看看"、"怎么解"、"我盘上"、"从我星盘上看"
- 问时机："什么时候适合"、"今年有机会吗"
- 问领域："我事业怎么样"、"感情运好吗"

## 非占星信号（下列情况 → is_astrology_question=false）
- 纯粹倾诉情绪："今天好累"、"不知道为什么就是烦"、"想找人说说话"
- 聊日常："刚看了一部电影"、"最近在读一本书"、"今天加班到很晚"
- 问好/寒暄："你好"、"睡了没"、"在吗"
- 分享开心事："我今天升职了"

## 输出格式

只输出 JSON（不要任何解释或 markdown）：

{
  "is_astrology_question": false,
  "topic": "电影",
  "emotion_hint": "calm",
  "astrology_association": null,
  "reasoning": "用户在分享刚看的电影，不是占星问题"
}

- is_astrology_question: true/false。true=走咨询管线，false=走陪伴管线。
- topic: 用户在聊什么（电影/书/音乐/工作/日常/感情/情绪/…）。仅用于帮助陪伴管线自然接话。
- emotion_hint: calm/happy/low/anxious/angry/tired。仅用于帮助陪伴管线选择回应基调。
- astrology_association: null 或轻量联想。例：用户聊了一堆旅行计划 → "你盘上木星在九宫，天生爱往外跑"。
  这只是给陪伴管线的联想建议，不是解盘。绝对不要做吉凶判断。
- reasoning: 一句话说明判断依据。
"""


class IntentParser:
    """LLM 意图理解优先，规则兜底的意图解析器（模式感知）。"""

    def __init__(self, router: IntentRouter | None = None, llm_client=None, decomposer=None):
        self._router = router or IntentRouter()
        self._llm = llm_client  # 可选；None 时纯规则
        self._decomposer = decomposer  # 可选；None 时 parse_deep() 退化为空壳

    def parse(
        self,
        message: str,
        context: dict | None = None,
        mode: ConsultMode | str = ConsultMode.DEEP,
    ) -> Intent:
        """解析用户消息为 Intent（模式感知）。

        1. 宫位引用（精确占星词汇）→ 确定性路由永远优先（硬线：语义场=唯一事实源）。
        2. FREE 模式 → LLM 判断是否聊占星（非占星 → 陪伴，占星 → DEEP 继续分类）。
        3. DEEP/QUICK → LLM 模式感知分类（领域受限枚举）+ 富输出解析。
        4. LLM 不可用/失败 → 规则路由（含 LLM 槽抽取降级）。
        """
        # 1. 宫位优先：确定性抽取比 LLM 快且准，领域/切片/反问全由规则定（Domain 权威）
        if self._router._house_from_text(message) is not None:
            return self._router.route(message, None, context)

        # 2. FREE 模式：只判断"是否在聊占星"
        if self._is_mode(mode, ConsultMode.FREE):
            intent = self._free_classify(message, context)
            if intent is not None:
                return intent

        # 3. 常规 LLM 分类（DEEP/QUICK 模式感知）
        if self._llm is not None and getattr(self._llm, "available", True):
            classified = self._llm_classify(message, context, mode)
            intent = self._from_classification(message, classified, context)
            if intent is not None:
                return intent

        # 4. 兜底：规则路由（可含 LLM 槽抽取，领域仍由规则定）。
        #    LLM 不可用时不调槽抽取——离线/无 key 时不产生无谓的 LLM 调用日志。
        slots: dict[str, IntentSlot] = {}
        if self._llm is not None and getattr(self._llm, "available", False):
            raw = self._llm_extract_slots(message, context)
            for name, value in raw.items():
                if isinstance(value, str) and value.strip():
                    slots[name] = IntentSlot(
                        name=name, raw_value=value, normalized_value=value,
                    )
        intent = self._router.route(message, slots, context)
        # 规则兜底的确认检测：上轮刚发过验证问句（pending_house_verify）+ 短句命中确认词
        # → 标 confirmation，让 runtime 收敛机制结论（LLM 关闭时也走通证据链闭环）。
        # 确认句不该被反问吞掉（"对，就是这样"不是含糊待澄清），清掉澄清标记。
        confirmed = self._detect_confirmation(message, context)
        if confirmed is not None:
            intent.intent_type = "confirmation"
            intent.confirmed = confirmed
            intent.requires_clarification = False
            intent.clarification_question = ""
        return intent

    def parse_deep(
        self,
        message: str,
        context: dict | None = None,
        mode: ConsultMode | str = ConsultMode.DEEP,
    ):
        """深度解析：LLM 拆解 → DecomposedIntent（模式感知透传）。"""
        from domain.reasoning.intent.decomposer import DecomposedIntent

        intent = self.parse(message, context, mode)
        if intent.requires_clarification:
            return DecomposedIntent.wrap(intent)
        if self._decomposer is not None:
            return self._decomposer.decompose(intent)
        return DecomposedIntent.wrap(intent)

    # ------------------------------------------------------------------
    # 模式工具
    # ------------------------------------------------------------------

    @staticmethod
    def _is_mode(mode: ConsultMode | str, target: ConsultMode) -> bool:
        return mode == target or mode == target.value

    def _system_for_mode(
        self, mode: ConsultMode | str, context: dict | None
    ) -> str:
        """DEEP/QUICK 的 system prompt（注入上下文块）。FREE 不走这里。

        用 .replace 而非 .format——prompt 里含 JSON 示例大括号，.format 会误解析。
        """
        prompt = _DEEP_INTENT_PROMPT
        if self._is_mode(mode, ConsultMode.QUICK):
            prompt = _QUICK_INTENT_PROMPT
        return prompt.replace(
            "__CONVERSATION_CONTEXT__", _build_context_block(context),
        )

    # ------------------------------------------------------------------
    # LLM 意图分类
    # ------------------------------------------------------------------

    def _llm_classify(
        self,
        message: str,
        context: dict | None = None,
        mode: ConsultMode | str = ConsultMode.DEEP,
    ) -> dict:
        """调用 LLM 分类意图（模式感知 prompt）。失败/异常 → {}（规则兜底）。"""
        if self._llm is None:
            return {}
        try:
            if not hasattr(self._llm, "classify_intent"):
                return {}
            system = self._system_for_mode(mode, context)
            raw = self._llm.classify_intent(system, message)
            return raw if isinstance(raw, dict) else {}
        except Exception:  # noqa: BLE001
            return {}

    def _free_classify(self, message: str, context: dict | None) -> Intent | None:
        """FREE 模式：LLM 判断是否聊占星。

        非占星 → Daily.Chat（陪伴管线）；占星 → 用 DEEP 模板继续分类。
        LLM 不可用/失败 → None（走规则兜底）。
        """
        if self._llm is None or not getattr(self._llm, "available", True):
            return None
        try:
            if not hasattr(self._llm, "classify_intent"):
                return None
            free = self._llm.classify_intent(_FREE_INTENT_PROMPT, message)
            if not isinstance(free, dict):
                return None
            if free.get("is_astrology_question") is False:
                intent = self._build_intent(
                    message, IntentDomain.DAILY, "Chat",
                    confidence=0.8, needs_clarification=False,
                )
                intent.intent_type = "chat"
                return intent
            # 占星 → 用 DEEP 模板继续分类（两次调用仅在 FREE 模式下转占星时发生）
            classified = self._llm.classify_intent(
                self._system_for_mode(ConsultMode.DEEP, context), message,
            )
            return self._from_classification(message, classified, context)
        except Exception:  # noqa: BLE001
            return None

    def _from_classification(
        self, message: str, classified: dict, context: dict | None
    ) -> Intent | None:
        """把 LLM 分类结果转为 Intent。无效领域 → None（回退规则）。

        LLM 只能从 IntentDomain 里选领域（受控枚举）；闲聊映射为 Daily.Chat。
        宫位切片 → 领域的映射仍由 Domain（signification 表）定——LLM 给 focus_slice
        后，用规则的 _match_slice/_domain_for_slice 规范化为权威领域（硬线）。
        """
        if not isinstance(classified, dict):
            return None

        # intent_type（对话路由信号；非法 → 默认 new_question，不阻断路由）
        intent_type = classified.get("intent_type")
        if not isinstance(intent_type, str) or intent_type not in _INTENT_TYPES:
            intent_type = "new_question"

        # chat / meta / confirmation：意图类型优先于领域（LLM 可能只给 intent_type
        # 不给 domain——确认轮用户只说"对，就是这样"，无领域可言）
        if intent_type in ("chat", "meta"):
            sub = "Chat" if intent_type == "chat" else "Meta"
            intent = self._build_intent(
                message, IntentDomain.DAILY, sub,
                confidence=0.8 if intent_type == "chat" else 0.9,
                needs_clarification=False,
            )
            intent.intent_type = intent_type
            return intent
        if intent_type == "confirmation":
            intent = self._build_intent(
                message, IntentDomain.DAILY, "",
                confidence=0.9, needs_clarification=False,
            )
            intent.intent_type = "confirmation"
            intent.confirmed = classified.get("confirmed") if isinstance(
                classified.get("confirmed"), bool
            ) else None
            # 确认里也可能带宫位（"对，就是12宫那个"）
            house = self._parse_house(classified.get("focus_house"))
            if house is not None:
                intent.slots["focus_house"] = IntentSlot(
                    name="focus_house", raw_value=f"{house}宫",
                    normalized_value=str(house), confidence=1.0,
                )
            return intent

        domain_raw = classified.get("domain")
        if not isinstance(domain_raw, str) or not domain_raw.strip():
            return None
        domain_raw = domain_raw.strip().lower()

        # 领域映射的闲聊/产品兜底（旧模型输出 domain=chat/meta 而非 intent_type）
        if domain_raw == "chat":
            return self._build_chat_intent(message)
        if domain_raw == "meta":
            return self._build_meta_intent(message)

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
        intent = self._build_intent(
            message, domain,
            str(subdomain) if isinstance(subdomain, str) else "",
            confidence=conf, needs_clarification=needs,
        )

        # ---- 富化：intent_type / focus_house / focus_slice / deep_dive / confirmed ----
        intent.intent_type = intent_type
        intent.confirmed = classified.get("confirmed") if isinstance(
            classified.get("confirmed"), bool
        ) else None
        intent.deep_dive = bool(classified.get("deep_dive"))

        focus_slice = classified.get("focus_slice")
        if isinstance(focus_slice, str) and focus_slice.strip():
            intent.focus_slice = focus_slice.strip()

        # focus_house（受控 1-12 → focus_house 槽位，走确定性宫位解读路径）
        house = self._parse_house(classified.get("focus_house"))
        if house is not None:
            intent.slots["focus_house"] = IntentSlot(
                name="focus_house", raw_value=f"{house}宫",
                normalized_value=str(house), confidence=1.0,
            )
            # 切片 → 领域由 Domain 权威化：LLM 的 focus_slice 在语义场命中 →
            # 用 signification 表的 domain（_SLICE_DOMAIN_PREF），覆盖 LLM 的领域猜。
            if intent.focus_slice is not None:
                slice_entry = self._router._match_slice(house, intent.focus_slice)
                if slice_entry is not None:
                    domain_authoritative = self._router._domain_for_slice(
                        slice_entry, None,
                    )
                    intent.domain = domain_authoritative
                    intent.focus_slice = str(slice_entry.get("word", "")) or intent.focus_slice
                    intent.slots["focus_domain"] = IntentSlot(
                        name="focus_domain",
                        raw_value=slice_entry.get("word", ""),
                        normalized_value=domain_authoritative.value,
                        confidence=0.9,
                    )
        return intent

    # ------------------------------------------------------------------
    # Intent 构造
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_house(raw) -> int | None:
        """LLM 输出的 focus_house → int(1-12)，非法 → None。"""
        if isinstance(raw, bool):
            return None
        try:
            h = int(raw)
        except (TypeError, ValueError):
            return None
        return h if 1 <= h <= 12 else None

    def _build_chat_intent(self, message: str) -> Intent:
        intent = self._build_intent(
            message, IntentDomain.DAILY, "Chat",
            confidence=0.8, needs_clarification=False,
        )
        intent.intent_type = "chat"
        return intent

    def _build_meta_intent(self, message: str) -> Intent:
        intent = self._build_intent(
            message, IntentDomain.DAILY, "Meta",
            confidence=0.9, needs_clarification=False,
        )
        intent.intent_type = "meta"
        return intent

    def _build_intent(
        self, message, domain, subdomain, *, confidence, needs_clarification,
    ) -> Intent:
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
    # 确定性确认检测（规则兜底，证据链闭环）
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_confirmation(message: str, context: dict | None) -> bool | None:
        """上轮发过验证问句 + 短句确认/否认 → True/False；否则 None。

        判定保守（宁缺毋滥）：
        - 前置：context.pending_house_verify 非空（刚问完机制验证）；
        - 消息 ≤ 20 字（真回答验证问句通常很短）；
        - 命中确认词（正/负分别枚举）。
        """
        if not (context or {}).get("pending_house_verify"):
            return None
        text = message.strip().replace("\n", " ")
        if len(text) > 20:
            return None
        for kw in _CONFIRM_POSITIVE:
            if kw in text:
                return True
        for kw in _CONFIRM_NEGATIVE:
            if kw in text:
                return False
        return None

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
