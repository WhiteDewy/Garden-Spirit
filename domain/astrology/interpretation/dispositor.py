"""飞星解析（宫主星飞入各宫）—— 确定性、无 LLM。

宫主星飞入某宫 = 把所掌宫位的力量带到该宫。得吉=带来帮助，受克=带来麻烦。
文案来自 knowledge/dispositor_rules.yaml（占星师经验库，4-12宫；1-3宫待补）。
得吉/受克由宫主星本身状态判定（刑冲未接纳重 / 落陷亦偏受克）。
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.enums import AspectType, Planet
from shared.models import Chart

from domain.astrology.common import aspects_to, assess_planet, house_rulers
from domain.astrology.interpretation.synapsis import ConnectionClassifier, effective_house
from domain.astrology.knowledge.loader import KnowledgeBase


@dataclass(frozen=True)
class DispositorReading:
    """一次飞星解读。"""

    from_house: int        # 原宫（宫主星所掌）
    to_house: int          # 飞入宫
    lord: Planet
    title: str
    text: str              # 得吉或受克文案
    quality: str           # jin / ke

    def to_dict(self) -> dict:
        return {
            "from_house": self.from_house,
            "to_house": self.to_house,
            "lord": self.lord.value,
            "title": self.title,
            "text": self.text,
            "quality": self.quality,
        }


def dispositor_interpretations(
    chart: Chart,
    kb: KnowledgeBase,
    classifier: ConnectionClassifier | None = None,
    houses: list[int] | None = None,
) -> list[DispositorReading]:
    """解析所有宫主星的飞星含义。

    houses: 仅解析指定宫（如 [6,7,11]），None = 全部。
    """
    table = (kb.dispositor_rules or {}).get("house_flights", {})
    classifier = classifier or ConnectionClassifier(kb)
    readings: list[DispositorReading] = []
    targets = houses or list(range(1, 13))

    for from_house in targets:
        rulers = house_rulers(chart, kb, from_house)   # 含劫夺宫主
        for lord in rulers:
            to_house = effective_house(chart, lord)
            # YAML 外层键（4:）解析为 int，内层键（"1":）为 str
            house_entries = table.get(from_house) or table.get(str(from_house)) or {}
            entry = house_entries.get(str(to_house)) or house_entries.get(to_house)
            if not entry:
                continue
            quality = _quality(chart, kb, lord, classifier)
            text = entry.get("jin") if quality == "jin" else entry.get("ke")
            readings.append(
                DispositorReading(
                    from_house=from_house,
                    to_house=to_house,
                    lord=lord,
                    title=entry.get("title", ""),
                    text=text or "",
                    quality=quality,
                )
            )
    return readings


def _quality(
    chart: Chart, kb: KnowledgeBase, lord: Planet, classifier: ConnectionClassifier
) -> str:
    """宫主星状态：刑冲未接纳重 → 受克；落陷亦偏受克。

    **世代/虚点修正**：北交/南交/莉莉丝/三王星不参与接纳（世代性），
    其刑冲不能等同个人行星硬碰。与 affliction_quality.yaml 的 outer 分类一致：
    - 有接纳的刑冲  = 磨合 (0.4)
    - 无接纳·实星    = 硬碰 (0.8)
    - 无接纳·世代/虚点 = 外部压力 (0.5)
    """
    outer_set = set(kb.affliction_quality.get("outer", [])) if kb.affliction_quality else set()

    # 半刑(45°) / 八分相(135°) / 梅花(150°) 为次要相位，不参与得吉/受克判定
    _minor_dynamic = {AspectType.SEMISQUARE, AspectType.SESQUIQUADRATE, AspectType.QUINCUNX}

    hard = 0.0
    for asp in aspects_to(chart, lord):
        info = kb.aspects.get(asp.aspect_type)
        if info is None or info.nature != "DYNAMIC":
            continue
        if asp.aspect_type in _minor_dynamic:
            continue
        other = asp.body2 if asp.body1 == lord else asp.body1
        received = classifier.is_received(chart, lord, other)
        if received:
            hard += 0.4
        elif other in outer_set:
            hard += 0.5  # 外部压力（世代/虚点，不参与接纳）
        else:
            hard += 0.8  # 实星硬碰
    assessment = assess_planet(chart, kb, lord, classifier=classifier)
    if assessment.essential_neg > 0:
        hard += 1.0  # 落陷/失势；保留本质轴内部吉凶两论，不用净分抹掉小尊贵
    return "ke" if hard >= 1.5 else "jin"
