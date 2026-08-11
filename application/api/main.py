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
from application.relationship import RelationshipService, naturalize_recall
from application.conversation.action import ActionDetector
from application.conversation.confirmation import ConfirmationDetector
from application.push import PushService
from application.conversation.fragments import (
    DEPTH_ACTION,
    DEPTH_CONSULT,
    DEPTH_OUTPOURING,
    DEPTH_SEEN,
    FragmentService,
)

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
    #: 情绪感知（陪伴协议第 1 步）：当前情绪 × 诉求类型
    emotion: str | None = None
    request_type: str | None = None
    #: 34 子类点亮（§2）：本条随聊点亮了哪些子类（"今日灵魂碎片"的原料）
    lit_fragments: list[str] = []
    #: 被照见（§4.2 +5）：本条用户确认上一轮镜映 → 补亮的子类
    seen_fragments: list[str] = []
    #: 来信式日记（§6.1）：本条倾诉是否生成了一封 keepsake 来信（"值得记住的时刻"）
    keepsake_created: bool = False
    #: 触发行动（§4.2 +20）：本条是"我真的去做了"行动回报 → 上一段会话点亮的子类补 +20
    actioned_fragments: list[str] = []


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


class FragmentOut(BaseModel):
    """一个 34 子类条目（"自我星盘轮"）。"""

    id: str
    zone: str          # planet / house / sign
    name: str          # "太阳·核心意志"
    triggers: str      # 触发说明
    depth: int         # 深度分（未点亮 = 0）
    level: int = 0     # 五层成长级（§4.2 1-5 级，未点亮 = 0；后端统一出级）
    #: 触发行动次数（§4.2 升顶门槛：4 级需 ≥1 次、5 级需 ≥2 次"真做过"）
    action_count: int = 0


class FragmentsOut(BaseModel):
    """全部 34 子类 + 当前深度分（含未点亮=0，供"盲区即课题"叙事）。"""

    person_id: str
    fragments: list[FragmentOut]


class SoulFragmentOut(BaseModel):
    """今日灵魂碎片的一个子类（§2.5 每日结算）。"""

    id: str
    name: str          # "太阳·核心意志"
    zone: str          # planet / house / sign
    delta: int         # 今天累计点亮深度分


class SoulFragmentsTodayOut(BaseModel):
    """今日灵魂碎片（§2.5）：今天（盘主本地日）点亮的 top N 子类。"""

    person_id: str
    date: str          # 本地日期 YYYY-MM-DD
    fragments: list[SoulFragmentOut]


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


class PushSubscribeIn(BaseModel):
    """浏览器 PushSubscription.toJSON() 上报（Web Push 订阅）。"""

    person_id: str
    subscription: dict


class PushUnsubscribeIn(BaseModel):
    """退订（endpoint 失效 / 用户关通知）。"""

    person_id: str
    endpoint: str


class PushTriggerResult(BaseModel):
    """每日推送触发结果统计（external cron 用）。"""

    total_persons: int
    skipped_quiet: int
    skipped_no_sub: int
    pushed: int


class TimelineEventOut(BaseModel):
    id: str
    occurred_at: str
    label: str
    kind: str
    detail: str = ""
    related_conclusion_id: str | None = None
    # 咨询记录补意图/需求（喂记忆写回）：domain = 八大领域，need = 诉求类型
    domain: str = ""
    need: str = ""


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
    read_at: str | None = None          # 用户打开信箱设已读（首页红点：今日来信未读）
    # 来信式日记（kind=keepsake）的落款推导链（§6.2）：显式可解释"为什么是这颗星"
    primary_need: str | None = None
    healing_name: str | None = None
    soul_fragments: list[str] = []   # 次需求点亮的 34 子类
    lit_fragments: list[str] = []    # 当日随聊点亮的 34 子类
    explain: str | None = None
    entry: bool = False              # 词条式来信（§6.1 日常/正面分享时刻）


class MailboxTodayIn(BaseModel):
    person_id: str


class GardenState(BaseModel):
    person_id: str
    today: str
    letter: LetterOut | None
    continue_from: dict | None = None    # {conversation_id, summary, started_at}
    domains: list[str] = []              # 已有画像的领域（我的宇宙）
    trust_level: str = "stranger"        # 关系层（A2）：当前信任等级
    pending_verifications: int = 0       # 行动层（B2）：待验证判断数（我的宇宙 nav 红点）
    # 首页红点细粒度：今日来信未读（用户打开信箱 → read_at 落库 → 消除）
    letter_unread: bool = False
    # 站内"回家看看"兜底（推送后置）：今天（本地日）点亮的 top3 灵魂碎片
    soul_fragments: list[SoulFragmentOut] = []


def _local_day_utc(person: Person) -> tuple[datetime, str]:
    """盘主本地日的起点（UTC）与本地日期字符串（YYYY-MM-DD）。

    与来信 letter_date 同口径：本地 00:00 起算当日账本，供"今日灵魂碎片"聚合。
    """
    tz_name = person.birth.location.timezone_name or "Asia/Shanghai"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001 - 非法时区兜底东八区（与来信一致）
        tz = ZoneInfo("Asia/Shanghai")
    local_now = datetime.now(tz)
    local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    utc_start = local_start.astimezone(timezone.utc)
    return utc_start, local_now.strftime("%Y-%m-%d")


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
    fragments = FragmentService()         # 随聊记录层：34 子类点亮（纯逻辑，无 io）
    confirmation = ConfirmationDetector(agent._llm)  # 被照见（§4.2 +5）确认识别
    action_detector = ActionDetector(agent._llm)     # 触发行动（§4.2 +20）识别器
    push_service = PushService(store, config.push)   # Web Push：订阅管理 + 来信推送

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
    app.state.fragments = fragments
    app.state.confirmation = confirmation
    app.state.action_detector = action_detector
    app.state.push_service = push_service

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

    @app.get("/person/{person_id}/fragments", response_model=FragmentsOut)
    def get_fragments(person_id: str) -> FragmentsOut:
        """自我星盘轮：全部 34 子类 + 深度分（未点亮 = 0，供"盲区即课题"）。"""
        _get_person(person_id)
        profile = store.get_profile(person_id)
        return FragmentsOut(
            person_id=person_id,
            fragments=[
                FragmentOut(**row)
                for row in fragments.grid(
                    profile,
                    action_counts=store.count_fragment_actions(person_id),
                )
            ],
        )

    @app.get("/person/{person_id}/soul-fragments/today", response_model=SoulFragmentsTodayOut)
    def soul_fragments_today(person_id: str) -> SoulFragmentsTodayOut:
        """今日灵魂碎片（§2.5 每日结算）：今天（盘主本地日）点亮的 top3 子类。

        账本按"盘主本地日 00:00 → now"聚合，与每日来信 letter_date 同日口径。
        """
        person = _get_person(person_id)
        utc_start, date_str = _local_day_utc(person)
        lights = store.list_fragment_lights(person_id, since=utc_start)
        return SoulFragmentsTodayOut(
            person_id=person_id,
            date=date_str,
            fragments=FragmentService.top_soul_fragments(lights, limit=3),
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

    @app.post("/person/{person_id}/letters/read-today", response_model=dict)
    def mark_letters_read_today(person_id: str) -> dict:
        """把今天（盘主本地日）未读的信标记为已读 → 首页信箱红点消除。

        打开信箱时调一次（幂等：只更新 read_at IS NULL 的行）。返回标记数。
        """
        person = _get_person(person_id)
        _, today_str = _local_day_utc(person)
        marked = store.mark_letters_read_today(person_id, today_str)
        return {"ok": True, "marked": marked}

    @app.get("/garden", response_model=GardenState)
    def garden(person_id: str = Query(...)) -> GardenState:
        """花园首页聚合（站内"回家看看"）：今日来信 + 今日灵魂碎片 + 继续昨天 + 领域 + 待验证。"""
        person = _get_person(person_id)
        today_letter = letter.get_or_create_daily(person)
        recent = store.list_conversation_summaries(person_id, limit=1)
        profile = store.get_profile(person_id)
        domains = list(profile.domain_summaries.keys()) if profile else []
        utc_start, _ = _local_day_utc(person)
        lights = store.list_fragment_lights(person_id, since=utc_start)
        # 继续昨天：摘要在读出口统一自然化（首页卡片与开场白同源，旧转写数据也可读）
        if recent:
            recent[0]["summary"] = naturalize_recall(recent[0].get("summary"))
        return GardenState(
            person_id=person_id,
            today=today_letter.letter_date,
            letter=_to_letter_out(today_letter),
            continue_from=recent[0] if recent else None,
            domains=domains,
            trust_level=relationship.level(profile).value,
            pending_verifications=action.pending_count(profile),
            letter_unread=today_letter.read_at is None,  # 今日来信未读 → 信箱 nav 红点
            soul_fragments=FragmentService.top_soul_fragments(lights, limit=3),
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

    # ------------------------------------------------------------------
    # Web Push（真实推送通道）：订阅 + VAPID 公钥 + 每日触发
    # ------------------------------------------------------------------

    @app.get("/push/vapid-public-key")
    def push_vapid_public_key() -> dict:
        """VAPID 公钥（base64url），前端 PushManager.subscribe 用。"""
        return {"public_key": push_service.vapid_public_key()}

    @app.post("/push/subscribe")
    def push_subscribe(body: PushSubscribeIn) -> dict:
        """存一条浏览器推送订阅（PushSubscription.toJSON()，加密落库）。"""
        _get_person(body.person_id)
        push_service.subscribe(body.person_id, body.subscription)
        return {"ok": True}

    @app.post("/push/unsubscribe")
    def push_unsubscribe(body: PushUnsubscribeIn) -> dict:
        """退订（endpoint 失效 / 用户关通知）。"""
        _get_person(body.person_id)
        deleted = push_service.unsubscribe(body.person_id, body.endpoint)
        return {"ok": True, "deleted": deleted}

    @app.post("/push/trigger", response_model=PushTriggerResult)
    def push_trigger() -> PushTriggerResult:
        """每日推送触发（external cron 调 scripts/push_daily.py）。

        遍历所有用户：push_frequency != daily 跳过；生成今天的来信（幂等）；
        推送给该用户所有设备。生产须限制本端点只允许内网/localhost 访问。
        """
        total = skipped_quiet = skipped_no_sub = pushed = 0
        for person in person_repo.list_all():
            total += 1
            profile = store.get_profile(person.id)
            if action.preferences(profile).get("push_frequency", "daily") != "daily":
                skipped_quiet += 1
                continue
            letter_obj = letter.get_or_create_daily(person)  # 幂等：已有则复用
            n = push_service.send_to_person(
                person.id,
                title=letter_obj.title or "星灵来信",
                body=(letter_obj.body or "").replace("\n", " ")[:80],
                url="/pages/mailbox/mailbox",
            )
            if n > 0:
                pushed += n
            else:
                skipped_no_sub += 1
        return PushTriggerResult(
            total_persons=total,
            skipped_quiet=skipped_quiet,
            skipped_no_sub=skipped_no_sub,
            pushed=pushed,
        )

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
                domain=e.domain,
                need=e.need,
            )
            for e in events
        ]

    @app.post("/chat", response_model=ChatOut)
    def chat(body: ChatIn) -> ChatOut:
        person = _get_person(body.person_id)

        session_id = body.session_id or new_id("sess")
        # 10 星灵回归：非法/旧宝石人格名（zircon/rose_quartz…）→ 落默认（月亮），不 500
        persona = None
        if body.persona:
            try:
                persona = PersonaType(body.persona)
            except ValueError:
                persona = None
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

        # 34 子类点亮（随聊记录层 §2 + 咨询反向点亮 §5）：只记"聊过什么"，不声称用户属性（硬线）。
        # - 随聊/问候轨道：按话题分类，深度分=倾诉（负面情绪）→ +3，一般提及 → +1。
        # - 咨询轨道：出了 Domain 结论 → 按领域确定性映射反向点亮，给最高深度分 +10（§5）。
        lit_fragments: list[str] = []
        seen_fragments: list[str] = []     # 被照见（§4.2 +5）：用户确认上一轮镜映 → 补亮
        actioned_fragments: list[str] = [] # 触发行动（§4.2 +20）：行动回报 → 上一段会话子类 +20
        keepsake_created = False
        # 成长复利账本（fragment_lights）：本轮所有点亮事件，连同 profile 一起落库。
        ledger: list = []
        if ctx is not None:
            # 触发行动（§4.2 +20）：必须先于随聊/咨询点亮跑——这样本轮点亮的
            # 不会混进"行动目标"（行动目标 = 更早的会话/轮次，见 _action_lighting）。
            actioned_fragments = _action_lighting(
                action_detector, store, body, ctx, profile, ledger,
            )
            # 被照见（§4.2 +5）：上一轮镜映/解读点亮的子类，本轮用户确认"对，就是这样"
            # → 补 +5（kind=seen）。确认检测 LLM 受控枚举 + 规则兜底，宁缺毋滥。
            if ctx.previous_lit_fragments and ctx.previous_lighted:
                if confirmation.is_confirmation(body.message):
                    seen_fragments = fragments.light(
                        profile, ctx.previous_lit_fragments, depth=DEPTH_SEEN,
                        kind="seen", source=body.message, ledger=ledger,
                    )
            if ctx.last_was_companion or ctx.last_was_chat:
                depth = 3 if (ctx.emotion_result and ctx.emotion_result.needs_care) else 1
                lit_fragments = fragments.light(
                    profile, ctx.fragments, depth=depth,
                    source=body.message, ledger=ledger,
                )
                # §6.1/§6.2 来信式日记：倾诉时刻（需要被接住）→ 星灵那段回复原样成信，
                # 落款走"内容→情绪需求→疗愈名"推导链（显式可解释）；次需求点亮的
                # 灵魂碎片同样 light() 进轮盘（两条路径汇入同一账本）。
                if (
                    ctx.last_was_companion
                    and ctx.emotion_result is not None
                    and ctx.emotion_result.needs_care
                ):
                    _keepsake, sig = letter.record_keepsake(
                        person,
                        content=body.message,
                        reply=answer,
                        lit_fragments=tuple(lit_fragments),
                    )
                    fragments.light(
                        profile, sig.soul_fragments, depth=DEPTH_OUTPOURING,
                        source=body.message, ledger=ledger,
                    )
                    keepsake_created = True
                # §6.1 词条式来信：日常/正面分享时刻（memorable 且非负面倾诉）→
                # LLM 当场蒸馏一句诗化记忆词条成信，落款照走推导链。不与上面的
                # 倾诉来信重复（memorable 的负面倾诉仍走 needs_care 分支，保留整段回复）。
                elif (
                    ctx.last_was_companion
                    and ctx.emotion_result is not None
                    and ctx.emotion_result.memorable
                ):
                    _entry, sig = letter.record_memorable(
                        person,
                        content=body.message,
                        reply=answer,
                        lit_fragments=tuple(lit_fragments),
                    )
                    fragments.light(
                        profile, sig.soul_fragments, depth=DEPTH_OUTPOURING,
                        source=body.message, ledger=ledger,
                    )
                    keepsake_created = True
            elif ctx.latest_conclusion is not None:
                consult_ids = FragmentService.fragments_for_domain(
                    ctx.latest_intent.domain.value
                )
                lit_fragments = fragments.light(
                    profile, consult_ids, depth=DEPTH_CONSULT,
                    source=f"consult:{ctx.latest_intent.domain.value}", ledger=ledger,
                )
            # 本轮点亮 → 作为下一轮的照见候选（本轮没点亮/澄清轮 → 保留上一轮候选）
            if lit_fragments:
                ctx.previous_lit_fragments = lit_fragments
                ctx.previous_lighted = True

        # 账本统一盖章所属会话（conversation.id）——触发行动（§4.2 +20）靠它精确回溯
        store.append_fragment_lights(
            body.person_id, ledger,
            session_id=ctx.conversation.id if ctx is not None else "",
        )
        store.save_profile(profile)

        # 陪伴轨道递出口（§7.2 第 4 步 + §7.3 软牵引门控）：
        # 只在随聊轨道递盘——诉求=被梳理/被推动（想理清/想行动）且信任达标。
        # 被听见/被安慰 → 不递盘（can_offer_chart 返回 False），继续陪。
        # 咨询轨道已出过星盘结论 → 不再重复递盘。
        from application.conversation.companion import can_offer_chart, soft_pull_line

        emotion_res = ctx.emotion_result if ctx else None
        if (
            ctx is not None
            and ctx.last_was_companion
            and emotion_res is not None
            and can_offer_chart(emotion_res.request, relationship.level(profile))
            and not answer.rstrip().endswith(("？", "?"))
        ):
            # §7.3 软牵引 = 诉求类型门控 × 共振星灵：语境定刻报告了哪颗星被触动，
            # 就指名这颗星邀请（仍只是邀请，结论由 Domain 在用户接受后出）。
            resonant = (
                ctx.planet_activation.primary
                if ctx.planet_activation is not None else None
            )
            pull = soft_pull_line(emotion_res.request, planet=resonant)
            if pull:
                answer = f"{answer}{pull}"

        # 邀请式引导：深度咨询且信任达标，且回答不以问句结尾（不打断提问）
        if written_back and not answer.rstrip().endswith(("？", "?")):
            invite = relationship.invitation(profile)
            if invite:
                answer = f"{answer}\n\n{invite}"

        emotion_res = ctx.emotion_result if ctx else None

        return ChatOut(
            answer=answer,
            session_id=session_id,
            intent_domain=domain,
            needs_related_person=needs_related,
            written_back=written_back,
            mode=mode.value,
            trust_level=relationship.level(profile).value,
            emotion=emotion_res.emotion.value if emotion_res else None,
            request_type=emotion_res.request.value if emotion_res else None,
            lit_fragments=lit_fragments,
            seen_fragments=seen_fragments,
            keepsake_created=keepsake_created,
            actioned_fragments=actioned_fragments,
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


def _action_lighting(detector, store, body, ctx, profile, ledger) -> list[str]:
    """触发行动（§4.2 +20）：本条是"我真的去做了"行动回报 → 补亮 +20 落账本。

    行动目标 = 上一段会话点亮的子类 ∪ 当前会话此前几轮点亮的子类：
    - 上一段会话：list_conversation_summaries 排除当前会话（ctx.conversation.id），
      逐段回溯其账本（session_id 精确锁定，不靠时间边界——会话 started_at 会随写回改写）。
    - 当前会话此前：账本 session_id=当前 conversation.id（本轮点亮还没落库，
      所以这里拿到的一定是"更早轮次"的点亮）。

    两者都没有 → 无从谈起（不能对从没聊过的子类"行动"），返回空。
    识别宁缺毋滥：+20 是稀有分，只有明确"完成"才算行动（ActionDetector LLM+规则兜底）。
    """
    if not detector.is_action_report(body.message):
        return []
    conv_id = ctx.conversation.id
    target: set[str] = set()
    for summary in store.list_conversation_summaries(body.person_id, limit=20):
        cid = summary.get("id")
        if not cid or cid == conv_id:
            continue
        for light in store.list_fragment_lights(body.person_id, session_id=cid, limit=200):
            target.add(light.subtype_id)
    for light in store.list_fragment_lights(body.person_id, session_id=conv_id, limit=200):
        target.add(light.subtype_id)
    if not target:
        return []
    return FragmentService.light(
        profile, sorted(target), depth=DEPTH_ACTION, kind="action",
        source=body.message, ledger=ledger,
    )


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
    """写回记忆。返回 True 表示"出了占星结论"（信任层按咨询计分）。

    咨询轨道 → apply_writeback（领域理解/沉淀判断/成长事件）→ True。
    随聊/问候轨道 → apply_chat_writeback（只存摘要，§6 双存）→ False
    （信任层仍按 casual 计分，见 /chat 的 is_casual 分支）。
    """
    ctx = agent.get_session_context(session_id)
    if ctx is None:
        return False
    if ctx.latest_conclusion is not None:
        memory.apply_writeback(
            person_id=person_id,
            conversation=ctx.conversation,
            intent=ctx.latest_intent,
            conclusion=ctx.latest_conclusion,
            need=ctx.emotion_result.request.value if ctx.emotion_result is not None else "",
        )
        return True
    if ctx.last_was_companion or ctx.last_was_chat:
        memory.apply_chat_writeback(
            person_id=person_id,
            conversation=ctx.conversation,
        )
    return False


def _iso_str(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _to_letter_out(l: Letter) -> LetterOut:
    meta = l.metadata or {}
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
        read_at=_iso_str(l.read_at),
        primary_need=meta.get("primary_need"),
        healing_name=meta.get("healing_name"),
        soul_fragments=list(meta.get("soul_fragments") or []),
        lit_fragments=list(meta.get("lit_fragments") or []),
        explain=meta.get("explain"),
        entry=bool(meta.get("entry")),
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
