"""刑克性质解读（确定性，无 LLM）。

刑克不能一概论凶。判据两轴：克向谁（贵/吉/凶/世代）× 有无接纳（磨合/硬碰）。
裁决文本来自 knowledge/affliction_quality.yaml（占星师经验库）。
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.enums import AspectType, Planet
from shared.models import Chart

from domain.astrology.common import aspects_to
from domain.astrology.interpretation.synapsis import ConnectionClassifier
from domain.astrology.knowledge.loader import KnowledgeBase


@dataclass(frozen=True)
class AfflictionReading:
    """一条刑克的"性质"解读。"""

    other: Planet            # 克它的星
    aspect_type: AspectType
    received: bool           # 有接纳 = 磨合；无接纳 = 硬碰
    target_kind: str         # noble / benefic / malefic / outer / neutral
    label: str               # 费力上升 / 磨合协调 / 硬碰消耗 / 外部压力…
    text: str

    def to_dict(self) -> dict:
        return {
            "other": self.other.value,
            "aspect_type": self.aspect_type.value,
            "received": self.received,
            "target_kind": self.target_kind,
            "label": self.label,
            "text": self.text,
        }


def _target_kind(kb: KnowledgeBase, other: Planet) -> str:
    table = kb.affliction_quality or {}
    if other in table.get("noble", []):
        return "noble"
    if other in table.get("benefic", []):
        return "benefic"
    if other in table.get("malefic", []):
        return "malefic"
    if other in table.get("outer", []):
        return "outer"
    return "neutral"


def affliction_readings(
    chart: Chart,
    kb: KnowledgeBase,
    lord: Planet,
    classifier: ConnectionClassifier | None = None,
) -> list[AfflictionReading]:
    """该领主每条动态相位（刑/冲/梅花）的克性解读。

    例：火星刑太阳 + 火星接纳太阳 → 克向贵星且有接纳 = "费力上升"（凶性被收编服务贵）。
    """
    classifier = classifier or ConnectionClassifier(kb)
    verdicts = (kb.affliction_quality or {}).get("verdicts", {})
    out: list[AfflictionReading] = []

    for asp in aspects_to(chart, lord):
        info = kb.aspects.get(asp.aspect_type)
        if info is None or info.nature != "DYNAMIC":
            continue
        other = asp.body2 if asp.body1 == lord else asp.body1
        received = classifier.is_received(chart, lord, other)
        kind = _target_kind(kb, other)
        key = ("received" if received else "unreceived") + "_" + kind
        v = verdicts.get(key, {})
        out.append(
            AfflictionReading(
                other=other,
                aspect_type=asp.aspect_type,
                received=received,
                target_kind=kind,
                label=v.get("label", key),
                text=v.get("text", ""),
            )
        )
    return out
