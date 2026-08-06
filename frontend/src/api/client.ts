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
}

export interface ChatIn {
  person_id: string;
  session_id?: string;
  message: string;
  persona?: string;
}

export interface ChatOut {
  answer: string;
  session_id: string;
  intent_domain: string | null;
  needs_related_person: boolean;
  written_back: boolean;
  trust_level: string;
}

export interface OpeningOut {
  opening: string;
  trust_level: string;
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
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
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
  opening: (personId: string) =>
    request<OpeningOut>("GET", `/person/${personId}/opening`),
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
  garden: (personId: string) =>
    request<GardenState>("GET", `/garden?person_id=${personId}`, undefined, 60000),
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
}

export interface GardenState {
  person_id: string;
  today: string;
  letter: LetterOut | null;
  continue_from: { conversation_id: string; summary: string; started_at?: string } | null;
  domains: string[];
  trust_level: string;
  pending_verifications: number;
}

export default api;
