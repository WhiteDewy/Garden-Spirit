<template>
  <view class="page gs-time-page" :class="phaseClass">
    <view class="me-glow" aria-hidden="true"></view>

    <view class="head">
      <view>
        <text class="eyebrow">MY JOURNEY</text>
        <text class="title">我的</text>
      </view>
    </view>

    <view class="profile">
      <view class="profile-avatar">✦</view>
      <view>
        <text class="profile-name">{{ person?.name || '我的花园' }}</text>
        <text class="profile-bio">{{ bioLine }}</text>
      </view>
    </view>

    <view class="stat-row">
      <view class="stat"><text class="stat-num">{{ days }}</text><text class="stat-label">记录天数</text></view>
      <view class="stat"><text class="stat-num">{{ litCount }}</text><text class="stat-label">点亮碎片</text></view>
      <view class="stat"><text class="stat-num">{{ findingCount }}</text><text class="stat-label">沉淀判断</text></view>
    </view>

    <text class="section-label">MY SPIRITS · 我的星灵</text>
    <view class="spirit-list">
      <view v-for="s in spirits" :key="s.glyph" :class="['spirit-card', { today: s.today }]">
        <view class="tiny-orb"><SpiritPortrait :planet="s.planet" /></view>
        <view>
          <text class="spirit-card-name">{{ s.name }}</text>
          <text class="spirit-card-sub">{{ s.healing }}</text>
          <text v-if="s.today" class="today-tag">今日推荐</text>
        </view>
      </view>
    </view>

    <text class="section-label">MY JOURNEY · 我的成长</text>
    <view class="settings">
      <view class="setting" @tap="comingSoon"><text>我的成长记录</text><text class="arrow">→</text></view>
      <view class="setting" @tap="comingSoon"><text>星灵关系</text><text class="arrow">→</text></view>
      <view class="setting" @tap="comingSoon"><text>隐私与安全</text><text class="arrow">→</text></view>
    </view>

    <BottomNav active="me" />
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import api, { type PersonOut } from "@/api/client";
import BottomNav from "@/components/BottomNav.vue";
import SpiritPortrait from "@/components/SpiritPortrait.vue";
import { useTimePhase } from "@/utils/timeTheme";

const PERSON_KEY = "gs_person_id";
const person = ref<PersonOut | null>(null);
const litCount = ref(0);
const findingCount = ref(0);
const todayPlanet = ref("");
const { phaseClass, refreshPhase } = useTimePhase();

// 10 星灵图鉴（疗愈名来自视觉定稿的星灵人设表）
const SPIRITS: Array<{ glyph: string; name: string; healing: string; planet: string }> = [
  { glyph: "☉", name: "太阳星灵", healing: "想被看见的我", planet: "sun" },
  { glyph: "☽", name: "月亮星灵", healing: "想被抱抱的我", planet: "moon" },
  { glyph: "☿", name: "水星星灵", healing: "想说话的我", planet: "mercury" },
  { glyph: "♀", name: "金星星灵", healing: "想爱与被爱", planet: "venus" },
  { glyph: "♂", name: "火星星灵", healing: "想要就冲的我", planet: "mars" },
  { glyph: "♃", name: "木星星灵", healing: "想飞的我", planet: "jupiter" },
  { glyph: "♄", name: "土星星灵", healing: "想负责的我", planet: "saturn" },
  { glyph: "♅", name: "天王星灵", healing: "想挣脱的我", planet: "uranus" },
  { glyph: "♆", name: "海王星灵", healing: "想做梦的我", planet: "neptune" },
  { glyph: "♇", name: "冥王星灵", healing: "想深挖的我", planet: "pluto" },
];
const spirits = computed(() => SPIRITS.map(s => ({ ...s, today: s.planet === todayPlanet.value })));

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
  const pid = uni.getStorageSync(PERSON_KEY) as string;
  if (!pid) return uni.redirectTo({ url: "/pages/index/index" });
  api.getPerson(pid).then(p => (person.value = p)).catch(() => undefined);
  api.recommendedSpirits(pid)
    .then(rec => { todayPlanet.value = rec.spirits?.[0]?.planet?.toLowerCase() || ""; })
    .catch(() => undefined);
  const [frag, fids] = await Promise.allSettled([api.fragments(pid), api.findings(pid)]);
  if (frag.status === "fulfilled") litCount.value = frag.value.fragments.filter(f => f.depth > 0).length;
  if (fids.status === "fulfilled") findingCount.value = fids.value.length;
});

function comingSoon() {
  uni.showToast({ title: "即将上线", icon: "none" });
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: radial-gradient(circle at 82% 12%, rgba(240, 210, 139, 0.1), transparent 28%), linear-gradient(170deg, #17362c 0%, #10271f 55%, #081613 100%);
  padding: 48rpx 36rpx 170rpx;
  box-sizing: border-box;
  position: relative;
  color: #edf1e9;
}
.me-glow { position: absolute; width: 480rpx; height: 480rpx; border-radius: 50%; right: -200rpx; top: 100rpx; background: rgba(183, 164, 113, 0.12); filter: blur(60rpx); pointer-events: none; }
.head { position: relative; z-index: 1; }
.eyebrow { display: block; font-size: 19rpx; letter-spacing: 0.16em; color: rgba(235, 241, 233, 0.4); font-weight: 800; }
.title { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 52rpx; font-weight: 600; color: #edf1e9; margin-top: 6rpx; }

.profile { display: flex; align-items: center; gap: 28rpx; padding: 26rpx 0 40rpx; position: relative; z-index: 1; }
.profile-avatar { width: 124rpx; height: 124rpx; border-radius: 50%; background: linear-gradient(145deg, #dfe5d8, #758d80); display: flex; align-items: center; justify-content: center; color: #fff; font-size: 46rpx; box-shadow: 0 0 70rpx rgba(210, 203, 164, 0.12); }
.profile-name { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 40rpx; font-weight: 600; color: #edf1e9; }
.profile-bio { display: block; font-size: 22rpx; color: rgba(235, 241, 233, 0.5); margin-top: 12rpx; line-height: 1.6; max-width: 440rpx; }

.stat-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16rpx; position: relative; z-index: 1; }
.stat { padding: 30rpx 22rpx; border: 1rpx solid rgba(255, 255, 255, 0.09); background: rgba(255, 255, 255, 0.05); border-radius: 28rpx; }
.stat-num { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 40rpx; font-weight: 600; color: #edf1e9; }
.stat-label { display: block; color: rgba(235, 241, 233, 0.43); font-size: 20rpx; margin-top: 8rpx; }

.section-label { display: block; font-size: 19rpx; letter-spacing: 0.16em; color: rgba(235, 241, 233, 0.4); margin: 44rpx 0 20rpx; position: relative; z-index: 1; }
.spirit-list { display: grid; grid-template-columns: repeat(2, 1fr); gap: 18rpx; position: relative; z-index: 1; }
.spirit-card { padding: 26rpx; border-radius: 30rpx; background: rgba(255, 255, 255, 0.05); border: 1rpx solid rgba(255, 255, 255, 0.08); display: flex; align-items: center; gap: 20rpx; }
.spirit-card.today { border-color: rgba(235, 216, 158, 0.4); background: rgba(235, 216, 158, 0.07); }
.tiny-orb { width: 64rpx; height: 64rpx; flex-shrink: 0; border-radius: 50%; background: radial-gradient(circle at 35% 30%, #fff, #b6c4b7 55%, #657b70); display: flex; align-items: center; justify-content: center; font-size: 30rpx; color: #2c3e36; }
.spirit-card-name { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 25rpx; font-weight: 600; color: #edf1e9; }
.spirit-card-sub { display: block; color: rgba(235, 241, 233, 0.4); font-size: 20rpx; margin-top: 6rpx; }
.today-tag { display: inline-block; margin-top: 8rpx; font-size: 18rpx; color: #ecd9a0; border: 1rpx solid rgba(235, 216, 158, 0.35); border-radius: 999rpx; padding: 2rpx 14rpx; }

.settings { margin-top: 6rpx; border-top: 1rpx solid rgba(255, 255, 255, 0.08); position: relative; z-index: 1; }
.setting { display: flex; justify-content: space-between; padding: 30rpx 4rpx; color: rgba(235, 241, 233, 0.68); font-size: 26rpx; }
.setting:active { color: #edf1e9; }
.arrow { opacity: 0.4; }
</style>
