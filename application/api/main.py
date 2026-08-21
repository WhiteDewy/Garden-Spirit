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
from typing import Any, Literal
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from foundation.astronomy.geocoding import geocode, manual_location
from foundation.config import AppConfig
from foundation.database import PersonRepository
from foundation.database.encryption import ENV_KEY_NAME, Encryptor
from foundation.database.store import GardenStore, _birth_from_json, _birth_to_json
from foundation.utils import birth_data_fallback, new_id, utc_now_aware
from shared.enums import ConsultMode, HouseSystem, IntentDomain, PersonaType, Planet
from shared.models import ChartProfile, GeoLocation, Letter, Person

from application.action import ActionService
from application.agent import GardenSpiritAgent
from application.learning import LearningService
from application.mailbox.letter_service import LetterService, SENDER_ZH
from application.memory.journal import JournalService, JournalSummarizer
from application.memory.service import MemoryService
from application.relationship import RelationshipService, naturalize_recall
from application.chart_cache import NatalChartCache
from application.conversation.action import ActionDetector
from application.conversation.confirmation import ConfirmationDetector
from application.conversation.persona import all_personas, get_persona
from application.push import PushService
from application.conversation.fragments import (
    DEPTH_ACTION,
    DEPTH_CONSULT,
    DEPTH_OUTPOURING,
    DEPTH_SEEN,
    FragmentService,
)
from domain.timeline.life_rhythm import build_life_rhythm
from domain.timeline.spirit_recommender import score_spirits

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


class AuthVerifyIn(BaseModel):
    """手机号验证码登录/注册。开发临时白名单：任意手机号 + 000000。"""

    phone: str
    code: str


class BirthOut(BaseModel):
    """档案编辑页回显出生数据：前端直接按建档表单填回。"""

    datetime_local: str
    location: GeoIn
    time_known: bool = True


class SelfProfileOut(PersonOut):
    """本人档案详情：比列表多出生数据与备注。"""

    birth: BirthOut
    notes: str = ""


class AccountOut(BaseModel):
    """后端权威账号态：手机号账号 owns 唯一本人档案。"""

    account_id: str
    phone: str
    self_person_id: str | None = None
    self_profile: SelfProfileOut | None = None


class ProfileListItemOut(BaseModel):
    """档案列表：self 唯一；related 只用于合盘，不能升为本人。"""

    id: str
    role: str
    name: str
    can_be_self: bool = False
    created_at: str | None = None


class ReportIntentIn(BaseModel):
    """主题观星台 → Chat 的报告型意图入口契约。只作路由/澄清上下文，不产出占星结论。"""

    entry_source: Literal["observatory"] = "observatory"
    entry_topic_key: str = Field(min_length=1, max_length=64)
    primary_topic: str | None = Field(default=None, max_length=64)
    secondary_topics: list[str] = Field(default_factory=list, max_length=8)
    intent_shape: Literal[
        "single_topic",
        "cross_topic_influence",
        "topic_switch_suggested",
        "clarification_required",
        "unsupported",
    ] | None = None
    report_type: Literal["monthly", "annual", "life_rhythm", "theme"] | None = None
    user_focus_text: str | None = Field(default=None, max_length=1000)


ReportSourceType = Literal[
    "profile",
    "finding",
    "timeline",
    "conversation",
    "memory",
    "fragment_light",
    "letter",
    "life_rhythm",
]


class ReportCompileInput(BaseModel):
    """Report Compiler MVP：只整理后端已有素材，不生成新的占星判断。"""

    report_type: Literal["chat_digest", "theme", "life_rhythm"] = "chat_digest"
    source: Literal["chat", "observatory", "manual"] = "chat"
    session_id: str | None = Field(default=None, max_length=128)
    topic: str | None = Field(default=None, max_length=160)
    report_intent: ReportIntentIn | None = None
    months: int = Field(default=3, ge=1, le=6)


class ReportSourceRefOut(BaseModel):
    """报告段落的证据引用：只指向后端权威素材。"""

    type: ReportSourceType
    id: str
    label: str = ""


class ReportSectionOut(BaseModel):
    key: str
    title: str
    body: str
    source_refs: list[ReportSourceRefOut] = Field(min_length=1)


class ReportOut(BaseModel):
    """结构化报告草稿；每个 section 都必须带 source_refs。"""

    id: str
    type: Literal["report"] = "report"
    status: Literal["draft"] = "draft"
    report_type: str
    person_id: str
    title: str
    summary: str
    generated_at: str
    sections: list[ReportSectionOut] = Field(min_length=1)
    source_refs: list[ReportSourceRefOut] = Field(default_factory=list)


class ChatIn(BaseModel):
    person_id: str
    session_id: str | None = None  # 留空 → 服务端生成（多轮追问传同一个）
    message: str
    persona: str | None = None     # 星灵人格名（小写，如 "zircon"）
    mode: str | None = None        # 咨询模式：quick/deep/annual/chart/free（默认 deep）
    related_person_id: str | None = None  # 本次合盘使用的对象（先 POST /related 保存）
    report_intent: ReportIntentIn | None = None  # 主题观星台入口上下文；只用于路由/澄清


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


class LifeRhythmOut(BaseModel):
    """Life Rhythm 报告地基：Domain 确定性输出，前端只渲染不推断。"""

    type: str
    person_id: str
    chart_id: str
    generated_at: str
    months: int
    timing_authority: str
    source_layers: list[str]
    natal_promise: list[dict] = Field(default_factory=list)
    firdaria_chapter: dict
    annual_activation: dict
    transit_triggers: list[dict] = Field(default_factory=list)


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


class JournalPageOut(BaseModel):
    """手账分页（信箱"我的手账"：20 条一页）。"""

    items: list[JournalOut]
    total: int
    page: int
    page_size: int
    has_more: bool


class RelatedPersonIn(BaseModel):
    """保存一个合盘对象（对方出生数据）。birth 复用建档的 BirthIn 格式。"""

    name: str
    birth: BirthIn
    gender: str | None = None
    notes: str = ""


class RelatedPersonOut(BaseModel):
    """合盘对象出参。列表视图省略出生数据（隐私：列表只要名字）。"""

    id: str
    person_id: str
    name: str
    created_at: str | None = None


class RelatedPersonDetailOut(RelatedPersonOut):
    """合盘对象编辑页详情：只用于 owner 自己查看/修改。"""

    birth: BirthOut
    gender: str | None = None
    notes: str = ""
    updated_at: str | None = None


class SpiritRecommendationOut(BaseModel):
    """今日一位星灵的推荐出参（可解释：为什么今天见 ta）。

    planet=行星值，name/healing_name/style 由人格映射（Application 层）；
    is_default=月亮兜底星（永远在列表里）；reason 为可追溯理由。
    """

    planet: str
    name: str
    healing_name: str
    style: str = ""
    score: float
    reason: str = ""
    is_default: bool = False
    is_firdaria_major_lord: bool = False
    is_firdaria_sub_lord: bool = False


class RecommendedSpiritsOut(BaseModel):
    """今日推荐（按综合分降序，含兜底月亮）。"""

    spirits: list[SpiritRecommendationOut]
    generated_at: str


class PersonaOut(BaseModel):
    """前端可选择的 10 星灵人格目录。"""

    key: str
    name: str
    healing_name: str
    style: str
    tone: str
    vocabulary: list[str] = []


class PersonExportOut(BaseModel):
    """合规数据导出：该用户全量数据明文聚合（下载 / 迁移 / 删除前存档）。

    PRD §8「可随时删除数据」的配套：删除前先导出留档。
    出生数据在 person（PersonOut），其余各表解密成明文 dict 列表。
    """

    person: PersonOut
    profile: dict | None = None
    conversations: list[dict] = []
    memory_items: list[dict] = []
    journal_entries: list[dict] = []
    life_events: list[dict] = []
    letters: list[dict] = []
    fragment_lights: list[dict] = []
    push_subscriptions: list[dict] = []
    related_persons: list[dict] = []
    exported_at: str


class RecallItem(BaseModel):
    """一条"我记得你"的记忆豆荚（确定性聚合，无 LLM）。

    kind 标识来源：
    - key_date         画像关键日期（"2025年夏天你考虑换工作"）
    - confirmed_finding  用户确认过的沉淀判断（"上次你确认过…"）
    - domain_summary   领域摘要（"关于感情我记得你说过…"）
    - top_fragment     点亮账本 top（"这格越走越亮"）
    - recent_topic     最近会话话题（"上次我们聊到…"）
    """

    kind: str
    label: str
    detail: str = ""
    at: str | None = None


class RecallOut(BaseModel):
    """记忆召回：确定性素材豆荚列表（无 LLM，硬线：LLM 只管"怎么疗愈"）。"""

    items: list[RecallItem]
    has_memory: bool


class DailyPushItemOut(BaseModel):
    level: int
    score: float | None = None
    house: int | None = None
    scene: str
    sender: str | None = None
    reason: str
    advice: str
    trigger_planet: str | None = None
    natal_planet: str | None = None
    aspect: str | None = None
    orb: float | None = None
    role: str | None = None
    confidence: float | None = None
    reason_chain: list[str] = []
    time_label: str = "全天背景"
    start_at: str | None = None
    end_at: str | None = None


class DailyPushOut(BaseModel):
    letter_date: str | None = None
    timezone_name: str | None = None
    summary: str
    items: list[DailyPushItemOut] = []
    disclaimer: str | None = None


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
    daily_push: DailyPushOut | None = None  # 当日日推：本地 0:00-24:00 聚合提醒（有几条推几条）


class MailboxTodayIn(BaseModel):
    person_id: str


class LetterPageOut(BaseModel):
    """信箱信件分页（20 条一页；kind 可选 daily/keepsake）。"""

    items: list[LetterOut]
    total: int
    page: int
    page_size: int
    has_more: bool


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
    # 记忆召回豆荚（"我记得你"素材；有内容才有，空用户为 None）
    recall: RecallOut | None = None


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


def _persistent_db_requires_key(config: AppConfig) -> None:
    """持久化库必须显式配置稳定密钥，避免生产误写随机密钥密文。"""
    if str(config.storage.db_path) == ":memory:":
        return
    if config.storage.encryption_key:
        return
    raise RuntimeError(
        f"持久化数据库 {config.storage.db_path} 缺少 {ENV_KEY_NAME}；"
        "拒绝使用随机开发密钥启动，请先在部署密钥或 .env 中配置稳定 Fernet key。"
    )


def create_app(config: AppConfig | None = None) -> FastAPI:
    config = config or _load_config()
    _persistent_db_requires_key(config)

    app = FastAPI(title=APP_NAME, version=APP_VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],      # PWA 开发期全放行；上线收紧
        allow_methods=["*"],
        allow_headers=["*"],
    )

    encryptor = Encryptor(key=config.storage.encryption_key)
    person_repo = PersonRepository(db_path=config.storage.db_path, encryptor=encryptor)
    store = GardenStore(db_path=config.storage.db_path, encryptor=encryptor)
    agent = GardenSpiritAgent(config)
    chart_cache = NatalChartCache(person_repo, agent._calculator)
    agent.set_chart_provider(chart_cache.get_or_compute)
    memory = MemoryService(store)
    journal = JournalService(store, summarizer=JournalSummarizer(agent._llm))
    letter = LetterService(
        store,
        llm_client=agent._llm,
        chart_provider=chart_cache.get_or_compute,
    )
    relationship = RelationshipService()  # A2 关系层：纯逻辑，无 io
    learning = LearningService(           # B1 学习层：验前事 → 置信度校准
        store,
        chart_provider=chart_cache.get_or_compute,
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
    app.state.chart_cache = chart_cache
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

    @app.post("/auth/phone/verify", response_model=AccountOut)
    def verify_phone(body: AuthVerifyIn) -> AccountOut:
        """手机号登录/注册：一号一本人档案，返回后端权威 self_person_id。"""
        _verify_dev_code(config, body.phone, body.code)
        account = store.upsert_phone_account(body.phone)
        return _to_account_out(account, person_repo)

    @app.get("/account/{account_id}", response_model=AccountOut)
    def get_account(account_id: str) -> AccountOut:
        account = store.get_phone_account(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="账号不存在，请先手机号登录")
        return _to_account_out(account, person_repo)

    @app.post("/account/{account_id}/self", response_model=AccountOut)
    def create_self_profile(account_id: str, body: PersonIn) -> AccountOut:
        """创建唯一本人档案；已有本人档案时幂等拒绝，避免 gs_person_id 覆盖。"""
        account = store.get_phone_account(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="账号不存在，请先手机号登录")
        if account.get("self_person_id"):
            raise HTTPException(status_code=409, detail="该手机号已有唯一本人档案，请使用档案修改")
        person = _to_person(body)
        person_repo.save(person)
        store.set_account_self_person(account_id, person.id)
        try:
            letter.get_or_create_daily(person)
        except Exception as exc:  # noqa: BLE001
            logger.warning("本人建档后生成今日来信失败，稍后由信箱入口兜底: %s", exc)
        account = store.get_phone_account(account_id)
        return _to_account_out(account or {}, person_repo)

    @app.put("/account/{account_id}/self", response_model=AccountOut)
    def update_self_profile(account_id: str, body: PersonIn) -> AccountOut:
        """修改本人档案：出生/宫制等影响解读，先清空旧业务数据再覆盖档案。"""
        account = store.get_phone_account(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="账号不存在，请先手机号登录")
        person_id = account.get("self_person_id") or ""
        if not person_id:
            raise HTTPException(status_code=404, detail="尚未创建本人档案")
        _get_person(person_id)
        person = _to_person(body)
        person.id = person_id
        store.reset_person_business_data(person_id)
        person_repo.save(person)
        try:
            letter.get_or_create_daily(person)
        except Exception as exc:  # noqa: BLE001
            logger.warning("本人档案更新后生成今日来信失败，稍后由信箱入口兜底: %s", exc)
        account = store.get_phone_account(account_id)
        return _to_account_out(account or {}, person_repo)

    @app.get("/account/{account_id}/profiles", response_model=list[ProfileListItemOut])
    def list_account_profiles(account_id: str) -> list[ProfileListItemOut]:
        """档案列表：本人唯一 + 合盘对象；合盘对象永不允许升为本人。"""
        account = store.get_phone_account(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="账号不存在，请先手机号登录")
        out: list[ProfileListItemOut] = []
        self_id = account.get("self_person_id") or ""
        if self_id:
            person = _get_person(self_id)
            out.append(ProfileListItemOut(
                id=person.id,
                role="self",
                name=person.name,
                can_be_self=True,
                created_at=_iso_str(person.created_at),
            ))
            out.extend(
                ProfileListItemOut(
                    id=d["id"],
                    role="related",
                    name=d["name"],
                    can_be_self=False,
                    created_at=d.get("created_at"),
                )
                for d in store.list_related_persons(self_id)
            )
        return out

    @app.post("/account/{account_id}/claim-xiatian", response_model=dict)
    def claim_xiatian_legacy_data(account_id: str) -> dict:
        """开发迁移：把夏天旧测试档案归并到 18513821306 的唯一本人档案。"""
        account = store.get_phone_account(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="账号不存在，请先手机号登录")
        if account.get("phone") != "18513821306":
            raise HTTPException(status_code=403, detail="旧数据认领仅限夏天测试账号")
        target_id = account.get("self_person_id") or ""
        if not target_id:
            raise HTTPException(status_code=404, detail="请先创建夏天的本人档案")
        _get_person(target_id)
        candidates = (
            "person_399bb64b9be44430",
            "person_da3c540ff05d4354",
            "person_d8624fb3de624942",
            "person_909e658438f54ac7",
        )
        merged: dict[str, dict[str, int]] = {}
        for old_id in candidates:
            if old_id == target_id or person_repo.get(old_id) is None:
                continue
            merged[old_id] = store.reassign_person_data(old_id, target_id)
        return {"target_person_id": target_id, "merged": merged}

    @app.post("/person", response_model=PersonOut)
    def create_person(body: PersonIn) -> PersonOut:
        person = _to_person(body)
        person_repo.save(person)
        try:
            # 产品规则：建档即生成当天来信；普通读信路径只幂等读取，不按版本自动刷新。
            letter.get_or_create_daily(person)
        except Exception as exc:  # noqa: BLE001 - 建档成功优先，来信失败可由 /mailbox/today 兜底补生成
            logger.warning("建档后生成今日来信失败，稍后由信箱入口兜底: %s", exc)
        return _to_person_out(person)

    @app.get("/person/{person_id}", response_model=PersonOut)
    def get_person(person_id: str) -> PersonOut:
        return _to_person_out(_get_person(person_id))

    @app.get("/person/{person_id}/export", response_model=PersonExportOut)
    def export_person(person_id: str) -> PersonExportOut:
        """合规数据导出：全量明文聚合（删除前存档 / 迁移备份 / 用户自取）。

        出生数据 + 画像 + 会话正文 + 原始消息 + 日记 + 人生事件 + 来信
        + 点亮账本 + 推送订阅 + 合盘对象（含出生数据）。
        """
        person = _get_person(person_id)
        data = store.export_person(person_id)
        return PersonExportOut(
            person=_to_person_out(person),
            profile=data.get("profile"),
            conversations=data.get("conversations", []),
            memory_items=data.get("memory_items", []),
            journal_entries=data.get("journal_entries", []),
            life_events=data.get("life_events", []),
            letters=data.get("letters", []),
            fragment_lights=data.get("fragment_lights", []),
            push_subscriptions=data.get("push_subscriptions", []),
            related_persons=data.get("related_persons", []),
            exported_at=_iso_str(datetime.now(timezone.utc)),
        )

    @app.delete("/person/{person_id}")
    def delete_person(person_id: str) -> dict:
        """合规全量删除（PRD §8「可随时删除数据」）。

        先清空 9 张业务表（store.purge_person 级联），再删 persons 表。
        不可逆操作：前端应先走 GET /export 存档并二次确认。
        """
        _get_person(person_id)  # 存在性校验（缺失 → 404）
        store.purge_person(person_id)
        person_repo.delete(person_id)
        return {"deleted": person_id}

    @app.get("/person/{person_id}/recall", response_model=RecallOut)
    def get_recall(person_id: str, persona: str | None = Query(None)) -> RecallOut:
        """记忆召回："我记得你"素材豆荚（确定性聚合，无 LLM）。

        画像关键日期 + 用户确认的判断 + 领域摘要 + 点亮账本 top + 最近话题。
        前端可做"记忆卡片"；开场白也从这里取一句（见 /opening）。
        persona：记忆镜头（同一份记忆，十种读法）——土星先讲事业摘要、月亮先讲
        情绪关键日期…；缺省 → 默认顺序。
        """
        _get_person(person_id)
        items = _build_recall_items(store.get_recall_data(person_id), persona=_resolve_persona(persona))
        return RecallOut(items=items, has_memory=bool(items))

    # ------------------------------------------------------------------
    # 合盘对象（related_person）：对方出生数据持久化，多轮合盘不再断链
    # ------------------------------------------------------------------

    @app.post("/person/{person_id}/related", response_model=RelatedPersonOut)
    def save_related_person(person_id: str, body: RelatedPersonIn) -> RelatedPersonOut:
        """保存一个合盘对象（对方出生数据，Fernet 加密落库）。

        前端流程：用户在聊天收到 needs_related_person=True → 弹出对方出生表单 →
        本端点保存 → 返回 id → 下次 /chat 带 related_person_id 走合盘。
        """
        _get_person(person_id)  # 校验所有者存在
        location = _resolve_location(body.birth.location)
        birth = _to_birth_data(body.birth, location)
        related_id = new_id("rel")
        store.save_related_person(
            related_id,
            person_id,
            body.name,
            _birth_to_json(birth),
            gender=body.gender or "",
            notes=body.notes,
        )
        return RelatedPersonOut(
            id=related_id,
            person_id=person_id,
            name=body.name,
            created_at=_iso_str(datetime.now(timezone.utc)),
        )

    @app.get("/person/{person_id}/related", response_model=list[RelatedPersonOut])
    def list_related_persons(person_id: str) -> list[RelatedPersonOut]:
        """列出该用户保存的合盘对象（只含名字——列表视图不暴露出生数据）。"""
        _get_person(person_id)
        return [
            RelatedPersonOut(
                id=d["id"],
                person_id=d["person_id"],
                name=d["name"],
                created_at=d.get("created_at"),
            )
            for d in store.list_related_persons(person_id)
        ]

    @app.get("/person/{person_id}/related/{related_id}", response_model=RelatedPersonDetailOut)
    def get_related_person_detail(person_id: str, related_id: str) -> RelatedPersonDetailOut:
        """读取一个合盘对象详情（编辑页回显出生数据/备注）。"""
        _get_person(person_id)
        data = store.get_related_person(related_id)
        if data is None or data["person_id"] != person_id:
            raise HTTPException(status_code=404, detail="合盘对象不存在")
        return _to_related_detail_out(data)

    @app.put("/person/{person_id}/related/{related_id}", response_model=RelatedPersonDetailOut)
    def update_related_person(person_id: str, related_id: str, body: RelatedPersonIn) -> RelatedPersonDetailOut:
        """修改合盘对象；仍只属于 owner，不能变成本人档案。"""
        _get_person(person_id)
        location = _resolve_location(body.birth.location)
        birth = _to_birth_data(body.birth, location)
        ok = store.update_related_person(
            related_id,
            person_id,
            body.name,
            _birth_to_json(birth),
            gender=body.gender or "",
            notes=body.notes,
        )
        if not ok:
            raise HTTPException(status_code=404, detail="合盘对象不存在")
        data = store.get_related_person(related_id)
        if data is None or data["person_id"] != person_id:
            raise HTTPException(status_code=404, detail="合盘对象不存在")
        return _to_related_detail_out(data)

    @app.delete("/person/{person_id}/related/{related_id}")
    def delete_related_person(person_id: str, related_id: str) -> dict:
        """删除一个合盘对象（合规：用户可随时删除自己的数据）。

        校验归属：只能删属于自己的对象，删除不存在/他人对象 → 404。
        """
        data = store.get_related_person(related_id)
        if data is None or data["person_id"] != person_id:
            raise HTTPException(status_code=404, detail="合盘对象不存在")
        store.delete_related_person(related_id)
        return {"deleted": related_id}

    # ------------------------------------------------------------------
    # 星灵推荐引擎：今天该见哪颗星（三轴评分，Domain 无 LLM）
    # ------------------------------------------------------------------

    @app.get(
        "/person/{person_id}/recommended-spirits",
        response_model=RecommendedSpiritsOut,
    )
    def recommended_spirits(person_id: str) -> RecommendedSpiritsOut:
        """今日星灵推荐：行运活跃 0.5 + 近期共振 0.3 + 长期课题 0.2（未实现并入前两轴）。

        首页素材：按综合分降序出 10 颗，前端取 top3；月亮永远兜底（is_default）。
        理由可解释（"行运土星合你本命太阳"）——硬线：结论全由 Domain 出。
        """
        person = _get_person(person_id)
        profile = _get_or_init_profile(store, person_id)  # 无画像 → 空碎片，纯行运分
        natal = chart_cache.get_or_compute(person)
        target = datetime.now(timezone.utc)
        lat = person.birth.location.latitude
        lon = person.birth.location.longitude
        hs = person.house_system or HouseSystem.ALCABITIUS
        scores = score_spirits(
            natal, target, lat, lon, hs,
            fragment_depths=dict(profile.fragments or {}),
        )
        spirits = []
        for s in scores:
            persona = get_persona(s.planet.value)  # 人格映射（疗愈名/口吻在 Application 层）
            spirits.append(
                SpiritRecommendationOut(
                    planet=s.planet.value,
                    name=persona.name,
                    healing_name=persona.healing_name,
                    style=persona.style,
                    score=s.score,
                    reason="；".join(s.reason_parts) if s.reason_parts else "今日暂无明显行运触动",
                    is_default=(s.planet == Planet.MOON),
                    is_firdaria_major_lord=s.is_firdaria_major_lord,
                    is_firdaria_sub_lord=s.is_firdaria_sub_lord,
                )
            )
        return RecommendedSpiritsOut(
            spirits=spirits,
            generated_at=_iso_str(target),
        )

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

    @app.get("/person/{person_id}/journal", response_model=JournalPageOut)
    def list_journal(
        person_id: str,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
    ) -> JournalPageOut:
        """手账分页列表（20 条一页）。"""
        _get_person(person_id)
        items, total = journal.list(person_id, page=page, page_size=page_size)
        return JournalPageOut(
            items=[_to_journal_out(e) for e in items],
            total=total,
            page=page,
            page_size=page_size,
            has_more=page * page_size < total,
        )

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

    @app.post("/mailbox/today/force-refresh", response_model=LetterOut)
    def mailbox_today_force_refresh(body: MailboxTodayIn) -> LetterOut:
        """开发/管理员工具：显式重算今天的 daily 来信；普通用户路径不会自动刷新。"""
        if not config.debug:
            raise HTTPException(status_code=403, detail="force refresh 仅在 debug/admin 模式开放")
        person = _get_person(body.person_id)
        return _to_letter_out(letter.force_refresh_daily(person))

    @app.get("/person/{person_id}/letters", response_model=LetterPageOut)
    def list_letters(
        person_id: str,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        kind: str | None = Query(None),
    ) -> LetterPageOut:
        """信箱信件分页（20 条一页）。kind=daily 取日推历史 / kind=keepsake 取记忆来信；默认全部。"""
        _get_person(person_id)
        kind_val = kind if kind in ("daily", "keepsake") else None
        items, total = letter.list(person_id, kind=kind_val, page=page, page_size=page_size)
        return LetterPageOut(
            items=[_to_letter_out(l) for l in items],
            total=total,
            page=page,
            page_size=page_size,
            has_more=page * page_size < total,
        )

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
    def garden(person_id: str = Query(...), persona: str | None = Query(None)) -> GardenState:
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
        # 记忆召回豆荚（"我记得你"；空用户不吐空壳，前端少一个空态判断）
        recall_items = _build_recall_items(store.get_recall_data(person_id), persona=_resolve_persona(persona))
        recall = (
            RecallOut(items=recall_items, has_memory=True)
            if recall_items else None
        )
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
            recall=recall,
        )

    @app.get("/person/{person_id}/opening", response_model=OpeningOut)
    def get_opening(person_id: str, persona: str | None = Query(None)) -> OpeningOut:
        """进入花园的开场白：首次见面自我介绍 / 老用户欢迎回来。

        persona：记忆镜头——同一份记忆，土星用"你扛着的…还守得住吗"开场、
        月亮用"现在心里还沉吗"开场…；缺省 → 默认话术。
        """
        person = _get_person(person_id)
        profile = store.get_profile(person_id)
        recent = store.list_conversation_summaries(person_id, limit=1)
        p = _resolve_persona(persona)
        recall = _recall_for_opening(store.get_recall_data(person_id), persona=p)
        opening = relationship.opening_message(
            profile, person_name=person.name, continue_from=recent[0] if recent else None,
            recall=recall, persona=p,
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

    @app.get("/personas", response_model=list[PersonaOut])
    def list_personas() -> list[PersonaOut]:
        """前端星灵选择器：暴露 10 颗行星人格，不含推理结论。"""
        return [
            PersonaOut(
                key=p.key.value,
                name=p.name,
                healing_name=p.healing_name,
                style=p.style,
                tone=p.tone,
                vocabulary=list(p.vocabulary),
            )
            for p in all_personas()
        ]

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
            push_title = letter_obj.title or "星灵来信"
            push_body = _daily_push_body(letter_obj)
            n = push_service.send_to_person(
                person.id,
                title=push_title,
                body=push_body,
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

    @app.get("/person/{person_id}/life-rhythm", response_model=LifeRhythmOut)
    def get_life_rhythm(
        person_id: str,
        months: int = Query(default=6, ge=1, le=6),
    ) -> LifeRhythmOut:
        """Life Rhythm 报告地基：本命承诺 + 法达章节 + 小限年度 + 行运触发。

        这是报告型出口，不替代 /timeline 的成长事件列表。所有占星素材均由 Domain
        确定性生成；前端只渲染，不自行判断宫位、行星、吉凶或时机权威。
        """
        person = _get_person(person_id)
        chart = chart_cache.get_or_compute(person)
        rhythm = build_life_rhythm(
            person,
            chart,
            agent._calculator.kb,
            months=months,
        )
        return LifeRhythmOut(**rhythm.to_dict())

    @app.post("/person/{person_id}/reports/compile", response_model=ReportOut)
    def compile_report(person_id: str, body: ReportCompileInput) -> ReportOut:
        """Report Compiler MVP：把后端已有素材整理成草稿，不新造占星结论。"""
        person = _get_person(person_id)
        try:
            return _compile_report_draft(
                person=person,
                body=body,
                store=store,
                chart_provider=chart_cache.get_or_compute,
                kb=agent._calculator.kb,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

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
        # 10 星灵回归：非法/旧宝石人格名（zircon/rose_quartz…）→ 偏好 → 默认（月亮），不 500
        persona = _resolve_chat_persona(body.persona, store, action, body.person_id)
        mode = _parse_mode(body.mode)

        # 用户指定合盘对象 → 从 DB 恢复到会话上下文（多轮持久化）
        _restore_related_person(store, agent, session_id, body.person_id, body.related_person_id, person)

        answer = agent.handle_message(
            session_id,
            body.message,
            person,
            persona,
            mode=mode,
            report_intent=body.report_intent.model_dump() if body.report_intent else None,
        )

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


def _daily_push_body(letter_obj: Letter) -> str:
    """每日 push 优先推当日日推主提醒；没有则退回旧单条提醒/正文摘要。"""
    meta = letter_obj.metadata or {}
    daily_push = meta.get("daily_push")
    if isinstance(daily_push, dict):
        summary = str(daily_push.get("summary") or "").strip()
        items = daily_push.get("items")
        if summary:
            suffix = "，点开看今天只记三件事" if isinstance(items, list) and items else ""
            return f"{summary}{suffix}".replace("\n", " ")[:80]

    reminder = meta.get("daily_reminder")
    if isinstance(reminder, dict):
        reason = str(reminder.get("reason") or "").strip()
        advice = str(reminder.get("advice") or "").strip()
        text = f"{reason}{advice}".strip()
        if text:
            return text.replace("\n", " ")[:110]
    return (letter_obj.body or "").replace("\n", " ")[:80]


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


def _resolve_chat_persona(raw: str | None, store, action, person_id: str) -> PersonaType | None:
    """聊天人格安全解析：显式选择优先，其次用户偏好，最后交给 Agent 默认。"""
    for candidate in (raw, action.preferences(store.get_profile(person_id)).get("preferred_persona")):
        if not candidate:
            continue
        try:
            return PersonaType(str(candidate))
        except ValueError:
            continue
    return None


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
    birth = _to_birth_data(body.birth, location)

    try:
        house_system = HouseSystem(body.house_system) if body.house_system else HouseSystem.ALCABITIUS
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"不支持的宫位制: {body.house_system}") from exc

    return Person(
        id=body.id or new_id("person"),
        name=body.name,
        birth=birth,
        gender=body.gender,
        notes=body.notes,
        house_system=house_system,
    )


def _to_birth_data(birth_in: BirthIn, location: GeoLocation):
    """BirthIn + 已解析 GeoLocation → BirthData（墙钟→UTC + 正午降级）。

    建档与保存合盘对象共用同一套出生时间换算逻辑（避免两处漂移）。
    """
    try:
        dt_local = datetime.fromisoformat(birth_in.datetime_local)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"出生时间格式错误: {birth_in.datetime_local}"
        ) from exc

    if dt_local.tzinfo is None:
        dt_local = dt_local.replace(tzinfo=ZoneInfo(location.timezone_name))
    dt_utc = dt_local.astimezone(timezone.utc)
    return birth_data_fallback(dt_utc, location, birth_in.time_known)


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


def _birth_out(birth) -> BirthOut:
    local_dt = birth.datetime_utc.astimezone(ZoneInfo(birth.location.timezone_name))
    return BirthOut(
        datetime_local=local_dt.replace(tzinfo=None).isoformat(timespec="seconds"),
        location=GeoIn(
            latitude=birth.location.latitude,
            longitude=birth.location.longitude,
            altitude=birth.location.altitude,
            timezone_name=birth.location.timezone_name,
            place_name=birth.location.place_name,
        ),
        time_known=birth.time_known,
    )


def _to_self_profile_out(p: Person) -> SelfProfileOut:
    base = _to_person_out(p)
    return SelfProfileOut(
        **base.model_dump(),
        birth=_birth_out(p.birth),
        notes=p.notes,
    )


def _to_account_out(account: dict, person_repo: PersonRepository) -> AccountOut:
    self_id = account.get("self_person_id") or ""
    self_profile = None
    if self_id:
        person = person_repo.get(self_id)
        if person is not None:
            self_profile = _to_self_profile_out(person)
    return AccountOut(
        account_id=account.get("id", ""),
        phone=account.get("phone", ""),
        self_person_id=self_profile.id if self_profile is not None else None,
        self_profile=self_profile,
    )


def _to_related_detail_out(data: dict) -> RelatedPersonDetailOut:
    birth = data["birth_data"]
    return RelatedPersonDetailOut(
        id=data["id"],
        person_id=data["person_id"],
        name=data["name"],
        birth=_birth_out(birth),
        gender=data.get("gender") or None,
        notes=data.get("notes", ""),
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
    )


def _verify_dev_code(config: AppConfig, phone: str, code: str) -> None:
    """开发期验证码门：临时允许任意手机号用 000000 验证注册。"""
    normalized = "".join(ch for ch in str(phone) if ch.isdigit())
    if config.debug and normalized and code == "000000":
        return
    raise HTTPException(status_code=403, detail="验证码错误或当前环境未开放开发白名单")


def _restore_related_person(
    store: GardenStore,
    agent,
    session_id: str,
    person_id: str,
    related_person_id: str | None,
    person: Person,
) -> None:
    """每次 /chat 开头调用：把用户指定的合盘对象从 DB 恢复到会话上下文。

    related_person_id 为空 → 跳过（无合盘意图）。不存在 / 不属于该用户 → 静默跳过
    （不 500；对话走普通路径）。恢复成功 → agent.set_related_person() 注入内存会话。
    会话上下文可能还没建（handle_message 里才建），用盘主 person 预建。
    """
    if not related_person_id:
        return
    data = store.get_related_person(related_person_id)
    if data is None or data["person_id"] != person_id:
        return  # 安全：不允许跨用户访问他人合盘对象
    birth = data["birth_data"]
    partner = Person(
        id=data["id"],
        name=data["name"],
        birth=birth,
        gender=None,
        notes="",
    )
    agent.set_related_person(session_id, partner, person=person)


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


def _compile_report_draft(
    *,
    person: Person,
    body: ReportCompileInput,
    store: GardenStore,
    chart_provider,
    kb,
) -> ReportOut:
    """Report Compiler MVP：聚合后端已有素材；无证据不成段。"""
    sections: list[ReportSectionOut] = []
    topic = _report_topic(body)

    if body.report_type == "life_rhythm":
        chart = chart_provider(person)
        rhythm = build_life_rhythm(person, chart, kb, months=body.months).to_dict()
        life_ref = _report_ref(
            "life_rhythm",
            f"{person.id}:{rhythm.get('chart_id', 'chart')}:{body.months}m",
            "Life Rhythm 后端四层素材",
        )
        sections.extend(_life_rhythm_report_sections(rhythm, life_ref))
    else:
        profile = store.get_profile(person.id)
        if profile is not None:
            _append_profile_report_sections(sections, profile)

        conversation = store.get_conversation(body.session_id) if body.session_id else None
        if conversation is not None and conversation.person_id != person.id:
            conversation = None
        conversations = [conversation] if conversation is not None else store.list_conversations(person.id)[:3]
        _append_conversation_report_section(sections, conversations, body.session_id)

        memories = store.list_memory_items(
            person_id=person.id,
            session_id=body.session_id,
            limit=8,
        )
        _append_memory_report_section(sections, memories)

        events = store.list_life_events(person.id, limit=5)
        _append_timeline_report_section(sections, events)

        lights = store.list_fragment_lights(person.id, session_id=body.session_id, limit=8)
        _append_fragment_light_report_section(sections, lights, body.session_id or person.id)

        letters = store.list_letters(person.id, limit=3)
        _append_letter_report_section(sections, letters)

    if not sections:
        raise ValueError("暂无足够素材生成报告草稿")

    source_refs = _dedupe_report_refs(ref for s in sections for ref in s.source_refs)
    return ReportOut(
        id=new_id("report"),
        report_type=body.report_type,
        person_id=person.id,
        title=_report_title(body.report_type, topic),
        summary=f"已整理 {len(sections)} 个板块；每段都只引用后端已有素材，不新造占星结论。",
        generated_at=utc_now_aware().isoformat(),
        sections=sections,
        source_refs=source_refs,
    )


def _report_topic(body: ReportCompileInput) -> str:
    if body.topic and body.topic.strip():
        return body.topic.strip()
    if body.report_intent:
        for candidate in (body.report_intent.primary_topic, body.report_intent.entry_topic_key):
            if candidate and candidate.strip():
                return candidate.strip()
    return "这段对话"


def _report_title(report_type: str, topic: str) -> str:
    if report_type == "life_rhythm":
        return "人生章节报告草稿"
    if report_type == "theme":
        return f"「{topic}」主题报告草稿"
    return f"「{topic}」小报告草稿"


def _report_ref(source_type: ReportSourceType, source_id: str, label: str = "") -> ReportSourceRefOut:
    return ReportSourceRefOut(type=source_type, id=source_id, label=label)


def _dedupe_report_refs(refs) -> list[ReportSourceRefOut]:
    seen: set[tuple[str, str]] = set()
    out: list[ReportSourceRefOut] = []
    for ref in refs:
        key = (ref.type, ref.id)
        if key in seen:
            continue
        seen.add(key)
        out.append(ref)
    return out


def _clean_report_text(value: Any, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _append_profile_report_sections(sections: list[ReportSectionOut], profile: ChartProfile) -> None:
    summaries = [s for s in profile.domain_summaries.values() if _clean_report_text(s.summary)]
    if summaries:
        lines = [
            f"- {s.domain or '未分类'}：{_clean_report_text(s.summary, 220)}"
            for s in sorted(summaries, key=lambda item: item.confidence, reverse=True)[:4]
        ]
        sections.append(ReportSectionOut(
            key="profile_summaries",
            title="长期画像摘要",
            body="\n".join(lines),
            source_refs=[_report_ref("profile", profile.person_id, "长期画像")],
        ))

    findings = [f for f in profile.verified_findings if _clean_report_text(f.statement)]
    if findings:
        lines = [
            f"- {_clean_report_text(f.statement, 220)}（把握 {f.confidence:.0%}）"
            for f in sorted(findings, key=lambda item: item.confidence, reverse=True)[:5]
        ]
        sections.append(ReportSectionOut(
            key="verified_findings",
            title="已沉淀判断",
            body="\n".join(lines),
            source_refs=[_report_ref("finding", f.id, f.domain or "沉淀判断") for f in findings[:5]],
        ))


def _append_conversation_report_section(sections: list[ReportSectionOut], conversations, session_id: str | None) -> None:
    lines: list[str] = []
    refs: list[ReportSourceRefOut] = []
    for conv in conversations:
        if conv is None:
            continue
        refs.append(_report_ref("conversation", conv.id, "对话会话"))
        for turn in conv.turns[-3:]:
            user_text = _clean_report_text(turn.user_message, 140)
            if user_text:
                lines.append(f"- 用户提到：{user_text}")
            assistant_text = _clean_report_text(turn.assistant_response, 140)
            if assistant_text:
                lines.append(f"  星灵回应：{assistant_text}")
    if lines and refs:
        title = "本次对话整理" if session_id else "近期对话整理"
        sections.append(ReportSectionOut(
            key="conversation_digest",
            title=title,
            body="\n".join(lines[:10]),
            source_refs=_dedupe_report_refs(refs),
        ))


def _append_memory_report_section(sections: list[ReportSectionOut], memories) -> None:
    lines: list[str] = []
    refs: list[ReportSourceRefOut] = []
    for item in memories[:8]:
        text = _clean_report_text(item.content, 180)
        if not text:
            continue
        lines.append(f"- {item.role.value}：{text}")
        refs.append(_report_ref("memory", item.id, "记忆条目"))
    if lines and refs:
        sections.append(ReportSectionOut(
            key="memory_clues",
            title="记忆线索",
            body="\n".join(lines),
            source_refs=refs,
        ))


def _append_timeline_report_section(sections: list[ReportSectionOut], events) -> None:
    lines: list[str] = []
    refs: list[ReportSourceRefOut] = []
    for event in events[:5]:
        label = _clean_report_text(event.label, 120)
        if not label:
            continue
        when = event.occurred_at.date().isoformat() if event.occurred_at else "未定日期"
        detail = _clean_report_text(event.detail, 120)
        tail = f"｜{detail}" if detail else ""
        lines.append(f"- {when}｜{event.kind or 'life'}｜{label}{tail}")
        refs.append(_report_ref("timeline", event.id, event.domain or event.kind or "时间线"))
    if lines and refs:
        sections.append(ReportSectionOut(
            key="timeline_context",
            title="时间线素材",
            body="\n".join(lines),
            source_refs=refs,
        ))


def _append_fragment_light_report_section(sections: list[ReportSectionOut], lights, fallback_id: str) -> None:
    lines: list[str] = []
    refs: list[ReportSourceRefOut] = []
    for light in lights[:8]:
        name = FragmentService.name_for(light.subtype_id) or light.subtype_id
        when = light.lit_at.isoformat() if light.lit_at else ""
        source = _clean_report_text(light.source, 100)
        tail = f"｜摘录：{source}" if source else ""
        lines.append(f"- {name} +{light.delta}（{light.kind}）{tail}")
        refs.append(_report_ref(
            "fragment_light",
            f"{fallback_id}:{light.subtype_id}:{when}",
            name,
        ))
    if lines and refs:
        sections.append(ReportSectionOut(
            key="fragment_lights",
            title="被点亮的内在角落",
            body="\n".join(lines),
            source_refs=refs,
        ))


def _append_letter_report_section(sections: list[ReportSectionOut], letters) -> None:
    lines: list[str] = []
    refs: list[ReportSourceRefOut] = []
    for letter in letters[:3]:
        title = _clean_report_text(letter.title or "星灵来信", 100)
        body = _clean_report_text(letter.body, 180)
        if not body and not title:
            continue
        lines.append(f"- {letter.letter_date}｜{letter.kind}｜{title}：{body}")
        refs.append(_report_ref("letter", letter.id, letter.kind or "来信"))
    if lines and refs:
        sections.append(ReportSectionOut(
            key="letters",
            title="信箱素材",
            body="\n".join(lines),
            source_refs=refs,
        ))


def _life_rhythm_report_sections(rhythm: dict[str, Any], life_ref: ReportSourceRefOut) -> list[ReportSectionOut]:
    sections: list[ReportSectionOut] = []
    chapter = rhythm.get("firdaria_chapter") or {}
    period = chapter.get("period") or {}
    annual = rhythm.get("annual_activation") or {}
    triggers = rhythm.get("transit_triggers") or []
    source_layers = ", ".join(rhythm.get("source_layers") or [])

    sections.append(ReportSectionOut(
        key="life_rhythm_authority",
        title="报告权威边界",
        body=(
            f"本报告引用后端 Life Rhythm 四层素材：{source_layers or '本命承诺、法达章节、年度辅助、行运触发'}。"
            "法达是主章节；annual_activation 只作年度辅助；行运只作触发窗口。"
        ),
        source_refs=[life_ref],
    ))
    sections.append(ReportSectionOut(
        key="firdaria_chapter",
        title="当前法达章节",
        body=(
            f"大限主星：{period.get('major_lord', '')}（{period.get('major_start', '')} → {period.get('major_end', '')}）；"
            f"子限主星：{period.get('sub_lord', '')}（{period.get('sub_start', '')} → {period.get('sub_end', '')}）。"
        ),
        source_refs=[life_ref],
    ))
    sections.append(ReportSectionOut(
        key="annual_activation",
        title="年度辅助层",
        body=(
            f"{annual.get('age', '')} 岁年度点亮第 {annual.get('activation_house', '')} 宫；"
            f"activation_lord={annual.get('activation_lord') or '未定'}。此层只辅助解释年度场景，不替代法达时机权威。"
        ),
        source_refs=[life_ref],
    ))
    if triggers:
        lines = []
        for item in triggers[:6]:
            targets = ", ".join(item.get("target_planets") or []) or "目标点待定"
            lines.append(f"- {item.get('month', '')}｜{item.get('tag', '')}｜触发对象：{targets}")
        sections.append(ReportSectionOut(
            key="transit_triggers",
            title="未来触发窗口",
            body="\n".join(lines),
            source_refs=[life_ref],
        ))
    return sections


def _resolve_persona(raw: str | None):
    """查询参数 → PersonaProfile。None/空 → None（默认镜头）；未知字符串 → 月亮兜底。"""
    if not raw:
        return None
    return get_persona(raw)


def _build_recall_items(data: dict, persona=None) -> list[RecallItem]:
    """store.get_recall_data 的明文豆荚 → RecallItem 列表（确定性，无 LLM）。

    persona 提供"记忆镜头"（recall_priority/recall_domains）：同一份记忆，每颗星
    按自己擅长的读法重排（如土星先讲事业领域摘要、月亮先讲情绪关键日期）。
    None → 默认顺序（key_date 起），行为与旧版完全一致。
    """
    key_dates = [
        RecallItem(kind="key_date", label=(k.get("label") or "")[:80], at=k.get("at"))
        for k in data.get("key_dates", [])[:5]
        if (k.get("label") or "").strip()
    ]
    findings = [
        RecallItem(kind="confirmed_finding", label=(f.get("statement") or "")[:120], at=f.get("at"))
        for f in data.get("confirmed_findings", [])[:3]
        if (f.get("statement") or "").strip()
    ]
    # domain_summaries 已按 confidence 降序排好；镜头把擅长领域提前（组内保序）
    preferred = set(getattr(persona, "recall_domains", ()) or ())
    summaries = list(data.get("domain_summaries", []))[:3]
    if preferred:
        summaries = (
            [s for s in summaries if s.get("domain") in preferred]
            + [s for s in summaries if s.get("domain") not in preferred]
        )
    domain_items = [
        RecallItem(kind="domain_summary", label=(s.get("summary") or "")[:120], detail=s.get("domain", ""))
        for s in summaries
        if (s.get("summary") or "").strip()
    ]
    top_items = []
    for frag in data.get("top_fragments", [])[:3]:
        name = FragmentService.name_for(frag.get("subtype_id", ""))
        depth = int(frag.get("depth", 0) or 0)
        if name and depth > 0:
            top_items.append(RecallItem(
                kind="top_fragment",
                label=f"「{name}」这格越走越亮",
                detail=f"深度 {depth}",
            ))
    topic_items = []
    for t in data.get("recent_topics", [])[:3]:
        topic = naturalize_recall(t.get("summary"))
        if topic:
            topic_items.append(RecallItem(kind="recent_topic", label=topic, at=t.get("started_at")))

    groups = {
        "key_date": key_dates,
        "confirmed_finding": findings,
        "domain_summary": domain_items,
        "top_fragment": top_items,
        "recent_topic": topic_items,
    }
    default_order = ("key_date", "confirmed_finding", "domain_summary", "top_fragment", "recent_topic")
    priority = tuple(getattr(persona, "recall_priority", ()) or ())
    order = list(priority) + [k for k in default_order if k not in priority]

    items: list[RecallItem] = []
    for kind in order:
        items.extend(groups.get(kind, []))
    return items


def _recall_for_opening(data: dict, persona=None) -> dict | None:
    """开场白用精简记忆豆荚。默认优先级 confirmed > key_date > domain_summary。

    persona 的 recall_priority 可重排（如土星先讲领域摘要）；recall_domains 把
    擅长领域摘要提前。不含 recent_topic——它已由 continue_from 的"上次我们聊到"
    承担，避免重复。全空 → None（完全兼容无召回行为）。
    """
    items = data or {}
    preferred = set(getattr(persona, "recall_domains", ()) or ())
    summaries = list(items.get("domain_summaries", []))
    if preferred:
        summaries = (
            [s for s in summaries if s.get("domain") in preferred]
            + [s for s in summaries if s.get("domain") not in preferred]
        )
    recall = {
        "confirmed_findings": [
            {"statement": (f.get("statement") or "")[:120]}
            for f in items.get("confirmed_findings", [])
        ],
        "key_dates": [
            {"label": (k.get("label") or "")[:80]} for k in items.get("key_dates", [])
        ],
        "domain_summaries": [
            {"domain": s.get("domain", ""), "summary": (s.get("summary") or "")[:120]}
            for s in summaries
        ],
    }
    if not any(v for v in recall.values()):
        return None
    return recall


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
        daily_push=_daily_push_out(meta.get("daily_push")),
    )


def _daily_push_out(raw: object) -> DailyPushOut | None:
    if not isinstance(raw, dict):
        return None
    items: list[DailyPushItemOut] = []
    for item in raw.get("items") or []:
        if not isinstance(item, dict):
            continue
        try:
            items.append(DailyPushItemOut(**item))
        except Exception:
            continue
    return DailyPushOut(
        letter_date=raw.get("letter_date"),
        timezone_name=raw.get("timezone_name"),
        summary=str(raw.get("summary") or "今日星灵日推"),
        items=items,
        disclaimer=raw.get("disclaimer"),
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
