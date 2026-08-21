"""IntentDecomposer —— LLM 深度理解层（Layer 1）。

用 LLM 把用户的人话困境映射到占星结构：
- 哪些宫位是核心舞台
- 哪些行星在表演
- 哪些宫主星要追踪
- 哪些行星对的相位最关键
- 是否需要额外分析模块

原则二：领域归属来自 IntentRouter（规则），LLM 不判领域。
原则三：LLM 只做"语言→占星概念"映射，不做占星推理。
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from foundation.logger import get_logger
from shared.enums import IntentDomain, Priority
from shared.models import Intent

from domain.astrology.knowledge.loader import domain_planet_roles

from .canonical import CanonicalIntent, canonicalize_intent
from .intent_profiles import (
    ConditionalTask,
    IntentProfile,
    ProfileTask,
    evaluate_conditional_tasks,
    get_base_tasks,
    load_profiles,
)

logger = get_logger("reasoning.intent.decomposer")

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

_VALID_PLANET_KEYS: frozenset[str] = frozenset({
    "sun", "moon", "mercury", "venus", "mars",
    "jupiter", "saturn", "uranus", "neptune", "pluto",
})
_VALID_HOUSE_RANGE = range(1, 13)

_MODULE_DESCRIPTIONS: dict[str, str] = {
    "CareerStrength": "职业结构强度：10R状态+援军+事业格局",
    "Timing": "时机窗口：法达大运/子限+行运+窗口综合",
    "Risk": "风险识别：变动风险/财务风险",
    "Opportunity": "机会评估：新机会/转型窗口",
    "Finance": "财务分析：收入结构/现金流",
    "Psychology": "心理状态：本命心理模式+当前压力",
    "PartnerTraits": "对象特征：金火月+5R/7R状态",
    "Wealth": "财运格局：2R/8R/11R+木星触达",
    "RelationshipSynastry": "合盘分析：二人星盘互动",
    "RelationshipStatus": "感情状态：5R×7R+金火月一致性",
    "MarriagePotential": "婚姻潜力：7R状态+金土相位+承诺能力",
    "Daily": "每日运势：当日行运扫描",
    "Health": "健康分析：1/6/12宫+火星/土星",
    "Emotion": "情绪分析：月亮+4/8/12宫情绪流动",
    "Family": "家庭分析：4宫+日月土家庭根基",
    "Learning": "学习分析：水星+3/9宫学习天赋",
}

# domain → planet_nature domain_signals key
# （v2 领域引擎：词汇已合一，星性信号键即领域名；daily 是跨域行运视图，无星性列）
_DOMAIN_PLANET_KEY: dict[IntentDomain, str | None] = {
    IntentDomain.CAREER: "career",
    IntentDomain.RELATIONSHIP: "relationship",
    IntentDomain.WEALTH: "wealth",
    IntentDomain.HEALTH: "health",
    IntentDomain.EMOTION: "emotion",
    IntentDomain.FAMILY: "family",
    IntentDomain.LEARNING: "learning",
    IntentDomain.GROWTH: "growth",
    IntentDomain.NETWORK: "network",
    IntentDomain.SELF: "self",
    IntentDomain.DAILY: None,  # 跨域行运视图，无独立星性信号
}

# domain → theme_map 相关主题
_DOMAIN_THEME_KEYS: dict[IntentDomain, list[str]] = {
    IntentDomain.CAREER: ["career_psychology"],
    IntentDomain.RELATIONSHIP: ["partner_traits", "relationship_status", "marriage_potential"],
    IntentDomain.WEALTH: ["wealth"],
    IntentDomain.HEALTH: ["health"],
    IntentDomain.EMOTION: ["emotion"],
    IntentDomain.FAMILY: ["family"],
    IntentDomain.LEARNING: ["learning"],
    IntentDomain.DAILY: [],
}

# LLM 系统提示词
_DECOMPOSE_SYSTEM = (
    "You are an astrology expert system. Your role is to map human-language "
    "dilemmas to astrological structures. You DO NOT interpret the chart — "
    "you only identify WHAT to look at, not what it means.\n\n"
    "Given a user's question and astrological reference knowledge, determine:\n"
    "- Which houses (1-12) are most relevant to the situation\n"
    "- Which planets are the key players\n"
    "- Which house lords (by house number) to examine\n"
    "- Which planet pairs (aspect relations) are most telling\n"
    "- Which analysis modules (from the fixed list) would add value\n\n"
    "Output ONLY valid JSON. No markdown fences, no text outside the JSON object."
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class AnalysisTask:
    """一个结构化的分析任务。"""

    module: str
    priority: Priority = Priority.MEDIUM
    params: dict = field(default_factory=dict)
    reasoning: str = ""


@dataclass
class DecomposedIntent:
    """LLM 富化后的意图：原始 Intent + 占星焦点映射 + 合并后的任务列表。"""

    intent: Intent

    # LLM 产出的占星焦点
    focus_houses: list[int] = field(default_factory=list)
    focus_planets: list[str] = field(default_factory=list)
    focus_house_lords: list[int] = field(default_factory=list)
    focus_aspect_pairs: list[list] = field(default_factory=list)

    # 任务
    base_tasks: list[AnalysisTask] = field(default_factory=list)
    conditional_tasks: list[AnalysisTask] = field(default_factory=list)
    llm_extra_tasks: list[AnalysisTask] = field(default_factory=list)
    merged_tasks: list[AnalysisTask] = field(default_factory=list)

    # 元数据
    focus_dimensions: list[str] = field(default_factory=list)
    llm_used: bool = False
    decomposition_reasoning: str = ""
    llm_latency_ms: float = 0.0
    canonical: CanonicalIntent | None = None

    # ---- 便利属性（委托给 Intent） ----

    @property
    def domain(self) -> IntentDomain:
        return self.intent.domain

    @property
    def subdomain(self) -> str:
        return self.intent.subdomain

    @property
    def raw_query(self) -> str:
        return self.intent.raw_query

    @property
    def requires_clarification(self) -> bool:
        return self.intent.requires_clarification

    @classmethod
    def wrap(
        cls,
        intent: Intent,
        base_tasks: list[AnalysisTask] | None = None,
        conditional_tasks: list[AnalysisTask] | None = None,
    ) -> "DecomposedIntent":
        """创建最小 DecomposedIntent（无 LLM，纯规则）。"""
        bt = list(base_tasks or [])
        ct = list(conditional_tasks or [])
        focus_houses: list[int] = []
        house_slot = intent.get_slot("focus_house")
        if house_slot is not None:
            try:
                house = int(house_slot.normalized_value)
            except (TypeError, ValueError):
                house = 0
            if house in _VALID_HOUSE_RANGE:
                focus_houses.append(house)

        focus_planets: list[str] = []
        planet_slot = intent.get_slot("focus_planet")
        if planet_slot is not None:
            planet = str(planet_slot.normalized_value or "")
            if planet in _VALID_PLANET_KEYS:
                focus_planets.append(planet)

        return cls(
            intent=intent,
            focus_houses=focus_houses,
            focus_planets=focus_planets,
            base_tasks=bt,
            conditional_tasks=ct,
            merged_tasks=bt + ct,
            llm_used=False,
            canonical=canonicalize_intent(intent),
        )


# ---------------------------------------------------------------------------
# IntentDecomposer
# ---------------------------------------------------------------------------


class IntentDecomposer:
    """LLM 深度意图拆解器。

    1. 从 intent_profiles.yaml 取 base_tasks（安全网）
    2. 关键词匹配 conditional_tasks
    3. 若 LLM 可用：构建 domain 过滤后的 prompt，调用 LLM，校验输出
    4. 合并：base ∪ conditional ∪ validated_llm
    """

    def __init__(
        self,
        llm_client: Any = None,
        registered_modules: set[str] | None = None,
        profiles_path: str | None = None,
    ):
        self._llm = llm_client
        self._registered_modules = registered_modules or set(_MODULE_DESCRIPTIONS)
        self._profiles = load_profiles(profiles_path)
        self._house_significations = self._load_yaml("house_significations.yaml", is_kb=True)
        self._planet_nature = self._load_yaml("planet_nature.yaml", is_kb=True)
        self._theme_map = self._load_yaml("rules/theme_map.yaml", is_kb=True)

    # -----------------------------------------------------------------
    # 公共入口
    # -----------------------------------------------------------------

    def decompose(self, intent: Intent) -> DecomposedIntent:
        """解析 Intent → DecomposedIntent。"""
        domain = intent.domain
        raw_query = intent.raw_query

        # 1. 必修模块（安全网）
        base = get_base_tasks(self._profiles, domain, intent.subdomain)

        # 2. 触发词条件模块
        conditional = evaluate_conditional_tasks(self._profiles, domain, raw_query)

        # 去重（base 优先）
        seen: set[str] = set()
        deduped: list[AnalysisTask] = []
        for t in base + conditional:
            if t.module not in seen:
                seen.add(t.module)
                deduped.append(t)

        result = DecomposedIntent.wrap(intent, base, conditional)
        result.merged_tasks = list(deduped)

        # 3. LLM 深度拆解（可选）
        if self._llm is not None and self._llm.available:
            try:
                llm_data = self._call_llm(intent)
                result = self._merge_llm(result, llm_data)
                result.llm_used = True
                result.decomposition_reasoning = llm_data.get("reasoning", "")
                result.llm_latency_ms = llm_data.get("_latency_ms", 0.0)
            except Exception as exc:
                logger.warning(
                    "LLM decomposition failed for '%s'…, using profiles: %s",
                    raw_query[:60], exc,
                )

        return result

    # -----------------------------------------------------------------
    # LLM 调用
    # -----------------------------------------------------------------

    def _call_llm(self, intent: Intent) -> dict:
        """调用 LLM，返回解析后的 JSON dict。"""
        start = time.monotonic()
        user_prompt = self._build_user_prompt(intent)
        raw = self._llm.complete(
            prompt=user_prompt, system=_DECOMPOSE_SYSTEM, temperature=0.0,
        )
        elapsed = (time.monotonic() - start) * 1000
        data = self._parse_json(raw)
        data["_latency_ms"] = elapsed
        return data

    def _build_user_prompt(self, intent: Intent) -> str:
        """构建 domain 过滤后的 user prompt。"""
        domain = intent.domain
        base = get_base_tasks(self._profiles, domain, intent.subdomain)
        base_names = [t.module for t in base]

        sections: list[str] = []
        sections.append(f"USER'S QUESTION: {intent.raw_query}")
        sections.append(f"DETECTED DOMAIN: {domain.value}")
        sections.append(f"DETECTED SUBDOMAIN: {intent.subdomain or 'default'}")
        sections.append("")
        sections.append(f"=== HOUSE REFERENCE (domain: {domain.value}) ===")
        sections.append(self._fmt_houses(domain))
        sections.append("")
        sections.append("=== PLANET DOMAIN SIGNALS ===")
        sections.append(self._fmt_planets(domain))
        sections.append("")
        sections.append("=== THEME RECIPES ===")
        sections.append(self._fmt_themes(domain))
        sections.append("")
        sections.append("=== AVAILABLE ANALYSIS MODULES ===")
        sections.append(self._fmt_modules())
        sections.append("")
        sections.append(f"=== BASE TASKS (always included) ===")
        sections.append(f"These run regardless: {base_names}")
        sections.append("Only suggest extra_tasks that add value beyond these.")
        sections.append("")
        sections.append("OUTPUT THIS EXACT JSON STRUCTURE:")
        sections.append(json.dumps({
            "focus_houses": [10, 6, 2],
            "focus_planets": ["sun", "saturn"],
            "focus_house_lords": [10, 2],
            "focus_aspect_pairs": [["sun", "saturn"]],
            "focus_dimensions": ["事业格局与情绪压力的星象根源"],
            "reasoning": "Brief explanation of the mapping",
            "extra_tasks": [
                {"module": "Emotion", "priority": "medium", "reasoning": "…"},
            ],
        }, ensure_ascii=False, indent=2))

        return "\n".join(sections)

    # -----------------------------------------------------------------
    # YAML 摘要格式化
    # -----------------------------------------------------------------

    def _fmt_houses(self, domain: IntentDomain) -> str:
        profile = self._profiles.get(domain.value)
        relevant = profile.core_houses if profile else [1, 10]
        significations = self._house_significations.get("house_significations", {})
        lines: list[str] = []
        for h in relevant:
            entries = significations.get(h) or significations.get(str(h)) or []
            if entries:
                snippets: list[str] = []
                route_terms: list[str] = []
                for entry in entries[:4]:
                    if not isinstance(entry, dict):
                        continue
                    word = entry.get("word", "")
                    domains = "/".join(entry.get("domains", [])[:3])
                    if word:
                        snippets.append(f"{word} [{domains}]")
                    for kw in entry.get("route_keywords", []) or []:
                        if kw and kw not in route_terms:
                            route_terms.append(str(kw))
                lines.append(f"H{h}: {'; '.join(snippets)}. 路由词: {', '.join(route_terms[:8])}")
                continue
        return "\n".join(lines)

    def _fmt_planets(self, domain: IntentDomain) -> str:
        dk = _DOMAIN_PLANET_KEY.get(domain)
        if dk is None:
            return "（daily 为跨域行运视图，无独立星性信号——直接看行运即可）"
        planets = self._planet_nature.get("planets", {})
        lines: list[str] = []
        for pk, pd in planets.items():
            signals = pd.get("domain_signals", {})
            role = signals.get(dk, "neutral")
            if role in ("core", "supporting"):
                verb = pd.get("core_verb", "")
                label = pd.get("label", pk)
                lines.append(f"{label} ({pk}): role={role}, verb='{verb}'")
        return "\n".join(lines)

    def _fmt_themes(self, domain: IntentDomain) -> str:
        keys = _DOMAIN_THEME_KEYS.get(domain, [])
        lines: list[str] = []
        for tk, td in self._theme_map.items():
            if tk in keys:
                label = td.get("label_zh", tk)
                houses = td.get("core_houses", [])
                domain_key = td.get("domain") or _DOMAIN_PLANET_KEY.get(domain)
                core, supporting = domain_planet_roles(self._planet_nature, domain_key)
                lords = td.get("house_lords", [])
                lines.append(
                    f"{label}: houses={houses}, domain={domain_key}, "
                    f"planets(core)={core}, planets(supporting)={supporting}, lords={lords}"
                )
        return "\n".join(lines) if lines else "No specific theme recipe for this domain."

    def _fmt_modules(self) -> str:
        return "\n".join(
            f"  - {name}: {desc}"
            for name, desc in sorted(_MODULE_DESCRIPTIONS.items())
        )

    # -----------------------------------------------------------------
    # JSON 解析与校验
    # -----------------------------------------------------------------

    @staticmethod
    def _parse_json(raw: str) -> dict:
        """从 LLM 文本提取 JSON。"""
        raw = raw.strip()
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if m:
            raw = m.group(1)
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        m2 = re.search(r"\{.*\}", raw, re.DOTALL)
        if m2:
            try:
                data = json.loads(m2.group(0))
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass
        raise ValueError(f"无法从 LLM 响应中提取 JSON: {raw[:200]}")

    def _merge_llm(
        self, decomposed: DecomposedIntent, llm_data: dict,
    ) -> DecomposedIntent:
        """校验 LLM 输出并合并到 DecomposedIntent。"""
        # 校验宫位
        houses = [
            h for h in llm_data.get("focus_houses", [])
            if isinstance(h, int) and h in _VALID_HOUSE_RANGE
        ]
        # 校验行星
        planets = [
            p for p in llm_data.get("focus_planets", [])
            if isinstance(p, str) and p in _VALID_PLANET_KEYS
        ]
        # 校验宫主星
        lords = [
            l for l in llm_data.get("focus_house_lords", [])
            if isinstance(l, int) and l in _VALID_HOUSE_RANGE
        ]
        # 校验行星对
        pairs: list[list] = []
        for pair in llm_data.get("focus_aspect_pairs", []):
            if (
                isinstance(pair, list) and len(pair) >= 2
                and all(isinstance(p, str) and p in _VALID_PLANET_KEYS for p in pair[:2])
            ):
                pairs.append(pair[:2])

        # 校验额外模块
        llm_tasks: list[AnalysisTask] = []
        for td in llm_data.get("extra_tasks", []):
            mod = td.get("module", "")
            if mod not in self._registered_modules:
                logger.debug("跳过 LLM 建议的未注册模块: %s", mod)
                continue
            try:
                prio = Priority(td.get("priority", "medium"))
            except ValueError:
                prio = Priority.MEDIUM
            llm_tasks.append(AnalysisTask(
                module=mod,
                priority=prio,
                params=td.get("params", {}),
                reasoning=td.get("reasoning", ""),
            ))

        # 合并：base ∪ conditional ∪ validated_llm（base 优先，不重复）
        existing = {t.module for t in decomposed.base_tasks}
        for t in decomposed.conditional_tasks:
            existing.add(t.module)
        merged = list(decomposed.base_tasks) + [
            t for t in decomposed.conditional_tasks
            if t.module not in {bt.module for bt in decomposed.base_tasks}
        ]
        for t in llm_tasks:
            if t.module not in existing:
                merged.append(t)
                existing.add(t.module)

        decomposed.focus_houses = houses
        decomposed.focus_planets = planets
        decomposed.focus_house_lords = lords
        decomposed.focus_aspect_pairs = pairs
        decomposed.focus_dimensions = llm_data.get("focus_dimensions", [])
        decomposed.llm_extra_tasks = llm_tasks
        decomposed.merged_tasks = merged
        return decomposed

    # -----------------------------------------------------------------
    # YAML 加载
    # -----------------------------------------------------------------

    @staticmethod
    def _load_yaml(rel_path: str, *, is_kb: bool = False) -> dict:
        """加载知识库 YAML 文件。"""
        if is_kb:
            base = Path(__file__).parent.parent.parent / "astrology" / "knowledge"
        else:
            base = Path(__file__).parent
        path = base / rel_path
        if not path.exists():
            logger.warning("YAML 文件不存在: %s", path)
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
