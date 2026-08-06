"""LearningService —— 学习层（L5）编排器：验前事 → 置信度校准。

产品循环（后半段的新一步）：
  用户记录人生事件 → 法达倒推（Domain 验证）→ 命中就校准画像置信度 → 持久化
  用户反馈判断（confirmed/refuted）→ 校准该判断置信度

冻结架构：
- Domain（domain/learning/verifier.py）只算"验没验上"，无 io。
- 本服务在 Application 层，负责 load → verify → calibrate → save。
- 置信度是 Domain 数值的累积调整，绝不来自 LLM。
"""

from __future__ import annotations

from datetime import datetime

from foundation.database.store import GardenStore
from foundation.logger import get_logger
from foundation.utils import new_id, utc_now_aware
from shared.models import Chart, LifeEvent, Person, VerifiedFinding

from domain.learning.verifier import verify_all_findings
from domain.timeline.firdaria import compute_firdaria

logger = get_logger("application.learning.service")

#: 置信度校准参数（一次校准幅度 + 上下限）
CONFIRM_DELTA = 0.15     # 用户确认（feedback=confirmed）
REFUTE_DELTA = 0.15      # 用户反驳（feedback=refuted）
EVENT_VERIFY_DELTA = 0.10  # 事件验上（时间领主命中）
CONFIDENCE_CAP = 0.95
CONFIDENCE_FLOOR = 0.10


class LearningService:
    """验前事 + 反馈校准的编排入口。"""

    def __init__(self, store: GardenStore, chart_provider):
        """chart_provider: callable(Person) -> Chart（本命盘，供法达倒推）。"""
        self._store = store
        self._chart_provider = chart_provider

    # ------------------------------------------------------------------

    def record_life_event(
        self, person: Person, label: str, occurred_at: datetime, detail: str = ""
    ) -> dict:
        """记录一条人生事件 + 用它对全部沉淀判断做验前事 + 校准置信度。

        返回 {"event_id", "period_major", "period_sub", "verifications", "calibrated"}。
        事件时间早于出生 → ValueError（API 层转 422）。
        画像不存在（还没咨询过）→ 只记事件，不做验证。
        """
        birth = person.birth.datetime_utc
        if birth.tzinfo is None:
            birth = birth.replace(tzinfo=occurred_at.tzinfo or utc_now_aware().tzinfo)
        if occurred_at < birth:
            raise ValueError("事件时间早于出生时间，无法倒推法达")

        chart = self._chart_provider(person)
        period = compute_firdaria(chart.epoch_utc, chart.sect, reference=occurred_at)

        event = LifeEvent(
            id=new_id("evt"),
            person_id=person.id,
            occurred_at=occurred_at,
            label=label,
            kind="life",
            detail=detail,
            created_at=utc_now_aware(),
        )
        self._store.save_life_event(event)

        profile = self._store.get_profile(person.id)
        if profile is None or not profile.verified_findings:
            return {
                "event_id": event.id,
                "period_major": period.major_lord.value,
                "period_sub": period.sub_lord.value,
                "verifications": [],
                "calibrated": False,
            }

        verdicts = verify_all_findings(chart, occurred_at, profile.verified_findings)
        calibrated = self._apply_event_calibration(profile, verdicts, event)
        if calibrated:
            self._store.save_profile(profile)

        return {
            "event_id": event.id,
            "period_major": period.major_lord.value,
            "period_sub": period.sub_lord.value,
            "verifications": [_verdict_to_dict(v) for v in verdicts],
            "calibrated": calibrated,
        }

    def _apply_event_calibration(self, profile, verdicts, event: LifeEvent) -> bool:
        """把"验上"的判断做置信度校准 + 记验证痕迹。返回是否发生了校准。"""
        calibrated = False
        date_str = event.occurred_at.date().isoformat()
        for verdict in verdicts:
            if verdict.verdict != "confirmed":
                continue
            finding = next(
                (f for f in profile.verified_findings if f.id == verdict.finding_id), None
            )
            if finding is None:
                continue
            finding.confidence = round(
                min(CONFIDENCE_CAP, finding.confidence + EVENT_VERIFY_DELTA), 2
            )
            finding.confirmed_at = utc_now_aware()
            note = f"{date_str} 事件「{event.label}」验证通过（{verdict.reason}）"
            if note not in finding.verification_notes:
                finding.verification_notes.append(note)
            calibrated = True

        if calibrated:
            profile.updated_at = utc_now_aware()
        return calibrated

    # ------------------------------------------------------------------

    def calibrate_from_feedback(self, profile, finding: VerifiedFinding, feedback: str) -> dict:
        """用户对一条判断的反馈 → 校准置信度。

        返回 {"new_confidence"}。confirmed_at 在确认/反驳时都记（互动发生）。
        """
        if feedback == "confirmed":
            finding.confidence = round(
                min(CONFIDENCE_CAP, finding.confidence + CONFIRM_DELTA), 2
            )
        else:  # refuted
            finding.confidence = round(
                max(CONFIDENCE_FLOOR, finding.confidence - REFUTE_DELTA), 2
            )
        finding.confirmed_at = utc_now_aware()
        profile.updated_at = utc_now_aware()
        return {"new_confidence": finding.confidence}


def _verdict_to_dict(verdict) -> dict:
    return {
        "finding_id": verdict.finding_id,
        "statement": verdict.statement,
        "subject_planet": verdict.subject_planet.value if verdict.subject_planet else None,
        "verdict": verdict.verdict,
        "matched_lord": verdict.matched_lord.value if verdict.matched_lord else None,
        "reason": verdict.reason,
    }


__all__ = [
    "LearningService",
    "CONFIRM_DELTA",
    "REFUTE_DELTA",
    "EVENT_VERIFY_DELTA",
]
