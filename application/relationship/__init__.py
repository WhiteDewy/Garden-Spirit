"""A2 关系层：信任度量 / 自我介绍 / 邀请式引导。"""

from application.relationship.service import (
    LEVEL_THRESHOLDS,
    SIGNAL_WEIGHTS,
    TRUST_LABELS,
    RelationshipService,
)

__all__ = [
    "RelationshipService",
    "SIGNAL_WEIGHTS",
    "LEVEL_THRESHOLDS",
    "TRUST_LABELS",
]
