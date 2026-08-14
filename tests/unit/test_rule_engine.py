"""解读文法引擎测试：RuleEngine + 规则词库。"""

from datetime import datetime
import zoneinfo

import pytest

from domain.analysis import PartnerTraits
from domain.astrology.calculation import NatalChartCalculator
from domain.astrology.evidence import RuleEngine
from domain.astrology.knowledge import load_knowledge
from shared.enums import EvidencePolarity, Planet
from shared.models import BirthData, GeoLocation, Person


@pytest.fixture(scope="module")
def chart():
    person = Person(
        id="p_rules",
        name="规则测试",
        birth=BirthData(
            datetime(1990, 6, 15, 9, 30, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(31.2304, 121.4737, timezone_name="Asia/Shanghai", place_name="上海"),
        ),
    )
    return NatalChartCalculator().compute(person)


def test_rules_loaded():
    kb = load_knowledge()
    # planet_pairs 含 _fallback + 16 条专条
    assert len([k for k in kb.planet_pairs if k != "_fallback"]) >= 16
    # planet_in_house 全量覆盖：10 行星 × 12 宫 = 120
    assert len([k for k in kb.planet_in_house_rules if k != "_fallback"]) >= 120
    assert len(kb.house_lord_rules) >= 60  # 5 lords × 12 houses + fallback
    assert "partner_traits" in kb.theme_map
    assert "_fallback" in kb.planet_in_house_rules
    assert "_fallback" in kb.planet_pairs


def test_planet_in_house_full_coverage():
    """10 行星 × 12 宫全部有专条（保证任何落宫都有词义，不依赖 fallback）。"""
    kb = load_knowledge()
    planets = ["sun", "moon", "mercury", "venus", "mars", "jupiter",
               "saturn", "uranus", "neptune", "pluto"]
    for p in planets:
        got = {int(k.split("_")[1]) for k in kb.planet_in_house_rules if k.startswith(f"{p}_")}
        assert got == set(range(1, 13)), f"{p} 缺少宫位: {set(range(1,13)) - got}"


def test_interpret_planet_in_house_specific(chart):
    """演示用户：金星落10宫 → 命中 venus_10 专条。"""
    engine = RuleEngine()
    interps = engine.interpret_planet_in_house(chart, Planet.VENUS, "partner_traits")
    assert len(interps) == 1
    assert interps[0].rule_id == "planet_in_house:venus_10"
    assert interps[0].polarity == EvidencePolarity.NEUTRAL  # 落宫是描述
    assert "名分" in interps[0].core_insight  # 带刺内容


def test_interpret_planet_pair_has_rule_id(chart):
    """火星-月亮：命中有相位 → 产出带 rule_id 的解读。"""
    engine = RuleEngine()
    interps = engine.interpret_planet_pair(chart, Planet.MARS, Planet.MOON, "partner_traits")
    assert len(interps) >= 1
    assert interps[0].rule_id.startswith("planet_pair:mars_moon:")
    assert "身体磁力" in interps[0].core_insight or "激情" in interps[0].core_insight
    # 极性由相位性质决定，不可能是空
    assert interps[0].polarity in (EvidencePolarity.POSITIVE, EvidencePolarity.NEGATIVE, EvidencePolarity.NEUTRAL)


def test_interpret_house_lord_7th(chart):
    """演示用户 7宫主落6宫 → 命中 house_lord:7_6。"""
    engine = RuleEngine()
    interps = engine.interpret_house_lord(chart, 7, "partner_traits")
    assert len(interps) == 1
    assert interps[0].rule_id == "house_lord:7_6"
    assert "工作" in interps[0].core_insight


def test_run_theme_partner_traits(chart):
    """主题编排：partner_traits 产出多条带 rule_id 的解读。"""
    engine = RuleEngine()
    facts = engine.run_theme(chart, "partner_traits")
    assert len(facts) >= 5
    assert all(f.payload.get("rule_id") for f in facts)
    themes = {f.payload["theme"] for f in facts}
    assert "romantic_spark" in themes or "committed_partner" in themes


def test_partner_traits_module(chart):
    facts = PartnerTraits().analyze(chart, None, {})
    assert len(facts) >= 5
    assert all(f.payload.get("rule_id") for f in facts)


def test_run_theme_uses_domain_signals_not_theme_core_planets(chart):
    """R9：theme_map.core_planets 即使残留，也不能作为第二真相源驱动主题编排。"""
    kb = load_knowledge()
    recipe = dict(kb.theme_map["wealth"])
    recipe["core_planets"] = ["moon"]
    recipe["aspect_pairs"] = []
    recipe["house_lords"] = []
    recipe["rules"] = ["planet_in_house"]
    kb.theme_map["_r9_stale_core_planets"] = recipe

    facts = RuleEngine(kb).run_theme(chart, "_r9_stale_core_planets")
    rule_ids = {f.payload["rule_id"] for f in facts}
    assert any(rule_id.startswith("planet_in_house:venus_") for rule_id in rule_ids)
    assert any(rule_id.startswith("planet_in_house:jupiter_") for rule_id in rule_ids)
    assert not any(rule_id.startswith("planet_in_house:moon_") for rule_id in rule_ids)


# ---------------------------------------------------------------------------
# fallback 机制：未录入词库的行星对不静默丢弃
# ---------------------------------------------------------------------------


def test_planet_pair_fallback_produces_evidence(chart):
    """所有 45 对行星都在词库中，不走 fallback——但 _fallback 模板仍在（防御性）。"""
    engine = RuleEngine()
    kb = load_knowledge()
    assert "_fallback" in kb.planet_pairs
    # fallback 模板有 base/harmonious/dynamic 三个字段
    fb = kb.planet_pairs["_fallback"]
    assert "base" in fb
    assert "harmonious" in fb
    assert "dynamic" in fb
    # 所有真实行星对走专条，非 fallback
    interps = engine.interpret_planet_pair(chart, Planet.SUN, Planet.NEPTUNE)
    for i in interps:
        assert "fallback" not in i.rule_id, f"sun-neptune 应有专条: {i.rule_id}"


def test_planet_pair_fallback_confidence_lower(chart):
    """所有 45 对都有专条——验证专条置信度高于 fallback 最低值。"""
    engine = RuleEngine()
    interps = engine.interpret_planet_pair(chart, Planet.MARS, Planet.MOON)
    if interps:
        # 专条置信度应高于 fallback 可能的最低值
        assert interps[0].confidence > 0.4, f"专条置信度过低: {interps[0].confidence}"


def test_planet_pair_fallback_rule_id():
    """45 对行星全覆盖：每对都在词库中（不含 _fallback 本身）。"""
    kb = load_knowledge()
    pairs = {k for k in kb.planet_pairs if k != "_fallback"}
    assert len(pairs) == 45, f"期望 45 对，实际 {len(pairs)}"
    # 验证 _fallback 仍存在（防御性：防止未来新增行星时词库缺条目）
    assert "_fallback" in kb.planet_pairs


def test_planet_pair_known_pair_still_works(chart):
    """已录入的行星对（venus_mars）不受 fallback 影响。"""
    engine = RuleEngine()
    interps = engine.interpret_planet_pair(chart, Planet.VENUS, Planet.MARS)
    # 如果有相位，rule_id 应不含 fallback
    for i in interps:
        assert "fallback" not in i.rule_id, f"专条不应走 fallback: {i.rule_id}"


def test_house_lord_fallback(chart):
    """2宫主落宫——现在有专条覆盖，直接命中。"""
    engine = RuleEngine()
    interps = engine.interpret_house_lord(chart, 2)
    assert len(interps) >= 1
    assert interps[0].rule_id.startswith("house_lord:2_")
    # 专条不走 fallback
    assert "fallback" not in interps[0].rule_id
