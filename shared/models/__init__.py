"""shared/models —— 全系统唯一的数据契约。

从这里 import，绝不直接跨包 import 其他模型的内部路径。
"""

from shared.models.chart import (
    Aspect,
    Chart,
    ChartPlanet,
    EclipticPosition,
    EssentialDignity,
    FixedStarConjunction,
    HouseCusp,
    HousePosition,
    Lot,
    SignPosition,
)
from shared.models.conclusion import Conclusion, Finding, TimePeriod
from shared.models.conversation import Conversation, DialogueTurn
from shared.models.evidence import (
    Evidence,
    EvidenceConflict,
    EvidenceSet,
)
from shared.models.execution_plan import ExecutionPlan, ExecutionStatus, ExecutionStep
from shared.models.facts import Fact, FactSet
from shared.models.intent import Intent, IntentSlot
from shared.models.journal import JournalEntry
from shared.models.letter import Letter
from shared.models.life_event import LifeEvent
from shared.models.memory import Memory, MemoryItem
from shared.models.person import BirthData, GeoLocation, Person
from shared.models.profile import ChartProfile, DomainSummary, KeyDate, VerifiedFinding
from shared.models.strategy import (
    StepDependencyType,
    Strategy,
    StrategyCombinator,
    StrategyStep,
)
from shared.models.timeline import Timeline, TimelineWindow

__all__ = [
    # person
    "Person",
    "BirthData",
    "GeoLocation",
    # chart
    "Chart",
    "ChartPlanet",
    "EclipticPosition",
    "SignPosition",
    "HousePosition",
    "HouseCusp",
    "Aspect",
    "EssentialDignity",
    "Lot",
    "FixedStarConjunction",
    # facts
    "Fact",
    "FactSet",
    # evidence
    "Evidence",
    "EvidenceSet",
    "EvidenceConflict",
    # intent
    "Intent",
    "IntentSlot",
    # strategy
    "Strategy",
    "StrategyStep",
    "StrategyCombinator",
    "StepDependencyType",
    # execution plan
    "ExecutionPlan",
    "ExecutionStep",
    "ExecutionStatus",
    # conclusion
    "Conclusion",
    "Finding",
    "TimePeriod",
    # memory
    "Memory",
    "MemoryItem",
    # profile（第四层记忆）
    "ChartProfile",
    "DomainSummary",
    "VerifiedFinding",
    "KeyDate",
    # journal
    "JournalEntry",
    # letter
    "Letter",
    # life_event
    "LifeEvent",
    # conversation
    "Conversation",
    "DialogueTurn",
    # timeline
    "Timeline",
    "TimelineWindow",
]
