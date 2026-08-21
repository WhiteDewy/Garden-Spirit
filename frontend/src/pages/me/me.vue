<template>
  <view class="page gs-time-page" :class="phaseClass">
    <view class="me-glow" aria-hidden="true"></view>

    <view class="head">
      <view>
        <text class="eyebrow">MY INNER GARDEN</text>
        <text class="title">我的</text>
      </view>
    </view>

    <view class="profile-shell">
      <view class="profile-avatar"><SpiritPortrait :planet="residentSpirit.planet" /></view>
      <view class="profile-copy">
        <text class="profile-name">{{ person?.name || '我的花园' }}</text>
        <text class="profile-bio">{{ bioLine }}</text>
      </view>
    </view>

    <view class="resident-card">
      <view class="resident-main">
        <text class="card-kicker">RESIDENT SPIRIT · 常驻星灵</text>
        <text class="resident-name">{{ residentSpirit.name }}</text>
        <text class="resident-line">{{ residentSpirit.line }}</text>
      </view>
      <view v-if="residentSpirit.isPreferredOverride" class="today-note">
        <text>今日推荐仍在背景里：{{ residentSpirit.todayRecommendation?.healing_name || residentSpirit.todayRecommendation?.name }}</text>
      </view>
    </view>

    <view class="stat-row">
      <view class="stat"><text class="stat-num">{{ days }}</text><text class="stat-label">陪伴天数</text></view>
      <view class="stat"><text class="stat-num">{{ litCount }}</text><text class="stat-label">点亮碎片</text></view>
      <view class="stat"><text class="stat-num">{{ pendingCount }}</text><text class="stat-label">待验证</text></view>
    </view>

    <text class="section-label">SPIRIT RELATIONSHIP · 选择陪你的星灵</text>
    <view class="spirit-list">
      <view
        v-for="s in spirits"
        :key="s.planet"
        :class="['spirit-card', { today: s.today, preferred: s.preferred }]"
        @tap="chooseSpirit(s.planet)"
      >
        <view class="tiny-orb"><SpiritPortrait :planet="s.planet" /></view>
        <view class="spirit-card-copy">
          <text class="spirit-card-name">{{ s.name }}</text>
          <text class="spirit-card-sub">{{ s.healing }}</text>
          <text v-if="s.preferred" class="today-tag preferred-tag">常驻星灵</text>
          <text v-else-if="s.today" class="today-tag">今日推荐</text>
        </view>
      </view>
    </view>

    <text class="section-label">GROWTH · 我的成长</text>
    <view class="growth-grid">
      <view class="growth-card" @tap="goUniverse">
        <text class="growth-num">{{ litCount }}/{{ totalFragments }}</text>
        <text class="growth-title">自我星盘轮</text>
        <text class="growth-desc">看见已经被点亮的内在角落</text>
      </view>
      <view class="growth-card" @tap="goConsult">
        <text class="growth-num">{{ findingCount }}</text>
        <text class="growth-title">沉淀判断</text>
        <text class="growth-desc">{{ pendingCount ? `还有 ${pendingCount} 条需要验证` : '暂时没有待验证判断' }}</text>
      </view>
    </view>

    <text class="section-label">GARDEN RIGHTS · 权益与关系</text>
    <view class="rights-grid">
      <view class="right-card" @tap="vipComingSoon">
        <text class="right-icon">✺</text>
        <text class="right-title">VIP 花园权益</text>
        <text class="right-desc">后续承接会员、报告资产权益和专属复盘</text>
      </view>
      <view class="right-card" @tap="inviteComingSoon">
        <text class="right-icon">✿</text>
        <text class="right-title">邀请有礼</text>
        <text class="right-desc">把花园分享给重要的人</text>
      </view>
    </view>

    <text class="section-label">TRUST · 数据与安全</text>
    <view class="settings">
      <view class="setting" @tap="goMailbox"><view><text class="setting-title">我的信箱与手账</text><text class="setting-sub">查看来信、记忆词条和自己写下的时刻</text></view><text class="arrow">→</text></view>
      <view class="setting" @tap="goLifeRhythm"><view><text class="setting-title">人生章节报告</text><text class="setting-sub">查看 Life Rhythm：本命承诺、法达章节和未来触发窗口</text></view><text class="arrow">→</text></view>
      <view class="setting" @tap="reportsComingSoon"><view><text class="setting-title">已生成资产</text><text class="setting-sub">后续存放报告编译器生成的复盘与结构化资产</text></view><text class="arrow">→</text></view>
      <view class="setting" @tap="goPrivacy"><view><text class="setting-title">推送偏好</text><text class="setting-sub">管理今日来信、回家看看与复盘提醒</text></view><text class="arrow">→</text></view>
      <view class="setting" @tap="goPrivacy"><view><text class="setting-title">隐私与安全</text><text class="setting-sub">导出、删除和密钥安全说明</text></view><text class="arrow">→</text></view>
    </view>

    <BottomNav active="me" />
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import api, { ApiError, type PersonOut, type PersonaOut, type SpiritRecommendationOut } from "@/api/client";
import BottomNav from "@/components/BottomNav.vue";
import SpiritPortrait from "@/components/SpiritPortrait.vue";
import { selectSpirit } from "@/utils/spiritSelection";
import { useGardenBadges } from "@/utils/gardenBadges";
import { clearAccountCache, requireSelfPersonId } from "@/utils/account";
import { useTimePhase } from "@/utils/timeTheme";

const person = ref<PersonOut | null>(null);
const litCount = ref(0);
const totalFragments = ref(34);
const findingCount = ref(0);
const pendingCount = ref(0);
const preferredPersona = ref("");
const personaCatalog = ref<PersonaOut[]>([]);
const spiritCatalog = ref<SpiritRecommendationOut[]>([]);
const { phaseClass, refreshPhase } = useTimePhase();
const { refreshGardenBadges } = useGardenBadges();

const residentSpirit = computed(() => selectSpirit({
  preferredPersona: preferredPersona.value,
  recommendations: spiritCatalog.value,
  personas: personaCatalog.value,
}));

const todayPlanet = computed(() => spiritCatalog.value[0]?.planet?.toLowerCase() || "");

const spirits = computed(() => personaCatalog.value.map(s => {
  const planet = s.key.toLowerCase();
  return {
    planet,
    name: s.healing_name || s.name || "星灵",
    healing: s.style || "它会用自己的方式陪你理解自己。",
    today: planet === todayPlanet.value,
    preferred: planet === residentSpirit.value.planet,
  };
}));

const bioLine = computed(() => {
  if (!person.value) return "正在学着，更温柔地理解自己。";
  const place = person.value.place_name || "";
  return place ? `出生在 ${place} · 正在学着，更温柔地理解自己。` : "正在学着，更温柔地理解自己。";
});

const days = computed(() => {
  const created = person.value?.created_at;
  if (!created) return 1;
  const ms = Date.now() - new Date(created).getTime();
  return Math.max(1, Math.floor(ms / 86400000) + 1);
});

onShow(async () => {
  refreshPhase();
  const pid = await requireSelfPersonId();
  if (!pid) return;

  const [personRes, recRes, personasRes, prefsRes, fragRes, fidsRes] = await Promise.allSettled([
    api.getPerson(pid),
    api.recommendedSpirits(pid),
    api.personas(),
    api.getPreferences(pid),
    api.fragments(pid),
    api.findings(pid),
  ]);

  const expired = [personRes, recRes, prefsRes, fragRes, fidsRes].some(
    (r) => r.status === "rejected" && r.reason instanceof ApiError && r.reason.status === 410
  );
  if (expired) {
    clearAccountCache();
    uni.showToast({ title: "当前档案已无法解密，请重新建档", icon: "none" });
    return uni.redirectTo({ url: "/pages/index/index" });
  }

  if (personRes.status === "fulfilled") person.value = personRes.value;
  if (recRes.status === "fulfilled") spiritCatalog.value = recRes.value.spirits || [];
  else spiritCatalog.value = [];
  if (personasRes.status === "fulfilled") personaCatalog.value = personasRes.value || [];
  else personaCatalog.value = [];
  if (prefsRes.status === "fulfilled") preferredPersona.value = String(prefsRes.value.preferred_persona || "").toLowerCase();
  else preferredPersona.value = "";

  if (fragRes.status === "fulfilled") {
    totalFragments.value = fragRes.value.fragments.length || 34;
    litCount.value = fragRes.value.fragments.filter(f => f.depth > 0).length;
  }
  if (fidsRes.status === "fulfilled") {
    findingCount.value = fidsRes.value.length;
    pendingCount.value = fidsRes.value.filter(f => f.status === "unverified").length;
  }
  void refreshGardenBadges(pid, residentSpirit.value.planet);
});

async function chooseSpirit(planet: string) {
  const pid = await requireSelfPersonId();
  if (!pid || planet === preferredPersona.value) return;
  const previous = preferredPersona.value;
  preferredPersona.value = planet;
  try {
    const prefs = await api.updatePreferences(pid, { preferred_persona: planet });
    preferredPersona.value = String(prefs.preferred_persona || planet).toLowerCase();
    void refreshGardenBadges(pid, residentSpirit.value.planet);
    uni.showToast({ title: "已设为常驻星灵", icon: "none" });
  } catch (e: any) {
    preferredPersona.value = previous;
    uni.showToast({ title: e?.message || "暂时没设上，再试一次", icon: "none" });
  }
}

function goUniverse() {
  uni.navigateTo({ url: "/pages/universe/wheel" });
}
function goConsult() {
  uni.navigateTo({ url: "/pages/universe/consult" });
}
function goMailbox() {
  uni.reLaunch({ url: "/pages/mailbox/mailbox" });
}
function goLifeRhythm() {
  uni.navigateTo({ url: "/pages/universe/life-rhythm" });
}
function goPrivacy() {
  uni.navigateTo({ url: "/pages/me/privacy" });
}
function vipComingSoon() {
  uni.showToast({ title: "VIP 权益后续接入", icon: "none" });
}
function inviteComingSoon() {
  uni.showToast({ title: "邀请有礼后续开放", icon: "none" });
}
function reportsComingSoon() {
  uni.showToast({ title: "结构化资产后续接入", icon: "none" });
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: radial-gradient(circle at 82% 12%, rgba(240, 210, 139, 0.12), transparent 28%), linear-gradient(170deg, #17362c 0%, #10271f 55%, #081613 100%);
  padding: 48rpx 36rpx 170rpx;
  box-sizing: border-box;
  position: relative;
  color: #edf1e9;
}
.me-glow { position: absolute; width: 480rpx; height: 480rpx; border-radius: 50%; right: -200rpx; top: 100rpx; background: rgba(183, 164, 113, 0.12); filter: blur(60rpx); pointer-events: none; }
.head { position: relative; z-index: 1; }
.eyebrow { display: block; font-size: 19rpx; letter-spacing: 0.16em; color: rgba(235, 241, 233, 0.4); font-weight: 800; }
.title { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 52rpx; font-weight: 600; color: #edf1e9; margin-top: 6rpx; }

.profile-shell { display: flex; align-items: center; gap: 28rpx; padding: 26rpx 0 28rpx; position: relative; z-index: 1; }
.profile-avatar { width: 124rpx; height: 124rpx; flex-shrink: 0; border-radius: 50%; background: linear-gradient(145deg, #dfe5d8, #758d80); display: flex; align-items: center; justify-content: center; box-shadow: 0 0 70rpx rgba(210, 203, 164, 0.12); overflow: hidden; }
.profile-avatar :deep(.portrait) { width: 92%; height: 92%; }
.profile-name { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 40rpx; font-weight: 600; color: #edf1e9; }
.profile-bio { display: block; font-size: 22rpx; color: rgba(235, 241, 233, 0.5); margin-top: 12rpx; line-height: 1.6; max-width: 440rpx; }

.resident-card { position: relative; z-index: 1; padding: 34rpx 30rpx; border-radius: 34rpx; border: 1rpx solid rgba(240, 210, 139, 0.22); background: linear-gradient(145deg, rgba(240, 210, 139, 0.13), rgba(255, 255, 255, 0.045)); box-shadow: 0 24rpx 70rpx rgba(0, 0, 0, 0.12); }
.card-kicker { display: block; color: rgba(240, 210, 139, 0.72); font-size: 19rpx; letter-spacing: 0.14em; font-weight: 800; }
.resident-name { display: block; margin-top: 14rpx; font-family: Georgia, "Noto Serif SC", serif; font-size: 38rpx; font-weight: 600; color: #fff7e7; }
.resident-line { display: block; margin-top: 10rpx; color: rgba(255, 247, 231, 0.64); font-size: 24rpx; line-height: 1.7; }
.today-note { margin-top: 20rpx; padding: 16rpx 20rpx; border-radius: 20rpx; background: rgba(8, 22, 19, 0.24); color: rgba(255, 247, 231, 0.55); font-size: 21rpx; line-height: 1.6; }

.stat-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16rpx; margin-top: 22rpx; position: relative; z-index: 1; }
.stat { padding: 30rpx 22rpx; border: 1rpx solid rgba(255, 255, 255, 0.09); background: rgba(255, 255, 255, 0.05); border-radius: 28rpx; }
.stat-num { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 40rpx; font-weight: 600; color: #edf1e9; }
.stat-label { display: block; color: rgba(235, 241, 233, 0.43); font-size: 20rpx; margin-top: 8rpx; }

.section-label { display: block; font-size: 19rpx; letter-spacing: 0.16em; color: rgba(235, 241, 233, 0.4); margin: 44rpx 0 20rpx; position: relative; z-index: 1; }
.spirit-list { display: grid; grid-template-columns: repeat(2, 1fr); gap: 18rpx; position: relative; z-index: 1; }
.spirit-card { padding: 24rpx; border-radius: 30rpx; background: rgba(255, 255, 255, 0.05); border: 1rpx solid rgba(255, 255, 255, 0.08); display: flex; align-items: center; gap: 18rpx; min-height: 126rpx; }
.spirit-card.today { border-color: rgba(235, 216, 158, 0.4); background: rgba(235, 216, 158, 0.07); }
.spirit-card.preferred { border-color: rgba(240, 210, 139, 0.72); background: rgba(240, 210, 139, 0.12); box-shadow: 0 0 46rpx rgba(240, 210, 139, 0.12); }
.tiny-orb { width: 64rpx; height: 64rpx; flex-shrink: 0; border-radius: 50%; background: radial-gradient(circle at 35% 30%, #fff, #b6c4b7 55%, #657b70); display: flex; align-items: center; justify-content: center; overflow: hidden; }
.tiny-orb :deep(.portrait) { width: 92%; height: 92%; }
.spirit-card-copy { min-width: 0; }
.spirit-card-name { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 25rpx; font-weight: 600; color: #edf1e9; }
.spirit-card-sub { display: block; color: rgba(235, 241, 233, 0.4); font-size: 20rpx; margin-top: 6rpx; line-height: 1.45; }
.today-tag { display: inline-block; margin-top: 8rpx; font-size: 18rpx; color: #ecd9a0; border: 1rpx solid rgba(235, 216, 158, 0.35); border-radius: 999rpx; padding: 2rpx 14rpx; }
.preferred-tag { color: #10271f; background: #ecd9a0; border-color: rgba(236, 217, 160, 0.8); }

.growth-grid { position: relative; z-index: 1; display: grid; grid-template-columns: repeat(2, 1fr); gap: 18rpx; }
.growth-card { padding: 28rpx 24rpx; border-radius: 30rpx; border: 1rpx solid rgba(255, 255, 255, 0.09); background: rgba(255, 255, 255, 0.055); }
.growth-num { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 38rpx; color: #f0d28b; }
.growth-title { display: block; margin-top: 12rpx; font-size: 27rpx; font-weight: 650; color: #edf1e9; }
.growth-desc { display: block; margin-top: 8rpx; color: rgba(235, 241, 233, 0.46); font-size: 21rpx; line-height: 1.55; }

.rights-grid { position: relative; z-index: 1; display: grid; grid-template-columns: repeat(2, 1fr); gap: 18rpx; }
.right-card { padding: 28rpx 24rpx; border-radius: 30rpx; border: 1rpx solid rgba(240, 210, 139, 0.16); background: linear-gradient(145deg, rgba(240, 210, 139, 0.11), rgba(255, 255, 255, 0.045)); }
.right-icon { display: block; color: #f0d28b; font-size: 30rpx; }
.right-title { display: block; margin-top: 12rpx; font-size: 26rpx; color: #fff7e7; font-weight: 650; }
.right-desc { display: block; margin-top: 8rpx; color: rgba(235, 241, 233, 0.45); font-size: 21rpx; line-height: 1.55; }

.settings { margin-top: 6rpx; border-top: 1rpx solid rgba(255, 255, 255, 0.08); position: relative; z-index: 1; }
.setting { display: flex; justify-content: space-between; align-items: center; gap: 22rpx; padding: 30rpx 4rpx; color: rgba(235, 241, 233, 0.68); }
.setting-title { display: block; font-size: 26rpx; color: rgba(235, 241, 233, 0.76); }
.setting-sub { display: block; margin-top: 8rpx; font-size: 21rpx; color: rgba(235, 241, 233, 0.4); line-height: 1.55; }
.setting:active .setting-title { color: #edf1e9; }
.arrow { opacity: 0.4; font-size: 32rpx; }
</style>
