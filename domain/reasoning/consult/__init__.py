"""Consult Resolver —— 咨询模板引擎。

从用户问题自动推导：
1. 话题 → 主宫 + 辅宫 + 核心星 + 辅助星
2. 本命结构判断（转宫推导、交叉判断、场景映射）
3. 推运时间窗口（法达 × 本命宫主状态 + 行运）

三层规则体系（YAML 数据驱动）：
- house_significations.yaml  宫位语义场 + 路由词
- house_derived.yaml         转宫关系表
- planet_nature.yaml         星性规则
- natal_composition.yaml     本命组合规则
- timing_rules.yaml          推运规则
"""

from domain.reasoning.consult.resolver import (
    ConsultCallPlan,
    ConsultResolver,
    TopicPlan,
    get_resolver,
    resolve_call_plan,
    resolve_question,
)

__all__ = [
    "ConsultCallPlan",
    "ConsultResolver",
    "TopicPlan",
    "resolve_call_plan",
    "resolve_question",
    "get_resolver",
]
