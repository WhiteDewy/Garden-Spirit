"""Domain-owned canonical intent 防回归。"""

from shared.enums import IntentDomain
from shared.models import Intent

from domain.reasoning.intent import (
    CanonicalThemeRole,
    CanonicalThemeSource,
    IntentDecomposer,
    canonicalize_intent,
    domain_from_topic,
)


def _intent(**overrides) -> Intent:
    data = {
        "id": "intent_test",
        "raw_query": "我想看和母亲的关系对我事业的影响",
        "domain": IntentDomain.FAMILY,
        "subdomain": "",
        "domain_confidence": 0.9,
        "entry_source": "observatory",
        "entry_topic_key": "career",
        "entry_primary_topic": "career",
        "entry_secondary_topics": ["family"],
        "entry_intent_shape": "cross_topic_influence",
        "entry_report_type": "theme",
        "entry_user_focus_text": "我想看和母亲的关系对我事业的影响",
    }
    data.update(overrides)
    return Intent(**data)


def test_domain_from_topic_accepts_only_known_topics():
    assert domain_from_topic("career") is IntentDomain.CAREER
    assert domain_from_topic("study") is IntentDomain.LEARNING
    assert domain_from_topic("made_up") is None


def test_canonical_intent_keeps_report_primary_and_scalar_domain_separate():
    canonical = canonicalize_intent(_intent())

    assert canonical.primary.domain is IntentDomain.CAREER
    assert canonical.primary.role is CanonicalThemeRole.PRIMARY
    assert canonical.primary.sources == (CanonicalThemeSource.REPORT_CONTEXT,)
    assert canonical.entry_topic_key == "career"
    assert canonical.intent_shape == "cross_topic_influence"
    assert canonical.report_type == "theme"
    assert canonical.user_focus_text == "我想看和母亲的关系对我事业的影响"

    secondary = {theme.domain: theme for theme in canonical.secondary}
    assert set(secondary) == {IntentDomain.FAMILY}
    assert secondary[IntentDomain.FAMILY].role is CanonicalThemeRole.SECONDARY
    assert secondary[IntentDomain.FAMILY].sources == (CanonicalThemeSource.RULE,)
    assert "scalar 执行域" in secondary[IntentDomain.FAMILY].rationale


def test_canonical_intent_ignores_unknown_report_topics():
    canonical = canonicalize_intent(_intent(
        domain=IntentDomain.WEALTH,
        entry_topic_key="unknown",
        entry_primary_topic="unknown",
        entry_secondary_topics=["made_up", "family"],
    ))

    assert canonical.primary.domain is IntentDomain.WEALTH
    assert canonical.primary.sources == (CanonicalThemeSource.RULE,)
    assert [theme.domain for theme in canonical.secondary] == [IntentDomain.FAMILY]


def test_decomposer_attaches_canonical_without_changing_tasks():
    intent = _intent(domain=IntentDomain.FAMILY)
    result = IntentDecomposer(llm_client=None).decompose(intent)

    assert result.intent is intent
    assert result.canonical is not None
    assert result.canonical.primary.domain is IntentDomain.CAREER
    assert result.domain is IntentDomain.FAMILY
    assert result.merged_tasks
