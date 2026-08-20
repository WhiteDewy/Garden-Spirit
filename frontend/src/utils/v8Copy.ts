import type { ReportIntentShape, ReportType } from "@/api/client";

export interface V8DomainCopy {
  label: string;
  caption: string;
}

const DOMAIN_COPY: Record<string, V8DomainCopy> = {
  career: {
    label: "成就与方向",
    caption: "工作、责任与表达路径背后的内在主题",
  },
  relationship: {
    label: "亲密与连接",
    caption: "爱、边界与关系模式背后的内在主题",
  },
  wealth: {
    label: "资源与价值",
    caption: "金钱、选择与资源流动背后的内在主题",
  },
  health: {
    label: "身心节律",
    caption: "身体感受、压力与日常照顾的内在主题",
  },
  emotion: {
    label: "情绪天气",
    caption: "情绪起伏与安全感线索",
  },
  family: {
    label: "根系与家",
    caption: "家庭、归属与照顾关系线索",
  },
  learning: {
    label: "学习与表达",
    caption: "理解、表达与成长方式线索",
  },
  growth: {
    label: "远方与信念",
    caption: "视野、信念与人生扩展线索",
  },
  network: {
    label: "人际与社群",
    caption: "朋友、群体与连接方式线索",
  },
  self: {
    label: "自我地图",
    caption: "自我理解、核心意志与内在课题",
  },
  daily: {
    label: "今日光线",
    caption: "今天浮现出来的生活线索",
  },
};

function normalizeDomain(domain?: string | null) {
  return String(domain || "").trim().toLowerCase();
}

export function v8DomainCopy(domain?: string | null): V8DomainCopy {
  const key = normalizeDomain(domain);
  return DOMAIN_COPY[key] || {
    label: "星图线索",
    caption: "后端沉淀出的内在主题线索",
  };
}

export function v8DomainLabel(domain?: string | null) {
  return v8DomainCopy(domain).label;
}

export interface V8ObservatoryTopic {
  key: string;
  icon: string;
  name: string;
  shortName: string;
  domain?: string;
  status: "available" | "contract" | "report_later";
  sub: string;
  intro: string;
  askSamples: readonly string[];
  evidence: readonly string[];
  cta: string;
  chatSeed: string;
  reportType?: ReportType;
  intentShape?: ReportIntentShape;
  primaryTopic?: string;
  secondaryTopics?: readonly string[];
}

export const V8_OBSERVATORY_TOPICS: readonly V8ObservatoryTopic[] = [
  {
    key: "annual",
    icon: "✺",
    name: "年度光线",
    shortName: "年运",
    status: "report_later",
    sub: "年度主题 / 关键月份 / 机会压力窗口",
    intro: "适合把一年看成一段可复盘的章节：先看今年谁在管事，再看哪些月份更容易被触发。",
    askSamples: ["我今年最重要的主题是什么？", "接下来几个月哪里需要慢一点？", "今年适合把力气放在哪里？"],
    evidence: ["法达章节与子限", "日返年度快照", "未来 6 个月行运窗口"],
    cta: "和星灵聊今年",
    chatSeed: "我想看看我的年度主题和接下来几个月的节奏。",
    reportType: "annual",
    intentShape: "single_topic",
    primaryTopic: "annual",
  },
  {
    key: "monthly",
    icon: "☾",
    name: "本月节律",
    shortName: "月运",
    status: "contract",
    sub: "本月情绪 / 行动节律 / 提醒",
    intro: "适合看这个月的情绪重心、行动节奏和需要被照顾的生活场景；它不替代每日来信。",
    askSamples: ["我这个月的重心是什么？", "这个月情绪为什么有点反复？", "本月适合推进什么，不适合硬扛什么？"],
    evidence: ["月返当月主基调", "次限月亮情绪季节", "当月行运触发"],
    cta: "和星灵聊本月",
    chatSeed: "我想看看这个月的节律、情绪重心和提醒。",
    reportType: "monthly",
    intentShape: "single_topic",
    primaryTopic: "monthly",
  },
  {
    key: "life",
    icon: "♄",
    name: "人生章节",
    shortName: "人生",
    status: "report_later",
    sub: "长周期阶段 / 当前谁管事 / 人生规划",
    intro: "适合看长周期里的当前章节，不做机械切段，也不一次性摊开整个人生。",
    askSamples: ["我现在处在人生哪一章？", "这几年真正要学的课题是什么？", "为什么我最近总觉得在换阶段？"],
    evidence: ["法达大限与子限", "时间领主本命条件", "已确认人生事件"],
    cta: "聊聊当前章节",
    chatSeed: "我想看看我现在处在人生哪一章，以及这个阶段的主题。",
    reportType: "life_rhythm",
    intentShape: "single_topic",
    primaryTopic: "life",
  },
  {
    key: "relationship",
    icon: "♀",
    name: "亲密与连接",
    shortName: "情感",
    domain: "relationship",
    status: "available",
    sub: "恋爱、边界与关系模式的证据链",
    intro: "适合看你在亲密关系里的靠近方式、边界、期待与反复出现的连接模式。",
    askSamples: ["我在关系里最容易卡在哪里？", "我为什么总是被某类人吸引？", "这段关系我该怎么理解？"],
    evidence: ["关系领域沉淀判断", "相关宫位与承载者", "聊天中被照见的关系碎片"],
    cta: "聊聊关系模式",
    chatSeed: "我想聊聊我的亲密关系模式和边界。",
    reportType: "theme",
    intentShape: "single_topic",
    primaryTopic: "relationship",
  },
  {
    key: "career",
    icon: "☿",
    name: "成就与方向",
    shortName: "事业",
    domain: "career",
    status: "available",
    sub: "工作、责任与表达路径的证据链",
    intro: "适合看职业路径、表达方式、责任感、成就压力，以及什么时候该推进或调整。",
    askSamples: ["我最近事业卡在哪里？", "我适合怎样的工作节奏？", "现在要不要换方向？"],
    evidence: ["事业领域沉淀判断", "10 宫/6 宫等主题线索", "时机窗口与已验证事件"],
    cta: "聊聊事业方向",
    chatSeed: "我想聊聊我的事业方向、当前卡点和下一步节奏。",
    reportType: "theme",
    intentShape: "single_topic",
    primaryTopic: "career",
  },
  {
    key: "wealth",
    icon: "♃",
    name: "资源与价值",
    shortName: "财富",
    domain: "wealth",
    status: "available",
    sub: "金钱、选择与资源流动的证据链",
    intro: "适合看金钱安全感、资源交换、价值判断和共同钱议题，不包装成发财预言。",
    askSamples: ["我的金钱模式是什么？", "最近财务上哪里要留边界？", "我适合怎么建立稳定资源？"],
    evidence: ["财富领域沉淀判断", "2/8 宫资源线索", "风险与责任记录"],
    cta: "聊聊资源流动",
    chatSeed: "我想聊聊我的金钱模式、资源流动和财务边界。",
    reportType: "theme",
    intentShape: "single_topic",
    primaryTopic: "wealth",
  },
  {
    key: "study",
    icon: "☉",
    name: "学习与表达",
    shortName: "学业",
    domain: "learning",
    status: "available",
    sub: "学习方式 / 考学 / 深造线索",
    intro: "适合看理解、表达、考试、深造和知识吸收方式，也适合看沟通表达的卡点。",
    askSamples: ["我适合怎样学习？", "最近考试/进修要注意什么？", "为什么我表达时总卡住？"],
    evidence: ["学习领域沉淀判断", "3/9 宫语义切片", "表达与信念线索"],
    cta: "聊聊学习表达",
    chatSeed: "我想聊聊我的学习方式、表达卡点和成长路径。",
    reportType: "theme",
    intentShape: "single_topic",
    primaryTopic: "learning",
  },
  {
    key: "self",
    icon: "✦",
    name: "自我地图",
    shortName: "自我",
    domain: "self",
    status: "available",
    sub: "性格 / 灵魂课题 / 自我理解",
    intro: "适合回到你自己：核心意志、情绪反应、行动动力，以及已经被点亮的 34 个内在角落。",
    askSamples: ["我最核心的自我课题是什么？", "我为什么总是这样反应？", "最近哪个内在角落最需要被看见？"],
    evidence: ["自我星盘轮", "已点亮灵魂碎片", "自我领域沉淀判断"],
    cta: "聊聊我的自我地图",
    chatSeed: "我想聊聊我的自我地图、核心课题和最近被点亮的内在角落。",
    reportType: "theme",
    intentShape: "single_topic",
    primaryTopic: "self",
  },
  {
    key: "family",
    icon: "☊",
    name: "根系与家",
    shortName: "家庭",
    domain: "family",
    status: "available",
    sub: "原生家庭 / 父母 / 亲子关系",
    intro: "适合看家庭、归属、照顾关系和根系安全感，不把复杂经历简化成单一结论。",
    askSamples: ["我的家庭课题是什么？", "我和父母/孩子的相处模式怎么看？", "为什么我对家总有矛盾感？"],
    evidence: ["家庭领域沉淀判断", "4 宫根系线索", "记忆来信与已确认事件"],
    cta: "聊聊家庭根系",
    chatSeed: "我想聊聊我的家庭课题、归属感和照顾关系。",
    reportType: "theme",
    intentShape: "single_topic",
    primaryTopic: "family",
  },
] as const;

const TOPIC_STATUS_COPY: Record<V8ObservatoryTopic["status"], string> = {
  available: "可进入 Chat 深聊",
  contract: "证据链接入中",
  report_later: "报告后续开放",
};

export function v8TopicStatus(status: V8ObservatoryTopic["status"] = "contract") {
  return TOPIC_STATUS_COPY[status];
}

export function v8TopicToast(name: string) {
  return `${name}将接入星图证据链`;
}
