"""意图层 —— 领域规则判定（原则三）+ LLM 深度理解（Layer 1）。

LLM 只抽槽 + 映射占星结构，领域规则定归属。
"""

from domain.reasoning.intent.rules import IntentRouter, IntentRule
from domain.reasoning.intent.canonical import (
    CanonicalIntent,
    CanonicalTheme,
    CanonicalThemeRole,
    CanonicalThemeSource,
    canonicalize_intent,
    domain_from_topic,
)
from domain.reasoning.intent.decomposer import (
    AnalysisTask,
    DecomposedIntent,
    IntentDecomposer,
)

__all__ = [
    "IntentRouter",
    "IntentRule",
    "CanonicalIntent",
    "CanonicalTheme",
    "CanonicalThemeRole",
    "CanonicalThemeSource",
    "canonicalize_intent",
    "domain_from_topic",
    "IntentDecomposer",
    "DecomposedIntent",
    "AnalysisTask",
]
