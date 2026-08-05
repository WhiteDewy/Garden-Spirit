"""Sect（昼/夜）计算。

sect 由太阳在星盘中的半球决定：
- 太阳在地平线以上（7-12 宫）→ DAY
- 太阳在地平线以下（1-6 宫）→ NIGHT
"""

from __future__ import annotations

from shared.enums import Planet, Sect


class SectEngine:
    """根据太阳所在宫位判定 sect。"""

    @staticmethod
    def compute(sun_house: int) -> Sect:
        """太阳所在宫位 → sect。"""
        return Sect.DAY if 7 <= sun_house <= 12 else Sect.NIGHT

    @staticmethod
    def is_sect_benefic(planet: Planet, sect: Sect) -> bool:
        """该行星是否属于当前 sect 阵营（昼行星/夜行星）。

        昼行星：SUN, JUPITER, SATURN, MERCURY(昼)
        夜行星：MOON, VENUS, MARS, MERCURY(夜)
        """
        diurnal = {Planet.SUN, Planet.JUPITER, Planet.SATURN}
        nocturnal = {Planet.MOON, Planet.VENUS, Planet.MARS}
        if planet in diurnal:
            return sect == Sect.DAY
        if planet in nocturnal:
            return sect == Sect.NIGHT
        if planet == Planet.MERCURY:
            # 水星为伴曜：靠近昼行星为昼性，靠近夜行星为夜性
            return sect == Sect.DAY
        return False
