"""语义场选择引擎（确定性，无 LLM）。

同一宫位是多义词（语义场）。三步把控：
① 语境选择：问题域（domain）过滤 → 该宫位只激活相关含义（防关键词倾倒）
② per-signification 调制：每个含义按动态承载者（实盘宫主/宫内星/领域征象星）算强度
   （词级基础 × carrier 对应正/负轴 × 宫结构加权贡献），不按整宫单一状态平摊
③ 收敛门槛：event（事件预言）条目需强连接收敛数达标才发射；tendency 默认

宫主飞宫（含宫头末度）→ 飞行增强；共振词挂在解读上（LLM 只转述，不发明）。
"""

from __future__ import annotations

import re

from shared.enums import Planet
from shared.models import Chart

from domain.astrology.common import assess_planet, house_lord
from domain.astrology.knowledge import DignityEngine
from domain.astrology.knowledge.loader import KnowledgeBase, domain_planet_roles
from domain.astrology.interpretation.models import SignificationItem
from domain.astrology.interpretation.synapsis import ConnectionClassifier, effective_house

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
        enrichment: dict | None = None,
    ) -> list[SignificationItem]:
        """按问题域激活各宫位语义场，产出排序后的解读条目。

        domain: career / relationship / wealth / health / emotion / family / learning / self
        enrichment: 可选 ConsultCallPlan/DecomposedIntent 承载者；只决定读哪些星，评分仍走 assess_planet。
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
                # per-signification 调制：按本轮动态承载者（实盘宫主/宫内星/领域征象星）算强度，且按正/负/中性语义切片取对应轨道。
                carriers = self._carrier_tokens(chart, house, domain, enrichment)
                gpos, gneg, gov_pos_ev, gov_neg_ev = self._carrier_quality(chart, carriers)
                strength = self._strength(chart, house, e, pos, neg, gpos, gneg)
                if strength is None or strength < _MIN_STRENGTH:
                    continue
                # 各论各的：正向解读吃吉轨证据，负向解读吃凶轨证据；中性同时展示两边。
                pol = e.get("polarity", "neutral")
                if pol == "positive":
                    base_ev = pos_ev + gov_pos_ev
                elif pol == "negative":
                    base_ev = neg_ev + gov_neg_ev
                else:
                    base_ev = pos_ev + neg_ev + gov_pos_ev + gov_neg_ev
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
            lord_assessment = assess_planet(chart, self._kb, lord, self._dignity, self._classifier)
            lpos, lneg = self._house_weighted_score(lord_assessment)
            pos += lpos
            neg += lneg
            pos_ev.extend(self._house_axis_evidence(name, house, lord_assessment.essential_ev, positive=True))
            pos_ev.extend(self._polarity_evidence(lord_assessment.accidental_ev, positive=True))
            pos_ev.extend(self._polarity_evidence(lord_assessment.relational_ev, positive=True))
            neg_ev.extend(self._house_axis_evidence(name, house, lord_assessment.essential_ev, positive=False))
            neg_ev.extend(self._polarity_evidence(lord_assessment.accidental_ev, positive=False))
            neg_ev.extend(self._polarity_evidence(lord_assessment.relational_ev, positive=False))
        else:
            neg_ev.append(f"{house}宫主不明")

        for pl, cp in chart.planets.items():
            if pl not in _MEANINGFUL or cp.house.house != house:
                continue
            pname = self._kb.planet(pl).name_zh
            assessment = assess_planet(chart, self._kb, pl, self._dignity, self._classifier)
            apos, aneg = self._house_weighted_score(assessment)
            pos += apos * 0.5
            neg += aneg * 0.5
            pos_ev.extend(self._occupant_axis_evidence(pname, house, assessment.essential_ev, positive=True))
            pos_ev.extend(self._polarity_evidence(assessment.accidental_ev, positive=True))
            pos_ev.extend(self._polarity_evidence(assessment.relational_ev, positive=True))
            neg_ev.extend(self._occupant_axis_evidence(pname, house, assessment.essential_ev, positive=False))
            neg_ev.extend(self._polarity_evidence(assessment.accidental_ev, positive=False))
            neg_ev.extend(self._polarity_evidence(assessment.relational_ev, positive=False))

        return pos, neg, list(dict.fromkeys(pos_ev)), list(dict.fromkeys(neg_ev))

    @staticmethod
    def _house_weighted_score(assessment) -> tuple[float, float]:
        """house 层消费 assess_planet：尊贵打底，刑冲压力优先保留。"""
        house_pos = (
            assessment.essential_pos
            + assessment.accidental_pos * 0.4
            + assessment.relational_pos * 0.3
        )
        house_neg = (
            assessment.essential_neg
            + assessment.accidental_neg * 0.8
            + assessment.relational_neg * 1.5
        )
        return house_pos, house_neg

    @staticmethod
    def _polarity_evidence(evidence: tuple[str, ...], *, positive: bool) -> list[str]:
        """按证据语义拆正负轨，避免正向解读携带凶轨证据。"""
        negative_markers = ("受克", "受", "刑", "冲", "燃烧", "日光下", "逆行", "失时", "为凶星")
        positive_markers = ("尊贵", "和谐", "互溶", "接纳", "日核", "落角宫", "落续宫", "得时", "为吉星")
        if positive:
            return [
                ev for ev in evidence
                if any(marker in ev for marker in positive_markers)
                and not any(marker in ev for marker in negative_markers)
            ]
        return [ev for ev in evidence if any(marker in ev for marker in negative_markers)]

    @staticmethod
    def _house_axis_evidence(
        planet_name: str, house: int, evidence: tuple[str, ...], *, positive: bool
    ) -> list[str]:
        """assess_planet 本质轴证据 → 宫主语境证据（保持宫结构可读）。"""
        marker = f"{planet_name}尊贵" if positive else f"{planet_name}受克（"
        return [ev.replace(planet_name, f"{planet_name}为{house}宫主", 1) for ev in evidence if marker in ev]

    @staticmethod
    def _occupant_axis_evidence(
        planet_name: str, house: int, evidence: tuple[str, ...], *, positive: bool
    ) -> list[str]:
        """assess_planet 本质轴证据 → 宫内星语境证据。"""
        marker = f"{planet_name}尊贵" if positive else f"{planet_name}受克（"
        return [ev.replace(planet_name, f"{planet_name}落{house}宫", 1) for ev in evidence if marker in ev]

    # -- 强度调制 ---------------------------------------------------------

    def _strength(
        self, chart: Chart, house: int, entry: dict, pos: float, neg: float,
        gpos: float, gneg: float,
    ) -> float | None:
        """per-signification 调制（领域引擎 v2 §5）。

        含义强度 = 词级基础(intensity)
                 × (1 + carrier 对应正/负轴 × 0.4，最低保 0.15)  # 动态承载者状态（词级，占主导）
                 × (1 + 宫极性贡献 × 0.25)                 # 宫结构只贡献一部分，不独占
                 + 飞宫增强

        修复整宫状态平摊：同一宫的不同含义不共用“整宫净值”。本轮问题先解析
        实盘宫主/宫内星/领域征象星，再逐条按承载者吉凶两轨调制，互不污染。
        """
        base = float(entry.get("intensity", 2))
        pol = entry.get("polarity", "neutral")

        if pol == "positive":
            gov_factor = max(1 + gpos * 0.4, 0.15)
            house_contrib = pos
        elif pol == "negative":
            gov_factor = max(1 + gneg * 0.4, 0.15)
            house_contrib = neg
        else:
            gov_factor = max(1 + max(gpos, gneg) * 0.4, 0.15)
            house_contrib = max(pos, neg)
        s = base * gov_factor * (1 + house_contrib * 0.25)

        s += self._flight_boost(chart, house, entry.get("domains", []))

        # 事件预言门槛：需强连接收敛数达标（倾向切片默认直接发射）
        if entry.get("gated") == "event":
            targets = list(entry.get("corroborate_houses", []))
            corr = self._classifier.strong_count(chart, house, targets)
            if corr < int(entry.get("requires_corroboration", 2)):
                return None
            s += corr

        return round(s, 2)

    # -- per-signification 承载者 -------------------------------------------

    def _carrier_tokens(
        self,
        chart: Chart,
        house: int,
        domain: str,
        enrichment: dict | None = None,
    ) -> list[str]:
        """本轮问题的动态承载者：实盘宫主/宫内星/领域征象星。"""
        tokens: list[str] = []

        def add(value) -> None:
            if value in (None, ""):
                return
            if isinstance(value, Planet):
                token = value.value
            elif isinstance(value, int):
                token = self._lord_token(value)
            else:
                token = str(value)
            if token not in tokens:
                tokens.append(token)

        # 当前语义宫的实际宫主 + 宫内星，是 house consult 的最小动态地基。
        add(self._lord_token(house))
        for pl, cp in chart.planets.items():
            if pl in _MEANINGFUL and cp.house.house == house:
                add(pl)

        # 领域自然征象星来自 planet_nature.domain_signals，保持唯一知识源。
        core, supporting = domain_planet_roles(self._kb.planet_nature, domain)
        for token in [*core, *supporting]:
            add(token)

        if enrichment:
            for key in ("focus_house_lords", "focus_houses"):
                for h in enrichment.get(key) or []:
                    try:
                        add(self._lord_token(int(h)))
                    except (TypeError, ValueError):
                        continue
            for key in ("house_lord_planets", "house_occupants", "focus_planets"):
                for token in enrichment.get(key) or []:
                    add(token)
            for placement in enrichment.get("house_lord_placements") or []:
                if not isinstance(placement, dict):
                    continue
                try:
                    placement_house = int(placement.get("house") or 0)
                except (TypeError, ValueError):
                    continue
                if placement_house == house:
                    add(placement.get("lord"))

        return tokens

    @staticmethod
    def _lord_token(house: int) -> str:
        """宫号 → 宫主 token（兼容既有 {n}st/nd/rd/th_lord 解析）。"""
        suffix = "th"
        if house % 100 not in (11, 12, 13):
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(house % 10, "th")
        return f"{house}{suffix}_lord"

    def _carrier_quality(
        self, chart: Chart, carriers: list[str]
    ) -> tuple[float, float, list[str], list[str]]:
        """动态承载者状态 → (吉分量, 凶分量, 吉证据, 凶证据)。"""
        gpos, gneg = 0.0, 0.0
        pos_ev: list[str] = []
        neg_ev: list[str] = []
        seen: set[Planet] = set()
        for token in carriers:
            pl = self._resolve_carrier(chart, token)
            if pl is None or pl in seen or pl not in chart.planets:
                continue
            seen.add(pl)
            assessment = assess_planet(chart, self._kb, pl, self._dignity, self._classifier)
            gpos += assessment.pos
            gneg += assessment.neg
            pos_ev.extend(self._polarity_evidence(assessment.evidence, positive=True))
            neg_ev.extend(self._polarity_evidence(assessment.evidence, positive=False))
        return gpos, gneg, list(dict.fromkeys(pos_ev)), list(dict.fromkeys(neg_ev))

    def _resolve_carrier(self, chart: Chart, carrier: str) -> Planet | None:
        """carrier token → 行星。'3rd_lord' → 实盘 3 宫主星；'mercury' → 水星。"""
        m = re.fullmatch(r"(\d+)(?:st|nd|rd|th)_lord", carrier)
        if m:
            return house_lord(chart, self._kb, int(m.group(1)))
        try:
            return Planet(carrier)
        except ValueError:
            return None

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
                # detail 自带行星名（如"火星飞2宫"、"木星↔月亮互溶"），无需再拼"3宫主"前缀
                line = c.detail
                if line in seen:
                    continue
                seen.add(line)
                ev.append(line)
        return ev
