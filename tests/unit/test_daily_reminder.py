"""每日行运生活提醒测试。"""

from __future__ import annotations

from datetime import date, datetime, timezone
import zoneinfo

from application.api.main import _daily_push_body
from application.mailbox.letter_service import LetterService
from foundation.database.store import GardenStore
from shared.enums import AspectApplication, AspectType, ChartType, FactCategory, HouseSystem, Planet, PlanetSpeed, Sign, ZodiacType
from shared.models import (
    Aspect,
    BirthData,
    Chart,
    ChartPlanet,
    EclipticPosition,
    Fact,
    GeoLocation,
    HouseCusp,
    HousePosition,
    Person,
    SignPosition,
)
from shared.models.letter import Letter
from domain.analysis.daily_reminder import DailyReminder, DailyReminderDigest, DailyReminderEngine, _TimedReminder


def _person() -> Person:
    return Person(
        id="p_daily_reminder",
        name="夏天",
        birth=BirthData(
            datetime(1991, 3, 21, 9, 25, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(35.7, 113.35, timezone_name="Asia/Shanghai", place_name="山西陵川"),
        ),
        house_system=HouseSystem.WHOLE_SIGN,
    )


def _planet(planet: Planet, longitude: float, sign: Sign, house: int, speed: float = 1.0) -> ChartPlanet:
    return ChartPlanet(
        planet=planet,
        ecliptic=EclipticPosition(longitude=longitude),
        sign=SignPosition(sign=sign, degree_absolute=longitude, degree_in_sign=longitude % 30),
        house=HousePosition(house=house, cusp_degree=(house - 1) * 30.0, distance_from_cusp=longitude % 30),
        speed=PlanetSpeed.DIRECT,
        speed_deg_per_day=speed,
    )


def _whole_sign_cusps() -> dict[int, HouseCusp]:
    signs = [
        Sign.ARIES,
        Sign.TAURUS,
        Sign.GEMINI,
        Sign.CANCER,
        Sign.LEO,
        Sign.VIRGO,
        Sign.LIBRA,
        Sign.SCORPIO,
        Sign.SAGITTARIUS,
        Sign.CAPRICORN,
        Sign.AQUARIUS,
        Sign.PISCES,
    ]
    return {
        i + 1: HouseCusp(house=i + 1, degree=i * 30.0, sign=sign)
        for i, sign in enumerate(signs)
    }


def _chart_for_reminder(*, jupiter_house: int = 3, mercury_house: int = 4) -> Chart:
    now = datetime.now(timezone.utc)
    return Chart(
        id="chart_daily_reminder",
        person_id="p_daily_reminder",
        chart_type=ChartType.NATAL,
        calculated_at_utc=now,
        julian_day=0.0,
        epoch_utc=now,
        location="test",
        zodiac=ZodiacType.TROPICAL,
        house_system=HouseSystem.WHOLE_SIGN,
        planets={
            Planet.SUN: _planet(Planet.SUN, 10.0, Sign.ARIES, 1),
            Planet.MOON: _planet(Planet.MOON, 40.0, Sign.TAURUS, 2),
            Planet.MERCURY: _planet(Planet.MERCURY, 100.0, Sign.CANCER, mercury_house),
            Planet.VENUS: _planet(Planet.VENUS, 120.0, Sign.LEO, 5),
            Planet.MARS: _planet(Planet.MARS, 130.0, Sign.LEO, 5),
            Planet.JUPITER: _planet(Planet.JUPITER, 65.0, Sign.GEMINI, jupiter_house),
            Planet.SATURN: _planet(Planet.SATURN, 285.0, Sign.CAPRICORN, 10),
            Planet.URANUS: _planet(Planet.URANUS, 125.0, Sign.LEO, 5),
            Planet.NEPTUNE: _planet(Planet.NEPTUNE, 305.0, Sign.AQUARIUS, 11),
            Planet.PLUTO: _planet(Planet.PLUTO, 215.0, Sign.SCORPIO, 8),
        },
        house_cusps=_whole_sign_cusps(),
        aspects=[
            Aspect(
                body1=Planet.JUPITER,
                body2=Planet.URANUS,
                aspect_type=AspectType.SEXTILE,
                exact_angle=60.0,
                orb=0.1,
                application=AspectApplication.EXACT,
            ),
            Aspect(
                body1=Planet.JUPITER,
                body2=Planet.NEPTUNE,
                aspect_type=AspectType.TRINE,
                exact_angle=120.0,
                orb=0.1,
                application=AspectApplication.EXACT,
            ),
        ],
    )


def _chart_for_3h_jupiter_7h_8h_lord() -> Chart:
    """测试盘：木星落 3宫，同时是 7宫主与 8宫主。"""
    chart = _chart_for_reminder(jupiter_house=3, mercury_house=4)
    cusps = dict(chart.house_cusps)
    cusps[7] = HouseCusp(house=7, degree=240.0, sign=Sign.SAGITTARIUS)
    cusps[8] = HouseCusp(house=8, degree=330.0, sign=Sign.PISCES)
    return Chart(
        id=chart.id,
        person_id=chart.person_id,
        chart_type=chart.chart_type,
        calculated_at_utc=chart.calculated_at_utc,
        julian_day=chart.julian_day,
        epoch_utc=chart.epoch_utc,
        location=chart.location,
        zodiac=chart.zodiac,
        house_system=chart.house_system,
        planets=chart.planets,
        house_cusps=cusps,
        aspects=chart.aspects,
    )


class _FakeTransit:
    def __init__(self, aspects: list[Aspect]):
        self.aspects = aspects

    def transit_aspects(self, chart, target, transit_bodies=None):
        return list(self.aspects)


class _MorningMoonJupiterTransit:
    def transit_aspects(self, chart, target, transit_bodies=None):
        if transit_bodies and Planet.URANUS in transit_bodies and Planet.MOON not in transit_bodies:
            return []
        hour = target.astimezone(zoneinfo.ZoneInfo("Asia/Shanghai")).hour
        if hour in (8, 9):
            return [
                Aspect(
                    body1=Planet.MOON,
                    body2=Planet.JUPITER,
                    aspect_type=AspectType.SQUARE,
                    exact_angle=90.0,
                    orb=0.2 if hour == 8 else 0.5,
                    application=AspectApplication.APPLYING,
                )
            ]
        return []


class _HourlyTransit:
    def transit_aspects(self, chart, target, transit_bodies=None):
        if transit_bodies and Planet.URANUS in transit_bodies and Planet.MOON not in transit_bodies:
            return [
                Aspect(
                    body1=Planet.URANUS,
                    body2=Planet.JUPITER,
                    aspect_type=AspectType.SEXTILE,
                    exact_angle=60.0,
                    orb=0.3,
                    application=AspectApplication.APPLYING,
                ),
                Aspect(
                    body1=Planet.NEPTUNE,
                    body2=Planet.JUPITER,
                    aspect_type=AspectType.TRINE,
                    exact_angle=120.0,
                    orb=0.4,
                    application=AspectApplication.APPLYING,
                ),
            ]
        hour = target.astimezone(zoneinfo.ZoneInfo("Asia/Shanghai")).hour
        if hour in (8, 9):
            return [
                Aspect(
                    body1=Planet.MOON,
                    body2=Planet.JUPITER,
                    aspect_type=AspectType.SQUARE,
                    exact_angle=90.0,
                    orb=0.2 if hour == 8 else 0.5,
                    application=AspectApplication.APPLYING,
                )
            ]
        if hour in (14, 15):
            return [
                Aspect(
                    body1=Planet.MARS,
                    body2=Planet.MERCURY,
                    aspect_type=AspectType.CONJUNCTION,
                    exact_angle=0.0,
                    orb=0.0 if hour == 14 else 0.4,
                    application=AspectApplication.EXACT,
                )
            ]
        return []


def _engine_with(*aspects: Aspect) -> DailyReminderEngine:
    engine = DailyReminderEngine()
    engine._transit = _FakeTransit(list(aspects))  # noqa: SLF001 - 单元测试替换星历输入
    return engine


def test_moon_to_3h_jupiter_is_light_traffic_reminder():
    chart = _chart_for_reminder()
    engine = _engine_with(
        Aspect(
            body1=Planet.MOON,
            body2=Planet.JUPITER,
            aspect_type=AspectType.SQUARE,
            exact_angle=90.0,
            orb=0.2,
            application=AspectApplication.APPLYING,
        )
    )

    reminder = engine.top_reminder(chart, _person(), target=datetime(2026, 8, 18, tzinfo=timezone.utc))

    assert reminder is not None
    assert reminder.level == 1
    assert reminder.house == 3
    assert "通勤" in reminder.scene or "交通" in reminder.scene
    assert "车距" in reminder.advice
    assert "一定" not in reminder.body
    assert any("天王星" in item for item in reminder.reason_chain)
    assert any("海王星" in item for item in reminder.reason_chain)


def test_exact_mars_to_6th_lord_is_body_workflow_reminder():
    chart = _chart_for_reminder(mercury_house=4)  # Whole-sign 6宫处女，6R=水星
    engine = _engine_with(
        Aspect(
            body1=Planet.MARS,
            body2=Planet.MERCURY,
            aspect_type=AspectType.CONJUNCTION,
            exact_angle=0.0,
            orb=0.0,
            application=AspectApplication.EXACT,
        )
    )

    reminder = engine.top_reminder(chart, _person(), target=datetime(2026, 8, 18, tzinfo=timezone.utc))

    assert reminder is not None
    assert reminder.level >= 2
    assert reminder.house == 6
    assert reminder.role == "house_lord"
    assert "火星精准引动你的6宫主" in reminder.reason
    assert "搬重物" in reminder.advice
    assert "硬扛" in reminder.advice
    assert "一定" not in reminder.body


def test_daily_reminder_filters_minor_aspects_from_user_facing_digest():
    chart = _chart_for_reminder()
    engine = _engine_with(
        Aspect(
            body1=Planet.MOON,
            body2=Planet.JUPITER,
            aspect_type=AspectType.QUINCUNX,
            exact_angle=150.0,
            orb=0.2,
            application=AspectApplication.APPLYING,
        ),
        Aspect(
            body1=Planet.MOON,
            body2=Planet.MERCURY,
            aspect_type=AspectType.SEMISQUARE,
            exact_angle=45.0,
            orb=0.1,
            application=AspectApplication.APPLYING,
        ),
    )

    reminders = engine.reminders(chart, _person(), target=datetime(2026, 8, 18, tzinfo=timezone.utc))

    assert reminders == []


    """同一行运触发同一本命星时，多宫含义合成一条，不拆散成刷屏提醒。"""
    chart = _chart_for_3h_jupiter_7h_8h_lord()
    engine = DailyReminderEngine()
    engine._transit = _MorningMoonJupiterTransit()  # noqa: SLF001 - 单元测试替换星历输入

    digest = engine.daily_digest(chart, _person(), target_date=date(2026, 8, 18))

    moon_jupiter = [
        item for item in digest.items
        if item.trigger_planet == Planet.MOON and item.natal_planet == Planet.JUPITER
    ]
    assert len(moon_jupiter) == 1
    item = moon_jupiter[0]
    assert item.house == 3
    assert item.role == "multi_layer"
    assert item.time_label == "上午"
    assert "通勤" in item.scene or "交通" in item.scene
    assert "赔付" in item.scene or "合同" in item.scene
    assert "车距" in item.advice
    assert "证据" in item.advice
    assert any("3宫" in line and "通勤" in line for line in item.reason_chain)
    assert any("7宫主" in line and "合同" in line for line in item.reason_chain)
    assert any("8宫主" in line and "赔付" in line for line in item.reason_chain)
    assert any("合并提醒" in line and "不用拆成多条" in line for line in item.reason_chain)


def test_daily_digest_scans_local_day_and_keeps_background_reason_chain():
    chart = _chart_for_reminder(mercury_house=4)
    engine = DailyReminderEngine()
    engine._transit = _HourlyTransit()  # noqa: SLF001 - 单元测试替换星历输入

    digest = engine.daily_digest(chart, _person(), target_date=date(2026, 8, 18))

    assert digest.letter_date == "2026-08-18"
    assert digest.timezone_name == "Asia/Shanghai"
    assert digest.summary == "今天路上慢半拍，沟通和赔付留证据"
    assert len(digest.items) >= 2
    traffic = next(item for item in digest.items if item.house == 3)
    assert traffic.time_label == "上午"
    assert traffic.start_at and "T08:00:00" in traffic.start_at
    assert traffic.end_at and "T10:00:00" in traffic.end_at
    assert "通勤" in traffic.scene or "交通" in traffic.scene
    assert any("同一本命点背景：行运天王星" in item for item in traffic.reason_chain)
    assert any("同一本命点背景：行运海王星" in item for item in traffic.reason_chain)
    assert any(item.house == 6 and item.time_label == "下午" for item in digest.items)


def _synthetic_reminder(
    *,
    house: int,
    reason_chain: list[str],
    trigger: Planet = Planet.MOON,
    natal: Planet = Planet.JUPITER,
    score: float = 1.0,
    scene: str | None = None,
) -> DailyReminder:
    return DailyReminder(
        level=1,
        score=score,
        house=house,
        scene=scene or str({3: "通勤/交通/消息文书", 7: "合作/伴侣/客户/合同", 8: "保险/赔付/债务/共同钱"}.get(house, "日常场景")),
        sender=trigger.value,
        title="月亮提醒",
        reason="测试原因。",
        advice="测试建议。",
        trigger_planet=trigger,
        natal_planet=natal,
        aspect_type=AspectType.SQUARE,
        orb=0.2,
        role="multi_layer",
        confidence=0.8,
        reason_chain=reason_chain,
        time_label="上午",
        start_at="2026-08-18T08:00:00+08:00",
        end_at="2026-08-18T10:00:00+08:00",
    )


def test_daily_item_sort_keeps_traffic_people_money_before_plain_backgrounds():
    engine = DailyReminderEngine()
    important = _synthetic_reminder(
        house=3,
        score=0.8,
        reason_chain=[
            "木星作为3宫里的木星承载通勤/交通/消息文书",
            "木星作为7宫主承载合作/伴侣/客户/合同",
            "木星作为8宫主承载保险/赔付/债务/共同钱",
        ],
    )
    filler = [
        _synthetic_reminder(
            house=10,
            score=3.0 - i * 0.1,
            trigger=Planet.SATURN,
            natal=Planet.MERCURY,
            reason_chain=["水星作为10宫主承载工作责任/老板/公开表现"],
            scene="工作责任/老板/公开表现",
        )
        for i in range(8)
    ]

    sorted_items = sorted([*filler, important], key=engine._daily_item_sort_key)[:8]  # noqa: SLF001

    assert important in sorted_items
    assert sorted_items[0] is important


def test_daily_letter_stores_daily_push_metadata_and_push_prefers_digest_summary():
    chart = _chart_for_reminder(mercury_house=4)
    store = GardenStore(":memory:")
    service = LetterService(store, chart_provider=lambda person: chart)
    service._reminder = DailyReminderEngine()  # noqa: SLF001 - 固定日推候选
    service._reminder._transit = _HourlyTransit()  # noqa: SLF001 - 单元测试替换星历输入

    letter = service.get_or_create_daily(_person())

    assert letter.metadata["daily_reminder"]["house"] in (3, 6)
    assert letter.metadata["daily_push"]["letter_date"]
    assert len(letter.metadata["daily_push"]["items"]) >= 2
    assert "今日主提醒：" in letter.body
    assert "今天只记这几件事" in letter.body
    assert "为什么提醒它" not in letter.body
    push_body = _daily_push_body(letter)
    assert push_body.startswith(letter.metadata["daily_push"]["summary"])
    assert "点开看今天只记三件事" in push_body
    assert "｜" not in push_body
    assert len(push_body) <= 80


class _FakeLetterLLM:
    available = True

    def complete(self, *args, **kwargs):
        return "旧 LLM 生成的水星散文来信"


class _EmptyDigestDaily:
    def analyze(self, chart, person, params):
        return [
            Fact(
                id="fact_empty_digest",
                category=FactCategory.THEME,
                chart_id=chart.id,
                description="今日水星对你本命的水星形成三合——影响你的朋友领域",
                extracted_at=datetime.now(timezone.utc),
                payload={
                    "weight": 1.0,
                    "confidence": 0.8,
                    "rule_id": "daily:mercury:mercury:trine",
                },
            )
        ]


class _EmptyDigestReminder:
    def daily_digest(self, chart, person, params):
        return DailyReminderDigest(
            letter_date="2026-08-18",
            timezone_name="Asia/Shanghai",
            summary="今天没有特别强的日推提醒",
            items=[],
        )

    def top_reminder(self, chart, person, params):
        return None


def test_empty_daily_digest_uses_new_daily_template_not_legacy_llm_letter():
    chart = _chart_for_reminder(mercury_house=4)
    store = GardenStore(":memory:")
    service = LetterService(store, llm_client=_FakeLetterLLM(), chart_provider=lambda person: chart)
    service._daily = _EmptyDigestDaily()  # noqa: SLF001 - 精准模拟旧快照仍有 facts
    service._reminder = _EmptyDigestReminder()  # noqa: SLF001 - 精准模拟新日推无 items

    letter = service.get_or_create_daily(_person())

    assert letter.title.startswith("今日星灵日推")
    assert letter.sender == "mercury"
    assert letter.metadata["daily_push"]["items"] == []
    assert "今天没有特别强的日推提醒" in letter.body
    assert "旧 LLM" not in letter.body
    assert "水星来信" not in letter.title
    assert _daily_push_body(letter) == "今天没有特别强的日推提醒"


def test_daily_letter_is_stable_until_force_refresh():
    person = _person()
    chart = _chart_for_reminder(mercury_house=4)
    store = GardenStore(":memory:")
    old = Letter(
        id="old_daily",
        person_id=person.id,
        letter_date=datetime.now(zoneinfo.ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d"),
        sender="mercury",
        title="水星来信",
        body="旧的单条 LLM 来信正文",
        kind="daily",
        created_at=datetime(2026, 8, 18, tzinfo=timezone.utc),
        metadata={"daily_reminder": {"house": 11}},
    )
    store.save_letter(old)
    service = LetterService(store, chart_provider=lambda p: chart)
    service._reminder = DailyReminderEngine()  # noqa: SLF001 - 固定日推候选
    service._reminder._transit = _HourlyTransit()  # noqa: SLF001 - 单元测试替换星历输入

    letter = service.get_or_create_daily(person)
    saved = store.get_letter(person.id, old.letter_date, "daily")

    assert letter.id == "old_daily"
    assert saved is not None
    assert saved.body == "旧的单条 LLM 来信正文"
    assert "daily_push" not in saved.metadata

    refreshed = service.force_refresh_daily(person)
    saved = store.get_letter(person.id, old.letter_date, "daily")

    assert refreshed.id == "old_daily"
    assert saved is not None
    assert saved.id == "old_daily"
    assert saved.body != "旧的单条 LLM 来信正文"
    assert "daily_push" in saved.metadata
    assert len(saved.metadata["daily_push"]["items"]) >= 2
    assert "今日主提醒：" in saved.body
    assert "为什么提醒它" not in saved.body
    assert _daily_push_body(saved).startswith(saved.metadata["daily_push"]["summary"])
