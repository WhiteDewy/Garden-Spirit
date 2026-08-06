<template>
  <view class="page">
    <view class="head">
      <text class="title">🪐 我的宇宙</text>
      <text class="sub">花园对你的长期理解</text>
      <text v-if="trustLabel" class="trust-line">🌱 你们已是「{{ trustLabel }}」</text>
    </view>

    <view v-if="loading" class="empty">正在翻开你的宇宙……</view>
    <view v-else-if="!profile" class="empty">还没有画像——先去聊一次，花园才能开始认识你。</view>

    <view v-else>
      <view v-for="(ds, domain) in profile.domain_summaries" :key="domain" class="card">
        <view class="card-head">
          <text class="card-title">{{ domainZh(domain) }}</text>
          <text class="card-conf">{{ Math.round(ds.confidence * 100) }}% 把握</text>
        </view>
        <text class="card-summary">{{ ds.summary }}</text>
        <view v-if="ds.evidence_notes.length" class="card-notes">
          <text v-for="(n, i) in ds.evidence_notes" :key="i" class="note">· {{ n }}</text>
        </view>
      </view>

    <view v-if="findings.length" class="card">
      <text class="card-title">沉淀的判断</text>
      <text class="card-sub">{{ pendingFindings.length }} 条待验证 · {{ verifiedFindings.length }} 条已验证</text>

      <view v-for="f in pendingFindings" :key="f.id" class="finding">
        <text class="note">{{ f.statement }}</text>
        <view class="finding-meta">
          <text class="finding-conf">{{ Math.round(f.confidence * 100) }}%</text>
          <text v-if="f.domain" class="finding-domain">{{ domainZh(f.domain) }}</text>
        </view>
        <view class="btn-row">
          <text class="btn yes" @tap="verify(f, 'confirmed')">✓ 对上了</text>
          <text class="btn no" @tap="verify(f, 'refuted')">✗ 不对</text>
        </view>
      </view>

      <view v-if="verifiedFindings.length">
        <text class="sub-note">已验证</text>
        <view v-for="f in verifiedFindings" :key="f.id" class="finding verified">
          <text class="note">{{ f.statement }}</text>
          <text class="finding-status">{{
            f.feedback === 'confirmed' ? '✓ 已确认' : f.feedback === 'refuted' ? '✗ 已反驳' : '⚡ 事件已验证'
          }}</text>
        </view>
      </view>
    </view>
    </view>

    <button class="back" @tap="goChat">和星灵聊聊 →</button>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import api, { type FindingOut, type ProfileOut } from "@/api/client";

const PERSON_KEY = "gs_person_id";
const loading = ref(true);
const profile = ref<ProfileOut | null>(null);
const trustLabel = ref("");
const findings = ref<FindingOut[]>([]);
const pid = ref("");

const TRUST_ZH: Record<string, string> = {
  stranger: "陌生",
  acquaintance: "认识",
  trusted: "信任",
  intimate: "深交",
};

const pendingFindings = computed(() => findings.value.filter((f) => f.status === "unverified"));
const verifiedFindings = computed(() => findings.value.filter((f) => f.status === "verified"));

async function loadFindings() {
  try {
    findings.value = await api.findings(pid.value);
  } catch {
    findings.value = [];
  }
}

async function verify(f: FindingOut, feedback: "confirmed" | "refuted") {
  try {
    await api.feedbackFinding(pid.value, f.id, feedback);
    await loadFindings(); // 验证后刷新清单
  } catch {
    uni.showToast({ title: "操作失败，请重试", icon: "none" });
  }
}

onLoad(async () => {
  const personId = uni.getStorageSync(PERSON_KEY) as string;
  if (!personId) return uni.redirectTo({ url: "/pages/index/index" });
  pid.value = personId;
  try {
    profile.value = await api.profile(personId);
    trustLabel.value = TRUST_ZH[profile.value.trust_level] || "";
  } catch (e: any) {
    if (e.status === 404) profile.value = null; // 尚无画像
  } finally {
    loading.value = false;
  }
  await loadFindings();
});

const DOMAIN_ZH: Record<string, string> = {
  career: "事业", relationship: "感情", wealth: "财富", health: "健康",
  emotion: "情绪", family: "家庭", learning: "学习", daily: "今日",
};
function domainZh(d: string) {
  return DOMAIN_ZH[d] || d;
}

function goChat() {
  uni.navigateTo({ url: "/pages/chat/chat" });
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: linear-gradient(180deg, #0d1f1a 0%, #14332a 60%, #1d4436 100%);
  padding: 48rpx 36rpx;
  box-sizing: border-box;
}
.head { margin-bottom: 32rpx; }
.title { color: #e8f5e9; font-size: 44rpx; font-weight: 600; }
.sub { color: rgba(232,245,233,.55); font-size: 26rpx; margin-top: 8rpx; display: block; }
.trust-line { color: #a5d6a7; font-size: 24rpx; margin-top: 10rpx; display: block; }
.card {
  background: rgba(255,255,255,.07);
  border-radius: 20rpx;
  padding: 28rpx;
  margin-bottom: 20rpx;
}
.card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12rpx; }
.card-title { color: #a5d6a7; font-size: 30rpx; font-weight: 600; }
.card-conf { color: rgba(232,245,233,.5); font-size: 22rpx; }
.card-summary { color: #e8f5e9; font-size: 28rpx; line-height: 1.7; }
.card-notes { margin-top: 12rpx; }
.note { color: rgba(232,245,233,.65); font-size: 24rpx; line-height: 1.6; display: block; }
.empty { color: rgba(232,245,233,.6); font-size: 28rpx; text-align: center; padding: 100rpx 0; }
.card-sub { color: rgba(232,245,233,.5); font-size: 22rpx; display: block; margin-top: 6rpx; margin-bottom: 12rpx; }
.finding { padding: 16rpx 0; border-top: 1rpx solid rgba(255,255,255,.06); }
.finding-meta { display: flex; align-items: center; gap: 12rpx; margin-top: 6rpx; }
.finding-conf { color: rgba(232,245,233,.5); font-size: 22rpx; }
.finding-domain { color: #a5d6a7; font-size: 22rpx; }
.btn-row { display: flex; gap: 16rpx; margin-top: 12rpx; }
.btn { font-size: 24rpx; padding: 8rpx 22rpx; border-radius: 10rpx; }
.btn.yes { background: rgba(124,179,66,.25); color: #a5d6a7; }
.btn.no { background: rgba(255,179,77,.15); color: #ffb74d; }
.sub-note { color: rgba(232,245,233,.4); font-size: 22rpx; display: block; margin: 20rpx 0 8rpx; }
.finding.verified .note { color: rgba(232,245,233,.55); }
.finding-status { color: rgba(232,245,233,.45); font-size: 22rpx; display: block; margin-top: 6rpx; }
.back { margin-top: 20rpx; background: #7cb342; color: #fff; border-radius: 14rpx; }
</style>
