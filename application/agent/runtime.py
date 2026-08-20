"""Master Agent 主循环 —— 唯一的 Agent 入口。

核心链路（冻结）：
User → Intent Parser → Intent → Strategy → Execution Plan
     → Analysis Modules → Astrology Kernel → Facts → Evidence
     → Reasoner → Conclusion → (Persona + LLM) → Answer

原则一：本文件不计算宫位/相位/行星，只编排。
原则二：领域推理（Strategy/Evidence/Conclusion）不依赖 LLM。
原则三：LLM 只转述结论，不改变极性/建议。
"""

from __future__ import annotations

import random
from collections.abc import Callable

from foundation.config import AppConfig
from foundation.logger import get_logger
from foundation.utils import new_id
from shared.constants import HOUSE_SYSTEM_ZH
from shared.enums import ConsultMode, HouseSystem, IntentDomain, PersonaType, Planet, Priority, Verdict
from shared.models import (
    Chart, Conclusion, ExecutionStatus, Finding, Intent, IntentSlot, Person, Strategy, StrategyStep,
)

from application.agent.context_builder import ContextBuilder
from application.agent.intent_parser import IntentParser
from application.conversation.companion import should_use_companion
from application.conversation.emotion import EmotionPerception
from application.conversation.fragments import FragmentClassifier
from application.conversation.planet_activation import (
    PlanetActivation,
    PlanetActivationClassifier,
)

from domain.analysis import (
    CareerStrength,
    Daily,
    Emotion,
    Family,
    Finance,
    Health,
    Learning,
    MarriagePotential,
    Opportunity,
    PartnerTraits,
    Psychology,
    RelationshipStatus,
    RelationshipSynastry,
    Risk,
    Timing,
    Wealth,
)
from domain.astrology.calculation import NatalChartCalculator
from domain.reasoning import Composer, Executor, Planner, Reasoner, StrategyLoader

logger = get_logger("application.agent")

#: 意图领域 → 中文名（降级模板/叙事共用）
_DOMAIN_ZH = {
    "career": "事业",
    "relationship": "感情",
    "wealth": "财富",
    "health": "健康",
    "emotion": "情绪",
    "family": "家庭",
    "learning": "学习",
    "growth": "远方·信念",
    "network": "人际·社群",
    "self": "自我",
    "daily": "今日",
}

#: 降级模板开场白（按判定极性）
_VERDICT_OPENERS = {
    Verdict.FAVORABLE: "盘面上看，这件事总体是站在你这边的，可以更有底气地往前走。",
    Verdict.UNFAVORABLE: "盘面上看，这件事眼下阻力不小，但绝非绝路——关键是选对时机、看清条件。",
    Verdict.NEUTRAL: "盘面上看，这件事的方向还不完全明朗，需要结合现实条件来判断。",
    Verdict.NEEDS_MORE_DATA: "你的星盘上，这个问题还缺一些信息才能看准，先别急着下结论。",
}

#: 判定为"技术性评分/时机"的文本特征——降级模板过滤（素材留给 LLM 叙事）
_SCORING_MARKERS = ("综合评分", "净分", "尊贵分", "时间窗口", "行运对")


def _is_scoring_text(text: str) -> bool:
    return any(marker in text for marker in _SCORING_MARKERS)


#: 纯问候/闲聊短句 → 直接温暖回应（不进 LLM、不进澄清循环）
_CHAT_GREETINGS = (
    "你好", "您好", "嗨", "哈喽", "哈罗", "hello", "hi",
    "在吗", "在么", "随便聊聊", "聊聊天", "干嘛呢", "早上好", "晚上好",
)
_CHAT_REPLIES = (
    "在呢在呢——想聊什么随便说，我都在。怎么啦，想找人说说话？",
    "我在的。今天是有什么想聊的，还是单纯想找人说说话？",
    "在的！说说看，最近有什么新鲜事？",
)

#: 产品能力/身份类问题 → 能力介绍（"我是谁/我专业是什么/能帮你什么"）。
#: 触发不走关键词：LLM 分类为 meta → 此处返回；离线由规则兜底。
_CAPABILITY_REPLY = (
    "我是住在你星盘里的星灵——我的专业是解盘：读你本命盘里的结构，"
    "把它翻译成能听懂的人话。具体能帮你：\n"
    "· 看懂自己——事业、感情、财运、健康、情绪、家庭、学习，想不通就能问\n"
    "· 看懂时机——什么时候该发力、什么时候该蓄力\n"
    "· 陪你成长——写日记、收每日来信，越聊越懂你\n"
    "想先从哪块开始？"
)

#: 证据链深挖 → 机制验证问句（按切片词命中；没命中给通用问法）。
#: 引导用户确认/否认机制（下一轮 intent_type=confirmation → 收敛结论），
#: 对应 consult_method §3「对话验证，不讲独白」：结论要用户自己认领。
_VERIFY_QUESTION_MAP: list[tuple[str, str]] = [
    ("暗财", "你最近有没有靠不公开的渠道进账——副业、投资、资源置换这类？"),
    ("玄学", "你最近是不是在学或做玄学、灵性、幕后专业相关的事？"),
    ("沟通", "你最近有没有在写东西、做内容，或需要公开表达的场合？"),
    ("恋爱", "你最近身边有没有在靠近、或让你心动的人？"),
    ("事业", "你最近在事业上有没有具体动向——跳槽、升职、还是转方向？"),
]

_VERIFY_GENERIC = (
    "想验证一下：这个「{slice}」的线索，你最近在实际生活里有没有对应的行动或经历？"
    "你确认或否认，我都能据此把结论收紧。"
)


def _verification_question(slice_word: str) -> str | None:
    """切片词 → 机制验证问句（确定性，硬线：不产出占星结论）。"""
    if not slice_word:
        return None
    for needle, question in _VERIFY_QUESTION_MAP:
        if needle in slice_word:
            return question
    return _VERIFY_GENERIC.format(slice=slice_word)


class GardenSpiritAgent:
    """Agent 主循环。"""

    def __init__(self, config: AppConfig | None = None):
        self.config = config or AppConfig()

        # LLM 客户端（意图槽抽取 + 结论转述 + 深度拆解共用；不可用时自动降级）
        from foundation.llm.client import LLMClient

        self._llm = LLMClient(self.config.llm)

        # 情绪感知层（陪伴协议第 1 步）：感知情绪×诉求，供随聊轨道消费
        self._emotion = EmotionPerception(self._llm)

        # 34 子类点亮（随聊记录层，§2）：随聊轨道记"聊过什么"
        self._fragments = FragmentClassifier(self._llm)

        # 星灵激活（语境定刻，§1.1.1）：此刻哪颗星被触动，只报激活不判方向
        self._planets = PlanetActivationClassifier(self._llm)

        self.strategy_loader = StrategyLoader()
        self.planner = Planner()
        self.executor = Executor()
        self.composer = Composer()
        self.reasoner = Reasoner()
        self.context_builder = ContextBuilder()
        self._calculator = NatalChartCalculator()
        self._chart_provider: Callable[[Person, HouseSystem | None], Chart] = self._calculator.compute

        # 注册分析模块（必须在 IntentDecomposer 之前，因为 decomposer 需要模块名列表）
        self._register_analysis_modules()

        # 知识库（LLM 转述素材：飞星证据卡 / 本命概要）
        from domain.astrology.knowledge import load_knowledge

        self._kb = load_knowledge()

        # IntentDecomposer（Layer 1 深度理解：LLM 映射占星结构 + 任务富化）
        from domain.reasoning.intent.decomposer import IntentDecomposer

        self.intent_decomposer = IntentDecomposer(
            llm_client=self._llm,
            registered_modules=set(self.executor._modules.keys()),
        )
        self.intent_parser = IntentParser(
            llm_client=self._llm,
            decomposer=self.intent_decomposer,
        )

    def set_chart_provider(
        self,
        provider: Callable[[Person, HouseSystem | None], Chart],
    ) -> None:
        """注入本命盘读取入口（生产走加密缓存；测试可走即时计算/spy）。"""
        self._chart_provider = provider

    def _register_analysis_modules(self) -> None:
        self.executor.register(CareerStrength())
        self.executor.register(Timing())
        self.executor.register(Risk())
        self.executor.register(Opportunity())
        self.executor.register(Finance())
        self.executor.register(PartnerTraits())
        self.executor.register(Psychology())
        self.executor.register(Wealth())
        self.executor.register(RelationshipSynastry())
        self.executor.register(RelationshipStatus())
        self.executor.register(MarriagePotential())
        self.executor.register(Daily())
        self.executor.register(Health())
        self.executor.register(Emotion())
        self.executor.register(Family())
        self.executor.register(Learning())

    # ------------------------------------------------------------------

    def handle_message(
        self,
        session_id: str,
        message: str,
        person: Person,
        persona: PersonaType | None = None,
        mode: ConsultMode | str = ConsultMode.DEEP,
        report_intent: dict | None = None,
    ) -> str:
        """处理一条用户消息，返回助手回答。

        mode: 咨询模式——quick 精简分析+回答，deep 完整（默认）。
        """
        persona = persona or self.config.default_persona
        ctx = self.context_builder.get_or_create(session_id, person, persona)
        if report_intent:
            ctx.report_intent = report_intent
        else:
            ctx.report_intent = None
        intent_context = ctx.to_intent_context()
        ctx.begin_turn()
        ctx.record_user_message(message)

        # 0. Safety gate（对齐 requires_clarification 短路模式）
        #    自伤/自杀信号 → 阻断占星，返回专业求助引导（PRD §9）
        from application.conversation.safety import check_safety

        safety = check_safety(message)
        if safety.level == "blocked":
            ctx.record_assistant_response(safety.message)
            ctx.add_turn(message, safety.message)
            return safety.message

        # 0.5 纯问候/闲聊短句 → 温暖回应（不浪费 LLM、不进入澄清循环）
        chat_reply = self._detect_chat(message)
        if chat_reply is not None:
            ctx.last_was_chat = True  # A2：闲聊快路径没有 Intent，用标志位识别
            ctx.record_assistant_response(chat_reply)
            ctx.add_turn(message, chat_reply)
            return chat_reply

        # 0.7 情绪感知（陪伴协议第 1 步）：感知情绪×诉求，挂上下文供随聊轨道消费
        ctx.emotion_result = self._emotion.perceive(message)

        # 1. Intent 解析（LLM 深度拆解：领域路由 + 占星结构映射 + 任务富化）
        decomposed = self.intent_parser.parse_deep(
            message, context=intent_context, mode=mode,
        )
        intent = decomposed.intent

        # 1.5 随聊轨道（陪伴协议 §7.2）：分享/倾诉/迷茫 → 接住+镜映，绝不处方化。
        #     判定在澄清之前：含糊消息宁可先走陪伴，也不反问"你想问哪方面"（§8 兜底）。
        if should_use_companion(intent, ctx.emotion_result):
            reply = self._companion_reply(message, ctx.emotion_result, persona)
            ctx.last_was_chat = True       # A2：casual 信号（信任层小幅加分）
            ctx.last_was_companion = True  # 陪伴轨道标志（递出口门控在 API 层）
            ctx.latest_intent = intent     # 一致性：陪伴也是意图
            ctx.fragments = self._fragments.classify(message)  # §2 34 子类点亮（记"聊过什么"）
            # §1.1.1 语境定刻：此刻哪颗星被触动（只报激活，不判方向）+ 抓手 + 情绪/诉求
            ctx.planet_activation = PlanetActivation(
                planets=self._planets.classify(message),
                trigger=message,
                emotion=ctx.emotion_result.emotion if ctx.emotion_result else None,
                request=ctx.emotion_result.request if ctx.emotion_result else None,
            )
            ctx.record_assistant_response(reply)
            ctx.add_turn(message, reply)
            return reply

        if intent.requires_clarification:
            # 裸宫反问：暂存宫位，等本轮回答切片时经 context.active_house 消解
            house_slot = intent.get_slot("focus_house")
            if house_slot is not None:
                ctx.pending_focus_house = int(house_slot.normalized_value)
            return intent.clarification_question

        # 问星灵自己/产品能力（LLM 分类 meta / 离线规则兜底）→ 能力介绍，不进占星管线
        if intent.subdomain == "Meta":
            ctx.latest_intent = intent
            ctx.record_assistant_response(_CAPABILITY_REPLY)
            ctx.add_turn(message, _CAPABILITY_REPLY)
            return _CAPABILITY_REPLY

        # 深挖确认：用户对上轮证据链问句确认/否认（intent_type=confirmation）
        # → 收敛机制结论（"坐实"或"倾向"），不复述整段证据。
        # 宫位优先取 focus_house 槽；缺省则继承上轮深挖暂存 ctx.pending_house_verify。
        if intent.intent_type == "confirmation":
            house_slot = intent.get_slot("focus_house")
            verify = ctx.pending_house_verify
            if house_slot is None and verify is not None:
                house, v_domain, v_slice = verify
                intent.slots["focus_house"] = IntentSlot(
                    name="focus_house", raw_value=f"{house}宫",
                    normalized_value=str(house), confidence=1.0,
                )
                intent.slots["focus_domain"] = IntentSlot(
                    name="focus_domain", raw_value=v_slice,
                    normalized_value=v_domain, confidence=0.9,
                )
                house_slot = intent.get_slot("focus_house")
            if house_slot is not None:
                chart = self._chart_provider(person, None)
                from domain.reasoning.consult import get_resolver

                call_plan = get_resolver().resolve_call_plan(intent, chart=chart)
                enrichment = self._build_enrichment(decomposed, call_plan=call_plan)
                conclusion = self._house_conclusion(
                    chart, intent, house_slot, deep=True, confirmed=intent.confirmed,
                    enrichment=enrichment,
                )
                house = int(house_slot.normalized_value)
                ctx.pending_house_verify = None
                ctx.pending_focus_house = None
                answer = self._format_response(
                    conclusion, intent, persona, chart=chart, mode=mode,
                    house_focus=house, confirmed=intent.confirmed, call_plan=call_plan,
                )
                ctx.latest_intent = intent
                ctx.latest_conclusion = conclusion
                ctx.record_assistant_response(answer)
                ctx.add_turn(message, answer)
                return answer
            # 无宫位可收敛 → 落回常规路由（本轮当作新话题处理）

        # 宫位咨询路径：用户锁定"3宫表达"/"12宫财运" → 宫位语义场直接出解读。
        # 不走领域策略管线（那是 generic 领域结论，与宫位无关）；硬线不变——
        # 占星结论仍全由 Domain 的 HouseSignificationEngine 出，LLM 只叙事。
        house_slot = intent.get_slot("focus_house")
        if house_slot is not None:
            chart = self._chart_provider(person, None)
            from domain.reasoning.consult import get_resolver

            call_plan = get_resolver().resolve_call_plan(intent, chart=chart)
            enrichment = self._build_enrichment(decomposed, call_plan=call_plan)
            deep = intent.deep_dive or intent.intent_type == "follow_up_deep_dive"
            conclusion = self._house_conclusion(
                chart, intent, house_slot, deep=deep, enrichment=enrichment,
            )
            house = int(house_slot.normalized_value)
            ctx.pending_focus_house = None
            answer = self._format_response(
                conclusion, intent, persona, chart=chart, mode=mode,
                house_focus=house, call_plan=call_plan,
            )
            if deep:
                # 证据链深挖：暂存待验证 + 追加机制问句（引导用户确认，进入收敛轮）
                domain = (
                    intent.get_slot("focus_domain").normalized_value
                    if intent.get_slot("focus_domain") else intent.domain.value
                )
                slice_word = intent.focus_slice or conclusion.metadata.get("focus_slice", "")
                ctx.pending_house_verify = (house, domain, slice_word or "")
                vq = conclusion.metadata.get("verification_question")
                if vq:
                    answer = f"{answer}\n\n{vq}"
            ctx.latest_intent = intent
            ctx.latest_conclusion = conclusion
            ctx.record_assistant_response(answer)
            ctx.add_turn(message, answer)
            return answer

        # 合盘入口：提到具体对象（男朋友/女友…）→ 需要对方出生数据
        related_slot = intent.get_slot("related_person")
        if related_slot is not None and intent.domain == IntentDomain.RELATIONSHIP:
            if ctx.related_person is None:
                ctx.pending_related_person = True
                return (
                    f"想更准地分析你和{related_slot.raw_value}的关系，"
                    "我需要对方的出生时间、地点（越精确越好）。"
                )
            intent.subdomain = "Synastry"  # 有对方数据 → 走合盘

        # 2. 策略 → 计划 → 执行 → 证据 → 结论（全 Domain，无 LLM）
        strategy = self._select_strategy(decomposed, mode=mode)
        chart = self._chart_provider(person, None)
        from domain.reasoning.consult import get_resolver

        call_plan = get_resolver().resolve_call_plan(intent, chart=chart)
        plan, chart = self.planner.create_plan(
            intent, strategy, person, chart=chart,
            enrichment=self._build_enrichment(decomposed, call_plan=call_plan),
        )

        # 追问的时间指代（如"那明年呢？"）→ 偏移 Timing 扫描窗口起点
        time_offset = intent.get_slot("time_start_offset")
        if time_offset is not None:
            offset = int(time_offset.normalized_value)
            for step in plan.steps:
                if step.module == "Timing":
                    step.params["start_offset_months"] = offset

        # 合盘：注入对方星盘（同一宫位制——以用户为准，保证落宫解读可比）
        if intent.subdomain == "Synastry" and ctx.related_person is not None:
            partner_chart = self._calculator.compute(
                ctx.related_person, house_system=chart.house_system
            )
            for step in plan.steps:
                if step.module == "RelationshipSynastry":
                    step.params["partner_chart"] = partner_chart

        fact_set = self.executor.execute(plan, chart, person)
        evidence_set = self.composer.compose(fact_set, strategy, intent)

        # 核心模块失败 → 报"数据不足"，不硬造结论（正确性红线）
        failed_core = [
            s.module for s in plan.steps
            if s.status == ExecutionStatus.FAILED and s.priority == Priority.HIGH
        ]
        conclusion = self.reasoner.reason(evidence_set, intent, failed_core)
        conclusion.metadata["house_system"] = chart.house_system.name.lower()

        # 出生时间未知 → 精度降级提示（PRD §8）
        # 架构理由：_data_gaps() 在 Domain 层只收 intent 不收 person，
        # 按冻结架构不改 Domain 签名，故在 Application 层追加。
        if not person.birth.time_known:
            conclusion.data_gaps.append(
                "出生时间未精确到分钟，默认使用正午 12:00 排盘，"
                "宫位结论精度受限。上升/天顶落座描述可能不准确。"
            )

        # 3. 组织回答（LLM 人格化转述；不可用时降级 v1 模板）
        answer = self._format_response(
            conclusion, intent, persona, chart, mode=mode, call_plan=call_plan,
        )

        # 4. 记录会话
        ctx.latest_intent = intent
        ctx.latest_conclusion = conclusion
        ctx.pending_focus_house = None  # 宫位追问已闭环（含用户转问其他话题的情况）
        ctx.record_assistant_response(answer)
        ctx.add_turn(message, answer)
        return answer

    # ------------------------------------------------------------------

    def _companion_reply(self, message: str, emotion_result, persona) -> str:
        """陪伴协议生成回复（接住 + 镜映）。LLM 生成，规则兜底。"""
        from application.conversation.companion import companion_reply

        return companion_reply(
            message, emotion_result,
            llm_client=self._llm, persona=persona,
        )

    @staticmethod
    def _detect_chat(message: str) -> str | None:
        """纯问候/闲聊短句检测：命中返回温暖回应，否则 None。

        只匹配短句（≤10 字），长句交给意图路由——避免"聊聊感情"这类
        真提问被当成闲聊吞掉。
        """
        msg = message.strip()
        if not msg or len(msg) > 10:
            return None
        low = msg.lower()
        for kw in _CHAT_GREETINGS:
            if kw in low:
                return random.choice(_CHAT_REPLIES)
        return None

    def get_session_context(self, session_id: str):
        """取会话上下文（含 conversation/intent/conclusion），供记忆写回。"""
        return self.context_builder.get(session_id)

    def set_related_person(self, session_id: str, partner: Person, person: Person | None = None) -> None:
        """登记合盘对象（含其出生数据）。

        会话不存在时用盘主 person 预建（合盘对象跨请求恢复：/chat 开头恢复时
        本会话上下文还没被 handle_message 创建）。person=None 且会话不存在 → 报错。
        """
        ctx = self.context_builder._sessions.get(session_id)
        if ctx is None:
            if person is None:
                raise ValueError(f"会话不存在: {session_id}")
            ctx = self.context_builder.get_or_create(
                session_id, person, self.config.default_persona
            )
        ctx.related_person = partner
        ctx.pending_related_person = False

    def set_house_system(self, session_id: str, house_system) -> None:
        """设置会话用户偏好的宫位制（作用于会话内的 Person）。"""
        ctx = self.context_builder._sessions.get(session_id)
        if ctx is None:
            raise ValueError(f"会话不存在: {session_id}")
        ctx.person.house_system = house_system

    def _select_strategy(
        self, decomposed: "DecomposedIntent", mode: ConsultMode | str = ConsultMode.DEEP
    ) -> Strategy:
        """选择策略：优先精确匹配，兜底领域默认；深度模式追加 decomposer 任务。"""
        from domain.reasoning.intent.decomposer import DecomposedIntent  # noqa: PLC0415

        intent = decomposed.intent
        exact_ref = f"{intent.domain.value}.{intent.subdomain}" if intent.subdomain else ""
        strategy = self.strategy_loader.get(exact_ref)
        if strategy is None:
            strategy = self.strategy_loader.get_for_domain(intent.domain)
        if strategy is None:
            raise ValueError(f"没有可用的策略: {intent.domain.value}.{intent.subdomain}")

        # 快速咨询：只走策略自带模块，不追加（保证快而精）
        if mode == ConsultMode.QUICK or mode == "quick":
            return strategy

        # 深度模式：追加 decomposer 产出的额外模块（不重复已有模块）
        existing_modules = {s.analysis_module for s in strategy.steps}
        for task in decomposed.merged_tasks:
            if task.module not in existing_modules:
                strategy.steps.append(StrategyStep(
                    id=task.module,
                    name=task.module,
                    analysis_module=task.module,
                    required_facts=[],
                    config=dict(task.params),
                    weight_in_summary=0.7,
                    priority=task.priority,
                ))
                existing_modules.add(task.module)
                logger.debug("Decomposer 追加模块: %s", task.module)

        return strategy

    @staticmethod
    def _build_enrichment(decomposed: "DecomposedIntent", call_plan=None) -> dict:
        """从 DecomposedIntent + ConsultCallPlan 构建 step enrichment。"""
        from domain.reasoning.intent.decomposer import DecomposedIntent  # noqa: PLC0415

        def _unique(values):
            out = []
            for value in values:
                if value in (None, "") or value in out:
                    continue
                out.append(value)
            return out

        enrichment = {
            "focus_houses": list(decomposed.focus_houses),
            "focus_planets": list(decomposed.focus_planets),
            "focus_house_lords": list(decomposed.focus_house_lords),
            "focus_aspect_pairs": list(decomposed.focus_aspect_pairs),
            "focus_dimensions": list(decomposed.focus_dimensions),
        }
        if call_plan is None:
            return enrichment

        d = call_plan.to_dict()
        enrichment["focus_houses"] = _unique([
            *enrichment["focus_houses"],
            d.get("focus_house"),
            d.get("primary_house"),
            *(d.get("core_houses") or []),
            *(d.get("supplementary_houses") or []),
        ])
        enrichment["focus_house_lords"] = _unique([
            *enrichment["focus_house_lords"],
            *(d.get("house_lords") or []),
        ])
        enrichment["focus_planets"] = _unique([
            *enrichment["focus_planets"],
            *(d.get("natural_significators") or []),
            *(d.get("supporting_planets") or []),
            *(d.get("house_lord_planets") or []),
            *(d.get("house_occupants") or []),
        ])
        enrichment["focus_aspect_pairs"] = _unique([
            *enrichment["focus_aspect_pairs"],
            *(d.get("aspect_pairs") or []),
        ])
        enrichment["consult_call_plan_source"] = d.get("source")
        enrichment["house_lord_placements"] = d.get("house_lord_placements") or []
        enrichment["house_occupants"] = d.get("house_occupants") or []
        return enrichment

    def _format_response(
        self,
        conclusion: Conclusion,
        intent: Intent,
        persona: PersonaType,
        chart=None,
        mode: ConsultMode | str = ConsultMode.DEEP,
        house_focus: int | None = None,
        confirmed: bool | None = None,
        call_plan=None,
    ) -> str:
        """组织回答文本。

        LLM 可用 → 走 application/conversation/response.py 人格化转述。
        LLM 不可用 / 调用失败 → 降级 v1 模板（不阻断服务）。
        无论哪条路，结论内容都来自 Domain，LLM 只换语气。

        chart: 本命盘。用于生成飞星证据卡 + 本命概要（LLM 转述的素材）。
        house_focus: 宫位咨询（"3宫表达"）时注入，LLM 叙事围绕该宫收束。
        confirmed: 证据链收敛轮——LLM 叙事先承接确认/否认，再收敛不展开。
        call_plan: 本轮咨询主干；常规执行链已解析时复用同一份，避免 prompt/执行漂移。
        """
        answer = ""
        if self._llm.available:
            try:
                from application.conversation.response import paraphrase
                from domain.astrology.interpretation import dispositor_cards, natal_reading

                profiles = self._planet_profiles_for(intent, chart)

                # 飞星证据卡 + 本命概要：已建成但此前未接通的数据（LLM 素材）
                cards = dispositor_cards(chart, self._kb) if chart is not None else None
                natal = natal_reading(chart, self._kb) if chart is not None else None

                # 咨询模板：Intent → ConsultCallPlan，注入 LLM 叙事指导
                if call_plan is None:
                    from domain.reasoning.consult import get_resolver

                    call_plan = get_resolver().resolve_call_plan(intent, chart=chart)

                answer = paraphrase(
                    conclusion=conclusion,
                    persona=persona,
                    planet_profiles=profiles,
                    evidence_cards=cards,
                    natal=natal,
                    question=intent.raw_query,
                    llm_client=self._llm,
                    call_plan=call_plan,
                    mode=mode,
                    house_focus=house_focus,
                    confirmed=confirmed,
                )
            except Exception as exc:  # pragma: no cover - LLM 降级
                logger.warning("LLM 转述失败，降级 v1 模板: %s", exc)

        if not answer:
            answer = self._fallback_template(conclusion, intent, persona)

        # A3 输出护栏：统一收口。LLM 路径在此兜底；fallback 内部已自检
        # （coda 已带 marker，幂等，此处不会重复追加）。
        from application.conversation.healing import healing_guardrail_check

        coda = healing_guardrail_check(answer)
        if coda:
            answer += coda

        # Safety 输出护栏：医疗诊断/用药/寿命红线统一收口；不阻断健康咨询，
        # 但最终答复必须提示专业边界。合并扫描 answer + raw_query，避免
        # fallback 已追加 marker 后，raw_query 再触发第二次 coda。
        from application.conversation.safety import medical_boundary_check

        medical_coda = medical_boundary_check(f"{answer}\n{intent.raw_query or ''}")
        if medical_coda:
            answer += medical_coda
        return answer

    @staticmethod
    def _fallback_template(conclusion: Conclusion, intent: Intent, persona: PersonaType) -> str:
        """无 LLM 降级回答：人话叙述，不堆评分/术语。按疗愈 5 步弧线组织。

        弧线（A3 疗愈协议）：共情(开场) → 本命基调(summary) → 交叉(观察)
        → 时机 → 给出路(建议)。技术性评分（综合评分/净分/尊贵分）被过滤——
        那是给 LLM 叙事的素材，直接甩给用户就是生硬。persona 保留供扩展。
        """
        verdict = Verdict(conclusion.metadata.get("verdict", "neutral"))
        domain_zh = _DOMAIN_ZH.get(intent.domain.value, intent.domain.value)

        # ① 共情 + ② 本命基调：温暖开场接住情绪 + 总体判断
        if conclusion.metadata.get("descriptive"):
            lines = [conclusion.summary or f"关于{domain_zh}，我看了你的星盘。"]
            # 描述性解读（宫位语义场/倾向解读）也展示人文观察——不丢细节，
            # 评分项仍过滤（评分是 LLM 叙事的素材，不是给用户的直出文本）
            human = [f for f in conclusion.findings if not _is_scoring_text(f.text)]
            if human:
                lines.append("\n想先和你分享几个观察：")
                for f in human[:4]:
                    lines.append(f"  · {f.text}")
        else:
            lines = [
                _VERDICT_OPENERS.get(verdict, f"关于{domain_zh}，我看了你的星盘。"),
                conclusion.summary or f"关于{domain_zh}，我看了你的星盘。",
            ]

            # ③ 交叉观察：只展示人文表述。全被过滤就不展示观察节——
            # 宁可没有，也不把评分/时机文本直出给用户。
            human = [f for f in conclusion.findings if not _is_scoring_text(f.text)]
            if human:
                lines.append("\n想先和你分享几个观察：")
                for f in human[:3]:
                    lines.append(f"  · {f.text}")

            # ④ 时机
            if conclusion.time_periods:
                lines.append("\n关于时机：")
                for tp in conclusion.time_periods[:3]:
                    quality = {"positive": "有利", "negative": "有阻力", "neutral": "平稳"}.get(tp.quality.value, "平稳")
                    lines.append(f"  · {tp.label} —— {quality}")

        # ⑤ 给出路：建议就是出路；没有建议也要兜底一句，绝不留下绝路（A3 护栏）。
        if conclusion.recommendations:
            for rec in conclusion.recommendations:
                lines.append(f"\n建议：{rec}")
        elif not conclusion.metadata.get("descriptive"):
            from application.conversation.healing import GENERIC_WAY_OUT

            lines.append(GENERIC_WAY_OUT)

        for gap in conclusion.data_gaps:
            lines.append(f"\n提示：{gap}")

        body = "\n".join(lines)

        # A3 输出护栏：命中致命判决词 → 在公告/免责声明前补"给出路"收尾。
        from application.conversation.healing import healing_guardrail_check

        coda = healing_guardrail_check(body)
        if coda:
            body += coda

        # Safety 输出护栏：医疗诊断/用药/寿命红线统一收口，位于免责声明之前。
        from application.conversation.safety import medical_boundary_check

        medical_coda = medical_boundary_check(body) or medical_boundary_check(intent.raw_query)
        if medical_coda:
            body += medical_coda

        house_system = conclusion.metadata.get("house_system", "placidus")
        hs_label = HOUSE_SYSTEM_ZH.get(house_system, house_system)
        body += f"\n（本解读采用 {hs_label}）"

        # 免责声明（PRD §9）：统一走 safety 模块，单一来源
        from application.conversation.safety import disclaimer_text

        body += disclaimer_text()
        return body

    def _planet_profiles_for(self, intent: Intent, chart) -> list | None:
        """按主题从全星档案里抓取相关行星。

        用户理念：每颗星都是单点配置，主题分析只抓取相关项，不孤立只看某几颗。
        感情 → 金火月（+ 日月土的影响留在全部档案里）
        事业 → 日木土
        财 → 木土金水
        其余领域 → 全星档案
        """
        try:
            from domain.astrology.interpretation.planet_profile import (
                pick_for_theme,
                read_all_planets,
            )

            profiles = read_all_planets(chart, self._kb)
        except Exception:
            return None

        domain = intent.domain.value
        if domain == "relationship":
            return pick_for_theme(profiles, (
                Planet.VENUS, Planet.MARS, Planet.MOON,
                Planet.SUN, Planet.SATURN, Planet.JUPITER,
            ))
        if domain == "career":
            return pick_for_theme(profiles, (
                Planet.SUN, Planet.JUPITER, Planet.SATURN,
                Planet.MERCURY, Planet.MARS,
            ))
        if domain == "wealth":
            return pick_for_theme(profiles, (
                Planet.JUPITER, Planet.SATURN, Planet.VENUS, Planet.MERCURY,
            ))
        return profiles

    def _house_conclusion(
        self, chart, intent: Intent, house_slot, *, deep: bool = False,
        confirmed: bool | None = None, enrichment: dict | None = None,
    ) -> Conclusion:
        """宫位语义场解读 → Conclusion（确定性，无 LLM）。

        HouseSignificationEngine 按 (domain, houses=[N]) 激活该宫切片，
        条目 word/evidence 即领域结论（硬线：占星结论全由 Domain 出）；
        标记 descriptive（倾向解读）——LLM 只转述语气，不发明占星事实。

        deep=True（深挖追问）：放开采上限、evidence 全链展开（来源/通道/托底/风险），
        summary 改为机制视角，并生成机制验证问句（供下一轮 confirmation 收敛）。
        confirmed 非空（收敛轮）：summary 落"坐实/倾向"收束，不再问。
        """
        from datetime import datetime, timezone

        from domain.astrology.interpretation import HouseSignificationEngine
        from shared.enums import ConclusionCategory, EvidencePolarity

        house = int(house_slot.normalized_value)
        fd = intent.get_slot("focus_domain")
        domain = fd.normalized_value if fd is not None else intent.domain.value

        items = HouseSignificationEngine(self._kb).interpret(
            chart, domain, houses=[house], max_items=10 if deep else 6,
            enrichment=enrichment,
        )

        findings: list[Finding] = []
        for it in items:
            pol = {
                "positive": EvidencePolarity.POSITIVE,
                "negative": EvidencePolarity.NEGATIVE,
            }.get(it.polarity, EvidencePolarity.NEUTRAL)
            # 深挖：evidence 全链展开（机制逐环可见）；浅读：收敛 top-3 证据
            ev = "；".join(it.evidence) if deep else "；".join(it.evidence[:3])
            text = it.word + (f"——{ev}" if ev else "")
            findings.append(Finding(
                id=new_id("finding"),
                category=(
                    ConclusionCategory.FINDING if pol is EvidencePolarity.POSITIVE
                    else ConclusionCategory.WARNING if pol is EvidencePolarity.NEGATIVE
                    else ConclusionCategory.SUMMARY
                ),
                text=text,
                polarity=pol,
                confidence=min(it.strength / 5.0, 0.95),
                weight=it.strength,
            ))

        domain_zh = _DOMAIN_ZH.get(domain, domain)
        slice_zh = intent.focus_slice or (items[0].word if items else "")
        if items:
            if confirmed is True:
                summary = (
                    f"你确认了——「{slice_zh}」不是停在盘面上的结构，来路是坐实的，"
                    f"顺着 {domain_zh} 这条线落袋的可能性就具体多了。"
                )
            elif confirmed is False:
                summary = (
                    f"你否了这条路径——那「{slice_zh}」更多是潜在倾向，"
                    f"得看你实际的选择才会被激活。"
                )
            elif deep:
                summary = f"往下钻「{slice_zh}」的来路——机制是这样一环环扣起来的："
            else:
                top = items[0]
                summary = f"你{house}宫（{domain_zh}视角）最醒目的是「{top.word}」——先顺着这条看你的模式。"
        else:
            summary = f"你{house}宫在{domain_zh}这个面上暂时没有明显的结构信号，可以结合具体问题再细问。"

        overall_pol = EvidencePolarity.NEUTRAL
        if findings:
            net = sum(
                f.weight * (
                    1 if f.polarity == EvidencePolarity.POSITIVE
                    else -1 if f.polarity == EvidencePolarity.NEGATIVE else 0
                )
                for f in findings
            )
            overall_pol = (
                EvidencePolarity.POSITIVE if net > 0
                else EvidencePolarity.NEGATIVE if net < 0
                else EvidencePolarity.NEUTRAL
            )

        metadata = {
            "descriptive": True,
            "house_system": chart.house_system.name.lower(),
        }
        if deep:
            metadata["deep_dive"] = True
            metadata["focus_slice"] = slice_zh or ""
            if confirmed is None:
                vq = _verification_question(slice_zh)
                if vq:
                    metadata["verification_question"] = vq

        return Conclusion(
            id=new_id("conclusion"),
            intent_id=intent.id,
            evidence_set_id=new_id("evset"),
            domain=domain,
            summary=summary,
            findings=findings,
            overall_polarity=overall_pol,
            generated_at=datetime.now(timezone.utc),
            metadata=metadata,
        )
