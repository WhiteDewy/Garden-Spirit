"""RuleEngine —— 解读文法引擎。

把"词典 + 宫位 arena"合成为带刺的解读（core_insight）。
每条解读都带 rule_id，可审计。极性/权重由相位性质等确定性规则判定，
LLM 永不参与（原则三）。

引擎不产结论，只产"解读事实"（THEME 类 Fact），流入 Evidence 层。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from foundation.logger import get_logger
from foundation.utils import new_id
from shared.enums import EvidencePolarity, FactCategory, Planet
from shared.models import Aspect, Chart, Fact

from domain.astrology.common import aspects_to, house_lord
from domain.astrology.knowledge.loader import KnowledgeBase, load_knowledge
from domain.astrology.evidence.confidence import ConfidenceEngine

logger = get_logger("astrology.evidence.rules")

# 相位性质 → 极性（由 aspects.yaml 的 nature 决定）
_PAIR_POLARITY = {
    "HARMONIOUS": EvidencePolarity.POSITIVE,
    "DYNAMIC": EvidencePolarity.NEGATIVE,
    "NEUTRAL": EvidencePolarity.NEUTRAL,
}


@dataclass
class Interpretation:
    """一条合成的解读。"""

    core_insight: str
    theme: str                  # 证据主题标签
    polarity: EvidencePolarity
    weight: float
    confidence: float
    rule_id: str                # 可审计：如 planet_pair:mars_moon:dynamic
    supporting: list[str] = field(default_factory=list)

    def to_fact(self, chart: Chart) -> Fact:
        return Fact(
            id=new_id("fact"),
            category=FactCategory.THEME,
            chart_id=chart.id,
            description=self.core_insight,
            extracted_at=datetime.now(timezone.utc),
            payload={
                "theme": self.theme,
                "polarity": self.polarity.value,
                "weight": self.weight,
                "confidence": self.confidence,
                "module": "rule_engine",
                "rule_id": self.rule_id,
                "supporting": self.supporting,
            },
        )


class RuleEngine:
    """合成解读引擎。"""

    def __init__(self, kb: KnowledgeBase | None = None, confidence: ConfidenceEngine | None = None):
        self._kb = kb or load_knowledge()
        self._confidence = confidence or ConfidenceEngine()

    # ------------------------------------------------------------------
    # 三条文法规则
    # ------------------------------------------------------------------

    def interpret_planet_in_house(
        self, chart: Chart, planet: Planet, theme_id: str = "general"
    ) -> list[Interpretation]:
        """行星落宫 → 解读。"""
        if planet not in chart.planets:
            return []
        cp = chart.planets[planet]
        house = cp.house.house
        key = f"{planet.value}_{house}"
        entry = self._kb.planet_in_house_rules.get(key)

        if entry:
            core = entry["base"]
            rule_id = f"planet_in_house:{key}"
            confidence = 0.8
        else:
            # fallback：从行星/宫位关键词合成（诚实但更泛）
            p_info = self._kb.planet(planet)
            h_info = self._kb.house(house)
            p_kw = p_info.significations_zh[0] if p_info.significations_zh else "能量"
            h_kw = h_info.keywords_zh[0] if h_info.keywords_zh else "领域"
            tpl = self._kb.planet_in_house_rules.get("_fallback", {}).get(
                "base", "{planet_zh}落在{house_zh}——{planet_keyword}的能量投射在{house_keyword}领域"
            )
            core = tpl.format(
                planet_zh=p_info.name_zh,
                house_zh=h_info.name_zh,
                planet_keyword=p_kw,
                house_keyword=h_kw,
            )
            rule_id = f"planet_in_house:fallback:{planet.value}:{house}"
            confidence = 0.55

        theme = self._assign_theme(chart, planet, theme_id)
        return [
            Interpretation(
                core_insight=core,
                theme=theme,
                polarity=EvidencePolarity.NEUTRAL,  # 落宫是描述，无吉凶
                weight=0.8,
                confidence=confidence,
                rule_id=rule_id,
                supporting=[f"{self._kb.planet(planet).name_zh}落{house}宫"],
            )
        ]

    def interpret_planet_pair(
        self,
        chart: Chart,
        a: Planet,
        b: Planet,
        theme_id: str = "general",
        pair_weight: float = 1.0,
    ) -> list[Interpretation]:
        """行星对相位 → 解读（含落宫 arena 注入）。

        pair_weight: 主题专属权重（theme_map aspect_pairs 第三元素），
            用于放大核心信号（如倦怠的月土张力）。
        """
        if a not in chart.planets or b not in chart.planets:
            return []

        key = "_".join(sorted((a.value, b.value)))
        entry = self._kb.planet_pairs.get(key)
        # 未录入的行星对：用 fallback 模板合成通用描述（不静默丢弃）
        using_fallback = entry is None
        if using_fallback:
            entry = self._kb.planet_pairs.get("_fallback", {})

        results: list[Interpretation] = []
        for aspect in aspects_to(chart, a, {b}):
            info = self._kb.aspects.get(aspect.aspect_type)
            if info is None:
                continue
            nature = info.nature
            base = entry.get("base", "")
            sentence = entry.get("harmonious" if nature == "HARMONIOUS" else (
                "dynamic" if nature == "DYNAMIC" else "base"), base)

            # fallback：用行星关键词填充模板
            if using_fallback:
                pa = self._kb.planet(a)
                pb = self._kb.planet(b)
                sentence = sentence.format(
                    planet_a_zh=pa.name_zh,
                    planet_b_zh=pb.name_zh,
                    planet_a_keyword=pa.significations_zh[0] if pa.significations_zh else "能量",
                    planet_b_keyword=pb.significations_zh[0] if pb.significations_zh else "能量",
                )

            # 落宫 arena 注入
            arena_a = self._arena_desc(chart, a)
            arena_b = self._arena_desc(chart, b)
            core = f"{sentence}。这份联结发生在{arena_a}与{arena_b}之间"

            polarity = _PAIR_POLARITY.get(nature, EvidencePolarity.NEUTRAL)
            weight = info.weight_multiplier * pair_weight
            if aspect.application.value == "applying":
                weight *= 1.2
            elif aspect.application.value == "separating":
                weight *= 0.8
            # 紧相位置信度更高；fallback 置信度打折（无人工校验）
            base_conf = max(0.5, min(0.9, 0.9 - aspect.orb * 0.05))
            confidence = base_conf * 0.7 if using_fallback else base_conf

            theme = self._assign_theme(chart, a if a in (Planet.VENUS, Planet.MARS, Planet.MOON) else b, theme_id)
            rule_id_suffix = "fallback" if using_fallback else nature.lower()
            results.append(
                Interpretation(
                    core_insight=core,
                    theme=theme,
                    polarity=polarity,
                    weight=weight,
                    confidence=confidence,
                    rule_id=f"planet_pair:{key}:{rule_id_suffix}",
                    supporting=[
                        f"{self._kb.planet(a).name_zh}{aspect.aspect_type.value}{self._kb.planet(b).name_zh}",
                        f"{a.value}在{chart.planets[a].house.house}宫",
                        f"{b.value}在{chart.planets[b].house.house}宫",
                    ],
                )
            )
        return results

    def interpret_house_lord(
        self, chart: Chart, house_num: int, theme_id: str = "general"
    ) -> list[Interpretation]:
        """宫主星落宫 → 解读（7宫主=伴侣象征，最常用）。"""
        lord = house_lord(chart, self._kb, house_num)
        if lord is None or lord not in chart.planets:
            return []
        lord_info = self._kb.planet(lord)
        target_house = chart.planets[lord].house.house
        key = f"{house_num}_{target_house}"
        entry = self._kb.house_lord_rules.get(key)

        if entry:
            core = entry["base"]
            rule_id = f"house_lord:{key}"
            confidence = 0.8
        else:
            src_house = self._kb.house(house_num)
            tgt_house = self._kb.house(target_house)
            tpl = self._kb.house_lord_rules.get("_fallback", {}).get(
                "base", "{lord_zh}（{house_zh}的守护星）落在{target_house_zh}"
            )
            core = tpl.format(
                lord_zh=lord_info.name_zh,
                house_zh=src_house.name_zh,
                target_house_zh=tgt_house.name_zh,
                house_keyword=src_house.keywords_zh[0] if src_house.keywords_zh else "",
                target_house_keyword=tgt_house.keywords_zh[0] if tgt_house.keywords_zh else "",
            )
            rule_id = f"house_lord:fallback:{house_num}:{target_house}"
            confidence = 0.55

        theme = self._assign_theme(chart, lord, theme_id)
        return [
            Interpretation(
                core_insight=core,
                theme=theme,
                polarity=EvidencePolarity.NEUTRAL,  # 描述性
                weight=1.0,
                confidence=confidence,
                rule_id=rule_id,
                supporting=[f"{house_num}宫主{lord_info.name_zh}落{target_house}宫"],
            )
        ]

    # ------------------------------------------------------------------
    # 主题编排
    # ------------------------------------------------------------------

    def run_theme(self, chart: Chart, theme_id: str) -> list[Fact]:
        """按 theme_map 配方执行一个主题，产出解读事实。"""
        recipe = self._kb.theme_map.get(theme_id)
        if not recipe:
            logger.warning("未知主题: %s", theme_id)
            return []

        # 气质/模式主题：强制描述性框架（不判吉凶）
        descriptive = bool(recipe.get("descriptive", False))

        facts: list[Fact] = []
        rules_cfg = recipe.get("rules", [])
        core_planets = recipe.get("core_planets", [])
        core_houses = recipe.get("core_houses", [])
        # 落宫解读过滤：只保留行星落在核心宫位的解读（避免无关宫性格描述噪音）
        house_filter = bool(recipe.get("house_filter", False))
        core_house_set = {int(h) for h in core_houses}

        if "planet_in_house" in rules_cfg:
            for planet in core_planets:
                p = Planet(planet)
                if (
                    house_filter
                    and p in chart.planets
                    and chart.planets[p].house.house not in core_house_set
                ):
                    continue
                for interp in self.interpret_planet_in_house(chart, p, theme_id):
                    facts.append(interp.to_fact(chart))

        if "planet_pair" in rules_cfg:
            for pair in recipe.get("aspect_pairs", []):
                a, b = Planet(pair[0]), Planet(pair[1])
                pair_weight = float(pair[2]) if len(pair) > 2 else 1.0
                for interp in self.interpret_planet_pair(chart, a, b, theme_id, pair_weight):
                    facts.append(interp.to_fact(chart))

        if "house_lord" in rules_cfg:
            for h in recipe.get("house_lords", []):
                for interp in self.interpret_house_lord(chart, int(h), theme_id):
                    facts.append(interp.to_fact(chart))

        # 标记描述性主题（结论层据此强制"倾向描述"而非吉凶判断）
        for f in facts:
            f.payload["descriptive"] = descriptive

        logger.info("主题[%s] 产出 %d 条解读", theme_id, len(facts))
        return facts

    # ------------------------------------------------------------------

    def _arena_desc(self, chart: Chart, planet: Planet) -> str:
        """某行星落宫的舞台描述。"""
        name = self._kb.planet(planet).name_zh
        if planet not in chart.planets:
            return f"{name}的能量"
        cp = chart.planets[planet]
        return f"{name}落在{cp.house.house}宫"

    def _assign_theme(self, chart: Chart, planet: Planet, theme_id: str) -> str:
        """把解读归到 theme_map 的 evidence_theme 桶。"""
        recipe = self._kb.theme_map.get(theme_id, {})
        evidence_themes = recipe.get("evidence_themes", {})
        if not evidence_themes:
            return theme_id
        cp = chart.planets.get(planet)
        house = cp.house.house if cp else None
        for bucket, spec in evidence_themes.items():
            houses = spec.get("houses", [])
            planets = spec.get("planets", [])
            if house in houses or planet.value in planets:
                return bucket
        return theme_id
