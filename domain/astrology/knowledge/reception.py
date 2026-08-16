"""互容（Reception）计算。

- 互溶（Mutual）= 两行星各落在对方有尊贵关系的星座内（双向）。
  凭尊严成立，不需要相位；强度/严格度由 reception.yaml 配置。
- 接纳（Acceptance）= 单向尊严 + 主相位激活。无相位不构成接纳关系
  （废弃"潜在接纳"类别，见 docs/astrology_reception.md §3）。

权重全部来自 reception.yaml / dignity.yaml，本模块只做机械查表（原则三）。
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.enums import AspectType, DignityState, Planet, Sect, Sign

from .dignity import DignityEngine
from .loader import KnowledgeBase

#: 接纳激活允许的主相位（梅花/半刑/八分等次要相位不激活接纳）
_ACTIVE_ASPECT_DEFAULTS = (
    AspectType.CONJUNCTION,
    AspectType.OPPOSITION,
    AspectType.TRINE,
    AspectType.SQUARE,
    AspectType.SEXTILE,
)


@dataclass(frozen=True)
class Reception:
    """一次互溶关系（双向尊严）。

    完整尊贵集保留（如"太阳（庙+三分）互溶木星（庙）"），
    dignity_type 取两方向最强中较弱的一档，用于排序/强度。
    """

    planet_a: Planet
    planet_b: Planet
    #: A 落在 B 尊贵星座 → A 在该处的完整尊贵集（即"A 接纳 B"的依据）
    dignities_of_a_at_b: tuple[DignityState, ...]
    #: B 落在 A 尊贵星座 → B 在该处的完整尊贵集（即"B 接纳 A"的依据）
    dignities_of_b_at_a: tuple[DignityState, ...]
    #: 最强一档（取两方向较弱）——排序/强度
    dignity_type: DignityState
    score: int
    #: 两星之间的主相位（若有；互溶凭尊严成立，相位只增强并标注性质）
    aspect_type: AspectType | None = None
    aspect_nature: str | None = None
    description_zh: str = ""


@dataclass(frozen=True)
class Acceptance:
    """一次激活接纳（单向尊严 + 相位）。"""

    acceptor: Planet       # 接纳方（被其尊贵星座接收）
    accepted: Planet       # 被接纳方（落在接纳方尊贵星座内）
    #: 接纳方在被接纳方所在星座获得的完整尊贵集（如 三分+面）
    dignities: tuple[DignityState, ...]
    #: 最强一档
    dignity_type: DignityState
    score: int
    aspect_type: AspectType
    aspect_nature: str     # HARMONIOUS / DYNAMIC / NEUTRAL
    description_zh: str = ""


Position = tuple[Sign, float]


class ReceptionEngine:
    """检测星盘内的互溶与接纳关系。"""

    def __init__(self, kb: KnowledgeBase, dignity_engine: DignityEngine | None = None):
        self._kb = kb
        self._dignity = dignity_engine or DignityEngine(kb)
        self._table = kb.reception

    # -- 配置 -------------------------------------------------------------

    def _strictness(self) -> str:
        return getattr(self._table, "strictness", "standard") or "standard"

    def _require_aspect(self) -> bool:
        return getattr(self._table, "require_aspect", True)

    def _active_aspects(self) -> set[AspectType]:
        active = getattr(self._table, "active_aspects", None)
        return set(active) if active else set(_ACTIVE_ASPECT_DEFAULTS)

    # -- 互溶 -------------------------------------------------------------

    def detect(
        self,
        planet_positions: dict[Planet, Position | Sign],
        sect: Sect | None = None,
        aspects: list | None = None,
    ) -> list[Reception]:
        """检测所有互溶对（双向尊严，凭尊严成立，不需相位）。

        完整尊贵集与两者相位（若有）一并保留。
        仅参与行星参与（三王星世代性 + 虚点，见 reception.yaml excluded_planets）。
        """
        positions = self._participating(planet_positions)
        strictness = self._strictness()
        planets = list(positions.keys())
        aspect_map = self._aspect_map(aspects or [])
        active = self._active_aspects()
        receptions: list[Reception] = []

        for i, a in enumerate(planets):
            for b in planets[i + 1:]:
                d_ab = self._dignities_of(b, positions[a], sect)  # b 在 a 所在星座的尊贵 → b 接纳 a
                d_ba = self._dignities_of(a, positions[b], sect)  # a 在 b 所在星座的尊贵 → a 接纳 b
                if not self._passes_direction(d_ab, strictness):
                    continue
                if not self._passes_direction(d_ba, strictness):
                    continue

                best_ab, sc_ab = self._best_dignity(d_ab)
                best_ba, sc_ba = self._best_dignity(d_ba)
                if sc_ab <= sc_ba:
                    dignity_type, score = best_ab, sc_ab
                else:
                    dignity_type, score = best_ba, sc_ba

                aspect = aspect_map.get((a, b))
                aspect_type = aspect.aspect_type if aspect and aspect.aspect_type in active else None
                aspect_nature = self._kb.aspect(aspect_type).nature if aspect_type else None

                receptions.append(
                    Reception(
                        planet_a=a,
                        planet_b=b,
                        dignities_of_a_at_b=tuple(d_ba),
                        dignities_of_b_at_a=tuple(d_ab),
                        dignity_type=dignity_type,
                        score=score,
                        aspect_type=aspect_type,
                        aspect_nature=aspect_nature,
                        description_zh=(
                            f"{self._kb.planet(a).name_zh}与{self._kb.planet(b).name_zh}"
                            f"互溶（{dignity_type.value}）"
                        ),
                    )
                )
        return receptions

    # -- 接纳（单向 + 相位激活）-------------------------------------------

    def detect_acceptance(
        self,
        planet_positions: dict[Planet, Position | Sign],
        aspects: list,
        sect: Sect | None = None,
    ) -> list[Acceptance]:
        """检测所有激活接纳（单向尊严 + 主相位）。无相位单向尊严不产出。"""
        positions = self._participating(planet_positions)
        planets = list(positions.keys())
        aspect_map = self._aspect_map(aspects)
        active = self._active_aspects()
        require_aspect = self._require_aspect()

        # 已成互溶的对，不再重复计入接纳（互溶是更强的绑定）
        mutual_pairs = {
            (r.planet_a, r.planet_b) for r in self.detect(positions, sect)
        }

        acceptances: list[Acceptance] = []
        for a in planets:
            for b in planets:
                if a == b or (a, b) in mutual_pairs or (b, a) in mutual_pairs:
                    continue
                # b 接纳 a：a 落在 b 的尊贵星座内
                states = self._dignities_of(b, positions[a], sect)
                # 严格度同样适用于接纳：非庙/旺时，三分/界/面需"有其二"
                if not self._passes_direction(states, self._strictness()):
                    continue
                aspect = aspect_map.get((a, b))
                if require_aspect and aspect is None:
                    continue  # 无相位 → 不构成接纳

                best, score = self._best_dignity(states)
                aspect_type = aspect.aspect_type if aspect else AspectType.CONJUNCTION
                if aspect_type not in active:
                    continue
                nature = self._kb.aspect(aspect_type).nature if aspect else "NEUTRAL"

                acceptances.append(
                    Acceptance(
                        acceptor=b,
                        accepted=a,
                        dignities=tuple(states),
                        dignity_type=best,
                        aspect_type=aspect_type,
                        aspect_nature=nature,
                        score=score,
                        description_zh=(
                            f"{self._kb.planet(b).name_zh}接纳{self._kb.planet(a).name_zh}"
                            f"（{best.value}·{nature}）"
                        ),
                    )
                )
        return acceptances

    # -- 尊贵辅助 ---------------------------------------------------------

    def _dignities_of(
        self, planet: Planet, position: Position, sect: Sect | None
    ) -> list[DignityState]:
        """某行星在某位置获得的【正面】尊贵集（用于被接纳判定）。

        只返回 DOMICILE/EXALTATION/TRIPLICITY/TERM/FACE——失势/陷/游走
        不属于"接纳"，返回空即"未被接纳"。
        """
        sign, degree = position
        info = self._kb.planet(planet)
        states: list[DignityState] = []

        if sign in self._dignity.domicile_signs(planet):
            states.append(DignityState.DOMICILE)
        ex = info.exaltation
        if ex and sign == ex[0]:
            states.append(DignityState.EXALTATION)
        if self._triplicity_holds(planet, sign, sect):
            states.append(DignityState.TRIPLICITY)
        if self._dignity._is_term_lord(planet, sign, degree):
            states.append(DignityState.TERM)
        if self._dignity._is_face_lord(planet, sign, degree):
            states.append(DignityState.FACE)
        return states

    def _triplicity_holds(
        self, planet: Planet, sign: Sign, sect: Sect | None
    ) -> bool:
        """按 triplicity.mode 判定三分主。

        - all : 三分三主都算（日/夜/参予主）——项目中默认
        - sect: 仅按昼夜取一主（与 DignityEngine 一致）
        """
        element = self._kb.sign(sign).element
        lords = self._kb.dignity.triplicity_lords.get(element)
        if not lords:
            return False
        mode = getattr(self._table, "triplicity_mode", "all") or "all"
        if mode == "sect":
            key = "day" if sect == Sect.DAY else "night"
            return lords.get(key) == planet
        return planet in lords.values()

    def _best_dignity(self, states: list[DignityState]) -> tuple[DignityState | None, int]:
        """取尊贵列表中最强的一档及其分数（来自 reception.yaml scores）。"""
        # 排序：DOMICILE > EXALTATION > TRIPLICITY > TERM > FACE
        order = {DignityState.DOMICILE: 5, DignityState.EXALTATION: 4,
                 DignityState.TRIPLICITY: 3, DignityState.TERM: 2, DignityState.FACE: 1}
        best = None
        best_rank = -1
        for s in states:
            rank = order.get(s, 0)
            if rank > best_rank:
                best, best_rank = s, rank
        score = self._table.scores.get(best, 0) if best else 0
        return best, score

    def _passes_direction(self, states: list[DignityState], strictness: str) -> bool:
        """单方向的互溶严格度检验。"""
        if not states:
            return False
        best, _ = self._best_dignity(states)
        if strictness == "lenient":
            return True
        if strictness == "strict":
            return best in (DignityState.DOMICILE, DignityState.EXALTATION)
        # standard：庙/旺单一；三分/界/面需同方向"有其二"
        if best in (DignityState.DOMICILE, DignityState.EXALTATION):
            return True
        weak = [s for s in states if s in (
            DignityState.TRIPLICITY, DignityState.TERM, DignityState.FACE
        )]
        return len(weak) >= 2

    # -- 输入规范化 -------------------------------------------------------

    def _participating(
        self, positions: dict[Planet, Position | Sign]
    ) -> dict[Planet, Position]:
        """过滤出参与互溶/接纳的星体（排除三王星与虚点）。"""
        excluded = set(getattr(self._table, "excluded_planets", []) or [])
        out: dict[Planet, Position] = {}
        for p, v in positions.items():
            if p in excluded:
                continue
            if isinstance(v, tuple):
                out[p] = (v[0], float(v[1]))
            else:
                out[p] = (v, 15.0)  # 未给度数时用中值（仅影响界/面判定）
        return out

    @staticmethod
    def _normalize(
        positions: dict[Planet, Position | Sign]
    ) -> dict[Planet, Position]:
        out: dict[Planet, Position] = {}
        for p, v in positions.items():
            if isinstance(v, tuple):
                out[p] = (v[0], float(v[1]))
            else:
                out[p] = (v, 15.0)  # 未给度数时用中值（仅影响界/面判定）
        return out

    @staticmethod
    def _aspect_map(aspects: list) -> dict[tuple[Planet, Planet], object]:
        m: dict[tuple[Planet, Planet], object] = {}
        for asp in aspects:
            m[(asp.body1, asp.body2)] = asp
            m[(asp.body2, asp.body1)] = asp
        return m
