"""Chart 序列化/反序列化（注册时落库，运行时读缓存不重算）。

设计（原则：出生即定的数据算一次存下来）：
- 本命盘（Natal）出生时刻定死 → create_person 时 compute 一次，chart_to_json 落库。
- 运行时 chart_from_json 还原，不再调用 Swiss Ephemeris。
- 时间依赖部分（行运/日返/月返/次限）由缓存的 Natal Chart 派生，按需算。

全部枚举都是 str,Enum → 序列化用 .value，反序列化用 Enum(value)。
"""

from __future__ import annotations

import json
from datetime import datetime

from shared.enums import (
    AspectApplication,
    AspectType,
    ChartType,
    DignityState,
    HouseSystem,
    Planet,
    PlanetSpeed,
    Sect,
    Sign,
    ZodiacType,
)
from shared.models.chart import (
    Aspect,
    Chart,
    ChartAcceptance,
    ChartPlanet,
    ChartReception,
    EclipticPosition,
    EssentialDignity,
    FixedStarConjunction,
    HouseCusp,
    HousePosition,
    Lot,
    SignPosition,
)


# ---------------------------------------------------------------------------
# 序列化
# ---------------------------------------------------------------------------

def _dt(d: datetime) -> str:
    return d.isoformat()


def _ecliptic_to_dict(p: EclipticPosition) -> dict:
    return {
        "longitude": p.longitude, "latitude": p.latitude,
        "declination": p.declination, "right_ascension": p.right_ascension,
        "distance_au": p.distance_au,
    }


def _sign_position_to_dict(p: SignPosition | None) -> dict | None:
    if p is None:
        return None
    return {
        "sign": p.sign.value, "degree_absolute": p.degree_absolute,
        "degree_in_sign": p.degree_in_sign, "minutes": p.minutes, "seconds": p.seconds,
    }


def _house_position_to_dict(p: HousePosition) -> dict:
    return {
        "house": p.house, "cusp_degree": p.cusp_degree,
        "distance_from_cusp": p.distance_from_cusp,
    }


def _chart_planet_to_dict(p: ChartPlanet) -> dict:
    return {
        "planet": p.planet.value,
        "ecliptic": _ecliptic_to_dict(p.ecliptic),
        "sign": _sign_position_to_dict(p.sign),
        "house": _house_position_to_dict(p.house),
        "speed": p.speed.value,
        "speed_deg_per_day": p.speed_deg_per_day,
        "is_combust": p.is_combust, "is_cazimi": p.is_cazimi,
        "is_under_beams": p.is_under_beams,
    }


def _aspect_to_dict(a: Aspect) -> dict:
    return {
        "body1": a.body1.value, "body2": a.body2.value,
        "aspect_type": a.aspect_type.value, "exact_angle": a.exact_angle,
        "orb": a.orb, "application": a.application.value,
    }


def _dignity_to_dict(d: EssentialDignity) -> dict:
    return {
        "planet": d.planet.value, "sign": d.sign.value,
        "dignity_state": d.dignity_state.value, "score": d.score,
    }


def _reception_to_dict(r: ChartReception) -> dict:
    return {
        "planet_a": r.planet_a.value,
        "planet_b": r.planet_b.value,
        "dignities_of_a_at_b": [s.value for s in r.dignities_of_a_at_b],
        "dignities_of_b_at_a": [s.value for s in r.dignities_of_b_at_a],
        "dignity_type": r.dignity_type.value,
        "score": r.score,
        "aspect_type": r.aspect_type.value if r.aspect_type else None,
        "aspect_nature": r.aspect_nature,
        "description_zh": r.description_zh,
    }


def _acceptance_to_dict(a: ChartAcceptance) -> dict:
    return {
        "acceptor": a.acceptor.value,
        "accepted": a.accepted.value,
        "dignities": [s.value for s in a.dignities],
        "dignity_type": a.dignity_type.value,
        "score": a.score,
        "aspect_type": a.aspect_type.value,
        "aspect_nature": a.aspect_nature,
        "description_zh": a.description_zh,
    }


def _lot_to_dict(l: Lot) -> dict:
    return {
        "name": l.name, "formula": l.formula, "degree": l.degree,
        "sign": l.sign.value, "house": l.house,
    }


def _star_to_dict(s: FixedStarConjunction) -> dict:
    return {
        "star_name": s.star_name, "star_magnitude": s.star_magnitude,
        "planet": s.planet.value, "orb": s.orb,
        "star_degree": s.star_degree, "star_sign": s.star_sign.value,
    }


def chart_to_json(chart: Chart) -> str:
    """Chart → JSON 字符串（枚举全部转 .value）。"""
    data = {
        "id": chart.id,
        "person_id": chart.person_id,
        "chart_type": chart.chart_type.value,
        "calculated_at_utc": _dt(chart.calculated_at_utc),
        "julian_day": chart.julian_day,
        "epoch_utc": _dt(chart.epoch_utc),
        "location": chart.location,
        "zodiac": chart.zodiac.value,
        "house_system": chart.house_system.value,
        "planets": {
            p.value: _chart_planet_to_dict(cp)
            for p, cp in chart.planets.items()
        },
        "house_cusps": {
            str(h): {"house": c.house, "degree": c.degree, "sign": c.sign.value}
            for h, c in chart.house_cusps.items()
        },
        "ascendant": _sign_position_to_dict(chart.ascendant),
        "midheaven": _sign_position_to_dict(chart.midheaven),
        "aspects": [_aspect_to_dict(a) for a in chart.aspects],
        "dignities": {
            p.value: [_dignity_to_dict(d) for d in ds]
            for p, ds in chart.dignities.items()
        },
        "receptions": [_reception_to_dict(r) for r in chart.receptions],
        "acceptances": [_acceptance_to_dict(a) for a in chart.acceptances],
        "lots": [_lot_to_dict(l) for l in chart.lots],
        "fixed_star_conjunctions": [_star_to_dict(s) for s in chart.fixed_star_conjunctions],
        "sect": chart.sect.value if chart.sect else None,
        "moon_phase": chart.moon_phase,
        "reference_chart_id": chart.reference_chart_id,
        "reference_chart_type": chart.reference_chart_type.value if chart.reference_chart_type else None,
    }
    return json.dumps(data, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 反序列化
# ---------------------------------------------------------------------------

def _from_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _ecliptic_from_dict(d: dict) -> EclipticPosition:
    return EclipticPosition(
        longitude=d["longitude"], latitude=d.get("latitude", 0.0),
        declination=d.get("declination", 0.0),
        right_ascension=d.get("right_ascension", 0.0),
        distance_au=d.get("distance_au", 0.0),
    )


def _sign_position_from_dict(d: dict | None) -> SignPosition | None:
    if d is None:
        return None
    return SignPosition(
        sign=Sign(d["sign"]), degree_absolute=d["degree_absolute"],
        degree_in_sign=d["degree_in_sign"],
        minutes=d.get("minutes", 0), seconds=d.get("seconds", 0),
    )


def _house_position_from_dict(d: dict) -> HousePosition:
    return HousePosition(
        house=d["house"], cusp_degree=d["cusp_degree"],
        distance_from_cusp=d.get("distance_from_cusp", 0.0),
    )


def _chart_planet_from_dict(d: dict) -> ChartPlanet:
    return ChartPlanet(
        planet=Planet(d["planet"]),
        ecliptic=_ecliptic_from_dict(d["ecliptic"]),
        sign=_sign_position_from_dict(d["sign"]),
        house=_house_position_from_dict(d["house"]),
        speed=PlanetSpeed(d["speed"]),
        speed_deg_per_day=d.get("speed_deg_per_day", 0.0),
        is_combust=d.get("is_combust", False),
        is_cazimi=d.get("is_cazimi", False),
        is_under_beams=d.get("is_under_beams", False),
    )


def _aspect_from_dict(d: dict) -> Aspect:
    return Aspect(
        body1=Planet(d["body1"]), body2=Planet(d["body2"]),
        aspect_type=AspectType(d["aspect_type"]),
        exact_angle=d["exact_angle"], orb=d["orb"],
        application=AspectApplication(d["application"]),
    )


def _dignity_from_dict(d: dict) -> EssentialDignity:
    return EssentialDignity(
        planet=Planet(d["planet"]), sign=Sign(d["sign"]),
        dignity_state=DignityState(d["dignity_state"]), score=d["score"],
    )


def _reception_from_dict(d: dict) -> ChartReception:
    return ChartReception(
        planet_a=Planet(d["planet_a"]),
        planet_b=Planet(d["planet_b"]),
        dignities_of_a_at_b=tuple(
            DignityState(s) for s in d.get("dignities_of_a_at_b", [])
        ),
        dignities_of_b_at_a=tuple(
            DignityState(s) for s in d.get("dignities_of_b_at_a", [])
        ),
        dignity_type=DignityState(d["dignity_type"]),
        score=d["score"],
        aspect_type=AspectType(d["aspect_type"]) if d.get("aspect_type") else None,
        aspect_nature=d.get("aspect_nature"),
        description_zh=d.get("description_zh", ""),
    )


def _acceptance_from_dict(d: dict) -> ChartAcceptance:
    return ChartAcceptance(
        acceptor=Planet(d["acceptor"]),
        accepted=Planet(d["accepted"]),
        dignities=tuple(DignityState(s) for s in d.get("dignities", [])),
        dignity_type=DignityState(d["dignity_type"]),
        score=d["score"],
        aspect_type=AspectType(d["aspect_type"]),
        aspect_nature=d["aspect_nature"],
        description_zh=d.get("description_zh", ""),
    )


def _lot_from_dict(d: dict) -> Lot:
    return Lot(
        name=d["name"], formula=d["formula"], degree=d["degree"],
        sign=Sign(d["sign"]), house=d["house"],
    )


def _star_from_dict(d: dict) -> FixedStarConjunction:
    return FixedStarConjunction(
        star_name=d["star_name"], star_magnitude=d["star_magnitude"],
        planet=Planet(d["planet"]), orb=d["orb"],
        star_degree=d["star_degree"], star_sign=Sign(d["star_sign"]),
    )


def chart_from_json(raw: str) -> Chart:
    """JSON 字符串 → Chart（枚举全部还原）。"""
    d = json.loads(raw)
    house_cusps = {
        int(h): HouseCusp(house=c["house"], degree=c["degree"], sign=Sign(c["sign"]))
        for h, c in d.get("house_cusps", {}).items()
    }
    return Chart(
        id=d["id"], person_id=d["person_id"], chart_type=ChartType(d["chart_type"]),
        calculated_at_utc=_from_dt(d["calculated_at_utc"]),
        julian_day=d["julian_day"], epoch_utc=_from_dt(d["epoch_utc"]),
        location=d.get("location", ""), zodiac=ZodiacType(d["zodiac"]),
        house_system=HouseSystem(d["house_system"]),
        planets={
            Planet(k): _chart_planet_from_dict(v)
            for k, v in d.get("planets", {}).items()
        },
        house_cusps=house_cusps,
        ascendant=_sign_position_from_dict(d.get("ascendant")),
        midheaven=_sign_position_from_dict(d.get("midheaven")),
        aspects=[_aspect_from_dict(a) for a in d.get("aspects", [])],
        dignities={
            Planet(k): [_dignity_from_dict(v) for v in vs]
            for k, vs in d.get("dignities", {}).items()
        },
        receptions=[_reception_from_dict(r) for r in d.get("receptions", [])],
        acceptances=[_acceptance_from_dict(a) for a in d.get("acceptances", [])],
        lots=[_lot_from_dict(l) for l in d.get("lots", [])],
        fixed_star_conjunctions=[
            _star_from_dict(s) for s in d.get("fixed_star_conjunctions", [])
        ],
        sect=Sect(d["sect"]) if d.get("sect") else None,
        moon_phase=d.get("moon_phase"),
        reference_chart_id=d.get("reference_chart_id"),
        reference_chart_type=(
            ChartType(d["reference_chart_type"]) if d.get("reference_chart_type") else None
        ),
    )
