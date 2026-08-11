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

from application.conversation.fragments import FragmentService
from application.mailbox.signature import LetterSignature, NeedClassifier

logger = get_logger("application.mailbox.letter_service")

_LETTER_SYSTEM = """你是星灵花园里的星灵。每天给盘主写一封温暖的信，基于今天的星象快照。

要求：
- 100-150 字，像朋友来信，不用"尊敬的"这类正式口吻。
- 结构：先接住今天能量（1句）→ 一句贴近生活的提醒（基于星象）→ 结尾一句温暖落点。
- 星象事实只能来自快照，不编造；术语说人话。
只输出信的内容，不要标题、不要称呼。
"""

#: 词条蒸馏 system prompt（§6.1 日常/正面分享 → 一句诗化记忆存档）
_ENTRY_SYSTEM = """你是星灵花园里的星灵。用户刚才分享了一件 TA 在意的事，你回了一段话。

把"TA 的分享 + 你的回应"一起，蒸馏成一句诗化的"记忆词条"——像一句能收藏很久的话。
要求：
- 1-2 句，诗化、温柔、具体，抓住 TA 分享的具体内容（剧/书/歌/游戏/人/事/想法/经历），不要泛泛而谈。
- 不评论对错、不下结论、不做占星解读。
- 例：TA 在聊盗墓题材剧《九门》 → "在九门的世界里，你找到了暂时栖息的梦境。"
只输出词条本身（不要引号、不要标题、不要称呼）。
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
        # 落款推导链（§6.2）：内容 → 情绪需求（主/次）→ 疗愈名
        self._signature = NeedClassifier(llm_client)

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
    # 语境来信（§6.1 来信式日记 + §6.2 落款推导链）
    # ------------------------------------------------------------------

    def signature_for(self, content: str) -> LetterSignature:
        """内容 → 落款推导结果（主/次情绪需求 → 疗愈名 + 灵魂碎片）。"""
        return self._signature.classify(content)

    def context_letter(
        self,
        person: Person,
        *,
        content: str,
        reply: str,
        signature: LetterSignature | None = None,
        lit_fragments: tuple[str, ...] = (),
        entry: bool = False,
    ) -> Letter:
        """语境来信（keepsake）：星灵那段完整回复原样成信，落款用疗愈名。

        §6.1 正文 = 那段对话本身，不是它的摘要（治愈感来自具体，不来自总结）。
        灵魂碎片 = 落款推导的次需求碎片 ∪ 当天随聊点亮的碎片（作脚注，不是正文）。
        kind="keepsake"，推导过程留档在 metadata["explain"]（显式可解释）。
        entry=True → 词条式来信（§6.1 日常/正面分享时刻），reply 已是诗化词条。
        """
        sig = signature if signature is not None else self._signature.classify(content)

        # 灵魂碎片脚注：次需求碎片 + 当天随聊点亮，去重保序
        fragment_names = _fragment_name_lookup()
        footnote_ids: list[str] = []
        for fid in (*sig.soul_fragments, *lit_fragments):
            if fid in fragment_names and fid not in footnote_ids:
                footnote_ids.append(fid)
        footnote = " / ".join(fragment_names[fid] for fid in footnote_ids) or "（无）"

        body = (
            f"{reply.strip()}\n\n"
            f"◈ 今日灵魂碎片：{footnote}\n"
            f"{'':>24}—— {sig.healing_name}"
        )
        return Letter(
            id=new_id("letter"),
            person_id=person.id,
            letter_date=_local_date_str(person),
            sender=sig.planet.value,
            title=f"「{sig.healing_name}」来信",
            body=body,
            kind="keepsake",
            created_at=utc_now_aware(),
            metadata={
                "primary_need": sig.primary_need.value,
                "secondary_needs": [n.value for n in sig.secondary_needs],
                "soul_fragments": list(sig.soul_fragments),
                "lit_fragments": list(lit_fragments),
                "healing_name": sig.healing_name,
                "explain": sig.explain,
                "entry": entry,
            },
        )

    def record_keepsake(
        self,
        person: Person,
        *,
        content: str,
        reply: str,
        lit_fragments: tuple[str, ...] = (),
    ) -> tuple[Letter, LetterSignature]:
        """来信式日记（§6.1/§6.2）：一次倾诉时刻 → keepsake 来信并落库。

        正文 = 星灵那段完整回复原样（治愈感来自具体）；落款走
        "内容→情绪需求→疗愈名"推导链（显式可解释，不黑箱）。
        返回 (letter, signature)——signature.soul_fragments 是次需求点亮的
        34 子类，由调用方（API 层）继续 `light()` 进轮盘。
        """
        sig = self._signature.classify(content)
        letter = self.context_letter(
            person,
            content=content,
            reply=reply,
            signature=sig,
            lit_fragments=lit_fragments,
        )
        self._store.save_letter(letter)
        return letter, sig

    def record_memorable(
        self,
        person: Person,
        *,
        content: str,
        reply: str,
        lit_fragments: tuple[str, ...] = (),
    ) -> tuple[Letter, LetterSignature]:
        """词条式来信（§6.1 日常/正面分享时刻）→ keepsake 并落库。

        "九门"这类 calm+memorable 的分享：正文 = LLM 当场蒸馏的一句诗化
        记忆词条（"在九门的世界里，你找到了暂时栖息的梦境"）；LLM 不可用
        → 星灵回复原样兜底（仍是"记忆存档"）。落款仍走"内容→情绪需求→
        疗愈名"推导链（显式可解释），soul_fragments 由调用方 light() 进轮盘。
        metadata["entry"]=True 供前端区分词条样式；kind 仍是 keepsake（同一收件箱）。
        """
        sig = self._signature.classify(content)
        entry = self._compose_entry(content, reply)
        letter = self.context_letter(
            person,
            content=content,
            reply=entry,
            signature=sig,
            lit_fragments=lit_fragments,
            entry=True,
        )
        self._store.save_letter(letter)
        return letter, sig

    def _compose_entry(self, content: str, reply: str) -> str:
        """蒸馏一句诗化词条；LLM 不可用/失败 → 星灵回复原样（服务不断）。"""
        if self._llm is not None and getattr(self._llm, "available", True):
            try:
                text = self._llm.complete(
                    prompt=f"TA 说：{content}\n\n你说：{reply}",
                    system=_ENTRY_SYSTEM,
                    temperature=0.7,
                    max_tokens=120,
                )
                text = (text or "").strip()
                if text:
                    return text
            except Exception as exc:  # noqa: BLE001 - 降级不阻断
                logger.warning("词条蒸馏 LLM 失败，降级回复原样: %s", exc)
        return reply.strip()

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


def _fragment_name_lookup() -> dict[str, str]:
    """34 子类 id → 中文名（语境来信的灵魂碎片脚注用）。"""
    return {f["id"]: f["name"] for f in FragmentService.grid(None)}


def _local_date_str(person: Person) -> str:
    """盘主所在时区的今天（YYYY-MM-DD）。"""
    tz_name = person.birth.location.timezone_name or "Asia/Shanghai"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001
        tz = ZoneInfo("Asia/Shanghai")
    return datetime.now(tz).strftime("%Y-%m-%d")


__all__ = ["LetterService", "SENDER_ZH"]
