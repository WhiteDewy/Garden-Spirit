"""Evidence Builder —— 把 Facts 转成加权 Evidence。

**原则三防火墙**：极性与权重完全由知识库（dignity/aspect/reception 的 YAML）
+ 本模块的确定性规则决定，与 LLM 无关。

通用规则（所有意图共享）：
- DIGNITY 事实   → 极性 = 分值符号，权重 = |分值|；若同时给出 essential_pos/essential_neg，则本质轴吉凶并见优先保留受克
- ASPECT 事实    → 极性 = 相位性质（吉/凶/中性），权重 = weight_multiplier，入相加成
- RECEPTION 事实 → 极性 = 正，权重 = 互容分
- THEME 事实     → 由分析模块写入 weight/polarity，本模块直接采纳（分析模块必须来自 Domain）
- 其余（POSITION/HOUSE）→ 中性，供分析模块组合
"""

from __future__ import annotations

from datetime import datetime, timezone

from foundation.config import EvidenceConfig
from foundation.utils import new_id
from shared.enums import (
    AspectApplication,
    DignityState,
    EvidenceConfidence,
    EvidencePolarity,
    FactCategory,
)
from shared.models import Evidence, EvidenceSet, Fact, FactSet

from domain.astrology.knowledge.loader import KnowledgeBase

from .confidence import ConfidenceEngine

# 相位入相加成
_APPLYING_BONUS = 1.2
_SEPARATING_PENALTY = 0.8


class EvidenceBuilder:
    """通用 Facts → Evidence 转换。"""

    def __init__(
        self,
        kb: KnowledgeBase,
        confidence: ConfidenceEngine | None = None,
        config: EvidenceConfig | None = None,
    ):
        self._kb = kb
        self._config = config or EvidenceConfig()
        self._confidence = confidence or ConfidenceEngine(config)

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def build(
        self,
        fact_set: FactSet,
        domain: str,
        query_context: str,
        evidence_rules: dict | None = None,
    ) -> EvidenceSet:
        """FactSet → EvidenceSet。"""
        rules = evidence_rules or {}
        items: list[Evidence] = []
        for fact in fact_set.facts:
            item = self._evidence_from_fact(fact, domain, rules)
            if item is not None and item.confidence >= self._config.min_confidence:
                items.append(item)

        positive = [e for e in items if e.polarity == EvidencePolarity.POSITIVE]
        negative = [e for e in items if e.polarity == EvidencePolarity.NEGATIVE]
        neutral = [e for e in items if e.polarity == EvidencePolarity.NEUTRAL]

        evidence_set = EvidenceSet(
            id=new_id("evidence"),
            fact_set_id=fact_set.id,
            domain=domain,
            query_context=query_context,
            positive_evidence=positive,
            negative_evidence=negative,
            neutral_evidence=neutral,
            generated_at=datetime.now(timezone.utc),
        )
        # 冲突检测与消解
        evidence_set.conflicts = self._confidence.detect_conflicts(evidence_set)
        evidence_set.resolved_conflicts = self._confidence.resolve_all(evidence_set)
        return evidence_set

    # ------------------------------------------------------------------
    # 单条转换
    # ------------------------------------------------------------------

    def _evidence_from_fact(
        self, fact: Fact, domain: str, rules: dict
    ) -> Evidence | None:
        category = fact.category

        if category == FactCategory.DIGNITY:
            return self._dignity_evidence(fact, domain)
        if category == FactCategory.ASPECT:
            return self._aspect_evidence(fact, domain)
        if category == FactCategory.RECEPTION:
            return self._reception_evidence(fact, domain)
        if category == FactCategory.THEME:
            return self._theme_evidence(fact, domain, rules)
        # POSITION/HOUSE 等：默认中性，留给分析模块组合
        return None

    def _dignity_evidence(self, fact: Fact, domain: str) -> Evidence | None:
        state = fact.payload.get("dignity")
        score = int(fact.payload.get("score", 0))
        essential_pos = float(fact.payload.get("essential_pos", 0.0))
        essential_neg = float(fact.payload.get("essential_neg", 0.0))
        if essential_pos > 0 and essential_neg > 0 and score > 0:
            score = -int(round(essential_neg / 0.35))
        if state is None:
            return None

        if score == 0 or state == DignityState.PEREGRINE.value:
            polarity = EvidencePolarity.NEUTRAL
            weight = 0.0
        else:
            polarity = EvidencePolarity.POSITIVE if score > 0 else EvidencePolarity.NEGATIVE
            weight = float(abs(score))

        # 入庙/曜升置信度更高；陷/弱同样明确
        confidence = 0.85 if state in (DignityState.DOMICILE.value, DignityState.EXALTATION.value) else 0.75
        if state in (DignityState.DETRIMENT.value, DignityState.FALL.value):
            confidence = 0.7

        return Evidence(
            id=new_id("ev"),
            fact_id=fact.id,
            polarity=polarity,
            weight=weight,
            confidence=confidence,
            evidence_confidence=self._confidence.bucket(confidence),
            domain=domain,
            analysis_module=str(fact.payload.get("module", "evidence")),
            reasoning=f"{fact.description}",
            generated_at=fact.extracted_at,
            metadata={
                "subject": f"planet:{fact.payload.get('planet')}",
                "planet": fact.payload.get("planet"),
                "theme": str(fact.payload.get("theme", "dignity")),
                "source_quality": "essential",
            },
        )

    def _aspect_evidence(self, fact: Fact, domain: str) -> Evidence | None:
        aspect_type = fact.payload.get("aspect")
        info = self._kb.aspects.get(aspect_type) if aspect_type else None
        if info is None:
            return None

        nature = info.nature  # HARMONIOUS / DYNAMIC / NEUTRAL
        if nature == "HARMONIOUS":
            polarity = EvidencePolarity.POSITIVE
        elif nature == "DYNAMIC":
            polarity = EvidencePolarity.NEGATIVE
        else:
            polarity = EvidencePolarity.NEUTRAL

        weight = info.weight_multiplier
        applying = fact.payload.get("applying")
        if applying == AspectApplication.APPLYING.value:
            weight *= _APPLYING_BONUS
        elif applying == AspectApplication.SEPARATING.value:
            weight *= _SEPARATING_PENALTY

        orb = float(fact.payload.get("orb", 1.0))
        # 容许度越小越确定
        confidence = max(0.4, min(0.9, 0.9 - orb * 0.05))

        return Evidence(
            id=new_id("ev"),
            fact_id=fact.id,
            polarity=polarity,
            weight=weight,
            confidence=confidence,
            evidence_confidence=self._confidence.bucket(confidence),
            domain=domain,
            analysis_module=str(fact.payload.get("module", "evidence")),
            reasoning=f"{fact.description}",
            generated_at=fact.extracted_at,
            metadata={
                "subject": f"aspect:{fact.payload.get('body1')}-{fact.payload.get('body2')}",
                "theme": str(fact.payload.get("theme", "aspect")),
                "source_quality": "pattern",
            },
        )

    def _reception_evidence(self, fact: Fact, domain: str) -> Evidence | None:
        score = int(fact.payload.get("score", 0))
        if score <= 0:
            return None
        return Evidence(
            id=new_id("ev"),
            fact_id=fact.id,
            polarity=EvidencePolarity.POSITIVE,
            weight=float(score),
            confidence=0.8,
            evidence_confidence=EvidenceConfidence.HIGH,
            domain=domain,
            analysis_module="evidence",
            reasoning=f"{fact.description}",
            generated_at=fact.extracted_at,
            metadata={
                "subject": f"reception:{fact.payload.get('planet_a')}-{fact.payload.get('planet_b')}",
                "source_quality": "essential",
            },
        )

    def _theme_evidence(self, fact: Fact, domain: str, rules: dict) -> Evidence | None:
        """分析模块直接写入的证据化事实（THEME 类别）。

        分析模块必须来自 Domain（原则三），它们写入的 polarity/weight/confidence
        被视为领域规则输出。
        """
        polarity_raw = fact.payload.get("polarity")
        if polarity_raw is None:
            return None
        polarity = EvidencePolarity(polarity_raw)
        weight = float(fact.payload.get("weight", 0.0))
        confidence = float(fact.payload.get("confidence", 0.7))
        theme = str(fact.payload.get("theme", "general"))

        return Evidence(
            id=new_id("ev"),
            fact_id=fact.id,
            polarity=polarity,
            weight=weight,
            confidence=confidence,
            evidence_confidence=self._confidence.bucket(confidence),
            domain=domain,
            analysis_module=str(fact.payload.get("module", "analysis")),
            reasoning=f"{fact.description}",
            generated_at=fact.extracted_at,
            metadata={
                "subject": theme,
                "theme": theme,
                **fact.payload,
            },
        )
