"""ConclusionBuilder —— 从 Evidence 生成结构化的领域结论。

完全无 LLM：summary、findings、recommendations 都由确定性模板生成。
Conversation 层负责用人格 + LLM 转述，但绝不改变这里的内容。
"""

from __future__ import annotations

from datetime import datetime

from foundation.utils import new_id
from shared.enums import ConclusionCategory, EvidencePolarity, Verdict
from shared.models import (
    Conclusion,
    EvidenceSet,
    Finding,
    Intent,
    TimePeriod,
)

_VERDICT_SUMMARY = {
    Verdict.FAVORABLE: "盘面总体支持，条件有利。",
    Verdict.UNFAVORABLE: "盘面存在明显阻力，需谨慎对待。",
    Verdict.NEUTRAL: "支持与阻力并存，方向不明确。",
    Verdict.NEEDS_MORE_DATA: "信息不足，尚无法形成明确判断。",
}

_VERDICT_RECOMMENDATION = {
    Verdict.FAVORABLE: ["可积极推进，但仍需结合现实条件做决定。"],
    Verdict.UNFAVORABLE: ["建议暂缓，先解决盘面上显示的主要障碍。"],
    Verdict.NEUTRAL: ["建议同时评估两面，不宜急于下结论。"],
    Verdict.NEEDS_MORE_DATA: ["补充更准确的出生时间，或提供更多背景信息后重问。"],
}

_MAX_FINDINGS = 6


class ConclusionBuilder:
    """从 EvidenceSet 组装 Conclusion。"""

    def populate(
        self,
        conclusion: Conclusion,
        evidence_set: EvidenceSet,
        intent: Intent,
        verdict: Verdict,
        net_score: float,
        failed_core_modules: list[str] | None = None,
    ) -> None:
        """填充结论的 findings / summary / recommendations。"""
        all_items = evidence_set.all_evidence
        # 描述性解读：主题自带 descriptive 标记，或多数证据为中性
        theme_descriptive = any(
            e.metadata.get("descriptive") for e in all_items
        )
        descriptive = theme_descriptive or (
            bool(all_items)
            and len(evidence_set.neutral_evidence) / len(all_items) > 0.6
        )
        if descriptive:
            conclusion.metadata["descriptive"] = True

        conclusion.findings = self._build_findings(evidence_set, descriptive)
        conclusion.summary = self._summary(verdict, intent, descriptive)
        conclusion.recommendations = (
            [] if descriptive else list(_VERDICT_RECOMMENDATION[verdict])
        )

        # 时间窗口（Timing 模块的 window 证据）
        conclusion.time_periods = self._extract_time_periods(evidence_set)

        # 数据缺口：出生时间精度不足等
        conclusion.data_gaps = self._data_gaps(intent)

        # 核心模块失败 → 明确提示，不硬造结论
        for module in failed_core_modules or []:
            conclusion.data_gaps.append(f"核心分析模块 {module} 尚未启用，此问题的判断不完整")

    @staticmethod
    def _extract_time_periods(evidence_set: EvidenceSet) -> list[TimePeriod]:
        """从带 window_start/window_end 的证据提取时间窗口。"""
        periods: list[TimePeriod] = []
        for e in evidence_set.all_evidence:
            start = e.metadata.get("window_start")
            end = e.metadata.get("window_end")
            if not start or not end:
                continue
            try:
                periods.append(
                    TimePeriod(
                        label=f"{start[:7]} 至 {end[:7]}",
                        start=datetime.fromisoformat(start),
                        end=datetime.fromisoformat(end),
                        quality=e.polarity,
                        key_events=[e.reasoning],
                    )
                )
            except ValueError:
                continue
        return periods

    # ------------------------------------------------------------------

    def _build_findings(self, evidence_set: EvidenceSet, descriptive: bool = False) -> list[Finding]:
        """生成 findings。

        - descriptive（描述性解读）：每条解读独立成条（不折叠），按权重排序。
        - 否则：按主题聚合，取代表性证据。
        """
        if descriptive:
            findings: list[Finding] = []
            seen: set[str] = set()
            for e in evidence_set.all_evidence:
                key = str(e.metadata.get("rule_id") or e.reasoning)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    Finding(
                        id=new_id("finding"),
                        category=ConclusionCategory.SUMMARY,
                        text=e.reasoning,
                        polarity=e.polarity,
                        confidence=e.confidence,
                        supporting_evidence_ids=[e.id],
                        weight=e.weight * e.confidence,
                    )
                )
            findings.sort(key=lambda f: abs(f.weight), reverse=True)
            return findings[:_MAX_FINDINGS]

        by_theme: dict[str, list] = {}
        for e in evidence_set.all_evidence:
            theme = str(e.metadata.get("theme", e.analysis_module))
            by_theme.setdefault(theme, []).append(e)

        findings = []
        for theme, items in by_theme.items():
            if not items:
                continue
            net = sum(
                e.weight * e.confidence
                * (1 if e.polarity == EvidencePolarity.POSITIVE
                   else -1 if e.polarity == EvidencePolarity.NEGATIVE else 0)
                for e in items
            )
            # 代表性证据：优先选"主题总结"（含 score 元数据的聚合事实）
            strongest = max(
                items,
                key=lambda e: (
                    e.metadata.get("score") is not None,
                    abs(e.weight) * e.confidence,
                ),
            )
            polarity = (
                EvidencePolarity.POSITIVE if net > 0
                else EvidencePolarity.NEGATIVE if net < 0
                else EvidencePolarity.NEUTRAL
            )
            findings.append(
                Finding(
                    id=new_id("finding"),
                    category=self._category(polarity),
                    text=strongest.reasoning,
                    polarity=polarity,
                    confidence=strongest.confidence,
                    supporting_evidence_ids=[e.id for e in items],
                    weight=net,
                )
            )

        findings.sort(key=lambda f: abs(f.weight), reverse=True)
        return findings[:_MAX_FINDINGS]

    @staticmethod
    def _category(polarity: EvidencePolarity) -> ConclusionCategory:
        if polarity == EvidencePolarity.POSITIVE:
            return ConclusionCategory.FINDING
        if polarity == EvidencePolarity.NEGATIVE:
            return ConclusionCategory.WARNING
        return ConclusionCategory.SUMMARY

    @staticmethod
    def _summary(verdict: Verdict, intent: Intent, descriptive: bool = False) -> str:
        domain_label = intent.domain.value
        if descriptive:
            return f"这是关于{domain_label}的一份倾向解读——说的是'你的模式'，没有绝对的好坏"
        return f"关于{domain_label}的询问：{_VERDICT_SUMMARY[verdict]}"

    @staticmethod
    def _data_gaps(intent: Intent) -> list[str]:
        gaps: list[str] = []
        # 出生时间精度由 Person 提供，Intent 本身不携带；此处留接口
        return gaps
