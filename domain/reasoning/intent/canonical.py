"""跨主题意图 canonicalization（Domain-owned）。

这一层只把入口上下文、规则路由结果和用户原文整理成可审计的主题结构；
不做宫位/行星/吉凶/时机判断，也不替代现有单域执行链。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from shared.enums import IntentDomain
from shared.models import Intent


class CanonicalThemeRole(StrEnum):
    """主题在本次问题里的角色。"""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    CONTEXT = "context"


class CanonicalThemeSource(StrEnum):
    """主题来源，用于审计为什么纳入该主题。"""

    RULE = "rule"
    REPORT_CONTEXT = "report_context"
    LLM_SLOT = "llm_slot"
    FOLLOWUP = "followup"


@dataclass(frozen=True)
class CanonicalTheme:
    """一个被 Domain 认可的主题原子。"""

    domain: IntentDomain
    role: CanonicalThemeRole
    subdomain: str = ""
    confidence: float = 0.0
    sources: tuple[CanonicalThemeSource, ...] = field(default_factory=tuple)
    rationale: str = ""


@dataclass(frozen=True)
class CanonicalIntent:
    """单次用户问题的 canonical 主题结构。"""

    primary: CanonicalTheme
    secondary: tuple[CanonicalTheme, ...] = field(default_factory=tuple)
    entry_topic_key: str | None = None
    intent_shape: str | None = None
    report_type: str | None = None
    user_focus_text: str | None = None

    @property
    def themes(self) -> tuple[CanonicalTheme, ...]:
        return (self.primary, *self.secondary)


_TOPIC_TO_DOMAIN: dict[str, IntentDomain] = {
    "career": IntentDomain.CAREER,
    "relationship": IntentDomain.RELATIONSHIP,
    "wealth": IntentDomain.WEALTH,
    "health": IntentDomain.HEALTH,
    "emotion": IntentDomain.EMOTION,
    "family": IntentDomain.FAMILY,
    "learning": IntentDomain.LEARNING,
    "study": IntentDomain.LEARNING,
    "growth": IntentDomain.GROWTH,
    "network": IntentDomain.NETWORK,
    "self": IntentDomain.SELF,
    "daily": IntentDomain.DAILY,
}


def domain_from_topic(topic: str | None) -> IntentDomain | None:
    """观星台 topic key → Domain 枚举；未知 topic 不信。"""
    if not topic:
        return None
    return _TOPIC_TO_DOMAIN.get(topic.strip().lower())


def _dedupe_sources(sources: list[CanonicalThemeSource]) -> tuple[CanonicalThemeSource, ...]:
    return tuple(dict.fromkeys(sources))


def canonicalize_intent(intent: Intent) -> CanonicalIntent:
    """从现有 scalar Intent 生成 canonical 主题结构。

    现阶段保持执行主链不变：`intent.domain` 仍是当前 Chat/咨询的 scalar
    执行域。若观星台显式给出 `primary_topic`，canonical.primary 表示报告
    问题的主议题；规则/LLM 收敛出的 `intent.domain` 若不同，则作为带来源的
    secondary/context 记录，供未来 Report Compiler 融合。
    """
    report_primary_domain = domain_from_topic(intent.entry_primary_topic)
    if report_primary_domain is None:
        report_primary_domain = domain_from_topic(intent.entry_topic_key)

    primary_domain = report_primary_domain or intent.domain
    primary_sources = [CanonicalThemeSource.RULE]
    if report_primary_domain is not None:
        primary_sources = [CanonicalThemeSource.REPORT_CONTEXT]
        if report_primary_domain is intent.domain:
            primary_sources.append(CanonicalThemeSource.RULE)

    primary = CanonicalTheme(
        domain=primary_domain,
        role=CanonicalThemeRole.PRIMARY,
        subdomain=intent.subdomain if primary_domain is intent.domain else "",
        confidence=(
            intent.domain_confidence
            if primary_domain is intent.domain else 0.65
        ),
        sources=_dedupe_sources(primary_sources),
        rationale=(
            "主题观星台给出的报告主议题；只作报告结构与澄清上下文，不改写 scalar 执行域。"
            if report_primary_domain is not None and primary_domain is not intent.domain
            else "现有 Domain 规则/LLM 受控枚举收敛后的主执行主题。"
        ),
    )

    secondary_by_domain: dict[IntentDomain, CanonicalTheme] = {}

    def add_secondary(
        domain: IntentDomain | None,
        *,
        role: CanonicalThemeRole,
        confidence: float,
        sources: tuple[CanonicalThemeSource, ...],
        rationale: str,
        subdomain: str = "",
    ) -> None:
        if domain is None or domain is primary_domain or domain in secondary_by_domain:
            return
        secondary_by_domain[domain] = CanonicalTheme(
            domain=domain,
            role=role,
            subdomain=subdomain,
            confidence=confidence,
            sources=sources,
            rationale=rationale,
        )

    add_secondary(
        intent.domain,
        role=CanonicalThemeRole.SECONDARY,
        subdomain=intent.subdomain,
        confidence=intent.domain_confidence,
        sources=(CanonicalThemeSource.RULE,),
        rationale="当前 scalar 执行域；保留原有运行链路的 Domain 收敛结果。",
    )

    for topic in intent.entry_secondary_topics:
        add_secondary(
            domain_from_topic(topic),
            role=CanonicalThemeRole.SECONDARY,
            confidence=0.6,
            sources=(CanonicalThemeSource.REPORT_CONTEXT,),
            rationale="主题观星台入口提示的跨主题影响来源；仅作上下文，不产出占星结论。",
        )

    entry_domain = domain_from_topic(intent.entry_topic_key)
    add_secondary(
        entry_domain,
        role=CanonicalThemeRole.CONTEXT,
        confidence=0.5,
        sources=(CanonicalThemeSource.REPORT_CONTEXT,),
        rationale="用户进入观星台时选择的入口主题；不是 hard lock。",
    )

    return CanonicalIntent(
        primary=primary,
        secondary=tuple(secondary_by_domain.values()),
        entry_topic_key=intent.entry_topic_key,
        intent_shape=intent.entry_intent_shape,
        report_type=intent.entry_report_type,
        user_focus_text=intent.entry_user_focus_text or intent.raw_query,
    )
