"""意图路由规则 —— 纯领域逻辑（原则三）。

LLM 只负责抽取原始槽位；把槽位/文本映射到 IntentDomain 与 subdomain
由这里的确定性规则完成。LLM 永不决定领域归属。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from foundation.logger import get_logger
from foundation.utils import new_id
from shared.enums import IntentDomain
from shared.models import Intent, IntentSlot

logger = get_logger("reasoning.intent")

_MIN_CONFIDENCE = 0.3


@dataclass(frozen=True)
class IntentRule:
    """一条意图规则：关键词 → 领域/子领域。"""

    domain: IntentDomain
    subdomain: str
    keywords: list[str] = field(default_factory=list)
    weight: float = 1.0


# ---------------------------------------------------------------------------
# 规则表（可扩展；未来可数据化为 YAML）
# ---------------------------------------------------------------------------

_RULES: list[IntentRule] = [
    # 职业
    IntentRule(IntentDomain.CAREER, "ChangeJob", ["换工作", "跳槽", "辞职", "离职", "换职业", "换份工作"]),
    IntentRule(IntentDomain.CAREER, "Promotion", ["升职", "晋升", "升迁", "加薪", "升", "爬升"]),
    IntentRule(IntentDomain.CAREER, "Entrepreneurship", ["创业", "开公司", "自己干", "单干", "做生意"]),
    IntentRule(IntentDomain.CAREER, "Burnout", ["累", "疲惫", "倦怠", "压力大", "撑不住", "没动力", "工作没意思"]),
    IntentRule(IntentDomain.CAREER, "Career", ["事业", "工作", "职业", "职场", "老板", "同事"]),
    # 感情
    IntentRule(IntentDomain.RELATIONSHIP, "PartnerTraits", ["对象是什么样", "对象特征", "未来对象", "未来的对象", "另一半", "什么样的人", "什么性格", "会是什么性格", "什么样的伴侣", "理想的伴侣", "适合什么类型", "什么样的男生", "什么样的女生", "会是什么样"], weight=1.5),
    IntentRule(IntentDomain.RELATIONSHIP, "Status", ["感情状态", "我们感情", "感情怎么样", "关系怎么样", "我们关系", "感情稳", "关系稳定", "感情好不好", "感情好吗", "感情怎么样"], weight=1.3),
    IntentRule(IntentDomain.RELATIONSHIP, "Start", ["在一起", "表白", "喜欢", "恋爱", "追求", "心动", "合适吗"]),
    IntentRule(IntentDomain.RELATIONSHIP, "Reconcile", ["复合", "和好", "挽回", "分手后", "回头"]),
    IntentRule(IntentDomain.RELATIONSHIP, "Commitment", ["结婚", "求婚", "婚姻", "承诺", "订婚", "嫁", "娶"]),
    IntentRule(IntentDomain.RELATIONSHIP, "Relationship", ["感情", "对象", "男友", "女友", "伴侣", "关系", "男朋友", "女朋友"]),
    # 财富
    IntentRule(IntentDomain.WEALTH, "Finance", ["钱", "财运", "财富", "投资", "赚钱", "收入", "涨薪", "股票", "理财"]),
    # 健康
    IntentRule(IntentDomain.HEALTH, "Health", ["健康", "生病", "身体", "疲惫感", "失眠", "状态差", "体弱"]),
    # 情绪
    IntentRule(IntentDomain.EMOTION, "Emotion", ["情绪", "难过", "低落", "焦虑", "抑郁", "开心不起来", "烦躁", "心情"]),
    # 家庭
    IntentRule(IntentDomain.FAMILY, "Family", ["家庭", "家人", "父母", "爸妈", "原生家庭", "和孩子", "亲子"]),
    # 学习
    IntentRule(IntentDomain.LEARNING, "Learning", ["学习", "考试", "考研", "读书", "学业", "备考", "课程", "学什么"]),
    # 每日/运势（"运势"是核心词——用户常说"这个月运势/最近运势/今天运势"）
    IntentRule(
        IntentDomain.DAILY, "Daily",
        ["今天运势", "今日运势", "今天的运势", "运势如何", "今天怎么样", "每日",
         "运势", "本月运势", "这个月运势", "这周运势", "本周运势", "最近运势", "近期运势", "流年运势"],
        weight=1.2,
    ),
    # 闲聊/问候（命中 → 温暖回应，不进入澄清循环）
    IntentRule(IntentDomain.DAILY, "Chat", ["随便聊聊", "聊聊天", "随便", "在吗", "在么", "你好", "嗨", "哈喽", "hello", "hi", "干嘛呢"]),
    # 问星灵自己/产品能力（LLM 主路径分类为 meta；这里是离线兜底）。
    # 全部带"你/这app"指向产品本身，避免误吞"我适合学什么专业"这类真实提问。
    IntentRule(IntentDomain.DAILY, "Meta", [
        "你是谁", "你是什么", "你是做什么的", "你是干嘛的", "你是干什么的", "你是啥",
        "你能做什么", "你可以做什么", "你能干什么", "你能教我", "你会什么",
        "你擅长", "你有什么专业", "你的专业", "你是学什么的", "你学什么的",
        "学到什么", "这有什么用", "有什么功能", "这app", "这个app",
    ], weight=1.6),
]

# 通用问句（命中则给所在领域的默认策略）
_GENERIC_QUERY = ["怎么样", "合适吗", "好不好", "如何", "时机", "什么时候", "适不适合", "该不该", "能不能", "要不要"]

# 特定对象称谓（问的是"某个具体的人"而非"未来/理想对象"→ 需要对方出生数据）
_RELATED_PERSON_TERMS = [
    "男朋友", "女朋友", "男友", "女友",
    "老公", "老婆", "丈夫", "妻子",
    "喜欢的人", "暗恋的人", "暧昧对象", "现任",
]

# ---------------------------------------------------------------------------
# 宫位识别（领域引擎 v2：语义场=唯一事实源，宫位是精确占星词汇，不走 LLM）
# ---------------------------------------------------------------------------

# "第3宫" / "3宫" / "三宫" / "十二宫"
_HOUSE_RE = re.compile(r"[第]?(?:(\d{1,2})|([一二三四五六七八九十]{1,3}))\s*宫")
_CN_NUM = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
    "十": 10, "十一": 11, "十二": 12,
}
# 用户口语 → 宫位切片词（出行→短途/走动 等，避免切片词表之外的近义表达漏判）
_SLICE_ALIASES: dict[str, str] = {
    "出行": "短途", "口才": "说话", "桃花": "恋爱",
}
# 歧义切片域的优先序（自我探索定位：表达/沟通类切片优先 self，其次 learning；
# 只有该切片同时声明这些域才生效，其余按切片声明的第一个域）
_SLICE_DOMAIN_PREF = ("self", "learning")


# 时间指代 → 起始月份偏移（相对当前月）。
# 追问"那明年呢？/下个月呢？/哪几个月？"时，若直接路由失败，继承活跃话题，
# 并把时间指代落成 time_start_offset 槽位，让 Timing 窗口从偏移处开始扫描。
# 2026-08 时：明年→2027-01(偏移5)，后年→2028-01(偏移17)，下个月→+1。
_TIME_FOLLOWUP_TERMS: dict[str, int] = {
    "明年": 5, "后年": 17, "今年": 0,
    "下个月": 1, "这个月": 0, "下个季度": 3,
    "下半年": 5, "上半年": 5,
    "哪个月": 0, "几月": 0, "几个月": 0, "什么时候": 0, "何时": 0, "哪几个月": 0,
}


class IntentRouter:
    """文本 → Intent（领域规则判定）。

    context 是 Application 传入的"蒸馏上下文"（活跃话题等），仅用于追问消解。
    领域归属永远由这里的确定性规则决定（原则三）。
    """

    def __init__(self):
        self._house_sigs: dict | None = None  # house_significations 懒加载

    def route(
        self,
        raw_query: str,
        slots: dict[str, IntentSlot] | None = None,
        context: dict | None = None,
    ) -> Intent:
        """把用户文本映射为领域验证后的 Intent。"""
        slots = slots or {}
        best_rule, best_score = self._match_best_rule(raw_query)

        # ---- 宫位识别（优先）：用户直接问"第3宫" ----
        house = self._house_from_text(raw_query)
        if house is not None:
            return self._route_house(raw_query, house, best_rule, best_score, slots)

        # 特定对象识别（如"我男朋友"）→ 需要对方出生数据才能合盘
        related = self._extract_related_person(raw_query)
        if related is not None:
            slots[related.name] = related

        # 宫位追问消解：上轮反问"3宫涵盖哪块"，本轮回答切片 → 锁领域
        follow_house = self._active_house(context)
        if follow_house is not None:
            resolved = self._resolve_house_followup(raw_query, follow_house, best_rule, best_score, slots)
            if resolved is not None:
                return resolved

        # 追问消解：直接路由未命中 → 继承活跃话题（时间指代）
        if (best_rule is None or best_score < _MIN_CONFIDENCE) and context:
            followup = self._resolve_time_followup(raw_query, context, slots)
            if followup is not None:
                return followup

        requires_clarification = best_rule is None or best_score < _MIN_CONFIDENCE

        return Intent(
            id=new_id("intent"),
            raw_query=raw_query,
            domain=best_rule.domain if best_rule else IntentDomain.DAILY,
            subdomain=best_rule.subdomain if best_rule else "",
            slots=slots,
            domain_confidence=best_score,
            parsed_at=datetime.now(timezone.utc),
            requires_clarification=requires_clarification,
            clarification_question=(
                "我还不确定你想问哪方面，可以具体说说吗？比如职业、感情、财运、健康、学习…"
                if requires_clarification
                else ""
            ),
        )

    @staticmethod
    def _match_best_rule(raw_query: str) -> tuple[IntentRule | None, float]:
        """关键词规则打分 → (最佳规则, 得分)。"""
        best_rule: IntentRule | None = None
        best_score = 0.0
        for rule in _RULES:
            hits = sum(1 for kw in rule.keywords if kw in raw_query)
            if hits == 0:
                continue
            score = hits * rule.weight / len(rule.keywords) ** 0.5
            if score > best_score:
                best_score = score
                best_rule = rule
        # 领域兜底：命中通用问句，但无法细分 subdomain
        if best_rule is None:
            for rule in _RULES:
                if any(kw in raw_query for kw in rule.keywords):
                    best_rule = rule
                    best_score = _MIN_CONFIDENCE
                    break
        return best_rule, best_score

    # -----------------------------------------------------------------
    # 宫位识别（领域引擎 v2）
    # -----------------------------------------------------------------

    @staticmethod
    def _house_from_text(text: str) -> int | None:
        """抽取宫位号：'第3宫'/'三宫'/'12宫' → int(1-12)，无宫位引用 → None。"""
        m = _HOUSE_RE.search(text)
        if not m:
            return None
        n = int(m.group(1)) if m.group(1) else _CN_NUM.get(m.group(2), 0)
        return n if 1 <= n <= 12 else None

    @staticmethod
    def _active_house(context: dict | None) -> int | None:
        h = (context or {}).get("active_house")
        return h if isinstance(h, int) and 1 <= h <= 12 else None

    def _house_slices(self, house: int) -> list[dict]:
        """该宫语义场切片（house_significations.yaml = 唯一事实源）。"""
        if self._house_sigs is None:
            import yaml  # noqa: PLC0415

            path = (
                Path(__file__).parents[3]
                / "domain" / "astrology" / "knowledge" / "house_significations.yaml"
            )
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            self._house_sigs = data.get("house_significations", {}) or {}
        return list(self._house_sigs.get(house, []) or [])

    @staticmethod
    def _slice_terms(entry: dict) -> list[str]:
        """切片可匹配词：word 各分量 + resonance + 口语别名。"""
        terms = [w for w in str(entry.get("word", "")).split("/") if w]
        terms += [r for r in (entry.get("resonance") or []) if r]
        for user, canonical in _SLICE_ALIASES.items():
            if canonical in terms and user not in terms:
                terms.append(user)
        return terms

    def _match_slice(self, house: int, raw_query: str) -> dict | None:
        """从该宫语义场找被用户点名的切片（如"表达"→沟通/表达/写作）。"""
        for entry in self._house_slices(house):
            if any(t and t in raw_query for t in self._slice_terms(entry)):
                return entry
        return None

    @staticmethod
    def _domain_for_slice(
        entry: dict, rule_domain: IntentDomain | None,
    ) -> IntentDomain:
        """切片 → 领域：规则已锁定用规则域；否则歧义切片按优先序，再按声明顺序。"""
        if rule_domain is not None:
            return rule_domain
        domains = entry.get("domains", [])
        for pref in _SLICE_DOMAIN_PREF:
            if pref in domains:
                return IntentDomain(pref)
        if domains:
            return IntentDomain(domains[0])
        return IntentDomain.DAILY

    def _route_house(
        self, raw_query: str, house: int,
        best_rule: IntentRule | None, best_score: float, slots: dict,
    ) -> Intent:
        """用户问"第N宫"：有切片词 → 锁领域；裸宫位 → 反问该宫涵盖哪些方面。"""
        slots["focus_house"] = IntentSlot(
            name="focus_house", raw_value=f"{house}宫",
            normalized_value=str(house), confidence=1.0,
        )
        slice_entry = self._match_slice(house, raw_query)
        if slice_entry is not None:
            rule_domain = best_rule.domain if (best_rule and best_score >= _MIN_CONFIDENCE) else None
            domain = self._domain_for_slice(slice_entry, rule_domain)
            slots["focus_domain"] = IntentSlot(
                name="focus_domain", raw_value=slice_entry.get("word", ""),
                normalized_value=domain.value, confidence=0.9,
            )
            return Intent(
                id=new_id("intent"), raw_query=raw_query, domain=domain,
                slots=slots, domain_confidence=max(best_score, 0.6),
                parsed_at=datetime.now(timezone.utc),
                requires_clarification=False, clarification_question="",
            )
        # 无切片词命中：
        # ① 规则已锁领域（如"12宫财运"→ 财运命中 wealth）→ 领域词优先，宫位作 focus
        if best_rule is not None and best_score >= _MIN_CONFIDENCE:
            slots["focus_domain"] = IntentSlot(
                name="focus_domain", raw_value="",
                normalized_value=best_rule.domain.value, confidence=0.9,
            )
            return Intent(
                id=new_id("intent"), raw_query=raw_query, domain=best_rule.domain,
                subdomain=best_rule.subdomain, slots=slots,
                domain_confidence=best_score,
                parsed_at=datetime.now(timezone.utc),
                requires_clarification=False, clarification_question="",
            )
        # ② 纯裸宫位 → 反问：列出该宫语义场切片（用户自选哪一块）
        labels = [e.get("word", "") for e in self._house_slices(house)]
        question = (
            f"{house}宫涵盖的方面挺多的——{'、'.join(labels)}。"
            f"你想问的是哪一块？"
            if labels else f"{house}宫……你具体想问它哪方面？"
        )
        return Intent(
            id=new_id("intent"), raw_query=raw_query, domain=IntentDomain.DAILY,
            slots=slots, domain_confidence=0.0,
            parsed_at=datetime.now(timezone.utc),
            requires_clarification=True, clarification_question=question,
        )

    def _resolve_house_followup(
        self, raw_query: str, house: int,
        best_rule: IntentRule | None, best_score: float, slots: dict,
    ) -> Intent | None:
        """上轮反问过"3宫涵盖哪块"，本轮回答切片 → 锁领域 + 继承宫位。

        若本轮与宫位无关（如用户转问感情）→ None，走常规路由。
        """
        slice_entry = self._match_slice(house, raw_query)
        if slice_entry is None:
            return None
        rule_domain = best_rule.domain if (best_rule and best_score >= _MIN_CONFIDENCE) else None
        domain = self._domain_for_slice(slice_entry, rule_domain)
        slots["focus_house"] = IntentSlot(
            name="focus_house", raw_value=f"{house}宫",
            normalized_value=str(house), confidence=1.0,
        )
        slots["focus_domain"] = IntentSlot(
            name="focus_domain", raw_value=slice_entry.get("word", ""),
            normalized_value=domain.value, confidence=0.9,
        )
        return Intent(
            id=new_id("intent"), raw_query=raw_query, domain=domain,
            slots=slots, domain_confidence=max(best_score, 0.6),
            parsed_at=datetime.now(timezone.utc),
            requires_clarification=False, clarification_question="",
        )

    @staticmethod
    def _resolve_time_followup(
        raw_query: str, context: dict, slots: dict[str, IntentSlot]
    ) -> Intent | None:
        """时间指代追问：继承活跃领域/子领域，落 time_start_offset 槽位。

        纯确定性规则（原则三）：领域归属来自上一轮已确认的 Intent，
        不来自 LLM。命中则置信度高于门槛，不再要求澄清。
        """
        active_domain = context.get("active_domain")
        if active_domain is None:
            return None

        for term, offset in _TIME_FOLLOWUP_TERMS.items():
            if term not in raw_query:
                continue
            slots["time_start_offset"] = IntentSlot(
                name="time_start_offset",
                raw_value=term,
                normalized_value=str(offset),
                confidence=0.9,
            )
            return Intent(
                id=new_id("intent"),
                raw_query=raw_query,
                domain=IntentDomain(active_domain),
                subdomain=context.get("active_subdomain") or "",
                slots=slots,
                domain_confidence=_MIN_CONFIDENCE + 0.4,
                parsed_at=datetime.now(timezone.utc),
                requires_clarification=False,
                clarification_question="",
            )
        return None

    @staticmethod
    def _extract_related_person(query: str) -> IntentSlot | None:
        """识别用户提到的具体对象（男朋友/女友/老公等）。"""
        for term in _RELATED_PERSON_TERMS:
            if term in query:
                return IntentSlot(
                    name="related_person",
                    raw_value=term,
                    normalized_value=term,
                    confidence=0.85,
                )
        return None
