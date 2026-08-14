"""宫位交感 + 连接分级（确定性技法）。

- 宫位交感：一星多宫主 → 交感宫群（该星特质的领域互相传导）。
- 连接分级：任意两宫主之间的连接类型与强度
  （互溶/接纳/相位/飞宫/同宫/潜在），用于事件条目的收敛计数。
"""

from __future__ import annotations

from collections import defaultdict

from shared.enums import DignityState, Planet
from shared.models import Chart

from domain.astrology.common import house_lord
from domain.astrology.knowledge import DignityEngine, ReceptionEngine
from domain.astrology.knowledge.loader import KnowledgeBase
from domain.astrology.interpretation.models import ConnectionFact, HouseSynapsis

_POSITIVE_DIGNITIES = (
    DignityState.DOMICILE,
    DignityState.EXALTATION,
    DignityState.TRIPLICITY,
    DignityState.TERM,
    DignityState.FACE,
)


def effective_house(chart: Chart, planet: Planet, threshold: float = 5.0) -> int:
    """宫头末度：行星距下一宫头 ≤ threshold（度）时，主影响下一宫（双宫都算，近的为主）。

    例：火星双子 23.3°，2宫头双子 23.5°，距 0.2° → effective_house = 2。
    """
    cp = chart.planets[planet]
    cur = cp.house.house
    abs_pos = cp.sign.degree_absolute
    n = cur % 12 + 1
    n_cusp = chart.house_cusps[n].degree
    dist = (n_cusp - abs_pos) % 360.0
    if 0.0 < dist <= threshold:
        return n
    return cur


def detect_synapsis(chart: Chart, kb: KnowledgeBase) -> list[HouseSynapsis]:
    """检测一星多宫主的交感宫群（≥2 宫）。"""
    lord_to_houses: dict[Planet, list[int]] = defaultdict(list)
    for house in range(1, 13):
        lord = house_lord(chart, kb, house)
        if lord is not None and lord in chart.planets:
            lord_to_houses[lord].append(house)

    result: list[HouseSynapsis] = []
    for lord, houses in lord_to_houses.items():
        if len(houses) < 2:
            continue
        manifestation = chart.planets[lord].house.house
        zh = kb.planet(lord).name_zh
        result.append(
            HouseSynapsis(
                hub_planet=lord,
                houses=tuple(sorted(houses)),
                manifestation_house=manifestation,
                description_zh=(
                    f"{zh}为{','.join(f'{h}宫' for h in sorted(houses))}宫主"
                    f"，落{manifestation}宫——这些领域经此星交感"
                ),
            )
        )
    return result


class ConnectionClassifier:
    """两宫主之间的连接分级（返回全部适用的连接，由调用方按强度筛选）。"""

    _STRONG_THRESHOLD = 2.5

    def __init__(self, kb: KnowledgeBase):
        self._kb = kb
        self._reception = ReceptionEngine(kb)
        self._dignity = DignityEngine(kb)

    def classify(self, chart: Chart, house_a: int, house_b: int) -> list[ConnectionFact]:
        """分类 house_a 宫主与 house_b 宫主之间的所有连接。"""
        la = house_lord(chart, self._kb, house_a)
        lb = house_lord(chart, self._kb, house_b)
        if la is None or lb is None or la not in chart.planets or lb not in chart.planets:
            return []
        if la == lb:
            return [ConnectionFact(f"{house_a}宫主", f"{house_b}宫主", "cohabit", 1.0, "同主")]

        conns: list[ConnectionFact] = []
        pair = {la, lb}

        # 互溶（双向尊严，最强）
        mutual = [
            r for r in self._reception.detect(self._positions(chart), sect=chart.sect)
            if {r.planet_a, r.planet_b} == pair
        ]
        if mutual:
            conns.append(ConnectionFact(
                f"{house_a}宫主", f"{house_b}宫主", "reception_mutual", 4.0,
                f"{self._kb.planet(la).name_zh}↔{self._kb.planet(lb).name_zh}互溶",
            ))

        # 激活接纳（单向尊严 + 相位）
        active = [
            a for a in self._reception.detect_acceptance(
                self._positions(chart), chart.aspects, sect=chart.sect
            )
            if {a.acceptor, a.accepted} == pair
        ]
        if active:
            a = active[0]
            conns.append(ConnectionFact(
                f"{house_a}宫主", f"{house_b}宫主", "reception_active", 3.0,
                f"{self._kb.planet(a.acceptor).name_zh}接纳{self._kb.planet(a.accepted).name_zh}",
            ))

        # 主相位
        for asp in chart.aspects:
            if {asp.body1, asp.body2} == pair:
                conns.append(ConnectionFact(
                    f"{house_a}宫主", f"{house_b}宫主", "aspect", 2.5,
                    asp.aspect_type.value,
                ))
                break

        # 飞宫（宫主落对方宫位，含宫头末度）
        if effective_house(chart, la) == house_b:
            conns.append(ConnectionFact(f"{house_a}宫主", f"{house_b}宫主", "flight", 2.0,
                                        f"{self._kb.planet(la).name_zh}飞{house_b}宫"))
        if effective_house(chart, lb) == house_a:
            conns.append(ConnectionFact(f"{house_a}宫主", f"{house_b}宫主", "flight", 2.0,
                                        f"{self._kb.planet(lb).name_zh}飞{house_a}宫"))

        # 同宫 / 同座（弱）
        if chart.planets[la].house.house == chart.planets[lb].house.house:
            conns.append(ConnectionFact(f"{house_a}宫主", f"{house_b}宫主", "cohabit", 1.0, "同宫"))
        if chart.planets[la].sign.sign == chart.planets[lb].sign.sign:
            conns.append(ConnectionFact(f"{house_a}宫主", f"{house_b}宫主", "cohabit", 1.0, "同座"))

        # 潜在接纳（单向尊严，无激活相位）—— 最弱
        if self._latent(chart, la, lb):
            conns.append(ConnectionFact(f"{house_a}宫主", f"{house_b}宫主", "reception_latent", 0.5,
                                        f"{self._kb.planet(lb).name_zh}对{self._kb.planet(la).name_zh}有单向尊严（未激活）"))
        if self._latent(chart, lb, la):
            conns.append(ConnectionFact(f"{house_a}宫主", f"{house_b}宫主", "reception_latent", 0.5,
                                        f"{self._kb.planet(la).name_zh}对{self._kb.planet(lb).name_zh}有单向尊严（未激活）"))

        return conns

    def is_strong(self, conn: ConnectionFact) -> bool:
        return conn.strength >= self._STRONG_THRESHOLD

    def is_received(self, chart: Chart, a: Planet, b: Planet) -> bool:
        """两星是否构成接纳关系（互溶或激活接纳）。

        用于"刑克是否有接纳"判定：刑克有接纳 = 磨合（惩罚轻），
        无接纳 = 硬碰（惩罚重）。三王星/虚点不参与接纳 → 其刑克视为未接纳。
        """
        mutual = [
            r for r in self._reception.detect(self._positions(chart), sect=chart.sect)
            if {r.planet_a, r.planet_b} == {a, b}
        ]
        if mutual:
            return True
        active = [
            x for x in self._reception.detect_acceptance(
                self._positions(chart), chart.aspects, sect=chart.sect
            )
            if {x.acceptor, x.accepted} == {a, b}
        ]
        return bool(active)

    def helpers_of(self, chart: Chart, planet: Planet) -> list[tuple[Planet, str]]:
        """谁帮这颗星（互溶/接纳帮手星）。返回 [(帮手星, "mutual"|"acceptance")]。

        被接纳/互溶 = 有帮手，是 assess_planet 关系轴的正向分量。
        三王星/虚点不参与（reception 引擎已排除）；互溶对不再重复计接纳。
        """
        positions = self._positions(chart)
        helpers: list[tuple[Planet, str]] = []
        for r in self._reception.detect(positions, sect=chart.sect):
            if planet in (r.planet_a, r.planet_b):
                other = r.planet_b if r.planet_a == planet else r.planet_a
                helpers.append((other, "mutual"))
        for acc in self._reception.detect_acceptance(positions, chart.aspects, sect=chart.sect):
            if acc.accepted == planet:
                helpers.append((acc.acceptor, "acceptance"))
        return helpers

    def strong_count(self, chart: Chart, house_a: int, targets: list[int]) -> int:
        """house_a 与 targets 各宫的强连接数（用于事件条目收敛）。"""
        count = 0
        for t in targets:
            for c in self.classify(chart, house_a, t):
                if self.is_strong(c):
                    count += 1
                    break
        return count

    # -- 内部 -------------------------------------------------------------

    @staticmethod
    def _positions(chart: Chart) -> dict[Planet, tuple]:
        return {
            pl: (cp.sign.sign, cp.sign.degree_in_sign)
            for pl, cp in chart.planets.items()
        }

    def _latent(self, chart: Chart, a: Planet, b: Planet) -> bool:
        """b 是否对 a 所在星座有正面尊贵（单向，未激活相位）。

        用 reception 引擎的尊贵集（尊重 triplicity.mode=all），
        与接纳引擎的判定保持一致。
        """
        a_cp = chart.planets[a]
        states = self._reception._dignities_of(
            b, (a_cp.sign.sign, a_cp.sign.degree_in_sign), chart.sect
        )
        return any(s in _POSITIVE_DIGNITIES for s in states)
