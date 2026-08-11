<template>
  <view class="page">
    <view class="sky">
      <text class="moon">🌙</text>
      <text class="title">星灵花园</text>
      <text class="subtitle">一座持续理解你、陪伴你成长的花园</text>
    </view>

    <view v-if="!creating" class="form">
      <view class="field">
        <text class="label">你的名字</text>
        <input v-model="form.name" class="input" placeholder="怎么称呼你？" />
      </view>

      <view class="field">
        <text class="label">出生日期</text>
        <picker mode="date" :value="form.date" @change="onDate">
          <view class="input picker">{{ form.date || '选择日期' }}</view>
        </picker>
      </view>

      <view class="field">
        <text class="label">出生时间</text>
        <picker mode="time" :value="form.time" :disabled="form.time_unknown" @change="onTime">
          <view class="input picker">{{ form.time || '选择时间（分钟精度）' }}</view>
        </picker>
      </view>

      <view class="field unknown-row" @tap="form.time_unknown = !form.time_unknown">
        <text class="unknown-text">{{ form.time_unknown ? '☑' : '☐' }} 不知道准确出生时间</text>
      </view>

      <view class="field">
        <text class="label">出生城市（选填）</text>
        <input v-model="form.city" class="input" placeholder="默认上海" />
      </view>

      <button class="enter-btn" :disabled="busy" @tap="enterGarden">
        {{ busy ? '正在播种……' : '走进花园' }}
      </button>
      <text v-if="error" class="error">{{ error }}</text>
    </view>

    <view v-else class="garden">
      <text class="ok">🌱 欢迎回来，{{ savedName }}</text>

      <!-- 站内"回家看看"兜底（推送后置）：首页即回家枢纽，把今日值得回来的都摆出来 -->
      <view v-if="gardenState" class="g-card today">
        <text class="g-label">今日 · {{ gardenState.today }}</text>
        <text class="g-letter-title">{{ gardenState.letter?.title || '一封来信' }}</text>
        <text class="g-letter-body">{{ (gardenState.letter?.body || '').slice(0, 60) }}…</text>
      </view>

      <view v-if="gardenState?.soul_fragments?.length" class="g-card frag">
        <text class="g-label">◈ 今日灵魂碎片</text>
        <text class="g-frags">{{ gardenState.soul_fragments.map((f: SoulFragmentOut) => f.name).join(' / ') }}</text>
      </view>

      <view v-if="gardenState?.continue_from" class="g-card">
        <text class="g-label">继续昨天的话题</text>
        <text class="g-summary">{{ (gardenState.continue_from.summary || '').slice(0, 50) }}…</text>
      </view>

      <view v-if="gardenState?.domains?.length" class="g-card">
        <text class="g-label">我的宇宙 · {{ gardenState.domains.length }} 个领域已有理解</text>
        <text class="g-summary">{{ gardenState.domains.map(domainZh).join(' / ') }}</text>
      </view>

      <view class="trust-row">
        <text v-if="gardenState?.trust_level" class="trust-chip">{{ trustZh(gardenState.trust_level) }}</text>
      </view>

      <button class="enter-btn" @tap="goChat">和星灵聊聊 →</button>
      <!-- 首页红点细粒度：信箱=今日来信未读；我的宇宙=有待验证判断 -->
      <view class="nav-row">
        <view class="nav-link" @tap="goMailbox">
          <text>💌 信箱</text>
          <text v-if="gardenState?.letter_unread" class="nav-badge"></text>
        </view>
        <view class="nav-link" @tap="goUniverse">
          <text>🪐 我的宇宙</text>
          <text v-if="(gardenState?.pending_verifications ?? 0) > 0" class="nav-badge"></text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import api, { type SoulFragmentOut } from "@/api/client";
import { subscribePush } from "@/utils/push";

const form = reactive({
  name: "",
  date: "",
  time: "",
  city: "",
  time_unknown: false,
});
const busy = ref(false);
const error = ref("");
const creating = ref(false);
const savedName = ref("");
const gardenState = ref<any>(null);

const PERSON_KEY = "gs_person_id";
const SESSION_KEY = "gs_session_id";
// Web Push：只主动请求一次权限（浏览器会记住结果，后续不再弹）
const PUSH_ASKED_KEY = "gs_push_asked";

const DOMAIN_ZH: Record<string, string> = {
  career: "事业", relationship: "感情", wealth: "财富", health: "健康",
  emotion: "情绪", family: "家庭", learning: "学习", daily: "今日",
};
function domainZh(d: string) {
  return DOMAIN_ZH[d] || d;
}

// 信任等级（A2 关系层）中文标签
const TRUST_ZH: Record<string, string> = {
  stranger: "初遇 · 陌生",
  acquaintance: "相识 · 认识",
  trusted: "信任 · 知心",
  intimate: "深交 · 知己",
};
function trustZh(level: string) {
  return TRUST_ZH[level] || level;
}

onShow(async () => {
  const pid = uni.getStorageSync(PERSON_KEY) as string;
  if (pid) {
    creating.value = true;
    try {
      const p = await api.getPerson(pid);
      savedName.value = p.name;
      gardenState.value = await api.garden(pid);
    } catch {
      // 画像/花园状态拉不到 → 至少还能进聊天
    }
    maybeSubscribePush(pid);
  }
});

// Web Push：延迟触发订阅（推送是增强能力，失败安静返回，绝不打断主页流程）。
// 只主动请求一次权限；granted → 直接订阅，denied/default → 不再打扰。
function maybeSubscribePush(pid: string) {
  if (uni.getStorageSync(PUSH_ASKED_KEY)) return;
  setTimeout(async () => {
    const ok = await subscribePush(pid);
    if (ok || (typeof Notification !== "undefined" && Notification.permission !== "default")) {
      uni.setStorageSync(PUSH_ASKED_KEY, true);
    }
  }, 1500);
}

function onDate(e: any) {
  form.date = e.detail.value;
}
function onTime(e: any) {
  form.time = e.detail.value;
}

async function enterGarden() {
  if (!form.name.trim()) return (error.value = "先告诉花园你的名字");
  if (!form.date) return (error.value = "需要出生日期");
  if (!form.time_unknown && !form.time) return (error.value = "需要出生时间（越精确越好）");
  busy.value = true;
  error.value = "";
  try {
    const city = form.city.trim() || "上海";
    // 本地墙钟时间 + 城市名 → 后端 geocode 解析经纬度/时区并换算 UTC
    const time = form.time_unknown ? "12:00" : form.time;
    const person = await api.createPerson({
      name: form.name.trim(),
      birth: {
        datetime_local: `${form.date}T${time}:00`,
        location: { place_name: city },
        time_known: !form.time_unknown,
      },
    });
    uni.setStorageSync(PERSON_KEY, person.id);
    uni.removeStorageSync(SESSION_KEY); // 新用户新会话
    savedName.value = person.name;
    creating.value = true;
    maybeSubscribePush(person.id);
  } catch (e: any) {
    error.value = e.message || "建档失败";
  } finally {
    busy.value = false;
  }
}

function goChat() {
  uni.navigateTo({ url: "/pages/chat/chat" });
}
function goMailbox() {
  uni.navigateTo({ url: "/pages/mailbox/mailbox" });
}
function goUniverse() {
  uni.navigateTo({ url: "/pages/universe/universe" });
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: linear-gradient(180deg, #0d1f1a 0%, #14332a 55%, #1d4436 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60rpx 48rpx;
  box-sizing: border-box;
}
.sky {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin: 80rpx 0 60rpx;
}
.moon {
  font-size: 72rpx;
  margin-bottom: 24rpx;
}
.title {
  color: #e8f5e9;
  font-size: 52rpx;
  font-weight: 600;
  letter-spacing: 8rpx;
}
.subtitle {
  color: rgba(232, 245, 233, 0.6);
  font-size: 26rpx;
  margin-top: 16rpx;
}
.form {
  width: 100%;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 24rpx;
  padding: 40rpx 36rpx;
  box-sizing: border-box;
}
.field {
  margin-bottom: 28rpx;
}
.label {
  color: rgba(232, 245, 233, 0.7);
  font-size: 24rpx;
  display: block;
  margin-bottom: 12rpx;
}
.input {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 14rpx;
  padding: 20rpx 24rpx;
  color: #e8f5e9;
  font-size: 30rpx;
}
.picker {
  display: flex;
  align-items: center;
}
.unknown-row {
  margin-bottom: 8rpx;
}
.unknown-text {
  color: rgba(232, 245, 233, 0.55);
  font-size: 26rpx;
}
.enter-btn {
  margin-top: 20rpx;
  background: #7cb342;
  color: #fff;
  font-size: 32rpx;
  border-radius: 14rpx;
}
.enter-btn[disabled] {
  opacity: 0.6;
}
.error {
  color: #ffb74d;
  font-size: 24rpx;
  margin-top: 20rpx;
  display: block;
}
.ok {
  color: #e8f5e9;
  font-size: 30rpx;
  display: block;
  text-align: center;
  margin-bottom: 24rpx;
}
.garden {
  width: 100%;
}
.g-card {
  background: rgba(255, 255, 255, 0.07);
  border-radius: 20rpx;
  padding: 26rpx 28rpx;
  margin-bottom: 18rpx;
}
/* 今日来信卡：视觉重心，比普通卡更"醒目"（回家看看的主入口） */
.g-card.today {
  background: rgba(124, 179, 66, 0.15);
  border: 1rpx solid rgba(124, 179, 66, 0.4);
}
/* 今日灵魂碎片卡：金边数据卡（与信箱脚注同语言） */
.g-card.frag {
  border-left: 4rpx solid rgba(255, 224, 130, 0.5);
}
.g-label {
  color: rgba(232, 245, 233, 0.5);
  font-size: 22rpx;
  display: block;
  margin-bottom: 10rpx;
}
.g-frags {
  color: #ffe082;
  font-size: 26rpx;
  line-height: 1.6;
  display: block;
}
.trust-row {
  display: flex;
  justify-content: center;
  gap: 16rpx;
  flex-wrap: wrap;
  margin-bottom: 20rpx;
}
.trust-chip {
  color: rgba(232, 245, 233, 0.7);
  font-size: 24rpx;
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.18);
  border-radius: 999rpx;
  padding: 8rpx 24rpx;
}
.g-letter-title {
  color: #a5d6a7;
  font-size: 30rpx;
  font-weight: 600;
  display: block;
  margin-bottom: 6rpx;
}
.g-letter-body,
.g-summary {
  color: rgba(232, 245, 233, 0.75);
  font-size: 26rpx;
  line-height: 1.6;
  display: block;
}
.nav-row {
  display: flex;
  justify-content: space-around;
  margin-top: 32rpx;
}
.nav-link {
  position: relative;   /* 红点绝对定位的锚点 */
  display: flex;
  align-items: center;
  color: rgba(232, 245, 233, 0.8);
  font-size: 30rpx;
  padding: 16rpx 0;
}
/* 首页红点细粒度：新消息/待办的小红点，无文字 */
.nav-badge {
  position: absolute;
  top: 4rpx;
  right: -18rpx;
  width: 12rpx;
  height: 12rpx;
  background: #ef5350;
  border-radius: 50%;
  box-shadow: 0 0 8rpx rgba(239, 83, 80, 0.6);  /* 柔和发光，贴近花园星光辉 */
}
</style>
