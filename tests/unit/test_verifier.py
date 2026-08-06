"""验前事测试（B1 学习层 L5）。

验证：
- extract_subject_planet 从判断语句提取主题星
- verify_event 用真实盘（夏天，昼生）在固定日期验证：
  主题星=大限主 → confirmed；=子限主 → confirmed；都不在 → inconclusive
- 诚实原则：缺席 ≠ 证伪（inconclusive 而非 refuted）
- LearningService.record_life_event 端到端：记录事件 + 验证 + 校准 + 落库
- 反馈校准：confirmed/refuted 的置信度增减与上下限
"""

from datetime import datetime, timezone
import zoneinfo

import pytest

from foundation.database.store import GardenStore
from foundation.utils import new_id, utc_now_aware
from shared.enums import HouseSystem, Planet
from shared.models import BirthData, ChartProfile, GeoLocation, Person, VerifiedFinding

from application.learning.service import LearningService
from domain.astrology.calculation import NatalChartCalculator
from domain.learning.verifier import (
    PLANET_ZH_LOOKUP,
    extract_subject_planet,
    verify_all_findings,
    verify_event,
)

#: 夏天盘 @2026-08-04 → 月亮大限 + 火星子限（对齐 test_firdaria.py 黄金测试）
REF = datetime(2026, 8, 4, tzinfo=timezone.utc)


def _person() -> Person:
    return Person(
        id="p_b1", name="测试",
        birth=BirthData(
            datetime(1991, 3, 21, 9, 25, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(35.7, 113.35, timezone_name="Asia/Shanghai", place_name="山西陵川"),
        ),
        house_system=HouseSystem.ALCABITIUS,
    )


@pytest.fixture(scope="module")
def chart():
    return NatalChartCalculator().compute(_person())


def _finding(statement: str, confidence: float = 0.6, fid: str | None = None) -> VerifiedFinding:
    return VerifiedFinding(id=fid or new_id("vf"), statement=statement, confidence=confidence)


# ----------------------------------------------------------------------
# 主题星提取
# ----------------------------------------------------------------------


def test_extract_subject_planet_matches():
    assert extract_subject_planet("土星落九宫：深造是职业跃迁的必经之路") is Planet.SATURN
    assert extract_subject_planet("7宫主金星落10宫：婚姻与事业纠缠") is Planet.VENUS
    assert extract_subject_planet("月亮落7宫，依赖的核心在伴侣") is Planet.MOON


def test_extract_subject_planet_outer_planets():
    assert extract_subject_planet("天王星落11宫：变革进入社群") is Planet.URANUS
    assert extract_subject_planet("海王星落12宫") is Planet.NEPTUNE


def test_extract_subject_planet_none():
    assert extract_subject_planet("深造/远行是你职业跃迁的必经之路") is None
    assert extract_subject_planet("") is None
    assert extract_subject_planet(None) is None


# ----------------------------------------------------------------------
# 事件验证（真实盘 + 固定日期）
# ----------------------------------------------------------------------


def test_verify_event_confirmed_major_lord(chart):
    """主题星=大限主（月亮）→ confirmed。"""
    v = verify_event(chart, REF, _finding("月亮落7宫，依赖的核心在伴侣"))
    assert v.verdict == "confirmed"
    assert v.subject_planet is Planet.MOON
    assert v.matched_lord is Planet.MOON


def test_verify_event_confirmed_sub_lord(chart):
    """主题星=子限主（火星）→ confirmed。"""
    v = verify_event(chart, REF, _finding("火星落5宫：心动时热烈而直接"))
    assert v.verdict == "confirmed"
    assert v.matched_lord is Planet.MARS


def test_verify_event_inconclusive_absent_lord(chart):
    """主题星不是当前时间领主（土星）→ inconclusive，绝不 refuted。"""
    v = verify_event(chart, REF, _finding("土星落九宫：深造是必经之路"))
    assert v.verdict == "inconclusive"
    assert v.matched_lord is None


def test_verify_event_no_extraction_inconclusive(chart):
    v = verify_event(chart, REF, _finding("深造/远行是职业跃迁的必经之路"))
    assert v.verdict == "inconclusive"
    assert v.subject_planet is None


def test_verify_all_findings_batch(chart):
    findings = [
        _finding("月亮落7宫", fid="f_moon"),
        _finding("土星落九宫", fid="f_saturn"),
        _finding("说不清主题", fid="f_na"),
    ]
    results = verify_all_findings(chart, REF, findings)
    assert [r.verdict for r in results] == ["confirmed", "inconclusive", "inconclusive"]


# ----------------------------------------------------------------------
# LearningService：验前事端到端
# ----------------------------------------------------------------------


def _make_service(store: GardenStore) -> LearningService:
    return LearningService(store, chart_provider=lambda p: NatalChartCalculator().compute(p))


def _save_profile_with(store: GardenStore, person_id: str, findings: list[VerifiedFinding]):
    now = utc_now_aware()
    prof = ChartProfile(person_id=person_id, created_at=now, updated_at=now)
    prof.verified_findings = findings
    store.save_profile(prof)
    return prof


def test_record_life_event_verifies_and_calibrates():
    store = GardenStore(":memory:")
    service = _make_service(store)
    person = _person()

    moon_finding = _finding("月亮落7宫，依赖的核心在伴侣", confidence=0.6, fid="f1")
    _save_profile_with(store, person.id, [moon_finding])

    result = service.record_life_event(person, "和伴侣领证", REF)
    assert result["calibrated"] is True
    assert result["period_major"] == "moon"
    assert result["verifications"][0]["verdict"] == "confirmed"

    # 置信度被校准 +0.1，痕迹落库
    profile = store.get_profile(person.id)
    f = profile.verified_findings[0]
    assert f.confidence == 0.7
    assert f.confirmed_at is not None
    assert any("领证" in n and "验证通过" in n for n in f.verification_notes)

    # 人生事件落库（时间轴可见）
    events = store.list_life_events(person.id)
    assert len(events) == 1
    assert events[0].kind == "life"
    assert events[0].label == "和伴侣领证"


def test_record_life_event_no_match_no_calibration():
    store = GardenStore(":memory:")
    service = _make_service(store)
    person = _person()
    _save_profile_with(store, person.id, [_finding("土星落九宫：深造是必经之路", fid="f2")])

    result = service.record_life_event(person, "出国旅行", REF)
    assert result["calibrated"] is False
    assert result["verifications"][0]["verdict"] == "inconclusive"

    profile = store.get_profile(person.id)
    assert profile.verified_findings[0].confidence == 0.6  # 未确认不动
    assert profile.verified_findings[0].verification_notes == []


def test_record_life_event_before_birth_raises():
    store = GardenStore(":memory:")
    service = _make_service(store)
    person = _person()
    with pytest.raises(ValueError):
        service.record_life_event(person, "无效事件", datetime(1990, 1, 1, tzinfo=timezone.utc))


def test_record_life_event_without_profile_records_event():
    """没咨询过（无画像）也能记事件——验前事为空但不报错。"""
    store = GardenStore(":memory:")
    service = _make_service(store)
    person = _person()

    result = service.record_life_event(person, "辞职", REF)
    assert result["calibrated"] is False
    assert result["verifications"] == []
    assert store.list_life_events(person.id)[0].label == "辞职"


# ----------------------------------------------------------------------
# 反馈校准
# ----------------------------------------------------------------------


def test_calibrate_from_feedback_deltas():
    store = GardenStore(":memory:")
    service = _make_service(store)
    profile = _save_profile_with(store, "p", [_finding("土星落九宫", confidence=0.6, fid="f1")])
    f = profile.verified_findings[0]

    assert service.calibrate_from_feedback(profile, f, "confirmed")["new_confidence"] == 0.75
    assert service.calibrate_from_feedback(profile, f, "refuted")["new_confidence"] == 0.6


def test_calibrate_from_feedback_caps():
    store = GardenStore(":memory:")
    service = _make_service(store)
    profile = _save_profile_with(store, "p", [_finding("土星落九宫", confidence=0.95, fid="f1")])
    assert service.calibrate_from_feedback(profile, profile.verified_findings[0], "confirmed")["new_confidence"] == 0.95

    profile2 = _save_profile_with(store, "p2", [_finding("土星落九宫", confidence=0.1, fid="f2")])
    assert service.calibrate_from_feedback(profile2, profile2.verified_findings[0], "refuted")["new_confidence"] == 0.1


def test_planet_zh_lookup_complete():
    """主题星中文名映射覆盖 10 星，供验证痕迹/返回用。"""
    assert PLANET_ZH_LOOKUP[Planet.MOON] == "月亮"
    assert PLANET_ZH_LOOKUP[Planet.SATURN] == "土星"
    assert len(PLANET_ZH_LOOKUP) == 10
