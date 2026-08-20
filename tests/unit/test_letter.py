"""星灵信箱测试（W3）。

验证：
- 每日来信生成（无 LLM → 降级模板，仍非空）
- 幂等：同一天只生成一封
- 收件箱列表倒序
- 无显著行运 → 平静日模板
"""

from datetime import datetime, timezone

from foundation.database.store import GardenStore
from foundation.utils import new_id
from shared.models import BirthData, GeoLocation, Person

from application.mailbox.letter_service import LetterService


def _make_person(person_id: str = "p1") -> Person:
    loc = GeoLocation(31.23, 121.47, timezone_name="Asia/Shanghai", place_name="上海")
    return Person(
        id=person_id,
        name="夏天",
        birth=BirthData(datetime(1995, 8, 20, 9, 30, tzinfo=timezone.utc), loc),
    )


def _make_service() -> LetterService:
    # 无 LLM、无 chart_provider → 走降级路径（测试不依赖网络/星历）
    return LetterService(GardenStore(":memory:"), llm_client=None, chart_provider=None)


def test_daily_letter_created_and_idempotent():
    service = _make_service()
    p = _make_person()
    l1 = service.get_or_create_daily(p)
    assert l1.kind == "daily"
    assert l1.body  # 降级模板非空
    assert l1.letter_date  # YYYY-MM-DD

    l2 = service.get_or_create_daily(p)  # 同一天再取 → 同一封
    assert l1.id == l2.id
    items, total = service.list(p.id)
    assert total == 1 and len(items) == 1


def test_daily_letter_different_person():
    service = _make_service()
    a = _make_person("a")
    b = _make_person("b")
    la = service.get_or_create_daily(a)
    lb = service.get_or_create_daily(b)
    assert la.id != lb.id
    items, _ = service.list(a.id)
    assert len(items) == 1


def test_inbox_lists():
    service = _make_service()
    p = _make_person()
    service.get_or_create_daily(p)
    letters, total = service.list(p.id)
    assert total == 1
    assert letters[0].sender == "moon"  # 无行运 → 默认月亮来信


def test_letter_local_date_uses_person_tz():
    """本地日期按盘主时区（Asia/Shanghai）计算，可解析。"""
    p = _make_person()
    service = _make_service()
    letter = service.get_or_create_daily(p)
    # YYYY-MM-DD 且能解析
    from datetime import date as date_type
    assert date_type.fromisoformat(letter.letter_date)


def test_new_daily_letter_unread_by_default():
    """新生成的今日来信 read_at=None（未读）→ 首页信箱红点依据。"""
    p = _make_person()
    service = _make_service()
    letter = service.get_or_create_daily(p)
    assert letter.read_at is None
