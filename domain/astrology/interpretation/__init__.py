"""占星解释引擎（确定性，无 LLM）。

横向能力：对任意盘、任意结构，按"问题域 + 结构质量"产出多维解读。
技法层：宫位交感（一星多宫主）、连接分级（相位/互溶/接纳/飞宫/同宫/潜在）、
        语义场选择（域过滤 + 质量调制 + 事件门槛 + 共振词）。
知识层：knowledge/house_significations.yaml（占星师可调）。
"""

from domain.astrology.interpretation.affliction import AfflictionReading, affliction_readings
from domain.astrology.interpretation.dispositor import DispositorReading, dispositor_interpretations
from domain.astrology.interpretation.evidence_card import EvidenceCard, dispositor_cards
from domain.astrology.interpretation.models import ConnectionFact, HouseSynapsis, SignificationItem
from domain.astrology.interpretation.natal import NatalReading, natal_reading
from domain.astrology.interpretation.planet_profile import PlanetProfile, read_all_planets, read_planet
from domain.astrology.interpretation.signification import HouseSignificationEngine
from domain.astrology.interpretation.synapsis import ConnectionClassifier, detect_synapsis

__all__ = [
    "AfflictionReading",
    "ConnectionClassifier",
    "ConnectionFact",
    "DispositorReading",
    "EvidenceCard",
    "HouseSignificationEngine",
    "HouseSynapsis",
    "NatalReading",
    "PlanetProfile",
    "SignificationItem",
    "affliction_readings",
    "detect_synapsis",
    "dispositor_cards",
    "dispositor_interpretations",
    "natal_reading",
    "read_all_planets",
    "read_planet",
]
