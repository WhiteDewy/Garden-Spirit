"""可复用分析模块 —— 语义镜头。

每个模块把主题映射到占星事实，由 Evidence 层统一加权。
"""

from domain.analysis.base import AnalysisModule
from domain.analysis.career_strength import CareerStrength
from domain.analysis.daily import Daily
from domain.analysis.finance import Finance
from domain.analysis.life_domains import Emotion, Family, Health, Learning
from domain.analysis.marriage_potential import MarriagePotential
from domain.analysis.opportunity import Opportunity
from domain.analysis.partner_traits import PartnerTraits
from domain.analysis.psychology import Psychology
from domain.analysis.relationship_status import RelationshipStatus
from domain.analysis.relationship_synastry import RelationshipSynastry
from domain.analysis.risk import Risk
from domain.analysis.theme_module import ThemeModule
from domain.analysis.timing import Timing
from domain.analysis.wealth import Wealth

__all__ = [
    "AnalysisModule",
    "ThemeModule",
    "CareerStrength",
    "Timing",
    "Risk",
    "Opportunity",
    "Finance",
    "PartnerTraits",
    "Psychology",
    "Wealth",
    "RelationshipSynastry",
    "RelationshipStatus",
    "MarriagePotential",
    "Daily",
    "Health",
    "Emotion",
    "Family",
    "Learning",
]
