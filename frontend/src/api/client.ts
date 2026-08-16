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

export interface ChatIn {
  person_id: string;
  session_id?: string;
  message: string;
  persona?: string;
  mode?: "quick" | "deep" | "annual" | "chart" | "free";
  related_person_id?: string;
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

function request<T>(method: "GET" | "POST" | "PUT", path: string, data?: unknown, timeout = 15000): Promise<T> {
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
  createPerson: (p: PersonIn) => request<PersonOut>("POST", "/person", p),
  getPerson: (id: string) => request<PersonOut>("GET", `/person/${id}`),
  // chat 涉及 LLM（意图拆解+叙事），可能较慢，单独放宽超时
  chat: (body: ChatIn) => request<ChatOut>("POST", "/chat", body, 60000),
  profile: (personId: string) => request<ProfileOut>("GET", `/person/${personId}/profile`),
  opening: (personId: string, persona?: string) =>
    request<OpeningOut>("GET", `/person/${personId}/opening${persona ? `?persona=${encodeURIComponent(persona)}` : ""}`),
  recommendedSpirits: (personId: string) =>
    request<RecommendedSpiritsOut>("GET", `/person/${personId}/recommended-spirits`),
  feedbackFinding: (personId: string, findingId: string, feedback: "confirmed" | "refuted") =>
    request<{ ok: boolean; user_feedback: string; trust_level: string; new_confidence: number }>(
      "POST", `/person/${personId}/findings/${findingId}/feedback`, { feedback }
    ),
  findings: (personId: string, pendingOnly = false) =>
    request<FindingOut[]>("GET", `/person/${personId}/findings?pending_only=${pendingOnly}`),
  getPreferences: (personId: string) =>
    request<Record<string, any>>("GET", `/person/${personId}/preferences`),
  updatePreferences: (personId: string, prefs: Record<string, any>) =>
    request<Record<string, any>>("PUT", `/person/${personId}/preferences`, prefs),
  timeline: (personId: string) => request<TimelineEventOut[]>("GET", `/person/${personId}/timeline`),
  journalList: (personId: string) => request<JournalOut[]>("GET", `/person/${personId}/journal`),
  journalCreate: (body: { person_id: string; content: string; mood?: string }) =>
    request<JournalOut>("POST", "/journal", body, 30000),
  mailboxToday: (personId: string) =>
    request<LetterOut>("POST", "/mailbox/today", { person_id: personId }, 60000),
  letters: (personId: string) => request<LetterOut[]>("GET", `/person/${personId}/letters`),
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
};

export interface JournalOut {
  id: string;
  person_id: string;
  content: string;
  mood: string;
  ai_summary: string;
  created_at?: string;
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
  // 来信式日记（kind=keepsake）的落款推导链（§6.2）：显式可解释"为什么是这颗星"
  primary_need?: string;
  healing_name?: string;
  soul_fragments?: string[];
  lit_fragments?: string[];
  explain?: string;
  entry?: boolean; // 词条式来信（§6.1 日常/正面分享时刻的诗化记忆词条）
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
