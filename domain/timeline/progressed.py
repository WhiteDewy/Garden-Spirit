"""次限月亮（Secondary Progressed Moon）计算器。

次限法：1 天 = 1 年。推运月亮 ~13°/年，每 ~2.5 年换座（换宫），
构成"当下的情绪季节/心理透镜"。回答"为什么我现在是这种状态"（本命盘不变，
次限月亮在变）。确定性、无 LLM；结果可 to_dict()（出口）。

判读：次限月亮星座 = 情绪透镜；在本命盘的落宫 = 情绪焦点领域。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from foundation.astronomy.ephemeris import planet_longitude, to_julian_day
from shared.constants import DEGREES_PER_SIGN, SIGNS_IN_ORDER
from shared.enums import HouseSystem, Planet, Sign
from shared.models import Chart, Person

from domain.astrology.calculation import NatalChartCalculator
from domain.timeline.returns import find_return_after, find_return_before

#: 次限月亮星座情绪透镜（自我探索用）
SIGN_EMOTIONAL_LENS: dict[str, str] = {
    "aries": "主动/行动/想开始/有冲劲",
    "taurus": "安稳/感官/坚持/求舒适",
    "gemini": "好奇/交流/多变/想学习",
    "cancer": "情绪/家庭/滋养/敏感",
    "leo": "表达/被看见/创造/骄傲",
    "virgo": "分析/服务/完美/抠细节",
    "libra": "关系/平衡/和谐/易犹豫",
    "scorpio": "深度/掌控/转化/占有",
    "sagittarius": "自由/探索/意义/乐观",
    "capricorn": "责任/成就/结构/压抑",
    "aquarius": "独立/创新/疏离/理想",
    "pisces": "灵性/直觉/融合/易逃避",
}

#: 次限月亮换座扫描上限（天=岁）
_SCAN_LIMIT_DAYS = 5 * 365

_OBLIQUITY = 23.4392911
#: 三限（Tertiary）：1天=1太阴月（29.53天）→ 推进量 = 年龄 × 365.25/29.53
_TERTIARY_FACTOR = 365.25 / 29.5306


def _moon_lon(dt: datetime) -> float:
    return planet_longitude(to_julian_day(dt), Planet.MOON)


def _ecl_to_ra(lon: float) -> float:
    """黄经 → 赤经。"""
    lon_r = math.radians(lon)
    eps = math.radians(_OBLIQUITY)
    return math.degrees(math.atan2(math.sin(lon_r) * math.cos(eps), math.cos(lon_r))) % 360.0


def _ra_to_ecl(ra: float) -> float:
    """赤经 → 黄经。"""
    ra_r = math.radians(ra)
    eps = math.radians(_OBLIQUITY)
    return math.degrees(math.atan2(math.sin(ra_r), math.cos(ra_r) * math.cos(eps))) % 360.0


def _alcabitius_cusps(asc: float, mc: float) -> dict[int, float]:
    """由上升+天顶计算阿卡比特宫头（赤经三等分法）。

    11/12 宫头三等分 MC→上升 的赤经弧；2/3 宫头三等分 上升→天底。
    次限盘角度（太阳弧上升/天顶）非真实时刻，故不依赖 pyswisseph。
    """
    ramc = _ecl_to_ra(mc)
    ra_asc = _ecl_to_ra(asc)
    arc_mc_asc = (ra_asc - ramc) % 360.0
    ra_11 = (ramc + arc_mc_asc / 3.0) % 360.0
    ra_12 = (ramc + arc_mc_asc * 2.0 / 3.0) % 360.0
    ra_ic = (ramc + 180.0) % 360.0
    arc_asc_ic = (ra_ic - ra_asc) % 360.0
    ra_2 = (ra_asc + arc_asc_ic / 3.0) % 360.0
    ra_3 = (ra_asc + arc_asc_ic * 2.0 / 3.0) % 360.0
    c11, c12 = _ra_to_ecl(ra_11), _ra_to_ecl(ra_12)
    c2, c3 = _ra_to_ecl(ra_2), _ra_to_ecl(ra_3)
    ic = (mc + 180.0) % 360.0
    dsc = (asc + 180.0) % 360.0
    return {
        1: asc % 360.0, 2: c2, 3: c3, 4: ic,
        5: (c11 + 180.0) % 360.0, 6: (c12 + 180.0) % 360.0,
        7: dsc, 8: (c2 + 180.0) % 360.0, 9: (c3 + 180.0) % 360.0,
        10: mc % 360.0, 11: c11, 12: c12,
    }


def _house_of_lon(cusps: dict[int, float], lon: float) -> int:
    """某黄经在宫头表中的宫位。"""
    for h in range(1, 13):
        a = cusps[h]
        b = cusps[h % 12 + 1] if h < 12 else cusps[1] + 360.0
        if b < a:
            b += 360.0
        t = lon if lon >= a else lon + 360.0
        if a <= t < b:
            return h
    return 1


@dataclass
class ProgressedMoon:
    """次限月亮状态。"""

    progressed_date: datetime       # 次限对应的真实日期
    age_years: float                # 推运年龄（岁）
    longitude: float                # 次限月亮黄经
    sign: Sign
    degree_in_sign: float
    natal_house: int                # 在本命盘的落宫
    entered_sign_date: datetime     # 进入当前星座的日历日期
    next_sign_change_date: datetime  # 下次换座日历日期
    next_sign: Sign

    def to_dict(self) -> dict:
        return {
            "type": "progressed_moon",
            "age_years": round(self.age_years, 1),
            "sign": self.sign.value,
            "degree_in_sign": round(self.degree_in_sign, 2),
            "natal_house": self.natal_house,
            "entered_sign_date": self.entered_sign_date.date().isoformat(),
            "next_sign_change_date": self.next_sign_change_date.date().isoformat(),
            "next_sign": self.next_sign.value,
            "lens": SIGN_EMOTIONAL_LENS.get(self.sign.value, ""),
        }


class ProgressedMoonCalculator:
    """次限月亮：推运日期 → 星座 + 本命落宫 + 换座时间。"""

    def __init__(self, calculator: NatalChartCalculator | None = None):
        self._calculator = calculator or NatalChartCalculator()

    def compute(
        self,
        natal_chart: Chart,
        birth: datetime,
        reference: datetime | None = None,
        mode: str = "secondary",
    ) -> ProgressedMoon:
        """当前次限/三限月亮状态。

        mode: "secondary"（1天=1年）| "tertiary"（1天=1太阴月）
        """
        ref = reference or datetime.now(timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        # 归一化到 UTC（birth 可能是 +08:00 感知时间，需转 UTC 再算，避免偏移伪影）
        birth = birth.astimezone(timezone.utc) if birth.tzinfo else birth.replace(tzinfo=timezone.utc)

        factor = _TERTIARY_FACTOR if mode == "tertiary" else 1.0
        age_years = (ref - birth).total_seconds() / 86400.0 / 365.25
        # 次限：1天=1年；三限：1天=1太阴月
        prog_date = birth + timedelta(days=age_years * factor)
        lon = _moon_lon(prog_date) % 360.0
        sign = SIGNS_IN_ORDER[int(lon // DEGREES_PER_SIGN) % 12]
        # 太阳弧法次限盘（对齐宫神星网）：次限上升/天顶 = 本命 + 太阳弧 → 阿卡比特宫头
        sa = (planet_longitude(to_julian_day(prog_date), Planet.SUN)
              - natal_chart.planets[Planet.SUN].ecliptic.longitude) % 360.0
        pasc = (natal_chart.ascendant.degree_absolute + sa) % 360.0
        pmc = (natal_chart.midheaven.degree_absolute + sa) % 360.0
        cusps = _alcabitius_cusps(pasc, pmc)
        natal_house = _house_of_lon(cusps, lon)
        # 进入当前星座 / 下次换座：推运日期（birth+Y天，Y=天=岁）下月亮过边界
        sign_start = int(lon // 30) * 30
        next_boundary = sign_start + 30
        entered_prog = find_return_before(_moon_lon, sign_start, prog_date, scan_days=5)
        next_prog = find_return_after(_moon_lon, next_boundary, prog_date, scan_days=5)
        next_sign = SIGNS_IN_ORDER[(int(next_boundary // 30)) % 12]
        # 推进天→日历日期：1 推进天 = 365.25/factor 现实天（保留小数）
        _days = lambda d: (d - birth).total_seconds() / 86400.0
        cal_factor = 365.25 / factor
        entered_sign_date = birth + timedelta(days=_days(entered_prog) * cal_factor)
        next_sign_change_date = birth + timedelta(days=_days(next_prog) * cal_factor)

        return ProgressedMoon(
            progressed_date=prog_date,
            age_years=age_years,
            longitude=lon,
            sign=sign,
            degree_in_sign=lon % DEGREES_PER_SIGN,
            natal_house=natal_house,
            entered_sign_date=entered_sign_date,
            next_sign_change_date=next_sign_change_date,
            next_sign=next_sign,
        )

    # -- 内部 -------------------------------------------------------------

    @staticmethod
    def _whole_sign_house(chart: Chart, sign: Sign) -> int:
        """整宫定位：某星座 = 第几整宫（从上升星座数起）。

        次限星的传统排法（宫神星网）：次限月亮按所在星座的整宫落宫，
        不用度数精确落阿卡比特宫头。
        """
        asc_index = SIGNS_IN_ORDER.index(chart.ascendant.sign)
        sign_index = SIGNS_IN_ORDER.index(sign)
        return ((sign_index - asc_index) % 12) + 1
