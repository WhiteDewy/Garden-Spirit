"""星灵花园 API —— 前端（PWA/uni-app）与 Agent 内核之间的 JSON 契约。

冻结架构：Application 层编排，不懂占星。星盘计算/推理全部在 Domain，
这里只把用户输入转成 Person/Intent，把 Agent 输出转成前端能消费的 JSON。

W1 骨架端点：
- GET  /health                     存活检查
- POST /person                     建档（出生数据，加密落库）
- GET  /person/{id}                读档
- POST /chat                       对话（接通 GardenSpiritAgent + 记忆写回）
- GET  /person/{id}/profile        长期画像（"我的宇宙"页的素材）
- GET  /person/{id}/timeline       成长时间轴（LifeEvent 列表）
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from foundation.astronomy.geocoding import geocode, manual_location
from foundation.config import AppConfig
from foundation.database import PersonRepository
from foundation.database.store import GardenStore
from foundation.utils import birth_data_fallback, new_id, utc_now_aware
from shared.enums import ConsultMode, HouseSystem, IntentDomain, PersonaType
from shared.models import ChartProfile, GeoLocation, Letter, Person

from application.action import ActionService
from application.agent import GardenSpiritAgent
from application.learning import LearningService
from application.mailbox.letter_service import LetterService, SENDER_ZH
from application.memory.journal import JournalService, JournalSummarizer
from application.memory.service import MemoryService
from application.relationship import RelationshipService

APP_NAME = "星灵花园 Garden-Spirit"
APP_VERSION = "0.1.0"


# ----------------------------------------------------------------------
# 请求/响应模型（Pydantic，前端契约）
# ----------------------------------------------------------------------


class GeoIn(BaseModel):
    #: 精确路径（advanced 用户）：经纬度必须成对 + timezone_name
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    altitude: float = 0.0
    timezone_name: str = ""      # IANA 时区名，如 "Asia/Shanghai"
    place_name: str = ""         # 主路径：城市名，后端 geocode 解析经纬度+时区


class BirthIn(BaseModel):
    #: 出生地本地墙钟时间（不含时区），如 "1995-08-20T04:00:00"
    #: 后端按 geocode 解析出的出生地时区换算成 UTC（前端不做时区数学）
    datetime_local: str
    location: GeoIn
    time_known: bool = True


class PersonIn(BaseModel):
    id: str | None = None        # 留空 → 服务端生成
    name: str
    birth: BirthIn
    gender: str | None = None
    notes: str = ""
    house_system: str | None = None


class PersonOut(BaseModel):
    id: str
    name: str
    gender: str | None
    place_name: str
    time_known: bool
    house_system: str | None
    created_at: str | None = None
    #: 会员解锁位（v0.5 预留：false = 基础版，true = 深度咨询/完整画像）
    is_premium: bool = False


class ChatIn(BaseModel):
    person_id: str
    session_id: str | None = None  # 留空 → 服务端生成（多轮追问传同一个）
    message: str
    persona: str | None = None     # 星灵人格名（小写，如 "zircon"）
    mode: str | None = None        # 咨询模式：quick/deep/annual/chart/free（默认 deep）


class ChatOut(BaseModel):
    answer: str
    session_id: str
    intent_domain: str | None = None
    needs_related_person: bool = False
    written_back: bool = False
    mode: str = "deep"
    #: 关系层（A2）：当前信任等级（stranger/acquaintance/trusted/intimate）
    trust_level: str = "stranger"


class ProfileOut(BaseModel):
    person_id: str
    domain_summaries: dict[str, object]
    verified_findings: list[dict]
    key_dates: list[dict]
    trust_level: str = "stranger"
    updated_at: str | None = None


class OpeningOut(BaseModel):
    """进入花园的开场白（首次见面自我介绍 / 老用户欢迎回来）。"""

    opening: str
    trust_level: str


class FeedbackIn(BaseModel):
    #: 用户对沉淀判断的验证：confirmed（对上了）/ refuted（不对）
    feedback: str


class LifeEventIn(BaseModel):
    #: 记录一条人生事件（验前事的学习原料）
    label: str
    #: ISO 时间（naive 视为 UTC；法达精度到月，时区偏移影响可忽略）
    occurred_at: str
    detail: str = ""


class LifeEventVerifyOut(BaseModel):
    event_id: str
    label: str
    period_major: str              # 事件时的法达大限主
    period_sub: str                # 子限主
    verifications: list[dict] = []  # 每条判断的验证结果
    calibrated: bool = False        # 是否有判断被校准


class FindingOut(BaseModel):
    """一条沉淀判断 + 验证状态（B2 待验证清单）。"""

    id: str
    statement: str
    domain: str = ""
    confidence: float = 0.0
    status: str = "unverified"      # "unverified" | "verified"
    feedback: str = ""              # "" | "confirmed" | "refuted"
    event_verified: bool = False
    verification_notes: list[str] = []
    confirmed_at: str | None = None


class PreferenceIn(BaseModel):
    """用户偏好更新（B2 行动层）。只更新出现的字段。"""

    push_frequency: str | None = None
    sensitive_topics: list[str] | None = None
    preferred_persona: str | None = None


class TimelineEventOut(BaseModel):
    id: str
    occurred_at: str
    label: str
    kind: str
    detail: str = ""
    related_conclusion_id: str | None = None


class JournalIn(BaseModel):
    person_id: str
    content: str
    mood: str = ""


class JournalUpdate(BaseModel):
    content: str | None = None
    mood: str | None = None


class JournalOut(BaseModel):
    id: str
    person_id: str
    content: str
    mood: str
    ai_summary: str
    created_at: str | None = None
    updated_at: str | None = None


class LetterOut(BaseModel):
    id: str
    person_id: str
    letter_date: str
    sender: str
    sender_zh: str
    title: str
    body: str
    kind: str
    created_at: str | None = None


class MailboxTodayIn(BaseModel):
    person_id: str


class GardenState(BaseModel):
    person_id: str
    today: str
    letter: LetterOut | None
    continue_from: dict | None = None    # {conversation_id, summary, started_at}
    domains: list[str] = []              # 已有画像的领域（我的宇宙）
    trust_level: str = "stranger"        # 关系层（A2）：当前信任等级
    pending_verifications: int = 0       # 行动层（B2）：待验证判断数（主动提醒）


# ----------------------------------------------------------------------
# 依赖注入：AppConfig / 仓库 / Agent 单例
# ----------------------------------------------------------------------


def _load_config() -> AppConfig:
    return AppConfig()


def create_app(config: AppConfig | None = None) -> FastAPI:
    config = config or _load_config()

    app = FastAPI(title=APP_NAME, version=APP_VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],      # PWA 开发期全放行；上线收紧
        allow_methods=["*"],
        allow_headers=["*"],
    )

    person_repo = PersonRepository(db_path=config.storage.db_path)
    store = GardenStore(db_path=config.storage.db_path)
    agent = GardenSpiritAgent(config)
    memory = MemoryService(store)
    journal = JournalService(store, summarizer=JournalSummarizer(agent._llm))
    letter = LetterService(
        store,
        llm_client=agent._llm,
        chart_provider=lambda p: agent._calculator.compute(p),
    )
    relationship = RelationshipService()  # A2 关系层：纯逻辑，无 io
    learning = LearningService(           # B1 学习层：验前事 → 置信度校准
        store,
        chart_provider=lambda p: agent._calculator.compute(p),
    )
    action = ActionService()              # B2 行动层：待验证清单 + 偏好

    # 注入到 app.state，供路由与测试访问
    app.state.config = config
    app.state.person_repo = person_repo
    app.state.store = store
    app.state.agent = agent
    app.state.memory = memory
    app.state.journal = journal
    app.state.letter = letter
    app.state.relationship = relationship
    app.state.learning = learning
    app.state.action = action

    def _get_person(person_id: str) -> Person:
        """读用户档案；缺失 → 404，解密失败（密钥变更/损坏）→ 410。

        解密失败不裸抛 500：对用户诚实告知"数据不可读，需重新建档"。
        """
        try:
            person = person_repo.get(person_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=410, detail="出生数据不可解密（密钥变更或数据损坏），请重新建档"
            ) from exc
        if person is None:
            raise HTTPException(status_code=404, detail="用户不存在，先 POST /person")
        return person

    # ------------------------------------------------------------------
    # 路由
    # ------------------------------------------------------------------

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "app": APP_NAME,
            "version": APP_VERSION,
            "llm_available": agent._llm.available if hasattr(agent, "_llm") else False,
        }

    @app.post("/person", response_model=PersonOut)
    def create_person(body: PersonIn) -> PersonOut:
        person = _to_person(body)
        person_repo.save(person)
        return _to_person_out(person)

    @app.get("/person/{person_id}", response_model=PersonOut)
    def get_person(person_id: str) -> PersonOut:
        return _to_person_out(_get_person(person_id))

    @app.get("/person/{person_id}/profile", response_model=ProfileOut)
    def get_profile(person_id: str) -> ProfileOut:
        profile = store.get_profile(person_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="尚无画像（先对话一次）")
        return ProfileOut(
            person_id=profile.person_id,
            domain_summaries={
                d.domain: {"summary": d.summary, "confidence": d.confidence,
                           "evidence_notes": d.evidence_notes, "updated_at": _iso_str(d.updated_at)}
                for d in profile.domain_summaries.values()
            },
            verified_findings=_profile_findings(action, profile),
            key_dates=[
                {"id": k.id, "label": k.label, "date": _iso_str(k.date), "kind": k.kind}
                for k in profile.key_dates
            ],
            trust_level=relationship.level(profile).value,
            updated_at=_iso_str(profile.updated_at),
        )

    @app.post("/journal", response_model=JournalOut)
    def create_journal(body: JournalIn) -> JournalOut:
        _get_person(body.person_id)  # 用户必须存在
        if not body.content.strip():
            raise HTTPException(status_code=422, detail="日记内容不能为空")
        entry = journal.create(body.person_id, body.content.strip(), body.mood)

        # A2 关系层：写日记是信任信号（倾诉）
        profile = _get_or_init_profile(store, body.person_id)
        relationship.record_journal(profile)
        store.save_profile(profile)

        return _to_journal_out(entry)

    @app.get("/person/{person_id}/journal", response_model=list[JournalOut])
    def list_journal(person_id: str) -> list[JournalOut]:
        _get_person(person_id)
        return [_to_journal_out(e) for e in journal.list(person_id)]

    @app.put("/journal/{entry_id}", response_model=JournalOut)
    def update_journal(entry_id: str, body: JournalUpdate) -> JournalOut:
        entry = journal.update(entry_id, content=body.content, mood=body.mood)
        if entry is None:
            raise HTTPException(status_code=404, detail="日记不存在")
        return _to_journal_out(entry)

    @app.post("/mailbox/today", response_model=LetterOut)
    def mailbox_today(body: MailboxTodayIn) -> LetterOut:
        """今天的星灵来信：没有则生成一封（幂等按天）。"""
        person = _get_person(body.person_id)
        return _to_letter_out(letter.get_or_create_daily(person))

    @app.get("/person/{person_id}/letters", response_model=list[LetterOut])
    def list_letters(person_id: str) -> list[LetterOut]:
        _get_person(person_id)
        return [_to_letter_out(l) for l in letter.list(person_id)]

    @app.get("/garden", response_model=GardenState)
    def garden(person_id: str = Query(...)) -> GardenState:
        """花园首页聚合：今日来信 + 继续昨天 + 我的宇宙领域。"""
        person = _get_person(person_id)
        today_letter = letter.get_or_create_daily(person)
        recent = store.list_conversation_summaries(person_id, limit=1)
        profile = store.get_profile(person_id)
        domains = list(profile.domain_summaries.keys()) if profile else []
        return GardenState(
            person_id=person_id,
            today=today_letter.letter_date,
            letter=_to_letter_out(today_letter),
            continue_from=recent[0] if recent else None,
            domains=domains,
            trust_level=relationship.level(profile).value,
            pending_verifications=action.pending_count(profile),
        )

    @app.get("/person/{person_id}/opening", response_model=OpeningOut)
    def get_opening(person_id: str) -> OpeningOut:
        """进入花园的开场白：首次见面自我介绍 / 老用户欢迎回来。"""
        person = _get_person(person_id)
        profile = store.get_profile(person_id)
        recent = store.list_conversation_summaries(person_id, limit=1)
        opening = relationship.opening_message(
            profile, person_name=person.name, continue_from=recent[0] if recent else None,
        )
        return OpeningOut(
            opening=opening,
            trust_level=relationship.level(profile).value,
        )

    @app.post("/person/{person_id}/findings/{finding_id}/feedback", response_model=dict)
    def feedback_finding(person_id: str, finding_id: str, body: FeedbackIn) -> dict:
        """用户验证一条沉淀判断：confirmed（对上了）/ refuted（不对）。

        验证是信任信号（A2 关系层）——诚实反馈本身就在深化关系。
        """
        _get_person(person_id)  # 用户必须存在
        if body.feedback not in ("confirmed", "refuted"):
            raise HTTPException(status_code=422, detail="feedback 只能为 confirmed 或 refuted")
        profile = store.get_profile(person_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="尚无画像（先对话一次）")
        target = next((f for f in profile.verified_findings if f.id == finding_id), None)
        if target is None:
            raise HTTPException(status_code=404, detail="沉淀判断不存在")
        target.user_feedback = body.feedback
        relationship.record_finding_feedback(profile, body.feedback)
        # B1 学习层：反馈校准置信度（confirmed +0.15 / refuted −0.15）
        cal = learning.calibrate_from_feedback(profile, target, body.feedback)
        store.save_profile(profile)
        return {
            "ok": True,
            "user_feedback": body.feedback,
            "trust_level": relationship.level(profile).value,
            "new_confidence": cal["new_confidence"],
        }

    @app.post("/person/{person_id}/events", response_model=LifeEventVerifyOut)
    def create_life_event(person_id: str, body: LifeEventIn) -> LifeEventVerifyOut:
        """记录一条人生事件 + 验前事：法达倒推 × 事件 → 验证沉淀判断 → 校准置信度。

        B1 学习层入口。事件发生在某判断主题星的主运期 → 该判断"验上了"，
        ‎confidence +0.1；不在 → 未确认（诚实原则：缺席 ≠ 证伪）。
        """
        person = _get_person(person_id)
        if not body.label.strip():
            raise HTTPException(status_code=422, detail="事件名称不能为空")
        try:
            occurred_at = _parse_event_time(body.occurred_at)
            result = learning.record_life_event(
                person, body.label.strip(), occurred_at, body.detail,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return LifeEventVerifyOut(
            event_id=result["event_id"],
            label=body.label.strip(),
            period_major=result["period_major"],
            period_sub=result["period_sub"],
            verifications=result["verifications"],
            calibrated=result["calibrated"],
        )

    @app.get("/person/{person_id}/findings", response_model=list[FindingOut])
    def list_findings(person_id: str, pending_only: bool = Query(False)) -> list[FindingOut]:
        """待验证清单（B2）：罗列全部沉淀判断 + 验证状态。

        pending_only=true → 只返回未验证的（用户"后面一起验证"的队列）。
        """
        _get_person(person_id)
        profile = store.get_profile(person_id)
        items = action.findings_status(profile)
        if pending_only:
            items = [i for i in items if i["status"] == "unverified"]
        return [_to_finding_out(i) for i in items]

    @app.get("/person/{person_id}/preferences", response_model=dict)
    def get_preferences(person_id: str) -> dict:
        """读用户偏好（B2 行动层）。未设置过的 key 返回默认值。"""
        _get_person(person_id)
        profile = store.get_profile(person_id)
        return action.preferences(profile)

    @app.put("/person/{person_id}/preferences", response_model=dict)
    def update_preferences(person_id: str, body: PreferenceIn) -> dict:
        """更新用户偏好（部分更新：只改出现的字段）。"""
        _get_person(person_id)
        submitted = body.model_dump(exclude_none=True)
        try:
            cleaned = action.validate_preferences(submitted)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not cleaned:
            return action.preferences(store.get_profile(person_id))

        profile = _get_or_init_profile(store, person_id)
        profile.preferences = {**action.preferences(profile), **cleaned}
        store.save_profile(profile)
        return action.preferences(profile)

    @app.get("/person/{person_id}/timeline", response_model=list[TimelineEventOut])
    def get_timeline(person_id: str) -> list[TimelineEventOut]:
        events = store.list_life_events(person_id)
        return [
            TimelineEventOut(
                id=e.id,
                occurred_at=e.occurred_at.isoformat() if e.occurred_at else "",
                label=e.label,
                kind=e.kind,
                detail=e.detail,
                related_conclusion_id=e.related_conclusion_id,
            )
            for e in events
        ]

    @app.post("/chat", response_model=ChatOut)
    def chat(body: ChatIn) -> ChatOut:
        person = _get_person(body.person_id)

        session_id = body.session_id or new_id("sess")
        persona = PersonaType(body.persona) if body.persona else None
        mode = _parse_mode(body.mode)

        # 已有会话且该用户请求过合盘对象 → 登记（单会话内生效）
        _restore_related_person(agent, session_id, body.person_id, person)

        answer = agent.handle_message(session_id, body.message, person, persona, mode=mode)

        written_back = _maybe_writeback(
            agent, memory, session_id, body.person_id
        )
        ctx = agent.get_session_context(session_id)
        domain = ctx.latest_intent.domain.value if ctx and ctx.latest_intent else None
        needs_related = bool(ctx and ctx.pending_related_person)

        # A2 关系层：记录信任信号 + 邀请式引导 + 回传等级
        profile = _get_or_init_profile(store, body.person_id)
        # 闲聊 = 问候快路径（last_was_chat）或 Daily.Chat 子领域（意图解析）
        is_casual = bool(
            (ctx and ctx.last_was_chat)
            or (ctx and ctx.latest_intent
                and ctx.latest_intent.domain == IntentDomain.DAILY
                and ctx.latest_intent.subdomain == "Chat")
        )
        if written_back:
            relationship.record_consult(profile, mode=mode)
        elif is_casual:
            relationship.record_consult(profile, casual=True)
        store.save_profile(profile)

        # 邀请式引导：深度咨询且信任达标，且回答不以问句结尾（不打断提问）
        if written_back and not answer.rstrip().endswith(("？", "?")):
            invite = relationship.invitation(profile)
            if invite:
                answer = f"{answer}\n\n{invite}"

        return ChatOut(
            answer=answer,
            session_id=session_id,
            intent_domain=domain,
            needs_related_person=needs_related,
            written_back=written_back,
            mode=mode.value,
            trust_level=relationship.level(profile).value,
        )

    return app


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _parse_mode(raw: str | None) -> ConsultMode:
    """咨询模式安全解析：空/非法 → 默认 deep（不 500）。"""
    if not raw:
        return ConsultMode.DEEP
    try:
        return ConsultMode(raw)
    except ValueError:
        return ConsultMode.DEEP


def _to_person(body: PersonIn) -> Person:
    """构造 Person。

    出生地：优先精确经纬度+时区；否则由 place_name 经 geocode 解析。
    解析失败 → 422 明确报错（**不允许**静默用错误坐标——占星城市错了宫位全错）。
    时间：接收出生地墙钟时间，按解析出的时区换算成 UTC；时间未知走正午降级。
    """
    location = _resolve_location(body.birth.location)

    try:
        dt_local = datetime.fromisoformat(body.birth.datetime_local)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"出生时间格式错误: {body.birth.datetime_local}") from exc

    if dt_local.tzinfo is None:
        dt_local = dt_local.replace(tzinfo=ZoneInfo(location.timezone_name))
    dt_utc = dt_local.astimezone(timezone.utc)
    birth = birth_data_fallback(dt_utc, location, body.birth.time_known)

    return Person(
        id=body.id or new_id("person"),
        name=body.name,
        birth=birth,
        gender=body.gender,
        notes=body.notes,
        house_system=HouseSystem(body.house_system) if body.house_system else None,
    )


def _resolve_location(loc: GeoIn) -> GeoLocation:
    """出生地 → GeoLocation（含时区）。两种合法路径：

    1. 精确：经纬度成对 + IANA 时区名（advanced 用户/GPS）。
    2. 城市名：geocode 解析经纬度 + 推导时区。
    其余 → 422，绝不静默降级到错误坐标。
    """
    if loc.latitude is not None or loc.longitude is not None:
        if loc.latitude is None or loc.longitude is None:
            raise HTTPException(status_code=422, detail="经纬度必须成对提供")
        if not loc.timezone_name:
            raise HTTPException(status_code=422, detail="提供精确经纬度时必须同时给出 timezone_name（IANA 时区名）")
        return GeoLocation(
            latitude=loc.latitude,
            longitude=loc.longitude,
            altitude=loc.altitude,
            timezone_name=loc.timezone_name,
            place_name=loc.place_name or f"{loc.latitude:.4f},{loc.longitude:.4f}",
        )

    if not loc.place_name:
        raise HTTPException(status_code=422, detail="需要提供出生城市（place_name）或精确经纬度+时区")

    result = geocode(loc.place_name)
    if result is None:
        raise HTTPException(
            status_code=422,
            detail=f"无法解析出生地「{loc.place_name}」，请补充到市级；"
                   "或直接提供精确经纬度 + timezone_name",
        )
    return GeoLocation(
        latitude=result.latitude,
        longitude=result.longitude,
        altitude=loc.altitude,
        timezone_name=result.timezone_name,
        place_name=result.place_name,
    )


def _to_person_out(p: Person) -> PersonOut:
    return PersonOut(
        id=p.id,
        name=p.name,
        gender=p.gender,
        place_name=p.birth.location.place_name,
        time_known=p.birth.time_known,
        house_system=p.house_system.value if p.house_system else None,
        created_at=_iso_str(p.created_at),
        is_premium=False,  # v0.5 预留会员位，后续接付费状态
    )


def _restore_related_person(agent, session_id: str, person_id: str, person: Person) -> None:
    """单会话合盘对象目前只活在内存里；跨会话恢复留到 V2（持久化会话）。"""
    return None


def _to_finding_out(item: dict) -> FindingOut:
    return FindingOut(
        id=item["id"],
        statement=item["statement"],
        domain=item.get("domain", ""),
        confidence=item.get("confidence", 0.0),
        status=item["status"],
        feedback=item.get("feedback", ""),
        event_verified=item.get("event_verified", False),
        verification_notes=item.get("verification_notes", []),
        confirmed_at=item.get("confirmed_at"),
    )


def _profile_findings(action, profile) -> list[dict]:
    """画像里的沉淀判断 → 带验证状态的 dict 列表（B2：status 逐条对应）。"""
    status_map = {s["id"]: s["status"] for s in action.findings_status(profile)}
    return [
        {"id": f.id, "statement": f.statement, "confidence": f.confidence,
         "domain": f.domain, "status": status_map.get(f.id, "unverified")}
        for f in profile.verified_findings
    ]


def _parse_event_time(raw: str) -> datetime:
    """解析人生事件时间：ISO → UTC。naive 视为 UTC（法达精度到月）。"""
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(
            f"事件时间格式错误: {raw}（用 ISO 格式，如 2021-09-01 或 2021-09-01T12:00:00）"
        ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _get_or_init_profile(store: GardenStore, person_id: str) -> ChartProfile:
    """取画像；无则初始化空画像（首次闲聊/写日记即建 profile，信任从 0 起步）。"""
    profile = store.get_profile(person_id)
    if profile is None:
        now = utc_now_aware()
        profile = ChartProfile(person_id=person_id, created_at=now, updated_at=now)
    return profile


def _maybe_writeback(agent, memory, session_id: str, person_id: str) -> bool:
    ctx = agent.get_session_context(session_id)
    if ctx is None or ctx.latest_conclusion is None:
        return False
    memory.apply_writeback(
        person_id=person_id,
        conversation=ctx.conversation,
        intent=ctx.latest_intent,
        conclusion=ctx.latest_conclusion,
    )
    return True


def _iso_str(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _to_letter_out(l: Letter) -> LetterOut:
    return LetterOut(
        id=l.id,
        person_id=l.person_id,
        letter_date=l.letter_date,
        sender=l.sender,
        sender_zh=SENDER_ZH.get(l.sender, l.sender),
        title=l.title,
        body=l.body,
        kind=l.kind,
        created_at=_iso_str(l.created_at),
    )


def _to_journal_out(e) -> JournalOut:
    return JournalOut(
        id=e.id,
        person_id=e.person_id,
        content=e.content,
        mood=e.mood,
        ai_summary=e.ai_summary,
        created_at=_iso_str(e.created_at),
        updated_at=_iso_str(e.updated_at),
    )


app = create_app()
