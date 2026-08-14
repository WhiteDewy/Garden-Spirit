"""意图分析配置加载器。

从 intent_profiles.yaml 读取每个领域的必修模块、触发词条件、
核心占星结构，供 IntentDecomposer 使用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from shared.enums import Priority

_DEFAULT_PROFILES_PATH = Path(__file__).parent / "intent_profiles.yaml"


@dataclass
class ProfileTask:
    """一条分析任务配置。"""

    module: str
    priority: str  # "high" / "medium" / "low"
    params: dict = field(default_factory=dict)


@dataclass
class ConditionalTask:
    """触发词 → 附加模块。"""

    triggers: list[str]
    add_modules: list[ProfileTask] = field(default_factory=list)


@dataclass
class IntentProfile:
    """一个意图领域的完整分析配方。"""

    domain: str
    label_zh: str
    description: str
    base_tasks: list[ProfileTask] = field(default_factory=list)
    conditional_tasks: list[ConditionalTask] = field(default_factory=list)
    focus_dimensions: list[str] = field(default_factory=list)
    core_houses: list[int] = field(default_factory=list)
    house_lords: list[int] = field(default_factory=list)
    aspect_pairs: list[list] = field(default_factory=list)
    known_subdomains: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 加载
# ---------------------------------------------------------------------------

def load_profiles(path: str | None = None) -> dict[str, IntentProfile]:
    """加载 intent_profiles.yaml → dict[domain_key, IntentProfile]."""
    p = Path(path) if path else _DEFAULT_PROFILES_PATH
    if not p.exists():
        return {}
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    profiles: dict[str, IntentProfile] = {}
    for domain_key, data in raw.items():
        base = [
            ProfileTask(
                module=t["module"],
                priority=t.get("priority", "medium"),
                params=t.get("params", {}),
            )
            for t in data.get("base_tasks", [])
        ]
        cond: list[ConditionalTask] = []
        for ct in data.get("conditional_tasks", []):
            cond.append(ConditionalTask(
                triggers=ct.get("triggers", []),
                add_modules=[
                    ProfileTask(
                        module=m["module"],
                        priority=m.get("priority", "medium"),
                        params=m.get("params", {}),
                    )
                    for m in ct.get("add_modules", [])
                ],
            ))
        profiles[domain_key] = IntentProfile(
            domain=data.get("domain", domain_key),
            label_zh=data.get("label_zh", domain_key),
            description=data.get("description", ""),
            base_tasks=base,
            conditional_tasks=cond,
            focus_dimensions=data.get("focus_dimensions", []),
            core_houses=data.get("core_houses", []),
            house_lords=data.get("house_lords", []),
            aspect_pairs=data.get("aspect_pairs", []),
            known_subdomains=data.get("known_subdomains", {}),
        )
    return profiles


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------

def get_base_tasks(
    profiles: dict[str, IntentProfile],
    domain,
    subdomain: str = "",
) -> list:
    """获取某领域的必修任务（AnalysisTask 列表）。"""
    from .decomposer import AnalysisTask  # noqa: PLC0415 — 避免循环导入

    domain_str = domain.value if hasattr(domain, "value") else str(domain)
    profile = profiles.get(domain_str)
    if profile is None:
        return []

    tasks: list[AnalysisTask] = []
    for pt in profile.base_tasks:
        try:
            priority = Priority(pt.priority)
        except ValueError:
            priority = Priority.MEDIUM
        tasks.append(AnalysisTask(
            module=pt.module,
            priority=priority,
            params=dict(pt.params),
            reasoning=f"base_task:{domain_str}",
        ))
    return tasks


def evaluate_conditional_tasks(
    profiles: dict[str, IntentProfile],
    domain,
    raw_query: str,
) -> list:
    """根据触发词匹配条件任务（AnalysisTask 列表）。"""
    from .decomposer import AnalysisTask  # noqa: PLC0415

    domain_str = domain.value if hasattr(domain, "value") else str(domain)
    profile = profiles.get(domain_str)
    if profile is None:
        return []

    tasks: list[AnalysisTask] = []
    for ct in profile.conditional_tasks:
        if any(trigger in raw_query for trigger in ct.triggers):
            for m in ct.add_modules:
                try:
                    priority = Priority(m.priority)
                except ValueError:
                    priority = Priority.MEDIUM
                tasks.append(AnalysisTask(
                    module=m.module,
                    priority=priority,
                    params=dict(m.params),
                    reasoning=f"conditional:{domain_str}",
                ))
    return tasks
