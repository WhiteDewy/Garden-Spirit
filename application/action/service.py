"""ActionService —— 行动层（L6）编排器：待验证清单 + 偏好。

行动层 = 让 Agent 从"答完就走"变成"主动关心"。B2 v1 落地两块：

1. **待验证清单**（用户核心诉求）：把没验证过的沉淀判断全部罗列，
   供用户一起验证。验证动作走现有 feedback 端点（B1 置信度校准）。
   判断"已验证"的标准：用户反馈过（confirmed/refuted）**或**被事件验过
   （verification_notes 非空）。都没有 → "待验证"。

2. **偏好控制**：push_frequency（推送频率）/ sensitive_topics（敏感话题）/
   preferred_persona。v1 存储 + 校验 + 暴露，真实推送系统接上后用。

纯编排 + 纯函数，无 LLM、无占星计算。无状态（除偏好默认值）。
"""

from __future__ import annotations

from shared.models import ChartProfile, VerifiedFinding

#: 偏好默认值
DEFAULT_PREFERENCES: dict[str, object] = {
    "push_frequency": "daily",      # daily | quiet | off
    "sensitive_topics": [],         # 敏感话题列表（v1 存储，不 gate 行为）
    "preferred_persona": "",        # PersonaType 值；空 = 用系统默认
}

#: 合法推送频率
PUSH_FREQUENCIES = ("daily", "quiet", "off")


class ActionService:
    """行动层编排：findings 状态 / 待验证计数 / 偏好。"""

    # ------------------------------------------------------------------
    # 待验证清单
    # ------------------------------------------------------------------

    @staticmethod
    def is_unverified(finding: VerifiedFinding) -> bool:
        """未验证 = 用户没反馈过 且 没有被事件验过。"""
        return not finding.user_feedback and not finding.verification_notes

    def findings_status(self, profile: ChartProfile | None) -> list[dict]:
        """画像里每条判断 → 带验证状态的结构化 dict（供前端罗列）。"""
        if profile is None:
            return []
        out: list[dict] = []
        for f in profile.verified_findings:
            unverified = self.is_unverified(f)
            out.append({
                "id": f.id,
                "statement": f.statement,
                "domain": getattr(f, "domain", "") or "",
                "confidence": f.confidence,
                "status": "unverified" if unverified else "verified",
                "feedback": f.user_feedback,
                "event_verified": bool(f.verification_notes),
                "verification_notes": list(f.verification_notes),
                "confirmed_at": f.confirmed_at.isoformat() if f.confirmed_at else None,
            })
        return out

    def pending_count(self, profile: ChartProfile | None) -> int:
        """待验证判断数（行动层的主动提醒：'有 N 条等你验证'）。"""
        if profile is None:
            return 0
        return sum(1 for f in profile.verified_findings if self.is_unverified(f))

    # ------------------------------------------------------------------
    # 偏好
    # ------------------------------------------------------------------

    @staticmethod
    def preferences(profile: ChartProfile | None) -> dict:
        """取偏好：未设置过的 key 用默认值补全，保证结构完整。"""
        raw = dict(profile.preferences) if profile is not None and profile.preferences else {}
        merged = dict(DEFAULT_PREFERENCES)
        merged.update({k: v for k, v in raw.items() if v is not None})
        return merged

    @staticmethod
    def validate_preferences(preferences: dict) -> dict:
        """校验用户提交的偏好，返回规范化后的子集；非法值抛 ValueError。"""
        cleaned: dict = {}

        if "push_frequency" in preferences:
            freq = preferences["push_frequency"]
            if freq not in PUSH_FREQUENCIES:
                raise ValueError(f"push_frequency 必须为 {PUSH_FREQUENCIES} 之一")
            cleaned["push_frequency"] = freq

        if "sensitive_topics" in preferences:
            topics = preferences["sensitive_topics"]
            if not isinstance(topics, list) or not all(
                isinstance(t, str) and t.strip() for t in topics
            ):
                raise ValueError("sensitive_topics 必须是非空字符串列表")
            cleaned["sensitive_topics"] = [t.strip() for t in topics][:20]

        if "preferred_persona" in preferences:
            persona = (preferences["preferred_persona"] or "").strip()
            if persona:
                from shared.enums import PersonaType

                if persona not in PersonaType._value2member_map_:
                    raise ValueError(f"preferred_persona 不是有效的人格名: {persona}")
            cleaned["preferred_persona"] = persona

        return cleaned


__all__ = ["ActionService", "DEFAULT_PREFERENCES", "PUSH_FREQUENCIES"]
