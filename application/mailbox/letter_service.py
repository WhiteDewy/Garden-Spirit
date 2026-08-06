"""LetterService —— 星灵来信的生成与收件箱。

每日来信 = 今日行运快照（Daily 模块，确定性）→ LLM 织成温暖的信。
幂等：同一 person 同一天只生成一封（letter_date 为本地日期）。
LLM 不可用 → 降级模板（仍基于真实行运事实，不编）。
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from foundation.database.store import GardenStore
from foundation.logger import get_logger
from foundation.utils import new_id, utc_now_aware
from shared.models import Letter, Person

from domain.analysis.daily import Daily

logger = get_logger("application.mailbox.letter_service")

_LETTER_SYSTEM = """你是星灵花园里的星灵。每天给盘主写一封温暖的信，基于今天的星象快照。

要求：
- 100-150 字，像朋友来信，不用"尊敬的"这类正式口吻。
- 结构：先接住今天能量（1句）→ 一句贴近生活的提醒（基于星象）→ 结尾一句温暖落点。
- 星象事实只能来自快照，不编造；术语说人话。
只输出信的内容，不要标题、不要称呼。
"""

#: 星灵来信的发件人显示名（sender → 中文）
SENDER_ZH = {
    "moon": "月亮", "sun": "太阳", "mercury": "水星", "venus": "金星",
    "mars": "火星", "jupiter": "木星", "saturn": "土星",
    "uranus": "天王星", "neptune": "海王星", "pluto": "冥王星",
}


class LetterService:
    """信箱服务。chart_provider: callable(person) -> Chart，生成每日行运用。"""

    def __init__(self, store: GardenStore, llm_client=None, chart_provider=None):
        self._store = store
        self._llm = llm_client
        self._chart_provider = chart_provider
        self._daily = Daily()

    # ------------------------------------------------------------------

    def get_or_create_daily(self, person: Person) -> Letter:
        """取今天的信；没有则生成并落库（幂等按天）。"""
        today = _local_date_str(person)
        existing = self._store.get_letter(person.id, today, "daily")
        if existing is not None:
            return existing

        facts: list = []
        if self._chart_provider is not None:
            try:
                chart = self._chart_provider(person)
                facts = self._daily.analyze(chart, person, {})
            except Exception as exc:  # noqa: BLE001 - 行运失败不阻断写信
                logger.warning("每日行运计算失败，写信用空快照: %s", exc)

        body, sender, title = self._compose(facts, today, person)
        letter = Letter(
            id=new_id("letter"),
            person_id=person.id,
            letter_date=today,
            sender=sender,
            title=title,
            body=body,
            kind="daily",
            created_at=utc_now_aware(),
        )
        self._store.save_letter(letter)
        return letter

    def list(self, person_id: str) -> list[Letter]:
        return self._store.list_letters(person_id)

    # ------------------------------------------------------------------

    def _compose(self, facts: list, today: str, person: Person) -> tuple[str, str, str]:
        """(body, sender, title)。sender 取当日最显著行运的行星。"""
        snapshot = self._snapshot(facts)
        sender = self._dominant_planet(facts) if facts else "moon"
        zh = SENDER_ZH.get(sender, sender)

        if self._llm is not None and self._llm.available and snapshot:
            try:
                body = self._llm.complete(
                    prompt=f"盘主：{person.name}\n\n今日星象快照：\n{snapshot}",
                    system=_LETTER_SYSTEM,
                    temperature=0.7,
                    max_tokens=400,
                ).strip()
                if body:
                    title = f"{zh}来信"
                    return body, sender, title
            except Exception as exc:  # noqa: BLE001 - 降级不阻断
                logger.warning("来信 LLM 失败，降级模板: %s", exc)

        # 降级模板（仍基于真实行运）
        if snapshot:
            body = (
                f"今天有一封来自{zh}的信。\n\n"
                f"{snapshot}\n\n"
                "愿今天的你，在生活的小事里找到自己的节奏。"
            )
        else:
            body = (
                "今天没有特别剧烈的星象扰动，是平静的一天。\n\n"
                "这样的日子适合把节奏放慢一点，看看手边真正重要的事。"
                "愿今天的你，好好照顾自己。"
            )
        return body, sender, f"{zh}来信"

    @staticmethod
    def _snapshot(facts: list) -> str:
        lines = []
        for f in facts[:4]:
            lines.append(f"- {f.description}")
        return "\n".join(lines)

    @staticmethod
    def _dominant_planet(facts: list) -> str:
        """从 rule_id "daily:<planet>:<planet>:<aspect>" 取最显著行运的发起星。"""
        if not facts:
            return "moon"
        top = max(facts, key=lambda f: abs(f.payload.get("weight", 0)) * f.payload.get("confidence", 0))
        rid = str(top.payload.get("rule_id", ""))
        parts = rid.split(":")
        if len(parts) >= 2 and parts[0] == "daily":
            return parts[1]
        return "moon"


def _local_date_str(person: Person) -> str:
    """盘主所在时区的今天（YYYY-MM-DD）。"""
    tz_name = person.birth.location.timezone_name or "Asia/Shanghai"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001
        tz = ZoneInfo("Asia/Shanghai")
    return datetime.now(tz).strftime("%Y-%m-%d")


__all__ = ["LetterService", "SENDER_ZH"]
