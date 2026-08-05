"""Phase 3 验证：Strategy YAML 加载 + 推理链装配。"""

from datetime import datetime
import zoneinfo

import pytest

from domain.reasoning import Planner, StrategyLoader
from domain.reasoning.strategy.schema import StrategyYAML
from shared.enums import IntentDomain
from shared.models import BirthData, GeoLocation, Intent, Person


def test_load_changejob_strategy():
    loader = StrategyLoader()
    strategy = loader.get("Career.ChangeJob")
    assert strategy is not None
    assert strategy.id == "Career.ChangeJob"
    names = [s.id for s in strategy.steps]
    assert "CareerStrength" in names
    assert "Timing" in names
    # Opportunity 依赖 CareerStrength + Timing
    opp = strategy.get_step("Opportunity")
    assert set(opp.dependencies) == {"CareerStrength", "Timing"}


def test_get_case_insensitive():
    """回归：路由传 'career.ChangeJob'（小写）必须命中 ChangeJob 而非 default。"""
    loader = StrategyLoader()
    strategy = loader.get("career.ChangeJob")
    assert strategy is not None
    assert strategy.id == "Career.ChangeJob"
    names = [s.id for s in strategy.steps]
    assert "Finance" in names  # 只有 ChangeJob 才有 Finance


def test_load_defaults_all_domains():
    loader = StrategyLoader()
    for domain in IntentDomain:
        assert loader.get_for_domain(domain) is not None, f"{domain} 缺少默认策略"


def test_schema_validation_unknown_dependency():
    with pytest.raises(Exception):
        StrategyYAML(
            intent="Career.Test",
            required_analysis=[{"module": "A"}, {"module": "B"}],
            model_dependencies={"A": ["NONEXISTENT"]},
        )


def test_planner_creates_plan():
    loader = StrategyLoader()
    strategy = loader.get("Career.ChangeJob")
    person = Person(
        id="p1",
        name="测试",
        birth=BirthData(
            datetime(1990, 6, 15, 9, 30, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(31.2304, 121.4737, timezone_name="Asia/Shanghai", place_name="上海"),
        ),
    )
    intent = Intent(
        id="i1", raw_query="我想换工作",
        domain=IntentDomain.CAREER, subdomain="career_change",
    )
    planner = Planner()
    plan, chart = planner.create_plan(intent, strategy, person)
    assert len(plan.steps) == len(strategy.steps)
    assert plan.chart_ids == [chart.id]
    assert chart.person_id == "p1"
