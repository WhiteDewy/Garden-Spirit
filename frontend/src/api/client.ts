/**
 * 星灵花园 API 客户端 —— 与后端 FastAPI 的薄契约层。
 *
 * 铁律：前端只消费 JSON，不含任何占星逻辑（冻结架构原则一/二）。
 * 换端（H5/小程序/App）时这个文件不变，变的只是 BASE_URL。
 */

/**
 * 后端地址：由构建环境注入（.env 的 VITE_API_BASE），不写死。
 * 开发默认本地；生产必须配置实际域名。
 */
const BASE_URL: string =
  (import.meta as any).env?.VITE_API_BASE || "http://127.0.0.1:8756";

export interface GeoIn {
  // 主路径：只填 place_name（城市名），后端 geocode 解析经纬度 + 时区
  place_name?: string;
  // 精确路径：经纬度成对 + timezone_name
  latitude?: number;
  longitude?: number;
  altitude?: number;
  timezone_name?: string;
}

export interface BirthIn {
  // 出生地本地墙钟时间（不含时区），后端按解析出的出生地时区换算 UTC
  datetime_local: string;
  location: GeoIn;
  time_known?: boolean;
}

export interface PersonIn {
  id?: string;
  name: string;
  birth: BirthIn;
  gender?: string;
  notes?: string;
  house_system?: string;
}

export interface PersonOut {
  id: string;
  name: string;
  gender: string | null;
  place_name: string;
  time_known: boolean;
  house_system: string | null;
  is_premium: boolean;
  created_at?: string | null;
}

export interface AuthVerifyIn {
  phone: string;
  code: string;
}

export interface BirthOut {
  datetime_local: string;
  location: GeoIn;
  time_known: boolean;
}

export interface SelfProfileOut extends PersonOut {
  birth: BirthOut;
  notes: string;
}

export interface AccountOut {
  account_id: string;
  phone: string;
  self_person_id: string | null;
  self_profile: SelfProfileOut | null;
}

export interface ProfileListItemOut {
  id: string;
  role: "self" | "related" | string;
  name: string;
  can_be_self: boolean;
  created_at?: string | null;
}

export interface RelatedPersonIn {
  name: string;
  birth: BirthIn;
  gender?: string;
  notes?: string;
}

export interface RelatedPersonOut {
  id: string;
  person_id: string;
  name: string;
  created_at?: string | null;
}

export interface RelatedPersonDetailOut extends RelatedPersonOut {
  birth: BirthOut;
  gender?: string | null;
  notes: string;
  updated_at?: string | null;
}

export type ReportIntentShape =
  | "single_topic"
  | "cross_topic_influence"
  | "topic_switch_suggested"
  | "clarification_required"
  | "unsupported";

export type ReportType = "monthly" | "annual" | "life_rhythm" | "theme";

export interface ReportIntentIn {
  // 主题观星台入口上下文；只作为后端意图路由/澄清素材，不承载占星结论。
  entry_source: "observatory";
  entry_topic_key: string;
  primary_topic?: string;
  secondary_topics?: string[];
  intent_shape?: ReportIntentShape;
  report_type?: ReportType;
  user_focus_text?: string;
}

export interface ChatIn {
  person_id: string;
  session_id?: string;
  message: string;
  persona?: string;
  mode?: "quick" | "deep" | "annual" | "chart" | "free";
  related_person_id?: string;
  report_intent?: ReportIntentIn;
}

export interface ChatOut {
  answer: string;
  session_id: string;
  intent_domain: string | null;
  needs_related_person: boolean;
  written_back: boolean;
  trust_level: string;
  // 情绪感知层：本条消息的情绪 × 诉求（陪伴协议第 1 步）
  emotion: string | null;
  request_type: string | null;
  // 34 子类点亮（§2）：本条随聊点亮了哪些子类
  lit_fragments: string[];
  // 被照见（§4.2 +5）：本条确认上一轮镜映 → 补亮的子类
  seen_fragments?: string[];
  // 来信式日记（§6.1）：本条倾诉是否生成了一封 keepsake 来信
  keepsake_created?: boolean;
  // 触发行动（§4.2 +20）：本条是"我真的去做了"行动回报 → 上一段会话点亮的子类 +20
  actioned_fragments?: string[];
}

export interface OpeningOut {
  opening: string;
  trust_level: string;
}

export interface SpiritRecommendationOut {
  planet: string;
  name: string;
  healing_name?: string;
  style?: string;
  score: number;
  reason: string;
  is_default?: boolean;
  is_firdaria_major_lord?: boolean;
  is_firdaria_sub_lord?: boolean;
}

export interface RecommendedSpiritsOut {
  spirits: SpiritRecommendationOut[];
  generated_at?: string;
}

export interface PersonaOut {
  key: string;
  name: string;
  healing_name?: string;
  style?: string;
  tone?: string;
  vocabulary?: string[];
}

export interface PreferencesOut {
  preferred_persona?: string;
  [key: string]: any;
}

export interface GardenRecallItem {
  kind: string;
  title?: string;
  summary?: string;
  text?: string;
  domain?: string;
}

export interface GardenRecallOut {
  has_memory: boolean;
  items: GardenRecallItem[];
}

export interface FindingOut {
  id: string;
  statement: string;
  domain: string;
  confidence: number;
  status: "unverified" | "verified";
  feedback: string;
  event_verified: boolean;
  verification_notes: string[];
  confirmed_at?: string;
}

export interface DomainSummaryOut {
  summary: string;
  confidence: number;
  evidence_notes: string[];
  updated_at?: string;
}

export interface ProfileOut {
  person_id: string;
  domain_summaries: Record<string, DomainSummaryOut>;
  verified_findings: Array<{ id: string; statement: string; confidence: number }>;
  key_dates: Array<{ id: string; label: string; date: string; kind: string }>;
  trust_level: string;
  updated_at?: string;
}

export interface TimelineEventOut {
  id: string;
  occurred_at: string;
  label: string;
  kind: string;
  detail: string;
  related_conclusion_id?: string;
  // 咨询记录补意图/需求（喂记忆写回）
  domain?: string;
  need?: string;
}

export interface LifeRhythmSignificationItem {
  house: number;
  word: string;
  polarity: string;
  intensity: number;
  strength: number;
  resonance: string[];
  evidence: string[];
  gated: string;
}

export interface LifeRhythmSynapsisItem {
  hub_planet: string;
  houses: number[];
  manifestation_house: number;
  description_zh: string;
}

export interface LifeRhythmNatalStage {
  type: "natal_promise";
  domain: string;
  domain_label: string;
  themes: LifeRhythmSignificationItem[];
  synapsis: LifeRhythmSynapsisItem[];
}

export interface LifeRhythmPeriod {
  major_lord: string;
  major_start: string;
  major_end: string;
  sub_lord: string;
  sub_start: string;
  sub_end: string;
}

export interface LifeRhythmCharacter {
  lord: string;
  nature: string;
  tone: string;
  domains: string[];
  behavior: string[];
  effort: string;
  afflictions: Array<Record<string, any>>;
  evidence: string[];
}

export interface LifeRhythmFirdariaChapter {
  type: "firdaria_chapter";
  timing_authority: "firdaria" | string;
  period: LifeRhythmPeriod;
  major: LifeRhythmSignificationItem[];
  sub: LifeRhythmSignificationItem[];
  major_character?: LifeRhythmCharacter | null;
  sub_character?: LifeRhythmCharacter | null;
}

export interface LifeRhythmAnnualActivation {
  type: "annual_activation";
  role: "auxiliary" | string;
  primary_timing_authority: "firdaria" | string;
  age: number;
  annual_start: string;
  annual_end: string;
  activation_house: number;
  activation_lord?: string | null;
  themes: LifeRhythmSignificationItem[];
  firdaria_overlap: string[];
}

export interface LifeRhythmTransitTrigger {
  type: "transit_trigger";
  month: string;
  score: number;
  tag: string;
  timing_authority: "firdaria" | string;
  target_planets: string[];
  helper_target_planets: string[];
  scoring_target_planets: string[];
  annual_activation?: LifeRhythmAnnualActivation | null;
}

export interface LifeRhythmOut {
  type: "life_rhythm";
  person_id: string;
  chart_id: string;
  generated_at: string;
  months: number;
  timing_authority: "firdaria" | string;
  source_layers: string[];
  natal_promise: LifeRhythmNatalStage[];
  firdaria_chapter: LifeRhythmFirdariaChapter;
  annual_activation: LifeRhythmAnnualActivation;
  transit_triggers: LifeRhythmTransitTrigger[];
}

export interface PersonExportOut {
  person: PersonOut;
  profile?: Record<string, any> | null;
  conversations: Array<Record<string, any>>;
  memory_items: Array<Record<string, any>>;
  journal_entries: Array<Record<string, any>>;
  life_events: Array<Record<string, any>>;
  letters: Array<Record<string, any>>;
  fragment_lights: Array<Record<string, any>>;
  push_subscriptions: Array<Record<string, any>>;
  related_persons: Array<Record<string, any>>;
  exported_at: string;
}

export interface PersonDeleteOut {
  deleted: string;
}

export interface FragmentOut {
  id: string;        // "sun_core"
  zone: string;      // "planet" | "house" | "sign"
  name: string;      // "太阳·核心意志"
  triggers: string;  // 触发说明
  depth: number;     // 深度分（0 = 未点亮）
  level: number;     // 五层成长级（§4.2 1-5 级，0 = 未点亮；后端统一出级）
  // 触发行动次数（§4.2 升顶门槛：4 级需 ≥1 次、5 级需 ≥2 次"真做过"）
  action_count?: number;
}

export interface FragmentsOut {
  person_id: string;
  fragments: FragmentOut[];
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/**
 * 请求异常 → 对用户友好的提示文案。
 * ApiError(0) / uni.request fail（ECONNREFUSED、request:fail、timeout…）都是"连不上后端"。
 */
export function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 0) return "连不上星灵花园，请确认后端服务已启动";
    if (e.status === 410) return "当前档案已无法解密，请重新建档";
    return `星灵花园响应异常（${e.status}）`;
  }
  if (e instanceof Error) {
    if (/request:fail|timeout|refused|ERR_|network|fail/i.test(e.message)) {
      return "连不上星灵花园，请确认后端服务已启动";
    }
    return e.message;
  }
  return "出了点意外，请稍后再试";
}

function request<T>(method: "GET" | "POST" | "PUT" | "DELETE", path: string, data?: unknown, timeout = 15000): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    uni.request({
      url: BASE_URL + path,
      method,
      data: data as any, // uni.request 的 data 签名较窄，业务载荷已在类型层约束
      header: { "Content-Type": "application/json" },
      timeout,
      success: (res) => {
        const status = res.statusCode || 0;
        if (status >= 200 && status < 300) {
          resolve(res.data as T);
        } else {
          reject(new ApiError(status, `请求失败 ${status}: ${JSON.stringify(res.data)}`));
        }
      },
      fail: (err) => reject(new Error(err.errMsg || "网络错误")),
    });
  });
}

export const api = {
  health: () => request<{ status: string; version: string }>("GET", "/health"),
  verifyPhone: (body: AuthVerifyIn) => request<AccountOut>("POST", "/auth/phone/verify", body),
  getAccount: (accountId: string) => request<AccountOut>("GET", `/account/${accountId}`),
  createSelfProfile: (accountId: string, p: PersonIn) => request<AccountOut>("POST", `/account/${accountId}/self`, p, 60000),
  updateSelfProfile: (accountId: string, p: PersonIn) => request<AccountOut>("PUT", `/account/${accountId}/self`, p, 60000),
  listAccountProfiles: (accountId: string) => request<ProfileListItemOut[]>("GET", `/account/${accountId}/profiles`),
  claimXiatianLegacyData: (accountId: string) => request<{ target_person_id: string; merged: Record<string, Record<string, number>> }>("POST", `/account/${accountId}/claim-xiatian`, undefined, 60000),
  createPerson: (p: PersonIn) => request<PersonOut>("POST", "/person", p),
  getPerson: (id: string) => request<PersonOut>("GET", `/person/${id}`),
  exportPerson: (id: string) => request<PersonExportOut>("GET", `/person/${id}/export`, undefined, 60000),
  deletePerson: (id: string) => request<PersonDeleteOut>("DELETE", `/person/${id}`, undefined, 60000),
  // chat 涉及 LLM（意图拆解+叙事），可能较慢，单独放宽超时
  chat: (body: ChatIn) => request<ChatOut>("POST", "/chat", body, 60000),
  profile: (personId: string) => request<ProfileOut>("GET", `/person/${personId}/profile`),
  opening: (personId: string, persona?: string) =>
    request<OpeningOut>("GET", `/person/${personId}/opening${persona ? `?persona=${encodeURIComponent(persona)}` : ""}`),
  recommendedSpirits: (personId: string) =>
    request<RecommendedSpiritsOut>("GET", `/person/${personId}/recommended-spirits`),
  personas: () => request<PersonaOut[]>("GET", "/personas"),
  feedbackFinding: (personId: string, findingId: string, feedback: "confirmed" | "refuted") =>
    request<{ ok: boolean; user_feedback: string; trust_level: string; new_confidence: number }>(
      "POST", `/person/${personId}/findings/${findingId}/feedback`, { feedback }
    ),
  findings: (personId: string, pendingOnly = false) =>
    request<FindingOut[]>("GET", `/person/${personId}/findings?pending_only=${pendingOnly}`),
  getPreferences: (personId: string) =>
    request<PreferencesOut>("GET", `/person/${personId}/preferences`),
  updatePreferences: (personId: string, prefs: Record<string, any>) =>
    request<PreferencesOut>("PUT", `/person/${personId}/preferences`, prefs),
  timeline: (personId: string) => request<TimelineEventOut[]>("GET", `/person/${personId}/timeline`),
  lifeRhythm: (personId: string, months = 6) =>
    request<LifeRhythmOut>("GET", `/person/${personId}/life-rhythm?months=${months}`, undefined, 60000),
  journalList: (personId: string, page = 1, page_size = 20) =>
    request<JournalPage>("GET", `/person/${personId}/journal?page=${page}&page_size=${page_size}`),
  journalCreate: (body: { person_id: string; content: string; mood?: string }) =>
    request<JournalOut>("POST", "/journal", body, 30000),
  mailboxToday: (personId: string) =>
    request<LetterOut>("POST", "/mailbox/today", { person_id: personId }, 60000),
  // 信箱信件分页（20 条一页；kind 可选 daily=日推历史 / keepsake=记忆来信）
  letters: (personId: string, opts?: { page?: number; page_size?: number; kind?: "daily" | "keepsake" }) => {
    const q: string[] = [];
    if (opts?.page && opts.page > 1) q.push(`page=${opts.page}`);
    if (opts?.page_size) q.push(`page_size=${opts.page_size}`);
    if (opts?.kind) q.push(`kind=${opts.kind}`);
    const qs = q.length ? `?${q.join("&")}` : "";
    return request<LetterPage>("GET", `/person/${personId}/letters${qs}`);
  },
  // 首页红点：打开信箱时把今日未读来信标记为已读（幂等）
  markLettersReadToday: (personId: string) =>
    request<{ ok: boolean; marked: number }>("POST", `/person/${personId}/letters/read-today`),
  garden: (personId: string, persona?: string) =>
    request<GardenState>("GET", `/garden?person_id=${personId}${persona ? `&persona=${encodeURIComponent(persona)}` : ""}`, undefined, 60000),
  // 自我星盘轮：34 子类全量 + 当前深度分（含未点亮 = 0，供"盲区即课题"叙事）
  fragments: (personId: string) =>
    request<FragmentsOut>("GET", `/person/${personId}/fragments`),
  // 今日灵魂碎片（§2.5 每日结算）：今天（本地日）点亮的 top3 子类
  soulFragmentsToday: (personId: string) =>
    request<SoulFragmentsTodayOut>("GET", `/person/${personId}/soul-fragments/today`),
  // Web Push（真实推送通道）：VAPID 公钥 / 订阅 / 退订
  getVapidPublicKey: () =>
    request<{ public_key: string }>("GET", "/push/vapid-public-key"),
  pushSubscribe: (personId: string, subscription: Record<string, any>) =>
    request<{ ok: boolean }>("POST", "/push/subscribe", { person_id: personId, subscription }),
  pushUnsubscribe: (personId: string, endpoint: string) =>
    request<{ ok: boolean; deleted: number }>("POST", "/push/unsubscribe", { person_id: personId, endpoint }),
  listRelatedPersons: (personId: string) =>
    request<RelatedPersonOut[]>("GET", `/person/${personId}/related`),
  createRelatedPerson: (personId: string, body: RelatedPersonIn) =>
    request<RelatedPersonOut>("POST", `/person/${personId}/related`, body, 60000),
  getRelatedPersonDetail: (personId: string, relatedId: string) =>
    request<RelatedPersonDetailOut>("GET", `/person/${personId}/related/${relatedId}`),
  updateRelatedPerson: (personId: string, relatedId: string, body: RelatedPersonIn) =>
    request<RelatedPersonDetailOut>("PUT", `/person/${personId}/related/${relatedId}`, body, 60000),
};

export interface JournalOut {
  id: string;
  person_id: string;
  content: string;
  mood: string;
  ai_summary: string;
  created_at?: string;
}

export interface JournalPage {
  items: JournalOut[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface DailyPushItemOut {
  level: number;
  score?: number | null;
  house?: number | null;
  scene: string;
  sender?: string | null;
  reason: string;
  advice: string;
  trigger_planet?: string | null;
  natal_planet?: string | null;
  aspect?: string | null;
  orb?: number | null;
  role?: string | null;
  confidence?: number | null;
  reason_chain: string[];
  time_label: string;
  start_at?: string | null;
  end_at?: string | null;
}

export interface DailyPushOut {
  letter_date?: string | null;
  timezone_name?: string | null;
  summary: string;
  items: DailyPushItemOut[];
  disclaimer?: string | null;
}

export interface LetterOut {
  id: string;
  person_id: string;
  letter_date: string;
  sender: string;
  sender_zh: string;
  title: string;
  body: string;
  kind: string;
  read_at?: string | null;
  daily_push?: DailyPushOut | null;
  // 来信式日记（kind=keepsake）的落款推导链（§6.2）：显式可解释"为什么是这颗星"
  primary_need?: string;
  healing_name?: string;
  soul_fragments?: string[];
  lit_fragments?: string[];
  explain?: string;
  entry?: boolean; // 词条式来信（§6.1 日常/正面分享时刻的诗化记忆词条）
}

export interface LetterPage {
  items: LetterOut[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface GardenState {
  person_id: string;
  today: string;
  letter: LetterOut | null;
  continue_from: { conversation_id: string; summary: string; started_at?: string } | null;
  domains: string[];
  trust_level: string;
  pending_verifications: number;
  // 首页红点细粒度：今日来信未读（打开信箱 → read-today 消除）
  letter_unread: boolean;
  // 站内"回家看看"兜底（推送后置）：今天（本地日）点亮的 top3 灵魂碎片
  soul_fragments: SoulFragmentOut[];
  // 记忆镜头：确定性召回的「我记得你」卡片（老后端缺字段时可为空）
  recall?: GardenRecallOut;
}

export interface SoulFragmentOut {
  id: string;
  name: string;   // "月亮·情绪潮汐"
  zone: string;   // planet / house / sign
  delta: number;  // 今天累计点亮深度分
}

export interface SoulFragmentsTodayOut {
  person_id: string;
  date: string;
  fragments: SoulFragmentOut[];
}

export default api;
