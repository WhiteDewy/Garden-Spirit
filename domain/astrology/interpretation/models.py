"""解释引擎数据模型。"""

from dataclasses import dataclass
from shared.enums import Planet


@dataclass(frozen=True)
class SignificationItem:
    """一条激活的宫位含义解读。

    gated: tendency（倾向，默认，可直接说）/ event（事件预言，高门槛收敛）。
    resonance: 通俗共鸣词（LLM 转述锚点，确定性数据）。
    evidence: 支撑该解读的结构证据（宫主/宫内星/交感/连接）。
    """

    house: int
    word: str
    polarity: str            # positive / negative / neutral（结构调制后）
    intensity: float         # 语义场基础强度
    strength: float          # 调制后强度（语境 + 结构 + 飞行增强 + 收敛）
    resonance: tuple[str, ...]
    evidence: tuple[str, ...]
    gated: str = "tendency"

    def to_dict(self) -> dict:
        """出口：JSON 友好（供 app 消费）。"""
        return {
            "house": self.house,
            "word": self.word,
            "polarity": self.polarity,
            "intensity": self.intensity,
            "strength": self.strength,
            "resonance": list(self.resonance),
            "evidence": list(self.evidence),
            "gated": self.gated,
        }


@dataclass(frozen=True)
class HouseSynapsis:
    """一星多宫主的交感宫群。

    一个行星管多个宫位 → 这些领域互相传导、共享该星特质。
    manifestation_house: 枢纽星所在宫（这些领域经何宫显化）。
    """

    hub_planet: Planet
    houses: tuple[int, ...]
    manifestation_house: int
    description_zh: str

    def to_dict(self) -> dict:
        return {
            "hub_planet": self.hub_planet.value,
            "houses": list(self.houses),
            "manifestation_house": self.manifestation_house,
            "description_zh": self.description_zh,
        }


@dataclass(frozen=True)
class ConnectionFact:
    """两个宫主/对象之间的连接（分级）。

    conn_type: reception_mutual / reception_active / aspect / flight / cohabit / reception_latent
    strength: 互溶4 > 接纳3 > 相位2.5 > 飞宫2 > 同宫1 > 潜在0.5
    """

    subject: str
    target: str
    conn_type: str
    strength: float
    detail: str

    def to_dict(self) -> dict:
        return {
            "subject": self.subject,
            "target": self.target,
            "conn_type": self.conn_type,
            "strength": self.strength,
            "detail": self.detail,
        }
