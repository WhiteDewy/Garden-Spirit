"""Facts：占星内核的输出，Evidence 的输入。

**关键边界（防火墙）**：
- Facts 是**机械的**——直接从 Chart 原始数值算法性提取。
- Facts **不带**解释、权重、极性。那是 Evidence 的职责。
- Fact 回答"是什么"，从不回答"意味着什么"。

越界检查：domain/astrology/calculation/ 下任何调用 Evidence()、
使用 EvidencePolarity 或赋值 Weight 的代码 = 边界违规。
"""

from dataclasses import dataclass, field
from datetime import datetime

from shared.enums import FactCategory, Planet
from shared.types import EntityId


@dataclass(frozen=True)
class Fact:
    """一条原子级占星事实（不可变）。

    每个 Fact 都能对照原始星盘数据机械验证。
    """

    id: EntityId
    category: FactCategory
    chart_id: EntityId
    description: str            # 人类可读但机械的表述，如 "火星在白羊座5.3° 十宫"
    extracted_at: datetime

    # 结构化负载，按类别不同：
    #   POSITION:  {"planet": "mars", "sign": "aries", "degree": 5.3, "house": 10}
    #   ASPECT:    {"body1": "mars", "body2": "saturn", "aspect": "trine", "orb": 2.3, "applying": true}
    #   DIGNITY:   {"planet": "venus", "sign": "taurus", "dignity": "domicile", "score": 5}
    #   RECEPTION: {"planet_a": "venus", "planet_b": "mars", "mutual": true}
    #   LORDSHIP:  {"house": 10, "ruler": "saturn", "ruler_sign": "capricorn", "ruler_house": 7}
    #   PATTERN:   {"type": "grand_trine", "bodies": ["sun", "moon", "jupiter"]}
    payload: dict[str, object] = field(default_factory=dict)


@dataclass
class FactSet:
    """从一个或多个图表提取的事实集合。

    FactSet 是计算管线的输出、Evidence 层的输入。
    """

    id: EntityId
    chart_ids: list[EntityId]
    intent_domain: str          # 为哪个意图领域生成
    facts: list[Fact] = field(default_factory=list)
    generated_at: datetime | None = None

    def get_by_category(self, category: FactCategory) -> list[Fact]:
        """按类别过滤。"""
        return [f for f in self.facts if f.category == category]

    def get_by_planet(self, planet: Planet) -> list[Fact]:
        """按行星过滤（检查 payload.planet）。"""
        return [f for f in self.facts if f.payload.get("planet") == planet.value]

    def get_by_type(self, fact_type: str) -> list[Fact]:
        """按 payload.type 过滤（自定义扩展）。"""
        return [f for f in self.facts if f.payload.get("type") == fact_type]

    def __len__(self) -> int:
        return len(self.facts)

    def __bool__(self) -> bool:
        return len(self.facts) > 0
