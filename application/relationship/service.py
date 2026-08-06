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
    "嗨，我是住在你星盘里的星灵。你刚种下的这张盘，像一张地图——"
    "标出你天生顺手的地方，也标出容易卡住的地方。"
    "可以问我事业、感情、财运，或任何最近想不通的事；"
    "聊得多了，我会记住你，记住你在意的变化。\n\n今天想从哪儿说起？"
)

#: 邀请式引导：信任等级达标时，深聊后附邀请（不硬切）。
_INVITATION = "——这件事我想给你细看。愿意的话，我们做一次更深入的推演。"

#: 欢迎回来摘要的最大长度（"上次我们聊到…"）
_MAX_SUMMARY_CHARS = 50


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

    def opening_message(self, profile, *, person_name: str = "", continue_from: dict | None = None) -> str:
        """进入花园的开场白。

        首次见面（尚无任何信任信号）→ 自我介绍；
        老用户 → 欢迎回来（按等级加前缀，附"上次聊到…"）。
        """
        if profile is None or sum(profile.trust_signals.values()) == 0:
            return _INTRO

        name = person_name or "你"
        lvl = self.level(profile)
        if lvl == TrustLevel.INTIMATE:
            parts = [f"老朋友，欢迎回来，{name}。"]
        elif lvl == TrustLevel.TRUSTED:
            parts = [f"我们聊过几回了。欢迎回来，{name}。"]
        else:
            parts = [f"欢迎回来，{name}。"]

        if continue_from and continue_from.get("summary"):
            summary = str(continue_from["summary"])[:_MAX_SUMMARY_CHARS]
            if summary:
                parts.append(f"上次我们聊到「{summary}」。")
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


__all__ = ["RelationshipService", "SIGNAL_WEIGHTS", "LEVEL_THRESHOLDS", "TRUST_LABELS"]
