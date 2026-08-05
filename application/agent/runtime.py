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

from foundation.config import AppConfig
from foundation.logger import get_logger
from shared.constants import HOUSE_SYSTEM_ZH
from shared.enums import IntentDomain, PersonaType, Planet, Priority, Verdict
from shared.models import Conclusion, ExecutionStatus, Intent, Person, Strategy, StrategyStep

from application.agent.context_builder import ContextBuilder
from application.agent.intent_parser import IntentParser

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


class GardenSpiritAgent:
    """Agent 主循环。"""

    def __init__(self, config: AppConfig | None = None):
        self.config = config or AppConfig()

        # LLM 客户端（意图槽抽取 + 结论转述 + 深度拆解共用；不可用时自动降级）
        from foundation.llm.client import LLMClient

        self._llm = LLMClient(self.config.llm)

        self.strategy_loader = StrategyLoader()
        self.planner = Planner()
        self.executor = Executor()
        self.composer = Composer()
        self.reasoner = Reasoner()
        self.context_builder = ContextBuilder()
        self._calculator = NatalChartCalculator()

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
    ) -> str:
        """处理一条用户消息，返回助手回答。"""
        persona = persona or self.config.default_persona
        ctx = self.context_builder.get_or_create(session_id, person, persona)
        ctx.record_user_message(message)

        # 0. Safety gate（对齐 requires_clarification 短路模式）
        #    自伤/自杀信号 → 阻断占星，返回专业求助引导（PRD §9）
        from application.conversation.safety import check_safety

        safety = check_safety(message)
        if safety.level == "blocked":
            ctx.record_assistant_response(safety.message)
            ctx.add_turn(message, safety.message)
            return safety.message

        # 1. Intent 解析（LLM 深度拆解：领域路由 + 占星结构映射 + 任务富化）
        decomposed = self.intent_parser.parse_deep(message, context=ctx.to_intent_context())
        intent = decomposed.intent
        if intent.requires_clarification:
            return intent.clarification_question

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
        strategy = self._select_strategy(decomposed)
        plan, chart = self.planner.create_plan(
            intent, strategy, person,
            enrichment=self._build_enrichment(decomposed),
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
        answer = self._format_response(conclusion, intent, persona, chart)

        # 4. 记录会话
        ctx.latest_intent = intent
        ctx.latest_conclusion = conclusion
        ctx.record_assistant_response(answer)
        ctx.add_turn(message, answer)
        return answer

    # ------------------------------------------------------------------

    def set_related_person(self, session_id: str, partner: Person) -> None:
        """登记合盘对象（含其出生数据）。"""
        ctx = self.context_builder._sessions.get(session_id)
        if ctx is None:
            raise ValueError(f"会话不存在: {session_id}")
        ctx.related_person = partner
        ctx.pending_related_person = False

    def set_house_system(self, session_id: str, house_system) -> None:
        """设置会话用户偏好的宫位制（作用于会话内的 Person）。"""
        ctx = self.context_builder._sessions.get(session_id)
        if ctx is None:
            raise ValueError(f"会话不存在: {session_id}")
        ctx.person.house_system = house_system

    def _select_strategy(self, decomposed: "DecomposedIntent") -> Strategy:
        """选择策略：优先精确匹配，兜底领域默认；追加 decomposer 的额外任务。"""
        from domain.reasoning.intent.decomposer import DecomposedIntent  # noqa: PLC0415

        intent = decomposed.intent
        exact_ref = f"{intent.domain.value}.{intent.subdomain}" if intent.subdomain else ""
        strategy = self.strategy_loader.get(exact_ref)
        if strategy is None:
            strategy = self.strategy_loader.get_for_domain(intent.domain)
        if strategy is None:
            raise ValueError(f"没有可用的策略: {intent.domain.value}.{intent.subdomain}")

        # 追加 decomposer 产出的额外模块（不重复已有模块）
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
    def _build_enrichment(decomposed: "DecomposedIntent") -> dict:
        """从 DecomposedIntent 构建 enrichment 字典，注入 step params。"""
        from domain.reasoning.intent.decomposer import DecomposedIntent  # noqa: PLC0415
        return {
            "focus_houses": decomposed.focus_houses,
            "focus_planets": decomposed.focus_planets,
            "focus_house_lords": decomposed.focus_house_lords,
            "focus_aspect_pairs": decomposed.focus_aspect_pairs,
            "focus_dimensions": decomposed.focus_dimensions,
        }

    def _format_response(
        self,
        conclusion: Conclusion,
        intent: Intent,
        persona: PersonaType,
        chart=None,
    ) -> str:
        """组织回答文本。

        LLM 可用 → 走 application/conversation/response.py 人格化转述。
        LLM 不可用 / 调用失败 → 降级 v1 模板（不阻断服务）。
        无论哪条路，结论内容都来自 Domain，LLM 只换语气。

        chart: 本命盘。用于生成飞星证据卡 + 本命概要（LLM 转述的素材）。
        """
        if self._llm.available:
            try:
                from application.conversation.response import paraphrase
                from domain.astrology.interpretation import dispositor_cards, natal_reading
                from domain.reasoning.consult import get_resolver

                profiles = self._planet_profiles_for(intent, chart)

                # 飞星证据卡 + 本命概要：已建成但此前未接通的数据（LLM 素材）
                cards = dispositor_cards(chart, self._kb) if chart is not None else None
                natal = natal_reading(chart, self._kb) if chart is not None else None

                # 咨询模板：从用户问题 → 话题结构，注入 LLM 叙事指导
                resolver = get_resolver()
                topic_plan = resolver.resolve_topic(intent.raw_query)

                return paraphrase(
                    conclusion=conclusion,
                    persona=persona,
                    planet_profiles=profiles,
                    evidence_cards=cards,
                    natal=natal,
                    question=intent.raw_query,
                    llm_client=self._llm,
                    topic_plan=topic_plan,
                )
            except Exception as exc:  # pragma: no cover - LLM 降级
                logger.warning("LLM 转述失败，降级 v1 模板: %s", exc)

        return self._fallback_template(conclusion, intent, persona)

    def _fallback_template(
        self, conclusion: Conclusion, intent: Intent, persona: PersonaType
    ) -> str:
        """v1 模板化回答（无 LLM）。persona 参数保留供扩展。"""
        verdict = Verdict(conclusion.metadata.get("verdict", "neutral"))
        verdict_text = {
            Verdict.FAVORABLE: "总体有利",
            Verdict.UNFAVORABLE: "阻力较大",
            Verdict.NEUTRAL: "方向不明确",
            Verdict.NEEDS_MORE_DATA: "信息不足",
        }.get(verdict, verdict.value)

        # 描述性解读：summary 已带说明，直接展示
        if conclusion.metadata.get("descriptive"):
            lines = [
                conclusion.summary or f"关于{intent.domain.value}的解读",
            ]
        else:
            lines = [
                conclusion.summary or f"关于{intent.domain.value}的解读",
                f"总体判断：{verdict_text}（置信度 {conclusion.overall_confidence:.0%}）",
            ]

        if conclusion.findings:
            lines.append("\n关键依据：")
            for f in conclusion.findings[:5]:
                mark = {"positive": "✓", "negative": "✗", "neutral": "·"}.get(f.polarity.value, "·")
                lines.append(f"  {mark} {f.text}")

        if conclusion.time_periods:
            lines.append("\n时间窗口：")
            for tp in conclusion.time_periods:
                lines.append(f"  {tp.label}（{tp.quality.value}）")

        for rec in conclusion.recommendations:
            lines.append(f"\n建议：{rec}")

        for gap in conclusion.data_gaps:
            lines.append(f"\n提示：{gap}")

        house_system = conclusion.metadata.get("house_system", "placidus")
        hs_label = HOUSE_SYSTEM_ZH.get(house_system, house_system)
        lines.append(f"\n* 本解读采用 {hs_label}")

        # 免责声明（PRD §9）：统一走 safety 模块，单一来源
        from application.conversation.safety import disclaimer_text

        lines.append(disclaimer_text())
        return "\n".join(lines)

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
