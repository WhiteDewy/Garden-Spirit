"""Consult Resolver —— 咨询模板引擎。

三层规则驱动，从用户问题自动推导完整的咨询结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any
import re

import yaml

from foundation.logger import get_logger
from shared.constants import DOMICILE_RULER_TRADITIONAL, PLANETS_IN_ORDER
from shared.enums import IntentDomain, Planet
from shared.models import Chart
from shared.models.intent import Intent

from domain.astrology.common import DIGNITY_ZH, assess_planet
from domain.astrology.interpretation.synapsis import ConnectionClassifier
from domain.astrology.knowledge.loader import domain_planet_roles, load_knowledge

logger = get_logger("reasoning.consult")

_RULES_DIR = Path(__file__).parent.parent.parent / "astrology" / "knowledge"
_RULES_SUBDIR = _RULES_DIR / "rules"
_INTENT_PROFILES_PATH = Path(__file__).parent.parent / "intent" / "intent_profiles.yaml"


# =============================================================================
# 数据类
# =============================================================================


@dataclass
class TopicPlan:
    """一个话题的完整解析结果（旧兼容层）。"""

    topic_id: str                          # "marriage" / "dating" / "career" ...
    topic_label: str                       # "婚姻" / "桃花" / "事业" ...
    primary_house: int                     # 主宫
    supplementary_houses: list[int] = field(default_factory=list)  # 辅宫
    primary_planets: list[str] = field(default_factory=list)       # 核心星（planet key）
    supporting_planets: list[str] = field(default_factory=list)    # 辅助星
    cross_readings: list[dict] = field(default_factory=list)       # 匹配的交叉判断
    scenarios: list[dict] = field(default_factory=list)            # 匹配的场景映射
    output_structure: dict | None = None   # 输出结构模板
    guardrails: list[str] = field(default_factory=list)            # 护栏规则

    def to_dict(self) -> dict:
        return {
            "topic_id": self.topic_id,
            "topic_label": self.topic_label,
            "primary_house": self.primary_house,
            "supplementary_houses": self.supplementary_houses,
            "primary_planets": self.primary_planets,
            "supporting_planets": self.supporting_planets,
            "cross_readings": self.cross_readings,
            "output_structure": self.output_structure,
            "guardrails": self.guardrails,
        }


@dataclass
class ConsultCallPlan:
    """体系二咨询调用主干：领域/宫位/切片 → 承载者集合。

    这是定位层向 Domain 证据链传递的 canonical 结构。它只描述「看哪里、读哪些
    承载者、按什么话题节奏转述」，不生成占星结论；结论仍由 Domain 层产出，LLM 只
    使用这里的 prompt payload 调整叙事组织。
    """

    domain: str
    domain_label: str
    focus_house: int
    topic_id: str
    topic_label: str
    focus_slice: str | None = None
    core_houses: list[int] = field(default_factory=list)
    supplementary_houses: list[int] = field(default_factory=list)
    natural_significators: list[str] = field(default_factory=list)
    supporting_planets: list[str] = field(default_factory=list)
    house_lords: list[int] = field(default_factory=list)          # 仍表示“要追踪哪几宫的宫主”
    house_lord_planets: list[str] = field(default_factory=list)   # 实盘宫头星座 → 传统七曜宫主
    house_lord_placements: list[dict] = field(default_factory=list)  # 7R=venus in H9 等可审计事实
    house_occupants: list[str] = field(default_factory=list)      # 实盘落入 core_houses 的行星
    aspect_pairs: list[list] = field(default_factory=list)
    cross_readings: list[dict] = field(default_factory=list)
    scenarios: list[dict] = field(default_factory=list)
    output_structure: dict | None = None
    guardrails: list[str] = field(default_factory=list)
    source: str = "consult_resolver_v2"

    @property
    def primary_house(self) -> int:
        """旧 TopicPlan 字段别名，供迁移期间兼容。"""
        return self.focus_house

    @property
    def primary_planets(self) -> list[str]:
        """旧 TopicPlan 字段别名：先天征象星作为当前 natural carriers。"""
        return self.natural_significators

    def to_topic_plan(self) -> TopicPlan:
        """降级为旧 TopicPlan，供 response.py 与存量测试迁移期继续使用。"""
        return TopicPlan(
            topic_id=self.topic_id,
            topic_label=self.topic_label,
            primary_house=self.focus_house,
            supplementary_houses=self.supplementary_houses,
            primary_planets=self.natural_significators,
            supporting_planets=self.supporting_planets,
            cross_readings=self.cross_readings,
            scenarios=self.scenarios,
            output_structure=self.output_structure,
            guardrails=self.guardrails,
        )

    def to_dict(self) -> dict:
        """序列化为 canonical 字段，并保留旧 prompt 注入需要的键。"""
        return {
            # canonical trunk
            "domain": self.domain,
            "domain_label": self.domain_label,
            "focus_house": self.focus_house,
            "focus_slice": self.focus_slice,
            "core_houses": self.core_houses,
            "natural_significators": self.natural_significators,
            "supporting_planets": self.supporting_planets,
            "house_lords": self.house_lords,
            "house_lord_planets": self.house_lord_planets,
            "house_lord_placements": self.house_lord_placements,
            "house_occupants": self.house_occupants,
            "aspect_pairs": self.aspect_pairs,
            "source": self.source,
            # legacy-compatible prompt payload
            "topic_id": self.topic_id,
            "topic_label": self.topic_label,
            "primary_house": self.focus_house,
            "supplementary_houses": self.supplementary_houses,
            "primary_planets": self.natural_significators,
            "cross_readings": self.cross_readings,
            "scenarios": self.scenarios,
            "output_structure": self.output_structure,
            "guardrails": self.guardrails,
        }


# =============================================================================
# Resolver
# =============================================================================


class ConsultResolver:
    """从用户问题 + 星盘数据 → 咨询结构。"""

    def __init__(self, kb=None):
        self._houses = self._load_yaml("houses.yaml")
        self._house_significations = self._load_yaml("house_significations.yaml")
        self._house_derived = self._load_yaml("house_derived.yaml")
        self._planet_nature = self._load_yaml("planet_nature.yaml")
        self._intent_profiles = self._load_intent_profiles()
        self._natal_comp = self._load_rules("natal_composition.yaml")
        self._timing_rules = self._load_rules("timing_rules.yaml")
        self._kb = kb  # KnowledgeBase reference（可选，用于查 lordship 等）

    # -----------------------------------------------------------------
    # 话题解析
    # -----------------------------------------------------------------

    def resolve_topic(self, question: str) -> TopicPlan:
        """从用户问题文字 → TopicPlan（兼容包装）。"""
        return self.resolve_call_plan(question).to_topic_plan()

    def resolve_call_plan(
        self,
        question: str | Intent,
        intent: Intent | None = None,
        chart: Chart | None = None,
    ) -> ConsultCallPlan:
        """从用户问题 / Intent → ConsultCallPlan 主干。

        Wave 1 先保持旧关键词资产作为命中层，同时把结果提升为体系二形态：
        domain + focus_house/focus_slice + 宫主/先天征象星/相位对。后续迁移只需替换
        这里的定位来源，不再让外部调用旧 TopicPlan。

        chart 存在时只补充可审计的实盘承载者（实际宫主星、宫主落宫、宫内星），
        不生成占星结论；结论仍由 Domain 层产出。
        """
        if isinstance(question, Intent):
            intent = question
            raw_question = intent.raw_query
        else:
            raw_question = question

        # 1. 关键词匹配 → 聚焦宫位（体系二语义场为唯一定位来源）
        focus_house = self._focus_house_from_intent(intent) or self._match_primary_house(raw_question)
        house_label = self._house_label(focus_house)

        # 2. 话题与领域：Intent 优先，旧 topic_id 兜底
        topic_id = self._infer_topic_id(focus_house, raw_question)
        domain = self._domain_for_topic(topic_id, intent)
        profile = self._intent_profile(domain)

        # 3. 体系二承载者集合（宫位/宫主/先天征象星/相位对）
        core_houses = self._as_int_list(profile.get("core_houses")) or [focus_house]
        supplementary = self._resolve_supplementary(focus_house, raw_question)
        house_lords = self._as_int_list(profile.get("house_lords")) or [focus_house]
        natural_significators, supporting_planets = self._resolve_planets(domain)
        aspect_pairs = profile.get("aspect_pairs", []) or []
        house_lord_planets, house_lord_placements, house_occupants = self._resolve_chart_carriers(
            chart=chart,
            house_lords=house_lords,
            core_houses=core_houses,
            focus_house=focus_house,
        )

        # 4. 旧 prompt payload 保持原样，确保 LLM 只拿叙事结构不改结论
        cross_readings = self._match_cross_readings(topic_id, focus_house, supplementary)
        scenarios = self._match_scenarios(
            topic_id,
            chart=chart,
            house_lords=house_lords,
            house_lord_placements=house_lord_placements,
        )
        output_structure = self._natal_comp.get("output_structures", {}).get(topic_id)
        guardrails = self._format_guardrails(self._natal_comp.get("guardrails", []))

        return ConsultCallPlan(
            domain=domain,
            domain_label=profile.get("label_zh", house_label or domain),
            focus_house=focus_house,
            focus_slice=intent.focus_slice if intent else None,
            topic_id=topic_id,
            topic_label=house_label or str(focus_house),
            core_houses=core_houses,
            supplementary_houses=supplementary,
            natural_significators=natural_significators,
            supporting_planets=supporting_planets,
            house_lords=house_lords,
            house_lord_planets=house_lord_planets,
            house_lord_placements=house_lord_placements,
            house_occupants=house_occupants,
            aspect_pairs=aspect_pairs,
            cross_readings=cross_readings,
            scenarios=scenarios,
            output_structure=output_structure,
            guardrails=guardrails,
        )

    def _focus_house_from_intent(self, intent: Intent | None) -> int | None:
        """Intent 槽位中的 focus_house 是规则层确定性结果，优先于关键词。"""
        if intent is None:
            return None
        slot = intent.get_slot("focus_house")
        if slot is None:
            return None
        try:
            house = int(slot.normalized_value)
        except (TypeError, ValueError):
            return None
        return house if 1 <= house <= 12 else None

    def _house_label(self, house: int) -> str:
        """宫位展示名：体系二语义场优先，基础宫位定义兜底。"""
        entries = self._house_significations.get("house_significations", {})
        house_entries = entries.get(house) or entries.get(str(house)) or []
        for entry in house_entries:
            if isinstance(entry, dict) and entry.get("word"):
                return str(entry["word"])

        house_info = self._houses.get(house) or self._houses.get(str(house)) or {}
        name = house_info.get("name", {}) if isinstance(house_info, dict) else {}
        if isinstance(name, dict) and name.get("zh"):
            return str(name["zh"])
        return f"H{house}"

    def _domain_for_topic(self, topic_id: str, intent: Intent | None = None) -> str:
        """话题 → 11 域。Intent 的 Domain 判定优先，旧 topic_id 仅兜底。"""
        if intent is not None and intent.domain != IntentDomain.DAILY:
            return intent.domain.value

        topic_to_domain = {
            "marriage": "relationship",
            "dating": "relationship",
            "career": "career",
            "career_change": "career",
            "job_skill": "career",
            "boss_colleague": "career",
            "wealth": "wealth",
            "health": "health",
            "study": "learning",
            "advanced_study": "learning",
            "family": "family",
            "villain": "relationship",
            "talent": "self",
        }
        return topic_to_domain.get(topic_id, "career")

    def _intent_profile(self, domain: str) -> dict:
        """读取 intent_profiles.yaml 中的体系二领域配方。"""
        return self._intent_profiles.get(domain, {}) or {}

    @staticmethod
    def _as_int_list(value: Any) -> list[int]:
        result: list[int] = []
        if not isinstance(value, list):
            return result
        for item in value:
            try:
                result.append(int(item))
            except (TypeError, ValueError):
                continue
        return result

    @staticmethod
    def _as_str_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]

    def _match_primary_house(self, question: str) -> int:
        """关键词匹配 → 主宫编号（体系二语义场唯一来源，无命中默认 H1）。"""
        best_house, best_score = self._score_house_significations(question)
        if best_score > 0:
            return best_house
        return 1

    def _score_house_significations(self, question: str) -> tuple[int, int]:
        """从 house_significations.yaml 的 route_keywords / word / resonance 匹配宫位。"""
        table = self._house_significations.get("house_significations", {})
        best_house = 1
        best_score = 0

        for h_key, entries in table.items():
            try:
                h_num = int(h_key)
            except (TypeError, ValueError):
                continue
            if not isinstance(entries, list):
                continue

            score = 0
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                for kw in entry.get("route_keywords", []) or []:
                    if kw and kw in question:
                        score += 3
                for kw in entry.get("route_secondary", []) or []:
                    if kw and kw in question:
                        score += 1
                word = entry.get("word", "")
                if word:
                    for term in str(word).replace("/", " ").split():
                        if term and term in question:
                            score += 2
                for kw in entry.get("resonance", []) or []:
                    if kw and kw in question:
                        score += 1

            if score > best_score:
                best_score = score
                best_house = h_num

        return best_house, best_score

    def _resolve_supplementary(self, primary_house: int, question: str) -> list[int]:
        """从主宫与问题语境确定辅宫。"""
        supplementary: list[int] = []

        # 固定辅宫映射（可以根据话题扩展）
        fixed_supp: dict[int, list[int]] = {
            7: [5, 1],    # 婚姻 → 恋爱(5)、自我(1)
            5: [7, 1],    # 恋爱 → 婚姻(7)、自我(1)
            10: [6, 2],   # 事业 → 工作(6)、财运(2)
            2: [8, 11],   # 财运 → 偏财(8)、进账(11)
            6: [10],      # 工作 → 事业(10)
            12: [7, 6],   # 小人 → 对手(7)、日常(6)
            9: [3],       # 深造 → 学习(3)
            3: [9],       # 学习 → 深造(9)
            1: [10, 7],   # 自我 → 事业(10)、伴侣(7)
            8: [2],       # 偏财 → 正财(2)
            11: [2, 7],   # 社群 → 财运(2)、合作(7)
            4: [10],      # 家庭 → 事业(10)
        }

        supplementary = fixed_supp.get(primary_house, [])
        return supplementary

    def _infer_topic_id(self, primary_house: int, question: str) -> str:
        """从主宫 + 问题关键词 → topic_id。"""
        # 关键词覆盖（更精细的话题区分）
        topic_overrides = {
            "换工作": "career_change",
            "跳槽": "career_change",
            "辞职": "career_change",
            "脱单": "dating",
            "谈对象": "dating",
            "谈恋爱": "dating",
            "桃花": "dating",
            "结婚": "marriage",
            "嫁": "marriage",
            "娶": "marriage",
            "小人": "villain",
            "深造": "advanced_study",
            "考研": "advanced_study",
            "留学": "advanced_study",
            "技能": "job_skill",
            "老板": "boss_colleague",
            "同事": "boss_colleague",
            "上级": "boss_colleague",
            "兴趣": "talent",
            "天赋": "talent",
            "才华": "talent",
            "健康": "health",
            "生病": "health",
            "身体": "health",
            "体检": "health",
        }

        for kw, topic_id in topic_overrides.items():
            if kw in question:
                return topic_id

        # 默认映射
        house_to_topic = {
            7: "marriage",
            5: "dating",
            10: "career",
            2: "wealth",
            6: "job_skill",
            12: "villain",
            9: "advanced_study",
            3: "study",
            1: "career",       # 问"我是谁/我适合做什么" → 事业方向
            8: "wealth",
            11: "wealth",
            4: "family",
        }
        return house_to_topic.get(primary_house, "career")

    def _resolve_planets(self, domain: str) -> tuple[list[str], list[str]]:
        """从 canonical domain_signals 派生核心星 + 辅助星。"""
        return domain_planet_roles(self._planet_nature, domain)

    def _resolve_chart_carriers(
        self,
        *,
        chart: Chart | None,
        house_lords: list[int],
        core_houses: list[int],
        focus_house: int,
    ) -> tuple[list[str], list[dict], list[str]]:
        """从实盘派生承载者：实际宫主星、宫主落宫、核心宫内星。

        静态 YAML 只负责语义定位；真正的“7R/10R 是谁”由本命盘宫头星座决定。
        宫主采用传统七曜守护，避免三王星成为宫主星并与互溶/接纳逻辑打架。
        """
        if chart is None:
            return [], [], []

        lord_planets: list[str] = []
        lord_placements: list[dict] = []
        seen_placements: set[tuple[int, str]] = set()
        for house in house_lords:
            cusp = chart.house_cusps.get(house)
            if cusp is None:
                continue
            lord = DOMICILE_RULER_TRADITIONAL.get(cusp.sign)
            if lord is None:
                continue
            if lord.value not in lord_planets:
                lord_planets.append(lord.value)

            placement = chart.planets.get(lord)
            item = {
                "house": house,
                "cusp_sign": cusp.sign.value,
                "lord": lord.value,
            }
            if placement is not None:
                item["lord_house"] = placement.house.house
                item["lord_sign"] = placement.sign.sign.value
            key = (house, lord.value)
            if key not in seen_placements:
                lord_placements.append(item)
                seen_placements.add(key)

        houses_to_scan = self._unique_ints([focus_house, *core_houses])
        occupants: list[str] = []
        for planet in PLANETS_IN_ORDER:
            placement = chart.planets.get(planet)
            if placement is not None and placement.house.house in houses_to_scan:
                occupants.append(planet.value)

        return lord_planets, lord_placements, occupants

    @staticmethod
    def _unique_ints(values: list[int]) -> list[int]:
        seen: set[int] = set()
        result: list[int] = []
        for value in values:
            if value not in seen:
                result.append(value)
                seen.add(value)
        return result

    # -----------------------------------------------------------------
    # 交叉判断匹配
    # -----------------------------------------------------------------

    def _match_cross_readings(self, topic_id: str, primary_house: int, supplementary: list[int]) -> list[dict]:
        """匹配适用于当前话题的交叉判断模板。"""
        cross_templates = self._natal_comp.get("cross_readings", {})
        matched: list[dict] = []

        for template_name, template in cross_templates.items():
            applies = template.get("applies_to", [])
            # 检查是否适用于当前话题
            applicable = False
            for entry in applies:
                if isinstance(entry, dict):
                    if topic_id in entry.get("topics", []):
                        applicable = True
                        break
                elif entry == "all":
                    applicable = True
                    break

            if applicable:
                matched.append({
                    "name": template_name,
                    "check": template.get("check", ""),
                    "variants": template.get("variants", {}),
                    "verdict_connected": template.get("verdict_connected", ""),
                    "verdict_disconnected": template.get("verdict_disconnected", ""),
                })

        return matched

    # -----------------------------------------------------------------
    # 场景映射匹配
    # -----------------------------------------------------------------

    def _match_scenarios(
        self,
        topic_id: str,
        *,
        chart: Chart | None = None,
        house_lords: list[int] | None = None,
        house_lord_placements: list[dict] | None = None,
    ) -> list[dict]:
        """匹配适用于当前话题的场景映射。

        无 chart 时保留 YAML 模板，作为旧 prompt 兼容层；有 chart 时只输出真实命中的
        topic scenarios，并把帮手星/受克状态作为可审计 payload 带出去。
        """
        scenario_maps = self._natal_comp.get("scenario_maps", {})
        matched: list[dict] = []

        # 通用场景（lord_angularity）仍是模板层，等待后续阶段逐条图上化。
        general = scenario_maps.get("lord_angularity", {})
        if general:
            matched.append({"type": "general", "rules": general})

        topic_scenario_key = f"{topic_id}_scenarios"
        topic_scenarios = scenario_maps.get(topic_scenario_key, [])
        for s in topic_scenarios:
            base = {"type": "topic", "condition": s.get("condition", ""), "say": s.get("say", "")}
            if chart is None:
                matched.append(base)
                continue

            evaluated = self._evaluate_topic_scenario(
                base,
                chart=chart,
                house_lords=house_lords or [],
                house_lord_placements=house_lord_placements or [],
            )
            if evaluated is not None:
                matched.append(evaluated)

        return matched

    def _evaluate_topic_scenario(
        self,
        scenario: dict,
        *,
        chart: Chart,
        house_lords: list[int],
        house_lord_placements: list[dict],
    ) -> dict | None:
        """把 YAML condition 落到真实 Chart 上；暂只实现 Phase 4 可审计帮手链。"""
        condition = str(scenario.get("condition", ""))
        lord_match = re.search(r"(\d{1,2})R", condition)
        if not lord_match:
            return None
        target_house = int(lord_match.group(1))
        if target_house not in house_lords:
            return None
        target_planet = self._scenario_lord_planet(chart, target_house)
        if target_planet is None or target_planet not in chart.planets:
            return None

        kb = self._kb_or_load()
        classifier = ConnectionClassifier(kb)
        assessment = assess_planet(chart, kb, target_planet, classifier=classifier)
        allies = classifier.ally_timeline(chart, target_planet)
        has_ally = bool(allies)
        debilitated = assessment.essential_neg > 0
        afflicted = assessment.relational_neg > 0
        placement = self._scenario_lord_placement(house_lord_placements, target_house, target_planet)

        matched = self._condition_matches(
            condition,
            target_planet=target_planet,
            debilitated=debilitated,
            afflicted=afflicted,
            has_ally=has_ally,
            lord_house=placement.get("lord_house") if placement else None,
        )
        if not matched:
            return None

        payload = {
            **scenario,
            "matched": True,
            "target_house": target_house,
            "target_lord": target_planet.value,
            "target_planet": target_planet.value,
            "target_planet_name": kb.planet(target_planet).name_zh,
            "essential_neg": assessment.essential_neg,
            "relational_neg": assessment.relational_neg,
            "essential_evidence": list(assessment.essential_ev),
            "relational_evidence": list(assessment.relational_ev),
        }
        if placement:
            payload["target_lord_placement"] = placement
        if allies:
            ally = allies[0]
            payload.update({
                "ally_planet": ally.helper.value,
                "ally_name": kb.planet(ally.helper).name_zh,
                "ally_kind": ally.kind,
                "ally_strength": ally.strength,
                "ally_dignity": ally.dignity_type.value,
                "ally_dignity_label": DIGNITY_ZH.get(ally.dignity_type, ally.dignity_type.value),
                "ally_aspect": ally.aspect_type,
                "ally_aspect_nature": ally.aspect_nature,
                "ally_detail": ally.detail,
                "ally_domain": self._ally_domain_label(chart, ally.helper),
                "ally_timeline": [self._ally_payload(chart, a) for a in allies],
            })
        payload["say"] = self._fill_scenario_say(str(payload.get("say", "")), payload)
        return payload

    def _condition_matches(
        self,
        condition: str,
        *,
        target_planet: Planet,
        debilitated: bool,
        afflicted: bool,
        has_ally: bool,
        lord_house: int | None,
    ) -> bool:
        """支持 scenario_maps 当前已声明且可由 Domain facts 安全判断的条件片段。"""
        if re.search(r"\bno_ally\b", condition) and has_ally:
            return False
        if re.search(r"\b(has_ally|ally_timeline_exists)\b", condition) and not has_ally:
            return False
        if "debilitated" in condition and not debilitated:
            return False
        if "afflicted" in condition and not afflicted:
            return False
        in_house = re.search(r"\b\d{1,2}R in (\d{1,2})\b", condition)
        if in_house and lord_house != int(in_house.group(1)):
            return False
        if "in cadent" in condition and lord_house not in {3, 6, 9, 12}:
            return False
        if "jupiter_mutual" in condition and target_planet != Planet.JUPITER:
            return False
        if "dignified" in condition:
            return False
        if "connected_to" in condition or "not_connected_to" in condition:
            return False
        if "strong" in condition or "weak" in condition:
            return False
        return any(token in condition for token in ("has_ally", "no_ally", "ally_timeline_exists"))

    def _scenario_lord_planet(self, chart: Chart, house: int) -> Planet | None:
        cusp = chart.house_cusps.get(house)
        if cusp is None:
            return None
        return DOMICILE_RULER_TRADITIONAL.get(cusp.sign)

    @staticmethod
    def _scenario_lord_placement(
        house_lord_placements: list[dict],
        house: int,
        planet: Planet,
    ) -> dict | None:
        for item in house_lord_placements:
            if item.get("house") == house and item.get("lord") == planet.value:
                return item
        return None

    def _ally_payload(self, chart: Chart, ally) -> dict:
        kb = self._kb_or_load()
        return {
            "target": ally.target.value,
            "helper": ally.helper.value,
            "helper_name": kb.planet(ally.helper).name_zh,
            "kind": ally.kind,
            "strength": ally.strength,
            "dignity": ally.dignity_type.value,
            "aspect": ally.aspect_type,
            "aspect_nature": ally.aspect_nature,
            "detail": ally.detail,
            "domain": self._ally_domain_label(chart, ally.helper),
        }

    @staticmethod
    def _fill_scenario_say(template: str, payload: dict) -> str:
        """填充已图上命中的场景文案；兼容 YAML 里的 `{al ally_name}` 拼写。"""
        text = template.replace("{al ally_name}", "{ally_name}")
        for key in ("ally_name", "ally_domain", "target_planet_name"):
            value = payload.get(key)
            if value is not None:
                text = text.replace("{" + key + "}", str(value))
        return text

    @staticmethod
    def _ally_domain_label(chart: Chart, planet: Planet) -> str:
        placement = chart.planets.get(planet)
        if placement is None:
            return f"{planet.value}领域"
        return f"{placement.house.house}宫领域"

    def _kb_or_load(self):
        if self._kb is None:
            self._kb = load_knowledge()
        return self._kb

    # -----------------------------------------------------------------
    # 护栏
    # -----------------------------------------------------------------

    def _format_guardrails(self, guardrails: list) -> list[str]:
        result: list[str] = []
        for g in guardrails:
            if isinstance(g, dict):
                result.append(f"不能说：{g.get('never_say', '')} → 改说：{g.get('say_instead', '')}")
            elif isinstance(g, str):
                result.append(g)
        return result

    # -----------------------------------------------------------------
    # 推运层
    # -----------------------------------------------------------------

    def get_timing_rules(self) -> dict:
        """返回推运规则（供外部使用）。"""
        return self._timing_rules

    def get_firdaria_major_rule(self, period_lord: str, target_house: int) -> dict | None:
        """查询特定大运星 × 目标宫的规则。"""
        major_rules = self._timing_rules.get("firdaria_major", {})
        matrix = major_rules.get("period_matrix", {})

        # 先检查是否 same_lord
        # 这里返回模板，具体填充由调用方根据实际星盘数据完成
        return {
            "period_matrix": matrix,
            "relationship_weight": major_rules.get("relationship_weight", {}),
            "marriage_major_say": major_rules.get("marriage_major_period_say", {}),
            "career_major_say": major_rules.get("career_major_period_say", {}),
        }

    # -----------------------------------------------------------------
    # 转宫推导（Derived House Logic）
    # -----------------------------------------------------------------

    @staticmethod
    def derived_house(lord_of_house: int, placed_in_house: int) -> int:
        """宫主X落宫Y → derived = (Y - X + 1)，结果≤0则+12。"""
        d = (placed_in_house - lord_of_house + 1) % 12
        return d if d != 0 else 12

    def get_lord_placement_meaning(
        self, lord_of_house: int, placed_in_house: int, lord_key: str | None = None
    ) -> dict | None:
        """获取宫主落宫的转宫含义。

        Args:
            lord_of_house: 宫主来源宫（如7=7R）
            placed_in_house: 宫主落在哪个宫
            lord_key: 宫主标识（"7R"/"5R"/"10R"/"2R"），用于查手写模板
        """
        # 优先查手写模板
        if lord_key:
            placements = self._natal_comp.get("lord_placement_derived", {})
            lord_data = placements.get(lord_key, {})
            if lord_data:
                lord_placements = lord_data.get("placements", {})
                entry = lord_placements.get(placed_in_house)
                if entry:
                    return entry

        # fallback：转宫公式推导（体系二 house_derived）
        derived = self.derived_house(lord_of_house, placed_in_house)
        meaning = self._derived_house_meaning(lord_of_house, derived)

        return {
            "derived": f"{lord_of_house}之{derived}",
            "meaning": meaning,
            "tell_user": [f"你的{lord_of_house}宫主落在第{placed_in_house}宫——{meaning}"],
        }

    def _derived_house_meaning(self, lord_of_house: int, derived: int) -> str:
        """读取转宫含义：house_derived.yaml 是唯一来源。"""
        derived_table = self._house_derived.get("derived_houses", {})
        by_lord = derived_table.get(lord_of_house) or derived_table.get(str(lord_of_house)) or {}
        meaning = by_lord.get(derived) or by_lord.get(str(derived))
        if meaning:
            return str(meaning)
        return f"{lord_of_house}之{derived}"

    # -----------------------------------------------------------------
    # Prompt 生成
    # -----------------------------------------------------------------

    def build_call_plan_prompt(self, plan: ConsultCallPlan | TopicPlan) -> str:
        """根据 ConsultCallPlan 生成咨询调用主干的 system prompt 注入。"""

        sections: list[str] = []

        # 输出结构
        if plan.output_structure:
            sections.append(self._render_output_structure(plan))

        # 交叉判断提示
        if plan.cross_readings:
            sections.append(self._render_cross_readings(plan))

        # 场景提示
        if plan.scenarios:
            sections.append(self._render_scenarios(plan))

        # 护栏
        if plan.guardrails:
            sections.append(self._render_guardrails(plan))

        return "\n\n".join(sections)

    def build_topic_prompt(self, plan: TopicPlan) -> str:
        """兼容旧名称：TopicPlan / ConsultCallPlan 都走同一 prompt 注入协议。"""
        return self.build_call_plan_prompt(plan)

    def _render_output_structure(self, plan: ConsultCallPlan | TopicPlan) -> str:
        struct = plan.output_structure
        label = struct.get("label", plan.topic_label)
        sections = struct.get("sections", [])

        lines = [f"## 话题：{label}——回答结构", ""]
        lines.append("请按以下顺序组织你的回答（每个section是一个自然段落，section标题不要直接输出，而是作为你叙事的顺序）：")
        lines.append("")

        for i, sec in enumerate(sections, 1):
            title = sec.get("title", "")
            focus = sec.get("focus", "")
            lines.append(f"{i}. **{title}**——聚焦：{focus}")

        lines.append("")
        lines.append("每个section都要引用下面提供的具体数据，不能空谈。")
        lines.append("结尾给一句温暖的落点，不说鸡汤——落点要跟前面讲的具体内容有关。")

        return "\n".join(lines)

    def _render_cross_readings(self, plan: ConsultCallPlan | TopicPlan) -> str:
        lines = ["## 必须做的交叉判断", ""]
        for cr in plan.cross_readings:
            name = cr.get("name", "")
            check_desc = cr.get("check", "")
            lines.append(f"- **{name}**：{check_desc}")

            verdict_c = cr.get("verdict_connected", "")
            verdict_d = cr.get("verdict_disconnected", "")
            if verdict_c:
                lines.append(f"  如果打通 → {verdict_c}")
            if verdict_d:
                lines.append(f"  如果没打通 → {verdict_d}")

            variants = cr.get("variants", {})
            for vk, vv in variants.items():
                lines.append(f"  {vk} → {vv}")

        lines.append("")
        lines.append("以上交叉判断必须基于下面提供的数据来做——数据里有什么就说什么，没有的不要编。")
        return "\n".join(lines)

    def _render_scenarios(self, plan: ConsultCallPlan | TopicPlan) -> str:
        lines = ["## 场景映射参考", ""]
        lines.append("以下场景映射提供'怎么把星盘语言转成人话'的参考。")
        lines.append("当星盘数据匹配到对应条件时，使用对应的说法：")
        lines.append("")

        for s in plan.scenarios:
            s_type = s.get("type", "")
            if s_type == "general":
                rules = s.get("rules", {})
                for key, rule in rules.items():
                    if isinstance(rule, dict):
                        lines.append(f"- {rule.get('say', '')}")
            elif s_type == "topic":
                lines.append(f"- 当 {s.get('condition', '')}：{s.get('say', '')}")

        return "\n".join(lines)

    def _render_guardrails(self, plan: ConsultCallPlan | TopicPlan) -> str:
        lines = ["## 不能说", ""]
        for g in plan.guardrails:
            lines.append(f"- {g}")
        return "\n".join(lines)

    # -----------------------------------------------------------------
    # 工具
    # -----------------------------------------------------------------

    @staticmethod
    def _load_yaml(filename: str) -> dict:
        path = _RULES_DIR / filename
        if not path.exists():
            logger.warning("规则文件不存在: %s", path)
            return {}
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    @staticmethod
    def _load_intent_profiles() -> dict:
        if not _INTENT_PROFILES_PATH.exists():
            logger.warning("意图配置不存在: %s", _INTENT_PROFILES_PATH)
            return {}
        with open(_INTENT_PROFILES_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    @staticmethod
    def _load_rules(filename: str) -> dict:
        path = _RULES_SUBDIR / filename
        if not path.exists():
            logger.warning("规则文件不存在: %s", path)
            return {}
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}


# =============================================================================
# 便捷函数
# =============================================================================


@lru_cache(maxsize=1)
def get_resolver() -> ConsultResolver:
    """获取 ConsultResolver 单例。"""
    return ConsultResolver()


def resolve_call_plan(
    question: str | Intent,
    intent: Intent | None = None,
    chart: Chart | None = None,
) -> ConsultCallPlan:
    """快速解析用户问题 / Intent → ConsultCallPlan 主干。"""
    resolver = get_resolver()
    return resolver.resolve_call_plan(question, intent=intent, chart=chart)


def resolve_question(question: str) -> TopicPlan:
    """快速解析用户问题 → TopicPlan（兼容包装）。"""
    return resolve_call_plan(question).to_topic_plan()
