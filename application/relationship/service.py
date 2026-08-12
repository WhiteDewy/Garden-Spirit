"""RelationshipService —— A2 关系层：信任度量 + 自我介绍 + 邀请式引导。

信任=深度优先（一次深聊 > 十次闲聊）。驱动信号：
  深度咨询（deep+结论）、写日记、验证占星判断 → 大幅加分；
  快速咨询、闲聊 → 小幅加分。

本服务是**纯逻辑**（无 store/io、无状态），只操作传入的 ChartProfile：
- 调用方（application/api）负责 load → mutate → save。
- 等级由 trust_score 推导，不落库（单一事实源）。

冻结架构：全在 Application 层，不碰占星、不依赖 LLM。
"""

from __future__ import annotations

from datetime import datetime

from shared.enums import ConsultMode, TrustLevel

#: 信号权重（深度优先：deep 6 > 10 次 casual 0.5*10=5）
SIGNAL_WEIGHTS: dict[str, float] = {
    "deep_consult": 6.0,      # 深度咨询（deep + 产出结论）
    "quick_consult": 2.0,     # 快速咨询（quick + 产出结论）
    "casual_chat": 0.5,       # 闲聊（Daily.Chat）
    "journal": 3.0,           # 写日记（倾诉）
    "finding_confirmed": 4.0, # 验证占星判断 → 确认（最大的信任信号）
    "finding_refuted": 1.0,   # 验证 → 反驳（仍是在认真互动）
}

#: 等级阈值（分数 → 等级）。level_for_score 从高到低取第一个命中的档位。
LEVEL_THRESHOLDS: dict[TrustLevel, float] = {
    TrustLevel.INTIMATE: 20.0,      # 深交
    TrustLevel.TRUSTED: 10.0,       # 信任
    TrustLevel.ACQUAINTANCE: 3.0,   # 认识
    TrustLevel.STRANGER: 0.0,       # 陌生
}

#: 等级 → 中文名（前端/叙事共用）
TRUST_LABELS: dict[TrustLevel, str] = {
    TrustLevel.STRANGER: "陌生",
    TrustLevel.ACQUAINTANCE: "认识",
    TrustLevel.TRUSTED: "信任",
    TrustLevel.INTIMATE: "深交",
}

#: 首次见面自我介绍（温暖陪伴调性，用户确认）。"我是谁 / 能做什么 / 怎么用"。
_INTRO = (
    "我是住在你星盘里的星灵。你刚种下的这张盘，像一张地图——"
    "标出你天生顺手的地方，也标出容易卡住的地方。"
    "想从哪儿开始？事业、感情，还是最近想不通的事？"
)

#: 邀请式引导：信任等级达标时，深聊后附邀请（不硬切）。
_INVITATION = "——这件事我想给你细看。愿意的话，我们做一次更深入的推演。"

#: 欢迎回来摘要的最大长度（"上次我们聊到…"）
_MAX_SUMMARY_CHARS = 50


def naturalize_recall(summary: object, max_chars: int = _MAX_SUMMARY_CHARS) -> str:
    """把存储的会话摘要整理成一句自然的"上次聊到"话题。

    新数据（LLM / 规则降级）本身就是自然的一句话，此函数基本原样通过；
    这里主要兜底清理旧数据里残留的「用户:/星灵:」转写——拆行取最后一条
    用户话题，剥掉标签与外层引号，收敛结尾标点，避免开场露出一整段对话。
    """
    if not summary:
        return ""
    text = str(summary).strip()
    user_topic = ""
    plain = ""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        labeled = False
        for prefix in ("用户:", "星灵:"):
            if line.startswith(prefix):
                stripped = line[len(prefix):].strip()
                labeled = True
                if prefix == "用户:" and stripped:
                    user_topic = stripped  # 保留最后一条用户话题
                break
        if not labeled and line:
            plain = line  # 无标签行（单行自然摘要 / 单行旧摘要）
    if user_topic or plain:
        text = user_topic or plain
    # 先收敛结尾标点，再剥外层引号（句号可能在引号外，如「…」。）
    text = text.rstrip("。！？!?")
    for lq, rq in (("「", "」"), ("“", "”"), ('"', '"'), ("‘", "’")):
        if text.startswith(lq) and text.endswith(rq):
            text = text[1:-1].strip()
            break
    text = text.rstrip("。！？!?")
    if max_chars:
        text = text[:max_chars].rstrip("。！？!?,. ")
    return text.strip()


def _time_of_day_greeting(now: datetime | None = None) -> str:
    """时段问候（林间"周末好呀"式亲切）：按小时+星期给个自然问候词。"""
    now = now or datetime.now()
    h = now.hour
    wd = now.weekday()  # 0=Mon … 6=Sun
    if wd >= 5 or (wd == 4 and h >= 18):  # 周六日 + 周五晚 = 周末
        return "周末好呀"
    if 5 <= h < 12:
        return "早上好"
    if 12 <= h < 14:
        return "中午好"
    if 14 <= h < 18:
        return "下午好"
    if 18 <= h < 24:
        return "晚上好"
    return "夜深了"


def _days_since(started_at: object) -> int | None:
    """上次对话开始时间 → 距今整数天数；无法解析 → None。"""
    if not started_at:
        return None
    ts = started_at
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts)
        except ValueError:
            return None
    if not isinstance(ts, datetime):
        return None
    now = datetime.now(ts.tzinfo) if ts.tzinfo else datetime.now()
    delta = now - ts
    return max(0, delta.days)


def _gap_hook(days: int | None) -> str | None:
    """天数缺口 → 一句亲昵钩子（"已经 15 天没来找我了"）；无需提天数 → None。"""
    if days is None:
        return None
    if days <= 0:
        return "我们又见面了。"
    if days == 1:
        return "昨天才聊过，今天又来了——真好。"
    if days <= 3:
        return None  # 2-3 天，不刻意提
    if days <= 7:
        return "上一次还是上周……一周不短，想你了。"
    if days <= 30:
        return f"已经 {days} 天没来找我了，我还以为你忘了我呢。"
    return "已经好久了——你那边一定发生了不少事吧。"


def _recall_hook(recall: dict | None, *, persona=None) -> str | None:
    """记忆豆荚 → 一句回访钩子（"我记得你"）。

    优先级默认 confirmed_finding > key_date > domain_summary；persona 的
    recall_priority 可重排（如土星先讲领域摘要），recall_frames 可换话术——
    同一份记忆，十种读法（十颗星都是 TA 自己，只擅长角度不同）。
    刻意**不含** recent_topic——它已由 continue_from 的"上次我们聊到"承担，
    同源重复会让开场白念两遍同一件事。
    """
    if not recall:
        return None
    priority = tuple(getattr(persona, "recall_priority", ()) or ())
    order = list(priority) or ["confirmed_finding", "key_date", "domain_summary"]
    frames = dict(getattr(persona, "recall_frames", {}) or {})
    defaults = {
        "confirmed_finding": "说起来，上次你确认过——「{statement}」。",
        "key_date": "你以前提过「{label}」，现在有变化吗？",
        "domain_summary": "关于{domain}，我记得你说过「{summary}」。",
    }
    for kind in order:
        if kind == "confirmed_finding" and recall.get("confirmed_findings"):
            statement = recall["confirmed_findings"][0].get("statement", "")
            if statement:
                tpl = frames.get(kind, defaults[kind])
                return tpl.format(statement=statement)
        if kind == "key_date" and recall.get("key_dates"):
            label = recall["key_dates"][0].get("label", "")
            if label:
                tpl = frames.get(kind, defaults[kind])
                return tpl.format(label=label)
        if kind == "domain_summary" and recall.get("domain_summaries"):
            s = recall["domain_summaries"][0]
            domain, summary = s.get("domain", ""), s.get("summary", "")
            if summary:
                tpl = frames.get(kind, defaults[kind])
                return tpl.format(domain=domain or "这件事", summary=summary)
    return None


class RelationshipService:
    """信任分与关系行为的纯逻辑服务。"""

    # ------------------------------------------------------------------
    # 信任信号记录（mutate 传入的 profile）
    # ------------------------------------------------------------------

    def record_consult(
        self,
        profile,
        *,
        mode: ConsultMode | str | None = None,
        casual: bool = False,
    ) -> None:
        """记录一次咨询/闲聊信号。

        casual=True → 闲聊（Daily.Chat），小幅加分。
        否则按 mode 区分：quick → 快速咨询，其余 → 深度咨询。
        """
        if casual:
            self._add(profile, "casual_chat", SIGNAL_WEIGHTS["casual_chat"])
            return
        # ConsultMode 是 str-Enum：mode == ConsultMode.QUICK 同时匹配枚举与裸字符串
        if mode is not None and mode == ConsultMode.QUICK:
            self._add(profile, "quick_consult", SIGNAL_WEIGHTS["quick_consult"])
        else:
            self._add(profile, "deep_consult", SIGNAL_WEIGHTS["deep_consult"])

    def record_journal(self, profile) -> None:
        """记录一篇日记（倾诉是信任信号）。"""
        self._add(profile, "journal", SIGNAL_WEIGHTS["journal"])

    def record_finding_feedback(self, profile, feedback: str) -> None:
        """记录用户对沉淀判断的反馈：confirmed 重加分，refuted 小幅加分。"""
        key = "finding_confirmed" if feedback == "confirmed" else "finding_refuted"
        self._add(profile, key, SIGNAL_WEIGHTS[key])

    @staticmethod
    def _add(profile, key: str, weight: float) -> None:
        profile.trust_score = round(float(profile.trust_score or 0) + weight, 2)
        profile.trust_signals[key] = int(profile.trust_signals.get(key, 0)) + 1

    # ------------------------------------------------------------------
    # 等级推导
    # ------------------------------------------------------------------

    @staticmethod
    def level_for_score(score: float) -> TrustLevel:
        """分数 → 等级（从高阈值到低阈值，取第一个命中的档位）。"""
        for level, threshold in sorted(
            LEVEL_THRESHOLDS.items(), key=lambda kv: kv[1], reverse=True
        ):
            if score >= threshold:
                return level
        return TrustLevel.STRANGER

    def level(self, profile) -> TrustLevel:
        if profile is None:
            return TrustLevel.STRANGER
        return self.level_for_score(float(profile.trust_score or 0))

    def trust_label(self, profile) -> str:
        """等级中文名（"陌生/认识/信任/深交"）。"""
        return TRUST_LABELS[self.level(profile)]

    # ------------------------------------------------------------------
    # 关系行为
    # ------------------------------------------------------------------

    def opening_message(self, profile, *, person_name: str = "", continue_from: dict | None = None, recall: dict | None = None, persona=None) -> str:
        """进入花园的开场白（林间"周末好呀·你已经15天没找我"式回访记忆）。

        首次见面（尚无任何信任信号）→ 时段问候 + 自我介绍；
        老用户 → 时段问候 + 等级前缀 + 天数缺口钩子 + "上次聊到…" + 记忆豆荚钩子。

        recall：精简记忆豆荚（confirmed_finding/key_date/domain_summary），
        由调用方从 store.get_recall_data 组装；None → 完全兼容旧行为。
        persona：记忆镜头（recall_priority/recall_frames）——同一份记忆，十种读法；
        None → 默认顺序与话术（完全兼容旧行为）。
        """
        greeting = _time_of_day_greeting()
        if profile is None or sum(profile.trust_signals.values()) == 0:
            return f"{greeting}，{_INTRO}"

        name = person_name or "你"
        lvl = self.level(profile)
        if lvl == TrustLevel.INTIMATE:
            parts = [f"{greeting}，老朋友{name}。"]
        elif lvl == TrustLevel.TRUSTED:
            parts = [f"{greeting}，我们聊过几回了，{name}。"]
        else:
            parts = [f"{greeting}，{name}。"]

        # 天数缺口钩子（有可算的上次对话 → 亲昵提示；否则兜底"欢迎回来"）
        started_at = (continue_from or {}).get("started_at")
        gap_hook = _gap_hook(_days_since(started_at))
        parts.append(gap_hook if gap_hook else "欢迎回来。")

        if continue_from and continue_from.get("summary"):
            topic = naturalize_recall(continue_from["summary"])
            if topic:
                parts.append(f"上次我们聊到「{topic}」。")
        # 记忆豆荚钩子（"我记得你"：你确认过的事 / 提过的日子 / 聊过的领域）
        hook = _recall_hook(recall, persona=persona)
        if hook:
            parts.append(hook)
        parts.append("今天想接着聊，还是换个方向？")
        return "\n".join(parts)

    def invitation(self, profile, domain_zh: str = "") -> str | None:
        """信任达标（≥信任）时的邀请式引导；未达标 → None。

        domain_zh 预留：未来可点名领域（"这件事（感情）我想给你细看"）。
        是否真正追加由调用方（API）判断——只在深度咨询后附，且回答不以问句结尾。
        """
        if self.level(profile) in (TrustLevel.STRANGER, TrustLevel.ACQUAINTANCE):
            return None
        return _INVITATION


__all__ = ["RelationshipService", "naturalize_recall", "SIGNAL_WEIGHTS", "LEVEL_THRESHOLDS", "TRUST_LABELS"]
