"""语义场选择引擎（确定性，无 LLM）。

同一宫位是多义词（语义场）。三步把控：
① 语境选择：问题域（domain）过滤 → 该宫位只激活相关含义（防关键词倾倒）
② 结构调制：宫主尊贵/吉凶/宫内星 → 质量分（-3..+3）→ 极性倾斜 + 强度调制
③ 收敛门槛：event（事件预言）条目需强连接收敛数达标才发射；tendency 默认

宫主飞宫（含宫头末度）→ 飞行增强；共振词挂在解读上（LLM 只转述，不发明）。
"""

from __future__ import annotations

from shared.enums import Planet
from shared.models import Chart

from domain.astrology.common import aspect_score, aspects_to, dignity_total, house_lord
from domain.astrology.knowledge import DignityEngine
from domain.astrology.knowledge.loader import KnowledgeBase
from domain.astrology.interpretation.models import SignificationItem
from domain.astrology.interpretation.synapsis import ConnectionClassifier, effective_house

_MALEFICS = {Planet.MARS, Planet.SATURN}
_BENEFICS = {Planet.JUPITER, Planet.VENUS}
_ASPECT_ZH = {
    "conjunction": "合", "opposition": "冲", "trine": "三合", "square": "刑",
    "sextile": "六合", "quincunx": "梅花", "semisextile": "半六合",
    "semisquare": "半刑", "sesquiquadrate": "八分相",
    "quintile": "五相", "biquintile": "倍五相",
}
_MEANINGFUL = {
    Planet.SUN, Planet.MOON, Planet.MERCURY, Planet.VENUS, Planet.MARS,
    Planet.JUPITER, Planet.SATURN, Planet.URANUS, Planet.NEPTUNE, Planet.PLUTO,
}
_MIN_STRENGTH = 0.3


class HouseSignificationEngine:
    """宫位语义场引擎：问题域 × 结构 → 多维解读。"""

    def __init__(self, kb: KnowledgeBase):
        self._kb = kb
        self._dignity = DignityEngine(kb)
        self._classifier = ConnectionClassifier(kb)
        self._table = kb.house_significations or {}

    def interpret(
        self,
        chart: Chart,
        domain: str,
        houses: list[int] | None = None,
        max_items: int = 8,
    ) -> list[SignificationItem]:
        """按问题域激活各宫位语义场，产出排序后的解读条目。

        domain: career / relationship / wealth / health / emotion / family / learning / self
        """
        items: list[SignificationItem] = []
        for house in range(1, 13):
            if houses and house not in houses:
                continue
            entries = self._table.get(house) or []
            eligible = [e for e in entries if domain in e.get("domains", [])]
            if not eligible:
                continue
            pos, neg, pos_ev, neg_ev = self._house_quality_dual(chart, house)
            conn_evidence = self._house_connection_evidence(chart, house)
            for e in eligible:
                strength = self._strength(chart, house, e, pos, neg)
                if strength is None or strength < _MIN_STRENGTH:
                    continue
                # 各论各的：正向解读吃吉轨证据，负向解读吃凶轨证据
                pol = e.get("polarity", "neutral")
                if pol == "positive":
                    base_ev = pos_ev
                elif pol == "negative":
                    base_ev = neg_ev
                else:
                    base_ev = pos_ev + neg_ev
                items.append(SignificationItem(
                    house=house,
                    word=e.get("word", ""),
                    polarity=pol,
                    intensity=float(e.get("intensity", 2)),
                    strength=strength,
                    resonance=tuple(e.get("resonance", []) or []),
                    evidence=tuple(base_ev + conn_evidence),
                    gated=e.get("gated", "tendency"),
                ))
        items.sort(key=lambda i: i.strength, reverse=True)
        return items[:max_items]

    # -- 结构质量 ---------------------------------------------------------

    def _house_quality_dual(
        self, chart: Chart, house: int
    ) -> tuple[float, float, list[str], list[str]]:
        """吉凶两论：返回 (吉分量, 凶分量, 吉证据, 凶证据)。

        吉凶分开累积、各自带证据，**不净合、不抵消**。
        吉：庙旺/吉星/和谐相/宫内吉星 → 驱动正向解读。
        凶：凶星/刑冲（未接纳重罚）/宫内凶星 → 驱动负向解读。
        """
        pos, neg = 0.0, 0.0
        pos_ev: list[str] = []
        neg_ev: list[str] = []

        lord = house_lord(chart, self._kb, house)
        if lord is not None and lord in chart.planets:
            name = self._kb.planet(lord).name_zh
            dt = dignity_total(chart, self._kb, lord, self._dignity)
            if dt > 0:
                pos += dt * 0.4
                pos_ev.append(f"{name}为{house}宫主（尊贵{dt:+d}）")
            elif dt < 0:
                neg += abs(dt) * 0.4
                neg_ev.append(f"{name}为{house}宫主（尊贵{dt:+d}）")
            if lord in _BENEFICS:
                pos += 1.0
                pos_ev.append(f"{name}为吉星")
            if lord in _MALEFICS:
                neg += 1.0
                neg_ev.append(f"{name}为凶星")
            for asp in aspects_to(chart, lord):
                info = self._kb.aspects.get(asp.aspect_type)
                if info is None:
                    continue
                asc = aspect_score(self._kb, asp)
                azh = _ASPECT_ZH.get(asp.aspect_type.value, asp.aspect_type.value)
                other = asp.body2 if asp.body1 == lord else asp.body1
                other_zh = self._kb.planet(other).name_zh
                if info.nature == "HARMONIOUS":
                    pos += asc * 0.2
                    pos_ev.append(f"{name}{azh}{other_zh}（和谐）")
                elif info.nature == "DYNAMIC":
                    neg += abs(asc) * 0.2
                    received = self._classifier.is_received(chart, lord, other)
                    neg += 0.4 if received else 0.8
                    tag = "磨合" if received else "未接纳"
                    neg_ev.append(f"{name}受{other_zh}{azh}（{tag}）")
        else:
            neg_ev.append(f"{house}宫主不明")

        for pl, cp in chart.planets.items():
            if pl not in _MEANINGFUL or cp.house.house != house:
                continue
            pname = self._kb.planet(pl).name_zh
            dt = dignity_total(chart, self._kb, pl, self._dignity)
            if dt > 0:
                pos += dt * 0.2
                pos_ev.append(f"{pname}落{house}宫（尊贵{dt:+d}）")
            elif dt < 0:
                neg += abs(dt) * 0.2
                neg_ev.append(f"{pname}落{house}宫（尊贵{dt:+d}）")
            if pl in _BENEFICS:
                pos += 0.5
                pos_ev.append(f"{pname}为吉星")
            if pl in _MALEFICS:
                neg += 0.5
                neg_ev.append(f"{pname}为凶星")

        return pos, neg, list(dict.fromkeys(pos_ev)), list(dict.fromkeys(neg_ev))

    # -- 强度调制 ---------------------------------------------------------

    def _strength(
        self, chart: Chart, house: int, entry: dict, pos: float, neg: float
    ) -> float | None:
        """吉凶两论：正向解读只吃吉分量，负向解读只吃凶分量，中性取较大者。不抵消。"""
        base = float(entry.get("intensity", 2))
        pol = entry.get("polarity", "neutral")

        if pol == "positive":
            s = base * (1 + pos * 0.4)
        elif pol == "negative":
            s = base * (1 + neg * 0.4)
        else:
            s = base * (1 + max(pos, neg) * 0.3)

        s += self._flight_boost(chart, house, entry.get("domains", []))

        # 事件预言门槛：需强连接收敛数达标（倾向切片默认直接发射）
        if entry.get("gated") == "event":
            targets = list(entry.get("corroborate_houses", []))
            corr = self._classifier.strong_count(chart, house, targets)
            if corr < int(entry.get("requires_corroboration", 2)):
                return None
            s += corr

        return round(s, 2)

    def _flight_boost(self, chart: Chart, house: int, domains: list[str]) -> float:
        """宫主飞宫（含末度）→ 飞入宫与该含义同域时增强。

        例：12R火星末度入2宫 → 12宫的钱财类含义（玄学财/暗财）增强。
        """
        lord = house_lord(chart, self._kb, house)
        if lord is None or lord not in chart.planets:
            return 0.0
        flown = effective_house(chart, lord)
        if flown == house or flown <= 0:
            return 0.0
        for fe in (self._table.get(flown) or []):
            if set(fe.get("domains", [])) & set(domains):
                return 1.0
        return 0.0

    # -- 证据 -------------------------------------------------------------

    def _house_connection_evidence(
        self, chart: Chart, house: int
    ) -> list[str]:
        """该宫主与关键宫位的强连接（作解读证据）。"""
        ev: list[str] = []
        seen: set[str] = set()
        for t in (2, 4, 5, 7, 8, 9, 10, 11, 12):
            if t == house:
                continue
            for c in self._classifier.classify(chart, house, t):
                # 纯相位证据已由吉凶双轨详细给出（如"土星三合月亮"），此处跳过
                if c.conn_type == "aspect":
                    continue
                if not (self._classifier.is_strong(c) or c.conn_type == "flight"):
                    continue
                line = f"{house}宫主{c.detail}"
                if line in seen:
                    continue
                seen.add(line)
                ev.append(line)
        return ev
