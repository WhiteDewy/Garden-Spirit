"""星灵推荐引擎测试：三轴评分（行运活跃 + 近期共振 + 长期课题）+ API 端点。

用"夏天"真实盘（昼生）验证确定性：
- 法达大限主 = 月亮、子限主 = 火星（对齐 test_firdaria 的宫神星网参考）。
- 行运相位用 10 行星全当行运体（显式传参，不动 TransitCalculator 默认外行星集）。
"""

from datetime import datetime, timezone
import zoneinfo

import pytest
from fastapi.testclient import TestClient

from domain.astrology.calculation import NatalChartCalculator
from domain.timeline.spirit_recommender import PlanetActivationScore, score_spirits
from shared.constants import PLANETS_IN_ORDER
from shared.enums import HouseSystem, Planet
from shared.models import BirthData, ChartProfile, GeoLocation, Person

from application.api.main import create_app
from foundation.config import AppConfig

REF = datetime(2026, 8, 4, tzinfo=timezone.utc)  # 与 test_firdaria 同参考：月亮大限+火星子限


def _person(hour: int = 9, minute: int = 25) -> Person:
    """夏天：1991-03-21 09:25 山西陵川（昼生，Alcabitius）。"""
    return Person(
        id="p_spirit",
        name="测试",
        birth=BirthData(
            datetime(1991, 3, 21, hour, minute, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(35.7, 113.35, timezone_name="Asia/Shanghai", place_name="山西陵川"),
        ),
        house_system=HouseSystem.ALCABITIUS,
    )


@pytest.fixture(scope="module")
def chart():
    return NatalChartCalculator().compute(_person())


def _scores(chart, fragment_depths=None):
    return score_spirits(
        chart, REF, 35.7, 113.35, HouseSystem.ALCABITIUS,
        fragment_depths=fragment_depths,
    )


# ----------------------------------------------------------------------
# Domain 三轴评分
# ----------------------------------------------------------------------


def test_returns_all_ten_planets(chart):
    scores = _scores(chart)
    assert len(scores) == 10
    present = {s.planet for s in scores}
    assert present == set(PLANETS_IN_ORDER)
    assert all(isinstance(s, PlanetActivationScore) for s in scores)


def test_scores_sorted_descending(chart):
    scores = _scores(chart)
    values = [s.score for s in scores]
    assert values == sorted(values, reverse=True)


def test_scores_non_negative(chart):
    scores = _scores(chart)
    assert all(s.score >= 0.0 for s in scores)
    assert all(s.transit_score >= 0.0 for s in scores)
    assert all(s.resonance_score >= 0.0 for s in scores)


def test_firdaria_flags_moon_major_mars_sub(chart):
    """确定性锚点：月亮大限主 + 火星子限主（宫神星网参考，对齐 test_firdaria）。"""
    scores = _scores(chart)
    by_planet = {s.planet: s for s in scores}
    assert by_planet[Planet.MOON].is_firdaria_major_lord is True
    assert by_planet[Planet.MARS].is_firdaria_sub_lord is True
    assert by_planet[Planet.SUN].is_firdaria_major_lord is False
    # 法达领主写在理由里（可解释）
    moon_reasons = "".join(by_planet[Planet.MOON].reason_parts)
    assert "法达" in moon_reasons
    mars_reasons = "".join(by_planet[Planet.MARS].reason_parts)
    assert "法达" in mars_reasons


def test_reasons_are_chinese_explainable(chart):
    """理由可追溯：命中的行星必有"行运X相位你本命Y"式中文说明。"""
    scores = _scores(chart)
    active = [s for s in scores if s.transit_count > 0]
    assert active, "行运活跃行星不应为零"
    for s in active:
        joined = "".join(s.reason_parts)
        assert "行运" in joined or "法达" in joined or "角宫" in joined


def test_transit_axis_differentiates(chart):
    """行运轴有区分度：不应全员拍平在满分级（cap 15 保住梯度）。"""
    scores = _scores(chart)
    transit_vals = {s.transit_score for s in scores}
    assert len(transit_vals) >= 2


def test_moon_always_present(chart):
    """月亮兜底星：无论分数如何，都在推荐列表里（is_default 在 API 层标注）。"""
    scores = _scores(chart)
    assert any(s.planet == Planet.MOON for s in scores)


def test_empty_fragments_no_crash(chart):
    scores = _scores(chart, fragment_depths=None)
    assert len(scores) == 10
    assert all(s.resonance_score == 0.0 for s in scores)


def test_fragment_resonance_boosts_score(chart):
    """近期共振：moon_tide 深度 8 → 月亮共振轴 8.0，且综合分严格抬高。"""
    baseline = {s.planet: s.score for s in _scores(chart)}
    boosted = _scores(chart, fragment_depths={"moon_tide": 8})
    by_planet = {s.planet: s for s in boosted}
    assert by_planet[Planet.MOON].resonance_score == pytest.approx(8.0)
    assert by_planet[Planet.MOON].score > baseline[Planet.MOON]
    # 共振只影响本星，不影响别星
    assert by_planet[Planet.SATURN].score == pytest.approx(baseline[Planet.SATURN])


def test_unknown_fragment_key_ignored(chart):
    """未知子类 key（如 gem 老宝石区）不应炸，只是不共振。"""
    scores = _scores(chart, fragment_depths={"moon_tide": 5, "gem_unknown": 99})
    assert len(scores) == 10


# ----------------------------------------------------------------------
# API 端点
# ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    config = AppConfig()
    config.storage.db_path = ":memory:"
    app = create_app(config)
    with TestClient(app) as c:
        yield c


def _payload() -> dict:
    # 出生地用离线静态表内的城市（CI 无网）；坐标差异不影响结构断言
    return {
        "name": "盘主",
        "birth": {
            "datetime_local": "1991-03-21T09:25:00",
            "location": {"place_name": "上海"},
            "time_known": True,
        },
        "house_system": "B",  # Alcabitius（pyswisseph 单字母码）
    }


def _create_owner(client) -> str:
    return client.post("/person", json=_payload()).json()["id"]


def test_endpoint_returns_ten_spirits(client):
    pid = _create_owner(client)
    resp = client.get(f"/person/{pid}/recommended-spirits")
    assert resp.status_code == 200
    data = resp.json()
    spirits = data["spirits"]
    assert len(spirits) == 10
    assert data["generated_at"]
    # 字段契约齐全
    for s in spirits:
        assert s["planet"]
        assert s["name"]
        assert s["healing_name"]
        assert isinstance(s["score"], float)
        assert isinstance(s["reason"], str)
        assert isinstance(s["is_default"], bool)


def test_moon_default_flag(client):
    """月亮=兜底星：is_default 只在月亮上，且名字映射为"月亮"。"""
    pid = _create_owner(client)
    spirits = client.get(f"/person/{pid}/recommended-spirits").json()["spirits"]
    moon = next(s for s in spirits if s["planet"] == "moon")
    assert moon["is_default"] is True
    assert moon["name"] == "月亮"
    assert moon["healing_name"]  # 疗愈名（想被抱抱的我…）非空
    assert all(s["is_default"] is False for s in spirits if s["planet"] != "moon")


def test_endpoint_reason_explainable(client):
    """理由可追溯：活跃星的理由含"行运/法达/角宫/常聊"之一。"""
    pid = _create_owner(client)
    spirits = client.get(f"/person/{pid}/recommended-spirits").json()["spirits"]
    active = [s for s in spirits if s["reason"]]
    assert active
    assert any(
        ("行运" in s["reason"] or "法达" in s["reason"]) for s in active
    )


def test_endpoint_unknown_person_404(client):
    assert client.get("/person/nope/recommended-spirits").status_code == 404


def test_endpoint_resonance_via_profile(client):
    """画像碎片共振：种 moon_tide 深度 8 → 月亮分严格抬高（跨天鲁棒）。"""
    pid = _create_owner(client)
    store = client.app.state.store
    base_moon = next(
        s for s in client.get(f"/person/{pid}/recommended-spirits").json()["spirits"]
        if s["planet"] == "moon"
    )["score"]

    now = datetime.now(timezone.utc)
    profile = ChartProfile(
        person_id=pid,
        fragments={"moon_tide": 8},
        created_at=now,
        updated_at=now,
    )
    store.save_profile(profile)

    moon = next(
        s for s in client.get(f"/person/{pid}/recommended-spirits").json()["spirits"]
        if s["planet"] == "moon"
    )
    assert moon["score"] > base_moon
