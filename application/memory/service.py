"""MemoryService —— "咨询后写回"编排器（产品循环后半段的核心胶水）。

一次咨询结束后调用：
  摘要（LLM/降级） → 合并进 ChartProfile → 存会话+摘要 → 生成成长事件 → 持久化

冻结架构约束：
- 本服务在 Application 层，负责编排跨会话状态。
- 画像里的置信度来自 Conclusion（Domain 产出），不来自 LLM 编造。
- 降级路径（无 LLM）也要能完成写回——只是画像不新增结构化理解。
"""

from __future__ import annotations

from foundation.database.store import GardenStore
from foundation.logger import get_logger
from foundation.utils import new_id, utc_now_aware
from shared.models import (
    ChartProfile,
    DomainSummary,
    KeyDate,
    LifeEvent,
    VerifiedFinding,
)
from shared.models.conclusion import Conclusion
from shared.models.conversation import Conversation
from shared.models.intent import Intent

from application.memory.summarizer import MemorySummarizer

logger = get_logger("application.memory.service")

#: 画像字段容量上限（防 LLM 输出失控把画像撑爆）
_MAX_KEY_DATES = 20
_MAX_FINDINGS = 30


class MemoryService:
    """跨会话记忆的写回入口。"""

    def __init__(self, store: GardenStore, summarizer: MemorySummarizer | None = None):
        self._store = store
        self._summarizer = summarizer or MemorySummarizer()

    # ------------------------------------------------------------------

    def get_or_create_profile(self, person_id: str) -> ChartProfile:
        profile = self._store.get_profile(person_id)
        if profile is None:
            now = utc_now_aware()
            profile = ChartProfile(person_id=person_id, created_at=now, updated_at=now)
        return profile

    def apply_writeback(
        self,
        *,
        person_id: str,
        conversation: Conversation,
        intent: Intent | None = None,
        conclusion: Conclusion | None = None,
    ) -> dict:
        """一次咨询后的完整写回。可安全重放（会话/画像 upsert，成长事件按结论去重）。

        返回 {"conversation_id", "summary", "profile_updated", "life_event_id"}。
        """
        domain = intent.domain.value if intent is not None else ""
        summary, updates = self._summarizer.summarize(conversation, domain)

        profile = self.get_or_create_profile(person_id)
        profile_updated = self._merge_profile(profile, updates, conclusion, intent)

        self._store.save_conversation(conversation, summary=summary)
        self._store.save_profile(profile)

        life_event_id: str | None = None
        if conclusion is not None:
            existing = self._store.get_life_event_by_conclusion(conclusion.id)
            if existing is not None:
                life_event_id = existing.id  # 重放：不重复生成成长事件
            else:
                event = LifeEvent(
                    id=new_id("evt"),
                    person_id=person_id,
                    occurred_at=conclusion.generated_at or utc_now_aware(),
                    label=self._event_label(domain, intent),
                    kind="consult",
                    detail=(conclusion.summary or "")[:300],
                    related_intent_id=intent.id if intent is not None else None,
                    related_conclusion_id=conclusion.id,
                    created_at=utc_now_aware(),
                )
                self._store.save_life_event(event)
                life_event_id = event.id

        return {
            "conversation_id": conversation.id,
            "summary": summary,
            "profile_updated": profile_updated,
            "life_event_id": life_event_id,
        }

    # ------------------------------------------------------------------
    # 画像合并（纯增量，不删已有内容）
    # ------------------------------------------------------------------

    def _merge_profile(
        self,
        profile: ChartProfile,
        updates: dict,
        conclusion: Conclusion | None,
        intent: Intent | None,
    ) -> bool:
        domain = intent.domain.value if intent is not None else ""
        updated = False

        # 1) 领域理解
        if domain:
            text = ""
            if updates.get("domain_summary"):
                text = str(updates["domain_summary"])
            elif conclusion is not None and conclusion.summary:
                text = conclusion.summary
            if text:
                confidence = conclusion.overall_confidence if conclusion is not None else 0.0
                notes = (
                    [f.text for f in conclusion.findings[:3]]
                    if conclusion is not None and conclusion.findings
                    else []
                )
                profile.domain_summaries[domain] = DomainSummary(
                    domain=domain,
                    summary=text,
                    confidence=confidence,
                    evidence_notes=notes,
                    updated_at=utc_now_aware(),
                )
                updated = True

        # 2) 关键日期（按 label 去重）
        for item in updates.get("key_dates", []):
            if not isinstance(item, dict) or not item.get("label"):
                continue
            label = str(item["label"])
            if any(kd.label == label for kd in profile.key_dates):
                continue
            profile.key_dates.append(KeyDate(
                id=new_id("kd"),
                date=self._parse_date(item.get("date")),
                label=label,
                kind="event",
            ))
            updated = True
        if len(profile.key_dates) > _MAX_KEY_DATES:
            profile.key_dates = profile.key_dates[-_MAX_KEY_DATES:]

        # 3) 星象观察（合并覆盖同名 key）
        for key, value in (updates.get("lord_states") or {}).items():
            if not isinstance(key, str) or not key:
                continue
            profile.lord_states[key] = value
            updated = True

        # 4) 沉淀判断（按 statement 去重）
        for stmt in updates.get("verified_findings", []):
            if not isinstance(stmt, str) or not stmt.strip():
                continue
            if any(f.statement == stmt for f in profile.verified_findings):
                continue
            profile.verified_findings.append(VerifiedFinding(
                id=new_id("vf"),
                statement=stmt,
                confidence=conclusion.overall_confidence if conclusion is not None else 0.0,
                source_intent_id=intent.id if intent is not None else None,
                domain=domain,  # B2：记录所属领域，供"待验证清单"按领域分组
            ))
            updated = True
        if len(profile.verified_findings) > _MAX_FINDINGS:
            profile.verified_findings = profile.verified_findings[-_MAX_FINDINGS:]

        if updated:
            profile.updated_at = utc_now_aware()
        return updated

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_date(raw) -> "object | None":
        """尽力解析 LLM 返回的日期；解析失败用当前时间，不阻塞写回。"""
        from dateutil import parser

        try:
            if not raw:
                raise ValueError("empty")
            return parser.parse(str(raw))
        except Exception:  # noqa: BLE001
            return utc_now_aware()

    @staticmethod
    def _event_label(domain: str, intent: Intent | None) -> str:
        sub = intent.subdomain if intent is not None and intent.subdomain else ""
        if sub:
            return f"{domain}.{sub} 咨询"
        zh = {"career": "事业", "relationship": "感情", "wealth": "财富", "emotion": "情绪",
              "health": "健康", "family": "家庭", "learning": "学习", "daily": "每日"}.get(domain, domain)
        return f"{zh or domain}咨询"


__all__ = ["MemoryService"]
