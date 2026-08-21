<template>
  <view class="page gs-time-page" :class="phaseClass">
    <view class="cosmos-glow" aria-hidden="true"></view>

    <!-- 自定义导航栏 -->
    <view class="navbar">
      <text class="nav-back" @tap="goBack">‹</text>
      <text class="nav-title">主题观星台</text>
      <view class="nav-right" />
    </view>

    <view class="head">
      <text class="eyebrow">OBSERVATORY · 主题观星台</text>
      <text class="title">选一个主题，让星图证据链慢慢显影。</text>
      <text class="sub">这里不前端生成预测结论；只把 Domain / Finding / Report 未来会承接的主题入口收在一起。</text>
      <text v-if="trustLabel" class="trust-line">🌱 你们已是「{{ trustLabel }}」</text>
    </view>

    <view v-if="loading" class="empty">正在校准观星台……</view>
    <view v-else-if="!profile" class="empty">还没有画像——先去聊一次，花园才能开始认识你。</view>

    <view v-else class="body">
      <scroll-view class="topic-tabs" scroll-x :show-scrollbar="false">
        <view class="tab-row">
          <view
            v-for="topic in topics"
            :key="topic.key"
            class="topic-tab"
            :class="{ active: topic.key === selectedKey }"
            @tap="selectTopic(topic.key)"
          >
            <text class="tab-icon">{{ topic.icon }}</text>
            <text class="tab-name">{{ topic.shortName }}</text>
            <text v-if="topicMetric(topic).pending" class="tab-dot"></text>
          </view>
        </view>
      </scroll-view>

      <view class="topic-card">
        <view class="topic-top">
          <view class="topic-orb"><text>{{ selectedTopic.icon }}</text></view>
          <view class="topic-main">
            <text class="topic-kicker">{{ v8TopicStatus(selectedTopic.status) }}</text>
            <text class="topic-name">{{ selectedTopic.name }}</text>
            <text class="topic-sub">{{ selectedTopic.sub }}</text>
          </view>
        </view>

        <text class="topic-intro">{{ selectedTopic.intro }}</text>

        <view class="metric-row">
          <view class="metric">
            <text class="metric-num">{{ selectedMetric.summaryCount }}</text>
            <text class="metric-label">沉淀线索</text>
          </view>
          <view class="metric">
            <text class="metric-num">{{ selectedMetric.pending }}</text>
            <text class="metric-label">待验证</text>
          </view>
          <view class="metric">
            <text class="metric-num">{{ selectedMetric.verified }}</text>
            <text class="metric-label">已确认</text>
          </view>
        </view>

        <view class="section-block">
          <text class="section-title">适合这样问</text>
          <view class="ask-list">
            <view v-for="q in selectedTopic.askSamples" :key="q" class="ask-chip" @tap="startChat(q)">
              <text>{{ q }}</text>
            </view>
          </view>
        </view>

        <view class="section-block custom-ask">
          <text class="section-title">也可以写下你的真实问题</text>
          <view class="custom-row">
            <input
              v-model="customQuestion"
              class="custom-input"
              confirm-type="send"
              placeholder="例如：母亲关系怎样影响我的事业？"
              @confirm="startCustomChat"
            />
            <button class="custom-send" @tap="startCustomChat">提问</button>
          </view>
          <text class="custom-hint">入口主题只作上下文；如果问题跨到家庭、关系或财富，后端会重新识别。</text>
        </view>

        <view class="section-block">
          <text class="section-title">证据链会看</text>
          <view class="evidence-list">
            <text v-for="e in selectedTopic.evidence" :key="e" class="evidence-item">· {{ e }}</text>
          </view>
        </view>

        <view class="action-row">
          <button class="primary-action" @tap="startChat(selectedTopic.chatSeed)">{{ selectedTopic.cta }}</button>
          <button class="ghost-action" @tap="openReportAction">{{ selectedTopic.reportType === 'life_rhythm' ? '查看人生章节' : '整理成报告' }}</button>
        </view>
      </view>

      <view v-if="selectedSummary" class="summary-card">
        <view class="summary-head">
          <text class="summary-title">已有领域摘要</text>
          <text class="summary-conf">{{ Math.round(selectedSummary.confidence * 100) }}% 把握</text>
        </view>
        <text class="summary-text">{{ selectedSummary.summary }}</text>
        <view v-if="selectedSummary.evidence_notes.length" class="summary-notes">
          <text v-for="(n, i) in selectedSummary.evidence_notes" :key="i" class="summary-note">· {{ n }}</text>
        </view>
      </view>

      <view class="findings-card">
        <view class="findings-head">
          <text class="findings-title">相关沉淀判断</text>
          <text class="findings-sub">{{ filteredFindings.length ? `${filteredFindings.length} 条` : '暂时没有' }}</text>
        </view>

        <view v-if="filteredFindings.length" class="finding-list">
          <view v-for="f in filteredFindings" :key="f.id" class="finding" :class="f.status">
            <view class="finding-top">
              <text class="finding-tag">{{ f.status === 'verified' ? '已校准' : '待校准' }}</text>
              <text class="finding-conf">{{ Math.round(f.confidence * 100) }}%</text>
            </view>
            <text class="finding-statement">{{ f.statement }}</text>
            <view v-if="f.verification_notes?.length" class="finding-notes">
              <text v-for="(n, i) in f.verification_notes.slice(0, 2)" :key="i" class="finding-note">· {{ n }}</text>
            </view>
            <view v-if="f.status === 'unverified'" class="finding-actions">
              <button class="finding-btn yes" :disabled="verifyingId === f.id" @tap.stop="verify(f, 'confirmed')">✓ 对上了</button>
              <button class="finding-btn no" :disabled="verifyingId === f.id" @tap.stop="verify(f, 'refuted')">✕ 不准确</button>
            </view>
            <text v-else class="finding-status">{{ f.feedback === 'confirmed' ? '✓ 已确认' : f.feedback === 'refuted' ? '✕ 已修正' : '⚡ 事件验证' }}</text>
          </view>
        </view>

        <view v-else class="empty-soft">
          <text class="empty-soft-title">这片主题还在等第一条证据</text>
          <text class="empty-soft-copy">从一次具体提问开始，星灵会把真正对上的理解沉淀下来。</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import api, { ApiError, type DomainSummaryOut, type FindingOut, type ProfileOut } from "@/api/client";
import { useTimePhase } from "@/utils/timeTheme";
import { V8_OBSERVATORY_TOPICS, v8TopicStatus, type V8ObservatoryTopic } from "@/utils/v8Copy";

import { clearAccountCache, requireSelfPersonId } from "@/utils/account";

const loading = ref(true);
const profile = ref<ProfileOut | null>(null);
const trustLabel = ref("");
const findings = ref<FindingOut[]>([]);
const pid = ref("");
const selectedKey = ref<string>(V8_OBSERVATORY_TOPICS[0].key);
const customQuestion = ref("");
const verifyingId = ref("");
const { phaseClass, refreshPhase } = useTimePhase();

const TRUST_ZH: Record<string, string> = {
  stranger: "陌生",
  acquaintance: "认识",
  trusted: "信任",
  intimate: "深交",
};

const topics = V8_OBSERVATORY_TOPICS;

const selectedTopic = computed(() => topics.find((t) => t.key === selectedKey.value) || topics[0]);

const selectedSummary = computed<DomainSummaryOut | null>(() => {
  const domain = selectedTopic.value.domain;
  if (!domain || !profile.value) return null;
  return profile.value.domain_summaries?.[domain] || null;
});

const filteredFindings = computed(() => {
  const domain = selectedTopic.value.domain;
  if (!domain) return findings.value;
  return findings.value.filter((f) => f.domain === domain);
});

const selectedMetric = computed(() => topicMetric(selectedTopic.value));

function topicMetric(topic: V8ObservatoryTopic) {
  const topicFindings = topic.domain ? findings.value.filter((f) => f.domain === topic.domain) : findings.value;
  const summaryCount = topic.domain && profile.value?.domain_summaries?.[topic.domain] ? 1 : 0;
  return {
    summaryCount,
    pending: topicFindings.filter((f) => f.status === "unverified").length,
    verified: topicFindings.filter((f) => f.status === "verified").length,
  };
}

async function loadFindings() {
  try {
    findings.value = await api.findings(pid.value);
  } catch {
    findings.value = [];
  }
}

async function verify(f: FindingOut, feedback: "confirmed" | "refuted") {
  if (verifyingId.value) return;
  verifyingId.value = f.id;
  try {
    await api.feedbackFinding(pid.value, f.id, feedback);
    await loadFindings();
    uni.showToast({ title: feedback === "confirmed" ? "已确认这条理解" : "已记下修正", icon: "none" });
  } catch {
    uni.showToast({ title: "操作失败，请重试", icon: "none" });
  } finally {
    verifyingId.value = "";
  }
}

onLoad(async (query) => {
  refreshPhase();
  const requested = typeof query?.topic === "string" ? decodeURIComponent(query.topic) : "";
  if (requested && topics.some((t) => t.key === requested)) selectedKey.value = requested;

  const personId = await requireSelfPersonId();
  if (!personId) return;
  pid.value = personId;
  try {
    profile.value = await api.profile(personId);
    trustLabel.value = TRUST_ZH[profile.value.trust_level] || "";
  } catch (e: any) {
    if (e instanceof ApiError && e.status === 410) {
      clearAccountCache();
      uni.showToast({ title: "当前档案已无法解密，请重新登录建档", icon: "none" });
      return uni.redirectTo({ url: "/pages/auth/login" });
    }
    if (e?.status === 404) profile.value = null;
  } finally {
    loading.value = false;
  }
  await loadFindings();
});

function selectTopic(key: string) {
  selectedKey.value = key;
}

function startChat(seed: string) {
  const topic = selectedTopic.value;
  const params: Record<string, string> = {
    message: seed,
    entry_source: "observatory",
    entry_topic_key: topic.key,
    user_focus_text: seed,
  };
  if (topic.primaryTopic) params.primary_topic = topic.primaryTopic;
  if (topic.secondaryTopics?.length) params.secondary_topics = topic.secondaryTopics.join(",");
  if (topic.reportType) params.report_type = topic.reportType;
  if (topic.intentShape) params.intent_shape = topic.intentShape;

  const query = Object.entries(params)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join("&");
  uni.navigateTo({ url: `/pages/chat/chat?${query}` });
}

function startCustomChat() {
  const text = customQuestion.value.trim();
  if (!text) {
    uni.showToast({ title: "先写下你想问的问题", icon: "none" });
    return;
  }
  customQuestion.value = "";
  startChat(text);
}

function openReportAction() {
  if (selectedTopic.value.reportType === "life_rhythm") {
    uni.navigateTo({ url: "/pages/universe/life-rhythm" });
    return;
  }
  reportComingSoon();
}

function reportComingSoon() {
  uni.showToast({ title: "报告编译器后续接入，不会前端伪造结论", icon: "none" });
}

function goBack() {
  uni.navigateBack();
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: radial-gradient(circle at 76% 8%, rgba(240, 210, 139, 0.14), transparent 30%), linear-gradient(180deg, #0d1f1a 0%, #14332a 60%, #1d4436 100%);
  padding: 0 36rpx 64rpx;
  box-sizing: border-box;
  color: #eef1ea;
  position: relative;
  overflow: hidden;
}
.cosmos-glow { position: absolute; width: 560rpx; height: 560rpx; border-radius: 50%; right: -180rpx; top: 180rpx; background: rgba(154, 205, 186, 0.12); filter: blur(60rpx); pointer-events: none; }

.navbar {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  padding: 24rpx 0;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.06);
  margin-bottom: 8rpx;
}
.nav-back { color: #e8f5e9; font-size: 52rpx; width: 60rpx; line-height: 1; }
.nav-title { flex: 1; text-align: center; color: #e8f5e9; font-size: 32rpx; font-weight: 600; }
.nav-right { width: 60rpx; }

.head { position: relative; z-index: 2; margin: 30rpx 0 28rpx; }
.eyebrow { display: block; font-size: 19rpx; letter-spacing: 0.16em; color: rgba(240, 210, 139, 0.66); font-weight: 800; }
.title { display: block; margin-top: 14rpx; font-family: Georgia, "Noto Serif SC", serif; color: #fff7e7; font-size: 43rpx; font-weight: 600; line-height: 1.28; }
.sub { color: rgba(232, 245, 233, 0.56); font-size: 24rpx; margin-top: 14rpx; line-height: 1.7; display: block; }
.trust-line { color: #a5d6a7; font-size: 23rpx; margin-top: 12rpx; display: block; }
.body { position: relative; z-index: 2; }
.empty { position: relative; z-index: 2; color: rgba(232, 245, 233, 0.6); font-size: 28rpx; text-align: center; padding: 100rpx 0; }

.topic-tabs { margin: 0 -36rpx 22rpx; padding: 0 0 2rpx; white-space: nowrap; }
.tab-row { display: inline-flex; gap: 14rpx; padding: 0 36rpx; }
.topic-tab { position: relative; display: inline-flex; align-items: center; gap: 9rpx; padding: 16rpx 22rpx; border-radius: 999rpx; background: rgba(255, 255, 255, 0.06); border: 1rpx solid rgba(255, 255, 255, 0.1); color: rgba(238, 241, 234, 0.7); }
.topic-tab.active { color: #19322a; background: linear-gradient(135deg, #f5df9f, #d6efc5); border-color: rgba(255, 247, 214, 0.7); box-shadow: 0 12rpx 36rpx rgba(240, 210, 139, 0.16); }
.tab-icon { font-size: 25rpx; }
.tab-name { font-size: 23rpx; font-weight: 700; }
.tab-dot { position: absolute; right: 8rpx; top: 6rpx; width: 12rpx; height: 12rpx; border-radius: 50%; background: #f0d28b; box-shadow: 0 0 16rpx rgba(240, 210, 139, 0.8); }
.topic-tab.active .tab-dot { background: #17362c; box-shadow: none; }

.topic-card, .summary-card, .findings-card {
  border-radius: 34rpx;
  padding: 30rpx 26rpx;
  background: rgba(255, 255, 255, 0.065);
  border: 1rpx solid rgba(185, 200, 189, 0.16);
  box-shadow: 0 22rpx 70rpx rgba(0, 0, 0, 0.12);
  margin-bottom: 22rpx;
}
.topic-top { display: flex; gap: 22rpx; align-items: center; }
.topic-orb { width: 92rpx; height: 92rpx; flex-shrink: 0; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: radial-gradient(circle at 35% 28%, #fff7dc, #d2b86f 56%, #426765); box-shadow: 0 0 52rpx rgba(240, 210, 139, 0.22); color: #17362c; font-size: 38rpx; }
.topic-main { flex: 1; min-width: 0; }
.topic-kicker { display: inline-flex; width: fit-content; padding: 7rpx 14rpx; border-radius: 999rpx; background: rgba(240, 210, 139, 0.12); color: #f0d28b; font-size: 19rpx; font-weight: 700; }
.topic-name { display: block; margin-top: 12rpx; font-family: Georgia, "Noto Serif SC", serif; font-size: 34rpx; font-weight: 600; color: #fff7e7; }
.topic-sub { display: block; margin-top: 7rpx; color: rgba(238, 241, 234, 0.48); font-size: 21rpx; line-height: 1.45; }
.topic-intro { display: block; margin-top: 24rpx; color: rgba(238, 241, 234, 0.76); font-size: 25rpx; line-height: 1.75; }

.metric-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14rpx; margin-top: 24rpx; }
.metric { border-radius: 24rpx; padding: 20rpx 12rpx; text-align: center; background: rgba(8, 22, 19, 0.26); border: 1rpx solid rgba(255, 255, 255, 0.07); }
.metric-num { display: block; color: #f5df9f; font-size: 34rpx; font-weight: 800; }
.metric-label { display: block; margin-top: 5rpx; color: rgba(238, 241, 234, 0.46); font-size: 19rpx; }

.section-block { margin-top: 26rpx; }
.section-title { display: block; color: rgba(240, 210, 139, 0.82); font-size: 22rpx; font-weight: 800; }
.ask-list { display: flex; flex-wrap: wrap; gap: 12rpx; margin-top: 14rpx; }
.ask-chip { padding: 13rpx 18rpx; border-radius: 999rpx; background: rgba(255, 255, 255, 0.07); border: 1rpx solid rgba(255, 255, 255, 0.1); color: rgba(238, 241, 234, 0.78); font-size: 21rpx; }
.ask-chip:active { background: rgba(240, 210, 139, 0.12); }
.custom-ask { padding: 22rpx; border-radius: 28rpx; background: rgba(8, 22, 19, 0.24); border: 1rpx solid rgba(240, 210, 139, 0.12); }
.custom-row { display: flex; align-items: center; gap: 12rpx; margin-top: 14rpx; }
.custom-input { flex: 1; min-height: 72rpx; border-radius: 999rpx; padding: 0 24rpx; background: rgba(255, 255, 255, 0.08); color: #eef1ea; font-size: 23rpx; }
.custom-send { margin: 0; min-width: 112rpx; height: 72rpx; line-height: 72rpx; border-radius: 999rpx; background: rgba(240, 210, 139, 0.18); color: #f8e2a7; font-size: 22rpx; padding: 0 20rpx; }
.custom-send::after { border: 0; }
.custom-hint { display: block; margin-top: 12rpx; color: rgba(238, 241, 234, 0.46); font-size: 20rpx; line-height: 1.55; }
.evidence-list { display: grid; gap: 9rpx; margin-top: 14rpx; }
.evidence-item { color: rgba(238, 241, 234, 0.58); font-size: 22rpx; line-height: 1.6; }
.action-row { display: grid; grid-template-columns: 1.15fr 0.85fr; gap: 14rpx; margin-top: 28rpx; }
.primary-action, .ghost-action { margin: 0; border-radius: 999rpx; padding: 20rpx 0; font-size: 23rpx; line-height: 1.2; }
.primary-action::after, .ghost-action::after { border: 0; }
.primary-action { background: linear-gradient(135deg, #f5df9f, #d6efc5); color: #17362c; font-weight: 800; }
.ghost-action { background: rgba(255, 255, 255, 0.055); color: rgba(238, 241, 234, 0.68); border: 1rpx solid rgba(255, 255, 255, 0.1); }

.summary-head, .findings-head { display: flex; justify-content: space-between; gap: 16rpx; align-items: center; }
.summary-title, .findings-title { color: #f0d28b; font-size: 25rpx; font-weight: 800; }
.summary-conf, .findings-sub { color: rgba(238, 241, 234, 0.48); font-size: 20rpx; }
.summary-text { display: block; margin-top: 16rpx; color: #e8f5e9; font-size: 25rpx; line-height: 1.75; }
.summary-notes { display: grid; gap: 8rpx; margin-top: 14rpx; }
.summary-note { color: rgba(232, 245, 233, 0.56); font-size: 21rpx; line-height: 1.6; }

.finding-list { display: grid; gap: 16rpx; margin-top: 22rpx; }
.finding { padding: 24rpx; border-radius: 28rpx; background: rgba(8, 22, 19, 0.34); border: 1rpx solid rgba(240, 210, 139, 0.12); }
.finding.verified { border-color: rgba(165, 214, 167, 0.14); }
.finding-top { display: flex; justify-content: space-between; align-items: center; gap: 16rpx; }
.finding-tag { color: #f0d28b; font-size: 20rpx; font-weight: 700; }
.finding-conf { color: rgba(238, 241, 234, 0.48); font-size: 19rpx; }
.finding-statement { display: block; margin-top: 15rpx; color: #fff7e7; font-size: 24rpx; line-height: 1.7; }
.finding-notes { display: grid; gap: 8rpx; margin-top: 13rpx; }
.finding-note { color: rgba(238, 241, 234, 0.5); font-size: 20rpx; line-height: 1.6; }
.finding-actions { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14rpx; margin-top: 19rpx; }
.finding-btn { margin: 0; padding: 17rpx 0; border-radius: 999rpx; font-size: 22rpx; line-height: 1.2; border: 1rpx solid rgba(255, 255, 255, 0.12); }
.finding-btn::after { border: 0; }
.finding-btn.yes { background: rgba(240, 210, 139, 0.16); color: #f8e2a7; }
.finding-btn.no { background: rgba(255, 255, 255, 0.055); color: rgba(238, 241, 234, 0.68); }
.finding-status { display: block; margin-top: 13rpx; color: rgba(165, 214, 167, 0.72); font-size: 20rpx; }
.empty-soft { margin-top: 22rpx; padding: 28rpx; border-radius: 26rpx; background: rgba(255, 255, 255, 0.045); border: 1rpx dashed rgba(238, 241, 234, 0.12); }
.empty-soft-title { display: block; color: #eef1ea; font-size: 24rpx; font-weight: 650; }
.empty-soft-copy { display: block; margin-top: 10rpx; color: rgba(238, 241, 234, 0.5); font-size: 21rpx; line-height: 1.6; }
</style>
