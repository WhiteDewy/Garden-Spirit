"""先天尊贵（Essential Dignity）计算。

权重全部来自 dignity.yaml 的 scores，本模块只做机械查表。
LLM 永不参与。
"""

from __future__ import annotations

from shared.enums import DignityState, Element, Planet, Sect, Sign

from .loader import DignityTable, KnowledgeBase


class DignityEngine:
    """给定行星在星座内的位置，算出尊贵状态与总分。"""

    def __init__(self, kb: KnowledgeBase):
        self._kb = kb
        self._table: DignityTable = kb.dignity

    # -- 查表访问 ---------------------------------------------------------

    def domicile_signs(self, planet: Planet) -> list[Sign]:
        """该行星的庙（按启用 scheme）。"""
        info = self._kb.planet(planet)
        if self._table.scheme == "traditional" and info.traditional_domicile:
            return info.traditional_domicile
        return info.domicile

    def exaltation(self, planet: Planet) -> tuple[Sign, float] | None:
        return self._kb.planet(planet).exaltation

    def detriment_signs(self, planet: Planet) -> list[Sign]:
        return self._kb.planet(planet).detriment

    def fall(self, planet: Planet) -> tuple[Sign, float] | None:
        return self._kb.planet(planet).fall

    def score(self, state: DignityState) -> int:
        return self._table.scores.get(state, 0)

    # -- 计算 -------------------------------------------------------------

    def compute(
        self, planet: Planet, sign: Sign, degree: float, sect: Sect | None = None
    ) -> tuple[list[DignityState], int]:
        """计算行星在 (sign, degree) 的尊贵状态。

        Returns:
            (states, total_score)
        """
        states: list[DignityState] = []

        if sign in self.domicile_signs(planet):
            states.append(DignityState.DOMICILE)
        elif sign in self.detriment_signs(planet):
            states.append(DignityState.DETRIMENT)

        ex = self.exaltation(planet)
        if ex and sign == ex[0]:
            states.append(DignityState.EXALTATION)
        else:
            fl = self.fall(planet)
            if fl and sign == fl[0]:
                states.append(DignityState.FALL)

        # 三分主星（需 sect）
        if sect is not None:
            triplicity_lord = self._triplicity_lord(sign, sect)
            if triplicity_lord == planet:
                states.append(DignityState.TRIPLICITY)

        # 界
        if self._is_term_lord(planet, sign, degree):
            states.append(DignityState.TERM)

        # 面
        if self._is_face_lord(planet, sign, degree):
            states.append(DignityState.FACE)

        if not states:
            states.append(DignityState.PEREGRINE)

        total = sum(self.score(s) for s in states)
        return states, total

    # -- 内部 -------------------------------------------------------------

    def _triplicity_lord(self, sign: Sign, sect: Sect) -> Planet | None:
        element = self._kb.sign(sign).element
        lords = self._table.triplicity_lords.get(element)
        if not lords:
            return None
        if sect == Sect.DAY:
            return lords.get("day")
        return lords.get("night")

    def _is_term_lord(self, planet: Planet, sign: Sign, degree: float) -> bool:
        term = self._table.terms.get(sign)
        if not term:
            return False
        for boundary, lord in zip(term.ranges, term.lords):
            if degree < boundary:
                return lord == planet
        return term.lords[-1] == planet

    def _is_face_lord(self, planet: Planet, sign: Sign, degree: float) -> bool:
        face = self._table.faces.get(sign)
        if not face:
            return False
        for boundary, lord in zip(face.ranges, face.lords):
            if degree < boundary:
                return lord == planet
        return face.lords[-1] == planet
