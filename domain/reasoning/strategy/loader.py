"""Strategy 加载器 —— 从 YAML 文件加载策略。

策略是插件系统：新增技法/策略 = 新增 YAML 文件，不改代码。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from foundation.logger import get_logger
from shared.enums import IntentDomain, Priority
from shared.models import Strategy, StrategyCombinator, StrategyStep

from .schema import StrategyYAML, StrategyStepYAML

logger = get_logger("reasoning.strategy")

_DEFAULT_DIR = Path(__file__).parent
_INTENT_DOMAIN_MAP = {d.value: d for d in IntentDomain}


class StrategyLoader:
    """加载并缓存所有策略。"""

    def __init__(self, strategy_dir: Path | None = None):
        self._dir = strategy_dir or _DEFAULT_DIR
        self._cache: dict[str, Strategy] | None = None

    # ------------------------------------------------------------------

    def load_all(self) -> dict[str, Strategy]:
        """加载目录下所有策略 YAML，按 intent 引用索引。"""
        if self._cache is not None:
            return self._cache

        strategies: dict[str, Strategy] = {}
        for path in self._dir.rglob("*.yaml"):
            if path.name == "default.yaml":
                continue  # default 单独处理
            try:
                strategy = self._load_file(path)
                strategies[strategy.id] = strategy
            except Exception as e:  # noqa: BLE001
                logger.error("策略加载失败 %s: %s", path, e)
                raise

        # 加载 default
        default_path = self._dir / "default.yaml"
        if default_path.exists():
            try:
                raw = yaml.safe_load(default_path.read_text(encoding="utf-8"))
                # default 条目缺少 intent 字段，注入 key
                for intent_ref, definition in raw.items():
                    definition["intent"] = intent_ref
                    strategies.setdefault(intent_ref, self._from_raw(intent_ref, definition))
            except Exception as e:  # noqa: BLE001
                logger.error("default.yaml 加载失败: %s", e)

        self._cache = strategies
        logger.info("策略加载完成: %d 个策略", len(strategies))
        return strategies

    def get(self, intent_ref: str) -> Strategy | None:
        """获取某个 intent 的策略（大小写不敏感）。

        YAML 中的 intent 键可能为 "Career.ChangeJob"，而调用方
        （Intent 路由）传入 "career.ChangeJob"，需兼容。
        """
        strategies = self.load_all()
        exact = strategies.get(intent_ref)
        if exact is not None:
            return exact
        lower = intent_ref.lower()
        for key, strategy in strategies.items():
            if key.lower() == lower:
                return strategy
        return None

    def get_for_domain(self, domain: IntentDomain | str) -> Strategy | None:
        """获取领域的默认策略（default.yaml 中的兜底）。"""
        key = domain.value if isinstance(domain, IntentDomain) else str(domain)
        return self.load_all().get(f"{key}.default")

    # ------------------------------------------------------------------

    def _load_file(self, path: Path) -> Strategy:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return self._from_raw(raw["intent"], raw)

    def _from_raw(self, intent_ref: str, raw: dict) -> Strategy:
        parsed = StrategyYAML(**raw)
        steps = [self._to_step(s) for s in parsed.required_analysis]
        domain = self._parse_domain(intent_ref)

        strategy = Strategy(
            id=intent_ref,
            name=intent_ref,
            description=parsed.description,
            intent_domains=[domain] if domain else [],
            steps=steps,
            combinator=StrategyCombinator.SEQUENCE,
            default_confidence_threshold=float(
                parsed.evidence_rules.get("conflict_threshold", 0.7)
            ),
            evidence_rules=dict(parsed.evidence_rules),
        )
        # 同步 model_dependencies 到 step.dependencies
        for step in strategy.steps:
            step.dependencies = list(parsed.model_dependencies.get(step.id, []))
        return strategy

    @staticmethod
    def _to_step(s: StrategyStepYAML) -> StrategyStep:
        return StrategyStep(
            id=s.module,
            name=s.module,
            analysis_module=s.module,
            required_facts=[],
            dependencies=list(s.depends_on),
            config=s.params,
            weight_in_summary=s.weight,
            priority=s.priority_enum(),
        )

    @staticmethod
    def _parse_domain(intent_ref: str) -> IntentDomain | None:
        """从 intent 引用（如 Career.ChangeJob）解析领域。"""
        prefix = intent_ref.split(".")[0].lower()
        return _INTENT_DOMAIN_MAP.get(prefix)
