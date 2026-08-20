<template>
  <view class="page gs-time-page" :class="phaseClass">
    <view class="top-glow" aria-hidden="true"></view>

    <view class="header">
      <view class="spirit-orb" aria-hidden="true"><SpiritPortrait :planet="spiritPlanet" /></view>
      <view class="header-copy">
        <text class="spirit-name">{{ spiritName }}</text>
        <text class="spirit-status">{{ thinking ? '正在翻看你的星图…' : '正在听你说' }}</text>
      </view>
      <text v-if="trustLabel" class="trust-tag">信任 · {{ trustLabel }}</text>
    </view>

    <scroll-view class="messages" scroll-y :scroll-into-view="scrollTo">
      <view class="time-divider"><text>{{ todayStr }}</text></view>
      <view v-for="(m, i) in messages" :key="i" class="msg-row" :class="m.role">
        <view class="bubble" :class="m.role">
          <text class="msg-text">{{ m.text }}</text>
        </view>
        <view v-if="m.role === 'assistant' && m.loopCards?.length" class="loop-panel">
          <text class="loop-kicker">THIS CONVERSATION LEFT LIGHT</text>
          <text class="loop-heading">这次聊天，花园已经替你收好。</text>
          <view
            v-for="card in m.loopCards"
            :key="card.key"
            class="loop-card"
            @tap.stop="handleLoopAction(card.action)"
          >
            <view class="loop-icon">{{ card.icon }}</view>
            <view class="loop-copy">
              <text class="loop-title">{{ card.title }}</text>
              <text class="loop-desc">{{ card.desc }}</text>
            </view>
            <text v-if="card.actionText" class="loop-action">{{ card.actionText }}</text>
          </view>
          <view class="loop-actions">
            <button class="loop-btn" @tap.stop="openMailbox">去信箱</button>
            <button class="loop-btn" @tap.stop="openFragments">看碎片</button>
            <button class="loop-btn" @tap.stop="continueAsking">继续追问</button>
            <button class="loop-btn ghost" @tap.stop="reportComingSoon">整理成报告</button>
          </view>
        </view>
      </view>
      <view v-if="thinking" class="msg-row assistant">
        <view class="bubble assistant">
          <text class="msg-text">🌙 正在查看你的星图……</text>
        </view>
      </view>

      <view v-if="!sentOnce && !thinking" class="quick-zone">
        <text class="quick-lead">不知道从哪开始，也可以：</text>
        <view class="quick-row">
          <button v-for="q in quickOptions" :key="q" class="quick-chip" @tap="sendQuick(q)">{{ q }}</button>
        </view>
      </view>
      <view id="bottom" />
    </scroll-view>

    <view class="composer">
      <input
        v-model="draft"
        class="composer-input"
        :placeholder="`和${spiritName}说说……`"
        confirm-type="send"
        @confirm="send"
      />
      <button class="composer-send" :disabled="thinking" @tap="send">↑</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import api, { ApiError, type ChatOut, type ReportIntentIn } from "@/api/client";
import SpiritPortrait from "@/components/SpiritPortrait.vue";
import { selectSpirit } from "@/utils/spiritSelection";
import { useTimePhase } from "@/utils/timeTheme";

import { cacheChatSessionId, clearAccountCache, getChatSessionId, requireSelfPersonId } from "@/utils/account";

type LoopAction = "mailbox" | "fragments" | "followup" | "report";
interface LoopCard {
  key: string;
  icon: string;
  title: string;
  desc: string;
  action?: LoopAction;
  actionText?: string;
}
interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  loopCards?: LoopCard[];
}

const spiritName = ref("星灵");
const draft = ref("");
const thinking = ref(false);
const scrollTo = ref("");
const trustLabel = ref("");
const sentOnce = ref(false);
const messages = ref<ChatMessage[]>([]);
const quickOptions = ["我最近有点累", "想聊聊心里的事", "随便聊聊"];
const persona = ref<string | undefined>();
const spiritPlanet = ref("moon");
const pendingSeedMessage = ref("");
const pendingReportIntent = ref<ReportIntentIn | null>(null);
const personId = ref("");
const { phaseClass, refreshPhase } = useTimePhase();

const todayStr = (() => {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `今天 ${p(d.getHours())}:${p(d.getMinutes())}`;
})();

// 信任等级中文名（A2 关系层，与后端 TrustLevel 对齐）
const TRUST_ZH: Record<string, string> = {
  stranger: "陌生",
  acquaintance: "认识",
  trusted: "信任",
  intimate: "深交",
};

function queryString(query: Record<string, unknown> | undefined, key: string) {
  const value = query?.[key];
  return typeof value === "string" ? decodeURIComponent(value).trim() : "";
}

function parseReportIntent(query: Record<string, unknown> | undefined): ReportIntentIn | null {
  const entryTopicKey = queryString(query, "entry_topic_key");
  if (!entryTopicKey) return null;
  const secondary = queryString(query, "secondary_topics");
  return {
    entry_source: "observatory",
    entry_topic_key: entryTopicKey,
    primary_topic: queryString(query, "primary_topic") || undefined,
    secondary_topics: secondary ? secondary.split(",").map((s) => s.trim()).filter(Boolean) : undefined,
    intent_shape: queryString(query, "intent_shape") as ReportIntentIn["intent_shape"] || undefined,
    report_type: queryString(query, "report_type") as ReportIntentIn["report_type"] || undefined,
    user_focus_text: queryString(query, "user_focus_text") || queryString(query, "message") || undefined,
  };
}

onLoad(async (query) => {
  refreshPhase();
  const seeded = queryString(query, "message");
  pendingSeedMessage.value = seeded.trim();
  pendingReportIntent.value = parseReportIntent(query);
  const pid = await requireSelfPersonId();
  if (!pid) return;
  personId.value = pid;

  // 常驻星灵优先；没有 preferred_persona 时，才用今日推荐作为本次陪伴人格。
  Promise.allSettled([api.getPreferences(pid), api.recommendedSpirits(pid), api.personas()])
    .then(([prefsRes, recRes, personasRes]) => {
      const selection = selectSpirit({
        preferredPersona: prefsRes.status === "fulfilled" ? prefsRes.value?.preferred_persona : "",
        recommendations: recRes.status === "fulfilled" ? recRes.value.spirits : [],
        personas: personasRes.status === "fulfilled" ? personasRes.value : [],
      });
      persona.value = selection.planet;
      spiritPlanet.value = selection.planet;
      spiritName.value = selection.name;
      return api.opening(pid, persona.value);
    })
    .then((o) => {
      if (!o?.opening) return;
      messages.value = [{ role: "assistant", text: o.opening }];
      trustLabel.value = TRUST_ZH[o.trust_level] || "";
    })
    .catch(() => undefined)
    .finally(() => {
      if (!messages.value.length) {
        messages.value.push({ role: "assistant", text: "今天想聊点什么？可以说一个具体问题，也可以只说最近的心情。" });
      }
      if (pendingSeedMessage.value) {
        draft.value = pendingSeedMessage.value;
        pendingSeedMessage.value = "";
        setTimeout(() => { void send(); }, 240);
      }
    });
});

async function send() {
  const text = draft.value.trim();
  if (!text || thinking.value) return;
  draft.value = "";
  sentOnce.value = true;
  messages.value.push({ role: "user", text });
  thinking.value = true;
  scrollTo.value = "bottom";

  const pid = personId.value || await requireSelfPersonId();
  if (!pid) return;
  personId.value = pid;
  const session = getChatSessionId();
  try {
    const res = await api.chat({
      person_id: pid,
      session_id: session,
      message: text,
      persona: persona.value,
      report_intent: pendingReportIntent.value || undefined,
    });
    cacheChatSessionId(res.session_id);
    pendingReportIntent.value = null;
    messages.value.push({ role: "assistant", text: res.answer, loopCards: buildLoopCards(res) });
  } catch (e: any) {
    if (e instanceof ApiError && (e.status === 404 || e.status === 410)) {
      // 用户档案过期/被清/旧密钥不可解 → 回建档页重新开始
      clearAccountCache();
      uni.showToast({ title: e.status === 410 ? "当前档案已无法解密，请重新登录建档" : "这个花园已经找不到了", icon: "none" });
      uni.reLaunch({ url: "/pages/auth/login" });
      return;
    }
    messages.value.push({
      role: "assistant",
      text: e && e.message && e.message.includes("timeout")
        ? "星灵想得有点久，请再问一次。"
        : "花园暂时联系不上星灵，请稍后再试。（" + (e?.message || "网络错误") + "）",
    });
  } finally {
    thinking.value = false;
    scrollTo.value = "bottom";
  }
}

function buildLoopCards(res: ChatOut): LoopCard[] {
  const cards: LoopCard[] = [];
  const litCount = res.lit_fragments?.length || 0;
  const seenCount = res.seen_fragments?.length || 0;
  const actionCount = res.actioned_fragments?.length || 0;

  if (litCount) {
    cards.push({
      key: "lit",
      icon: "✦",
      title: `点亮 ${litCount} 个内在角落`,
      desc: "这些碎片已进入自我星盘轮，之后可以在宇宙里慢慢回看。",
      action: "fragments",
      actionText: "看碎片",
    });
  }
  if (seenCount) {
    cards.push({
      key: "seen",
      icon: "✓",
      title: "这次确认，星灵记住了",
      desc: "被你确认过的判断会进入信任层，让花园以后更懂你。",
      action: "fragments",
      actionText: "看沉淀",
    });
  }
  if (actionCount) {
    cards.push({
      key: "action",
      icon: "✹",
      title: "行动进入成长账本",
      desc: "真正做出来的改变，会让对应碎片继续发光。",
      action: "fragments",
      actionText: "看成长",
    });
  }
  if (res.keepsake_created) {
    cards.push({
      key: "keepsake",
      icon: "✉",
      title: "新的记忆来信已放进信箱",
      desc: "这段重要的话被保存成可以回看的记忆资产。",
      action: "mailbox",
      actionText: "去信箱",
    });
  }
  return cards;
}

function handleLoopAction(action?: LoopAction) {
  if (action === "mailbox") return openMailbox();
  if (action === "fragments") return openFragments();
  if (action === "followup") return continueAsking();
  if (action === "report") return reportComingSoon();
}

function openMailbox() {
  uni.reLaunch({ url: "/pages/mailbox/mailbox" });
}

function openFragments() {
  uni.navigateTo({ url: "/pages/universe/wheel" });
}

function continueAsking() {
  draft.value = "我想继续追问刚才这一点。";
  scrollTo.value = "bottom";
}

function reportComingSoon() {
  uni.showToast({ title: "报告整理后续接入证据链", icon: "none" });
}

function sendQuick(q: string) {
  draft.value = q;
  void send();
}
</script>

<style scoped>
.page {
  height: 100vh;
  background: linear-gradient(180deg, #253a36 0%, #172824 68%, #14221f 100%);
  display: flex;
  flex-direction: column;
  position: relative;
}
.top-glow { position: absolute; width: 540rpx; height: 540rpx; border-radius: 50%; right: -160rpx; top: -140rpx; background: rgba(197, 183, 133, 0.13); filter: blur(70rpx); pointer-events: none; }
.header { display: flex; align-items: center; gap: 22rpx; padding: 34rpx 32rpx 26rpx; position: relative; z-index: 1; }
.spirit-orb { width: 96rpx; height: 96rpx; flex-shrink: 0; border-radius: 50%;
  background: radial-gradient(circle at 38% 34%, #fff 0 4%, transparent 5%), radial-gradient(circle at 62% 34%, #fff 0 4%, transparent 5%), radial-gradient(circle at 50% 48%, rgba(255, 255, 255, 0.8) 0 17%, transparent 18%), radial-gradient(circle at 50% 65%, rgba(224, 235, 222, 0.8) 0 28%, transparent 29%), linear-gradient(145deg, #e8ece0, #879f94);
  box-shadow: 0 0 0 2rpx rgba(255, 255, 255, 0.25), 0 16rpx 50rpx rgba(0, 0, 0, 0.25); overflow: hidden; }
.spirit-name { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 34rpx; font-weight: 600; color: #edf1e9; }
.spirit-status { display: block; margin-top: 6rpx; font-size: 21rpx; color: rgba(235, 241, 233, 0.4); }
.trust-tag { margin-left: auto; flex-shrink: 0; color: rgba(165, 214, 167, 0.9); font-size: 21rpx; background: rgba(124, 179, 66, 0.16); border: 1rpx solid rgba(165, 214, 167, 0.22); border-radius: 999rpx; padding: 8rpx 18rpx; }
.messages { flex: 1; padding: 12rpx 32rpx; box-sizing: border-box; position: relative; z-index: 1; }
.time-divider { text-align: center; font-size: 19rpx; color: rgba(235, 241, 233, 0.35); margin: 14rpx 0 30rpx; }
.msg-row { display: flex; flex-direction: column; margin-bottom: 26rpx; }
.msg-row.user { align-items: flex-end; }
.msg-row.assistant { align-items: flex-start; }
.bubble { max-width: 84%; border-radius: 40rpx 40rpx 40rpx 12rpx; padding: 28rpx 32rpx; }
.bubble.user { border-radius: 40rpx 40rpx 12rpx 40rpx; background: #637b6e; color: #f8f7ee; }
.bubble.assistant { background: rgba(255, 255, 255, 0.075); border: 1rpx solid rgba(255, 255, 255, 0.09); color: #edf1e9; }
.msg-text { font-family: Georgia, "Noto Serif SC", serif; font-size: 29rpx; line-height: 1.9; white-space: pre-wrap; word-break: break-word; }
.loop-panel { width: 86%; margin-top: 14rpx; padding: 24rpx; box-sizing: border-box; border-radius: 30rpx; border: 1rpx solid rgba(240, 210, 139, 0.2); background: linear-gradient(145deg, rgba(240, 210, 139, 0.13), rgba(255, 255, 255, 0.055)); box-shadow: 0 18rpx 58rpx rgba(0, 0, 0, 0.12); }
.loop-kicker { display: block; font-size: 17rpx; letter-spacing: 0.14em; color: rgba(240, 210, 139, 0.62); font-weight: 800; }
.loop-heading { display: block; margin-top: 8rpx; margin-bottom: 16rpx; color: #fff7e7; font-family: Georgia, "Noto Serif SC", serif; font-size: 27rpx; font-weight: 600; }
.loop-card { display: flex; align-items: center; gap: 16rpx; padding: 18rpx 0; border-top: 1rpx solid rgba(255, 255, 255, 0.08); }
.loop-icon { width: 46rpx; height: 46rpx; flex-shrink: 0; border-radius: 50%; background: rgba(240, 210, 139, 0.16); color: #f0d28b; display: flex; align-items: center; justify-content: center; font-size: 24rpx; }
.loop-copy { flex: 1; min-width: 0; }
.loop-title { display: block; color: rgba(255, 247, 231, 0.9); font-size: 24rpx; font-weight: 650; }
.loop-desc { display: block; margin-top: 6rpx; color: rgba(235, 241, 233, 0.46); font-size: 20rpx; line-height: 1.55; }
.loop-action { flex-shrink: 0; color: #f0d28b; font-size: 20rpx; }
.loop-actions { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10rpx; margin-top: 12rpx; }
.loop-btn { min-height: 58rpx; padding: 0; margin: 0; border-radius: 18rpx; background: rgba(255, 247, 231, 0.13); color: rgba(255, 247, 231, 0.84); font-size: 20rpx; line-height: 58rpx; }
.loop-btn.ghost { color: rgba(240, 210, 139, 0.78); background: rgba(240, 210, 139, 0.08); }
.quick-zone { margin-top: 34rpx; padding-bottom: 10rpx; }
.quick-lead { display: block; font-size: 22rpx; color: rgba(235, 241, 233, 0.45); margin-bottom: 16rpx; }
.quick-row { display: flex; flex-wrap: wrap; gap: 16rpx; }
.quick-chip { border: 1rpx solid rgba(255, 255, 255, 0.14); background: rgba(255, 255, 255, 0.055); border-radius: 34rpx; padding: 16rpx 26rpx; font-size: 24rpx; color: rgba(255, 255, 255, 0.72); line-height: 1.4; margin: 0; }
.composer { display: flex; align-items: center; gap: 14rpx; padding: 22rpx 30rpx; padding-bottom: calc(22rpx + env(safe-area-inset-bottom)); position: relative; z-index: 1; }
.composer-input { flex: 1; min-height: 96rpx; background: rgba(255, 255, 255, 0.09); border: 1rpx solid rgba(255, 255, 255, 0.1); border-radius: 44rpx; padding: 0 36rpx; color: #edf1e9; font-size: 27rpx; }
.composer-send { width: 84rpx; height: 84rpx; flex-shrink: 0; border-radius: 30rpx; background: #b8c8b7; color: #253a36; font-size: 36rpx; font-weight: 700; display: flex; align-items: center; justify-content: center; padding: 0; margin: 0; line-height: 1; }
.composer-send[disabled] { opacity: 0.5; }
</style>
