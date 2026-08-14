"""三轨合成器（领域引擎 v2 §4）：征象轨 × 宫主轨 × 互溶桥 → 领域合读。

确定性，无 LLM（硬线：占星结论全由 Domain 出，LLM 自由度只在"怎么疗愈/怎么陪伴"）。

领域 = 语义场精心挑选的子集，配方来自 intent_profiles.yaml；core_houses/house_lords
描述宫位结构，领域行星角色唯一来自 planet_nature.domain_signals（docs/domain_engine_v2.md §3）。对任一领域：

- 轨A · 征象轨（色彩）：domain_signals=core 的先天征象星状态 → 能力与底色
- 轨B · 宫主轨（结构，优先）：配方 core_houses 的宫主星状态 → 正轨能否立住
- 轨C · 互溶桥（通道）：征象星 × 宫主星 互溶/接纳/相位/飞宫/同宫 → 哪条路径兑现

合读规则（§4.4）：结构轨定成败、色彩轨定表现、桥轨定路径，五档结论可追溯。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shared.constants import ASPECT_ZH as _ASPECT_ZH
from shared.enums import Planet, PlanetSpeed, Sect
from shared.models import Chart

from domain.astrology.common import aspect_score, aspects_to, dignity_total, house_lord
from domain.astrology.interpretation.synapsis import ConnectionClassifier, effective_house
from domain.astrology.knowledge import DignityEngine
from domain.astrology.knowledge.loader import KnowledgeBase, domain_planet_roles

# 有桥阈值：主相位(2.5)及以上算"通道兑现"
_BRIDGE_MIN = 2.5
# 轨分强/弱阈值：净吉凶分 ≥ +1.0 算强，≤ -1.0 算弱
_TRACK_STRONG = 1.0
_TRACK_WEAK = -1.0


@dataclass(frozen=True)
class _PlanetAssessmentR9:
    """R9-scoped single-planet assessment used by the compositor only."""

    essential_pos: float
    essential_neg: float
    accidental_pos: float
    accidental_neg: float
    relational_pos: float
    relational_neg: float
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class TrackResult:
    """一条合成轨的结果。"""

    track: str                 # "A" / "B" / "C"
    kind: str                  # signification / lordship / bridge
    label: str                 # 中文轨名
    score: float               # 净分（轨A/B：吉-凶；轨C：桥强度 0-4）
    verdict: str               # strong / weak / mixed / none
    evidence: tuple[str, ...]
    planets: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "track": self.track,
            "kind": self.kind,
            "label": self.label,
            "score": round(self.score, 2),
            "verdict": self.verdict,
            "evidence": list(self.evidence),
            "planets": list(self.planets),
        }


@dataclass(frozen=True)
class CompositeReading:
    """一个领域的合成结论（三轨 + 合读）。"""

    domain: str
    code: str                  # smooth / detour / platform_weak_edge / capability_mismatch / hard / neutral
    title: str                 # 中文结论
    narrative: str             # 一句话叙事
    tracks: tuple[TrackResult, ...]

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "code": self.code,
            "title": self.title,
            "narrative": self.narrative,
            "tracks": [t.to_dict() for t in self.tracks],
        }


class DomainCompositor:
    """领域三轨合成器：读配方 → 三轨并出 → 合读规则 → 结论。"""

    def __init__(self, kb: KnowledgeBase, profiles: dict | None = None):
        self._kb = kb
        self._dignity = DignityEngine(kb)
        self._classifier = ConnectionClassifier(kb)
        if profiles is None:
            from domain.reasoning.intent.intent_profiles import load_profiles  # noqa: PLC0415

            profiles = load_profiles()
        self._profiles = profiles

    # -- 对外 -------------------------------------------------------------

    def compose(self, chart: Chart, domain: str) -> CompositeReading | None:
        """按领域三轨合成。无配方 → None。"""
        profile = self._profiles.get(domain)
        if profile is None:
            return None

        core_houses = [int(h) for h in (profile.core_houses or [])]
        core_planets, _supporting_planets = domain_planet_roles(self._kb.planet_nature, domain)

        track_a = self._track_signification(chart, core_planets)
        track_b = self._track_lordship(chart, core_houses)
        track_c = self._track_bridge(chart, track_a.planets, track_b.planets)
        code, title, narrative = self._synthesize(track_a, track_b, track_c)

        return CompositeReading(
            domain=domain,
            code=code,
            title=title,
            narrative=narrative,
            tracks=(track_a, track_b, track_c),
        )

    # -- 共享 · R9 单星评分 ----------------------------------------------------

    def _assess_planet_r9(self, chart: Chart, planet: Planet) -> _PlanetAssessmentR9:
        """合成器局部单星评分：用已提交公共 helper，避免依赖后续 v3 assess_planet。"""
        name = self._kb.planet(planet).name_zh
        epos, eneg = 0.0, 0.0
        apos, aneg = 0.0, 0.0
        rpos, rneg = 0.0, 0.0
        ev: list[str] = []

        dt = dignity_total(chart, self._kb, planet, self._dignity)
        if dt > 0:
            epos += dt * 0.35
            ev.append(f"{name}尊贵{dt:+d}")
        elif dt < 0:
            eneg += abs(dt) * 0.35
            ev.append(f"{name}受克（尊贵{dt:+d}）")

        cp = chart.planets[planet]
        if cp.is_cazimi:
            apos += 1.0
            ev.append(f"{name}日核")
        elif cp.is_combust:
            aneg += 1.0
            ev.append(f"{name}燃烧")
        elif cp.is_under_beams:
            aneg += 0.5
            ev.append(f"{name}日光下")

        if planet in {Planet.JUPITER, Planet.VENUS}:
            apos += 0.8 * self._benefic_malefic_scale(planet, chart.sect)
            ev.append(f"{name}为吉星")
        if planet in {Planet.MARS, Planet.SATURN}:
            aneg += 0.8 * self._benefic_malefic_scale(planet, chart.sect)
            ev.append(f"{name}为凶星")

        angularity = self._kb.house(cp.house.house).angularity
        if angularity == "ANGULAR":
            apos += 1.0
            ev.append(f"{name}落角宫")
        elif angularity == "SUCCEDENT":
            apos += 0.5
            ev.append(f"{name}落续宫")

        if cp.speed == PlanetSpeed.RETROGRADE:
            aneg += 0.5
            ev.append(f"{name}逆行")

        if planet in (Planet.SUN, Planet.MOON):
            if chart.sect == Sect.DAY:
                if planet == Planet.SUN:
                    apos += 0.5
                    ev.append(f"{name}得时")
                else:
                    aneg += 0.5
                    ev.append(f"{name}失时")
            elif chart.sect == Sect.NIGHT:
                if planet == Planet.MOON:
                    apos += 0.5
                    ev.append(f"{name}得时")
                else:
                    aneg += 0.5
                    ev.append(f"{name}失时")

        for asp in aspects_to(chart, planet):
            info = self._kb.aspects.get(asp.aspect_type)
            if info is None or asp.aspect_type.value not in {
                "conjunction", "opposition", "trine", "square", "sextile"
            }:
                continue
            other = asp.body2 if asp.body1 == planet else asp.body1
            other_zh = self._kb.planet(other).name_zh
            aspect_zh = _ASPECT_ZH.get(asp.aspect_type.value, asp.aspect_type.value)
            score = aspect_score(self._kb, asp)
            if info.nature == "HARMONIOUS":
                rpos += score * 0.3
                ev.append(f"{name}{aspect_zh}{other_zh}（和谐）")
            elif info.nature == "DYNAMIC":
                received = self._classifier.is_received(chart, planet, other)
                weight = 0.3 if received else 0.5
                tag = "磨合" if received else "未接纳"
                rneg += abs(score) * weight
                ev.append(f"{name}受{other_zh}{aspect_zh}（{tag}）")

        for helper, kind in self._helpers_of_r9(chart, planet):
            if kind == "mutual":
                rpos += 0.5
                ev.append(f"{name}↔{self._kb.planet(helper).name_zh}互溶")
            else:
                rpos += 0.3
                ev.append(f"{self._kb.planet(helper).name_zh}接纳{name}")

        return _PlanetAssessmentR9(
            essential_pos=epos,
            essential_neg=eneg,
            accidental_pos=apos,
            accidental_neg=aneg,
            relational_pos=rpos,
            relational_neg=rneg,
            evidence=tuple(dict.fromkeys(ev)),
        )

    def _helpers_of_r9(self, chart: Chart, planet: Planet) -> list[tuple[Planet, str]]:
        """R9 局部帮手星：避免依赖后续 v3 synapsis.helpers_of。"""
        positions = self._classifier._positions(chart)  # noqa: SLF001 - R9 scoped compatibility shim
        helpers: list[tuple[Planet, str]] = []
        for reception in self._classifier._reception.detect(positions, sect=chart.sect):  # noqa: SLF001
            if planet in (reception.planet_a, reception.planet_b):
                other = reception.planet_b if reception.planet_a == planet else reception.planet_a
                helpers.append((other, "mutual"))
        for acceptance in self._classifier._reception.detect_acceptance(  # noqa: SLF001
            positions, chart.aspects, sect=chart.sect
        ):
            if acceptance.accepted == planet:
                helpers.append((acceptance.acceptor, "acceptance"))
        return helpers

    @staticmethod
    def _benefic_malefic_scale(planet: Planet, chart_sect: Sect | None) -> float:
        """吉凶星昼夜缩放：吉星得时满额，凶星得时减半。"""
        if chart_sect is None:
            return 1.0
        in_sect = (
            (planet in (Planet.JUPITER, Planet.SATURN) and chart_sect == Sect.DAY)
            or (planet in (Planet.VENUS, Planet.MARS) and chart_sect == Sect.NIGHT)
        )
        if planet in (Planet.JUPITER, Planet.VENUS):
            return 1.0 if in_sect else 0.5
        if planet in (Planet.MARS, Planet.SATURN):
            return 0.5 if in_sect else 1.0
        return 1.0

    # -- 轨 A · 先天征象（色彩） --------------------------------------------

    def _track_signification(
        self, chart: Chart, core_planets: list[str]
    ) -> TrackResult:
        epos, eneg, apos, aneg, rpos, rneg = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        ev: list[str] = []
        planets: list[str] = []
        for key in core_planets:
            try:
                pl = Planet(key)
            except ValueError:
                continue
            if pl not in chart.planets:
                continue
            a = self._assess_planet_r9(chart, pl)
            epos += a.essential_pos
            eneg += a.essential_neg
            apos += a.accidental_pos
            aneg += a.accidental_neg
            rpos += a.relational_pos
            rneg += a.relational_neg
            ev.extend(a.evidence)
            planets.append(pl.value)
        return TrackResult(
            track="A",
            kind="signification",
            label="征象轨·先天征象",
            score=(epos + apos + rpos) - (eneg + aneg + rneg),
            verdict=self._verdict_axes(epos - eneg, apos - aneg, rpos - rneg),
            evidence=tuple(dict.fromkeys(ev)),
            planets=tuple(planets),
        )

    # -- 轨 B · 宫主（结构，优先） ------------------------------------------

    def _track_lordship(self, chart: Chart, core_houses: list[int]) -> TrackResult:
        epos, eneg, apos, aneg, rpos, rneg = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        ev: list[str] = []
        planets: list[str] = []
        seen: set[Planet] = set()
        for h in core_houses:
            lord = house_lord(chart, self._kb, h)
            if lord is None or lord in seen:
                continue
            seen.add(lord)
            if lord not in chart.planets:
                continue
            a = self._assess_planet_r9(chart, lord)
            epos += a.essential_pos
            eneg += a.essential_neg
            apos += a.accidental_pos
            aneg += a.accidental_neg
            rpos += a.relational_pos
            rneg += a.relational_neg
            ev.extend(a.evidence)
            planets.append(lord.value)
        return TrackResult(
            track="B",
            kind="lordship",
            label="宫主轨·宫性结构",
            score=(epos + apos + rpos) - (eneg + aneg + rneg),
            verdict=self._verdict_axes(epos - eneg, apos - aneg, rpos - rneg),
            evidence=tuple(dict.fromkeys(ev)),
            planets=tuple(planets),
        )

    # -- 轨 C · 互溶桥（通道） ----------------------------------------------

    def _track_bridge(
        self, chart: Chart, signifiers: tuple[str, ...], lords: tuple[str, ...]
    ) -> TrackResult:
        best = 0.0
        ev: list[str] = []
        involved: list[str] = []
        for a_key in signifiers:
            for b_key in lords:
                if a_key == b_key:
                    continue
                pa, pb = Planet(a_key), Planet(b_key)
                s, sev = self._pair_bridge(chart, pa, pb)
                if s > best:
                    best = s
                    ev = sev
                    involved = [pa.value, pb.value]
        if best >= 4.0:
            verdict = "strong"
        elif best >= _BRIDGE_MIN:
            verdict = "medium"
        else:
            verdict = "none"
        return TrackResult(
            track="C",
            kind="bridge",
            label="互溶桥·兑现通道",
            score=best,
            verdict=verdict,
            evidence=tuple(ev),
            planets=tuple(involved),
        )

    def _pair_bridge(self, chart: Chart, a: Planet, b: Planet) -> tuple[float, list[str]]:
        """两星通道强度：互溶/接纳 3.5 > 主相位 2.5 > 飞宫 2.0 > 同宫 1.0 > 无 0。

        天海冥不参与接纳（reception 已排除）→ 它们的相位只走"主相位"档，算关联而非结构。
        """
        azh = lambda pl: self._kb.planet(pl).name_zh  # noqa: E731
        if self._classifier.is_received(chart, a, b):
            return 3.5, [f"{azh(a)}↔{azh(b)}互溶/接纳"]
        for asp in chart.aspects:
            if {asp.body1, asp.body2} == {a, b}:
                aps = _ASPECT_ZH.get(asp.aspect_type.value, asp.aspect_type.value)
                return 2.5, [f"{azh(a)}与{azh(b)}{aps}"]
        for p, t in ((a, b), (b, a)):
            if effective_house(chart, p) == chart.planets[t].house.house:
                # 飞宫证据写宫号而非目标行星名（t 是行星，不是宫）
                return 2.0, [f"{azh(p)}飞{chart.planets[t].house.house}宫"]
        if chart.planets[a].house.house == chart.planets[b].house.house:
            return 1.0, [f"{azh(a)}与{azh(b)}同宫"]
        return 0.0, []

    # -- 合读规则（§4.4，确定性可追溯） -------------------------------------

    def _synthesize(
        self, track_a: TrackResult, track_b: TrackResult, track_c: TrackResult
    ) -> tuple[str, str, str]:
        structure = track_b.verdict
        color = track_a.verdict
        has_bridge = track_c.score >= _BRIDGE_MIN

        if has_bridge and structure == "strong" and color == "strong":
            return "smooth", "顺遂", "才能走正轨——结构托底、征象加持、互溶桥兑现，锦上添花。"
        if has_bridge and structure == "weak" and color == "strong":
            return "detour", "绕道成才", "结构不硬但你有本事——互溶桥指了条非主流的兑现路径，绕开正轨走通。"
        if not has_bridge and structure == "strong" and color == "weak":
            return "platform_weak_edge", "有平台缺锋芒", "结构托底、征象偏弱——平台在，但能力锋芒需要补。"
        if not has_bridge and structure == "weak" and color == "strong":
            return "capability_mismatch", "有能力不对口", "才华与结构之间没有通道——有能力，但得主动搭建连接才能兑现。"
        if not has_bridge and structure == "weak" and color == "weak":
            return "hard", "先天吃力", "结构与征象双弱、且无桥可绕——该领域先天吃力，建议借助外部支持。"
        return "neutral", "中性", "结构、征象、通道都在中间地带——需结合具体盘面细看。"

    @staticmethod
    def _verdict_axes(essential_net: float, accidental_net: float, relational_net: float) -> str:
        """四象限判：本质（尊贵）优先，本质中性时境遇+关系兜底（吉凶两论不净值）。"""
        if essential_net >= _TRACK_STRONG:
            return "strong"
        if essential_net <= _TRACK_WEAK:
            return "weak"
        support = accidental_net + relational_net
        if support >= _TRACK_STRONG:
            return "strong"
        if support <= _TRACK_WEAK:
            return "weak"
        return "mixed"
