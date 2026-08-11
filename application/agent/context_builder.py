"""ContextBuilder —— 会话上下文管理。

聚合：用户档案（Person）、会话记忆、当前意图。
不涉及任何占星计算（原则一）。
"""

from __future__ import annotations

from foundation.utils import new_id
from shared.models import Conversation, DialogueTurn, Memory, MemoryItem, Person

from shared.enums import PersonaType, Role


class ContextBuilder:
    """管理会话上下文。"""

    def __init__(self):
        self._sessions: dict[str, "SessionContext"] = {}

    def get_or_create(self, session_id: str, person: Person, persona: PersonaType) -> "SessionContext":
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionContext(
                session_id=session_id,
                person=person,
                persona=persona,
                conversation=Conversation(
                    id=new_id("conv"),
                    person_id=person.id,
                    persona=persona,
                ),
                memory=Memory(session_id=session_id, person_id=person.id),
            )
        return self._sessions[session_id]

    def get(self, session_id: str) -> "SessionContext | None":
        """取已存在的会话（写回/回访用）。不存在 → None。"""
        return self._sessions.get(session_id)


class SessionContext:
    """一个会话的上下文聚合。"""

    def __init__(self, session_id: str, person: Person, persona: PersonaType,
                 conversation: Conversation, memory: Memory):
        self.session_id = session_id
        self.person = person
        self.persona = persona
        self.conversation = conversation
        self.memory = memory
        self.latest_intent = None
        self.latest_conclusion = None
        self.emotion_result = None       # 情绪感知结果（陪伴协议第 1 步）; EmotionResult | None
        self.last_was_companion = False  # 本条是否走陪伴轨道（递出口门控在 API 层）
        self.fragments: list[str] = []   # 本条命中的 34 子类 id（§2 点亮，随聊轨道填）
        #: 被照见（§4.2 +5）：上一轮镜映/解读点亮的子类，本轮用户确认"对，就是这样"→ 补 +5。
        #: API 层结算本轮点亮后写入，下一轮作为照见候选读取。
        self.previous_lit_fragments: list[str] = []
        self.previous_lighted: bool = False   # 上一轮是否有值得确认的镜映/解读
        #: 语境定刻（§1.1.1）：此刻被触动的星灵 + 抓手 + 情绪/诉求（陪伴轨道填）。
        #: 只报激活，不判方向——方向由 Domain 相位表出（硬线）。
        self.planet_activation = None    # PlanetActivation | None
        self.related_person: Person | None = None      # 合盘对象（含出生数据）
        self.pending_related_person: bool = False      # 已问过对方数据，等待提供
        #: A2 关系层：本条消息是否命中纯问候/闲聊快路径（_detect_chat）。
        #: 该路径在意图解析之前返回，没有 Intent 可查，故用标志位识别 casual 信号。
        self.last_was_chat: bool = False

    def to_intent_context(self) -> dict:
        """蒸馏上下文：供 IntentParser 消解追问（如"那明年呢？"）。

        Application 层只传状态，不含任何占星含义（原则一）。
        """
        active_domain = self.latest_intent.domain.value if self.latest_intent else None
        active_subdomain = self.latest_intent.subdomain if self.latest_intent else None
        return {
            "active_domain": active_domain,
            "active_subdomain": active_subdomain,
            "pending_related_person": self.pending_related_person,
        }

    def record_user_message(self, message: str) -> None:
        from datetime import datetime, timezone

        item = MemoryItem(
            id=new_id("mem"),
            session_id=self.session_id,
            person_id=self.memory.person_id,
            role=Role.USER,
            content=message,
            timestamp=datetime.now(timezone.utc),
        )
        self.memory.add(item)

    def record_assistant_response(self, response: str) -> None:
        from datetime import datetime, timezone

        item = MemoryItem(
            id=new_id("mem"),
            session_id=self.session_id,
            person_id=self.memory.person_id,
            role=Role.ASSISTANT,
            content=response,
            timestamp=datetime.now(timezone.utc),
        )
        self.memory.add(item)

    def add_turn(self, user_message: str, assistant_response: str) -> None:
        from datetime import datetime, timezone

        turn = DialogueTurn(
            id=new_id("turn"),
            user_message=user_message,
            assistant_response=assistant_response,
            intent_id=self.latest_intent.id if self.latest_intent else None,
            conclusion_id=self.latest_conclusion.id if self.latest_conclusion else None,
            persona_used=self.persona,
            timestamp=datetime.now(timezone.utc),
        )
        self.conversation.add_turn(turn)
