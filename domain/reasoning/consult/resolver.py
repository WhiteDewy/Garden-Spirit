"""Consult Resolver —— 咨询模板引擎。

三层规则驱动，从用户问题自动推导完整的咨询结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from foundation.logger import get_logger
from shared.enums import Planet

logger = get_logger("reasoning.consult")

_RULES_DIR = Path(__file__).parent.parent.parent / "astrology" / "knowledge"
_RULES_SUBDIR = _RULES_DIR / "rules"


# =============================================================================
# 数据类
# =============================================================================


@dataclass
class TopicPlan:
    """一个话题的完整解析结果。"""

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


# =============================================================================
# Resolver
# =============================================================================


class ConsultResolver:
    """从用户问题 + 星盘数据 → 咨询结构。"""

    def __init__(self, kb=None):
        self._house_nature = self._load_yaml("house_nature.yaml")
        self._planet_nature = self._load_yaml("planet_nature.yaml")
        self._natal_comp = self._load_rules("natal_composition.yaml")
        self._timing_rules = self._load_rules("timing_rules.yaml")
        self._kb = kb  # KnowledgeBase reference（可选，用于查 lordship 等）

    # -----------------------------------------------------------------
    # 话题解析
    # -----------------------------------------------------------------

    def resolve_topic(self, question: str) -> TopicPlan:
        """从用户问题文字 → TopicPlan。"""

        # 1. 关键词匹配 → 主宫
        primary_house = self._match_primary_house(question)
        primary_info = self._house_nature["houses"][primary_house]

        # 2. 从主宫的 as_derived + 话题语境 → 辅宫
        supplementary = self._resolve_supplementary(primary_house, question)

        # 3. 从 topic_id → 确定核心星和辅助星
        topic_id = self._infer_topic_id(primary_house, question)
        primary_planets, supporting_planets = self._resolve_planets(topic_id, primary_house)

        # 4. 匹配交叉判断模板
        cross_readings = self._match_cross_readings(topic_id, primary_house, supplementary)

        # 5. 匹配场景映射
        scenarios = self._match_scenarios(topic_id)

        # 6. 获取输出结构
        output_structure = self._natal_comp.get("output_structures", {}).get(topic_id)

        # 7. 加载护栏
        guardrails = self._natal_comp.get("guardrails", [])

        return TopicPlan(
            topic_id=topic_id,
            topic_label=primary_info.get("label", str(primary_house)),
            primary_house=primary_house,
            supplementary_houses=supplementary,
            primary_planets=primary_planets,
            supporting_planets=supporting_planets,
            cross_readings=cross_readings,
            scenarios=scenarios,
            output_structure=output_structure,
            guardrails=self._format_guardrails(guardrails),
        )

    def _match_primary_house(self, question: str) -> int:
        """关键词匹配 → 主宫编号。"""
        houses = self._house_nature.get("houses", {})
        best_house = 1
        best_score = 0

        for h_num_str, info in houses.items():
            h_num = int(h_num_str)
            keywords = info.get("topic_keywords", {})
            primary_kw = keywords.get("primary", [])
            secondary_kw = keywords.get("secondary", [])

            score = 0
            for kw in primary_kw:
                if kw in question:
                    score += 3
            for kw in secondary_kw:
                if kw in question:
                    score += 1

            if score > best_score:
                best_score = score
                best_house = h_num

        return best_house

    def _resolve_supplementary(self, primary_house: int, question: str) -> list[int]:
        """从主宫的 as_derived 和问题语境确定辅宫。"""
        primary_info = self._house_nature["houses"][primary_house]
        derived = primary_info.get("as_derived", {})

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

    def _resolve_planets(self, topic_id: str, primary_house: int) -> tuple[list[str], list[str]]:
        """从 topic_id → 核心星 + 辅助星。"""
        planets_data = self._planet_nature.get("planets", {})

        # topic_id → domain key 映射
        topic_to_domain = {
            "marriage": "marriage",
            "dating": "dating",
            "career": "career",
            "career_change": "career",
            "job_skill": "career",
            "boss_colleague": "career",
            "wealth": "wealth",
            "health": "health",
            "study": "study",
            "advanced_study": "study",
            "family": "family",
            "villain": "villain",
            "talent": "dating",  # 兴趣/才华复用dating的星性
        }

        # health 的 domain_signals 需要确保 planet_nature.yaml 里有对应条目
        # sun/mars/saturn/moon 在 health domain 应标记为 core

        domain = topic_to_domain.get(topic_id, "career")

        primary: list[str] = []
        supporting: list[str] = []

        for p_key, p_info in planets_data.items():
            signals = p_info.get("domain_signals", {})
            signal = signals.get(domain, "neutral")
            if signal == "core":
                primary.append(p_key)
            elif signal == "supporting":
                supporting.append(p_key)

        return primary, supporting

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

    def _match_scenarios(self, topic_id: str) -> list[dict]:
        """匹配适用于当前话题的场景映射。"""
        scenario_maps = self._natal_comp.get("scenario_maps", {})
        matched: list[dict] = []

        # 通用场景（lord_angularity）
        general = scenario_maps.get("lord_angularity", {})
        if general:
            matched.append({"type": "general", "rules": general})

        # 话题专属场景
        topic_scenario_key = f"{topic_id}_scenarios"
        topic_scenarios = scenario_maps.get(topic_scenario_key, [])
        for s in topic_scenarios:
            matched.append({"type": "topic", "condition": s.get("condition", ""), "say": s.get("say", "")})

        return matched

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

        # fallback：转宫公式推导
        derived = self.derived_house(lord_of_house, placed_in_house)
        house_nature = self._house_nature.get("houses", {}).get(lord_of_house, {})
        as_derived = house_nature.get("as_derived", {})
        meaning = as_derived.get(derived, f"{lord_of_house}之{derived}")

        return {
            "derived": f"{lord_of_house}之{derived}",
            "meaning": meaning,
            "tell_user": [f"你的{lord_of_house}宫主落在第{placed_in_house}宫——{meaning}"],
        }

    # -----------------------------------------------------------------
    # Prompt 生成
    # -----------------------------------------------------------------

    def build_topic_prompt(self, plan: TopicPlan) -> str:
        """根据 TopicPlan 生成话题专属的 system prompt 注入。"""

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

    def _render_output_structure(self, plan: TopicPlan) -> str:
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

    def _render_cross_readings(self, plan: TopicPlan) -> str:
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

    def _render_scenarios(self, plan: TopicPlan) -> str:
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

    def _render_guardrails(self, plan: TopicPlan) -> str:
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


def resolve_question(question: str) -> TopicPlan:
    """快速解析用户问题 → TopicPlan。"""
    resolver = get_resolver()
    return resolver.resolve_topic(question)
