<template>
  <view class="page">
    <!-- 背景：星云 + 星野 + 渐晕（共享组件，固定层，不抢内容） -->
    <Starfield />

    <!-- 自定义导航栏 -->
    <view class="navbar">
      <text class="nav-back" @tap="goBack">‹</text>
      <text class="nav-title">自我星盘轮</text>
      <view class="nav-right" />
    </view>

    <view v-if="loading" class="empty">
      <text class="empty-main">正在铺开你的星空</text>
      <text class="empty-sub">星云缓缓转动，34 颗水晶球正在就位……</text>
    </view>

    <view v-else-if="error" class="empty">
      <text class="empty-main">连接不到星灵花园</text>
      <text class="empty-sub">{{ errorMsg }}</text>
      <button class="go-chat" @tap="reload">再试一次 →</button>
    </view>

    <view v-else-if="!fragments.length" class="empty">
      <text class="empty-main">还没有星象数据</text>
      <text class="empty-sub">先去聊一次，花园才能开始点亮你的星空。</text>
      <button class="go-chat" @tap="goChat">和星灵聊聊 →</button>
    </view>

    <view v-else class="body">
      <!-- 顶部总览卡 -->
      <view class="overview">
        <view class="ov-head">
          <text class="ov-line">✦ 已被 <text class="ov-num">{{ litCount }}</text> 颗星记得</text>
        </view>
        <view class="ov-progress">
          <view
            v-for="(s, i) in litSegments"
            :key="i"
            class="seg"
            :class="s ? 'on' : 'off'"
          />
        </view>
        <view class="ov-meta">
          <text class="ov-fraction">{{ litCount }} / {{ totalCount }}</text>
          <text v-if="blindCount" class="ov-blind">还有 {{ blindCount }} 个角落等着你</text>
          <text v-else class="ov-blind">你照亮了整片星空</text>
        </view>
        <view class="ov-caption">你的光，照亮了你走过的角落</view>
        <!-- 触发行动（§4.2 +20）：金色 ✦ = 你不只聊过，还真的做过 -->
        <view v-if="hasActions" class="ov-legend">
          <text class="ov-legend-glyph">✦</text>
          <text class="ov-legend-text">金星 = 你真的做出来的角落</text>
        </view>
      </view>

      <!-- 三区：行星动力 / 宫位舞台 / 星座风格 -->
      <view
        v-for="z in zones"
        :key="z.key"
        class="zone"
        :class="'zone-' + z.key"
      >
        <!-- 区段标题（章节感，清晰与子类分开） -->
        <view class="zone-head">
          <view class="zh-line" />
          <view class="zh-mid">
            <text class="zh-name">{{ z.name }}</text>
            <text class="zh-sub">{{ z.en }} · {{ z.desc }} · 已照见 {{ z.litCount }}/{{ z.items.length }}</text>
          </view>
          <view class="zh-line" />
        </view>

        <!-- 水晶球阵（3 列，点球跳详情页） -->
        <view class="crystal-grid">
          <view
            v-for="f in z.items"
            :key="f.id"
            class="crystal-cell"
          >
            <view
              class="ball-wrap"
              :class="[f.state, { 'level-4': f.level >= 4, 'level-5': f.level >= 5 }]"
              @tap="goDetail(f.id)"
            >
              <view class="beam" />
              <view v-if="f.state === 'ascended'" class="orbit-ring" />
              <view class="ball">
                <view class="ball-core">
                  <FragmentIcon :id="f.id" :state="f.state" class="ball-icon" />
                </view>
                <view v-if="f.state === 'unlit'" class="sat-orbit so1"><view class="sat-dot" /></view>
                <view v-if="f.state === 'unlit'" class="sat-orbit so2"><view class="sat-dot" /></view>
                <view v-if="f.state === 'unlit'" class="sat-orbit so3"><view class="sat-dot" /></view>
              </view>
              <view v-if="f.state !== 'unlit'" class="pedestal" />
              <view v-if="f.state === 'ascended'" class="level-badge">
                <text class="level-roman">{{ ROMAN[f.level] }}</text>
              </view>
              <!-- 触发行动（§4.2 +20）：金色 ✦ = 这个角落是真做出来的（纯 CSS，不新增图标） -->
              <view v-if="f.level >= 4" class="action-star">
                <text class="action-star-glyph">✦</text>
              </view>
            </view>

            <text class="ball-name" :class="f.state" @tap="goDetail(f.id)">{{ f.name }}</text>
          </view>
        </view>
      </view>

      <!-- 盲区即课题 -->
      <view v-if="blindCount" class="blind-card">
        <text class="blind-sym">☾</text>
        <text class="blind-title">盲区即课题</text>
        <text class="blind-body">
          你还没碰过 <text class="blind-em">{{ blindNames.join('、') }}</text>
          ——有些角落藏着你还未看见的自己。
        </text>
        <text class="blind-quote">你不碰的角落，往往是你最需要面对的。</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import api, { ApiError, describeError, type FragmentOut } from "@/api/client";
import Starfield from "@/components/Starfield.vue";
import FragmentIcon from "@/components/FragmentIcon.vue";
import {
  ROMAN,
  stateOf,
  ZONE_META,
  type BallState,
} from "@/utils/fragments";

const PERSON_KEY = "gs_person_id";

interface StarItem {
  id: string;
  name: string;
  triggers: string;
  depth: number;
  lit: boolean;
  state: BallState;
  level: number;
  actionCount: number;
}

interface ZoneData {
  key: string;
  name: string;
  en: string;
  desc: string;
  items: StarItem[];
  litCount: number;
}

// ---------------------------------------------------------------------------
// 状态
// ---------------------------------------------------------------------------

const loading = ref(true);
const loaded = ref(false);
const error = ref(false);
const errorMsg = ref("");
const fragments = ref<FragmentOut[]>([]);
const zones = ref<ZoneData[]>([]);

const totalCount = computed(() => fragments.value.length || 34);
const litCount = computed(() => fragments.value.filter((f) => f.depth > 0).length);
const blindCount = computed(() => totalCount.value - litCount.value);
// 触发行动（§4.2 +20）：是否有过"真做出来"的角落（金色 ✦ 图例只在这些球旁出现）
const hasActions = computed(() =>
  fragments.value.some((f) => (f.action_count ?? 0) > 0)
);
const litSegments = computed(() => fragments.value.map((f) => f.depth > 0));
const blindNames = computed(() =>
  fragments.value
    .filter((f) => f.depth === 0)
    .slice(0, 3)
    .map((f) => f.name)
);

function goDetail(id: string) {
  uni.navigateTo({ url: `/pages/universe/fragment?id=${id}` });
}

async function load() {
  const personId = uni.getStorageSync(PERSON_KEY) as string;
  if (!personId) return uni.redirectTo({ url: "/pages/index/index" });

  try {
    const res = await api.fragments(personId);
    fragments.value = res.fragments;
    error.value = false;

    zones.value = ZONE_META.map((meta) => {
      const items = res.fragments
        .filter((f) => f.zone === meta.key)
        .map((f) => {
          const depth = f.depth;
          return {
            id: f.id,
            name: f.name,
            triggers: f.triggers,
            depth,
            lit: depth > 0,
            state: stateOf(depth),
            level: f.level,
            actionCount: f.action_count ?? 0,
          };
        });
      return {
        ...meta,
        items,
        litCount: items.filter((s) => s.lit).length,
      };
    });
  } catch (e) {
    // person 已不存在（后端重置/换库）→ 清空本地身份，回首页重建
    if (e instanceof ApiError && e.status === 404) {
      uni.removeStorageSync(PERSON_KEY);
      uni.showToast({ title: "这个花园已经找不到了", icon: "none" });
      return uni.redirectTo({ url: "/pages/index/index" });
    }
    error.value = true;
    errorMsg.value = describeError(e);
    fragments.value = [];
  } finally {
    loading.value = false;
    loaded.value = true;
  }
}

// 首次进入显示 loading；从聊天页返回（onShow 再触发）静默刷新
onShow(() => {
  if (!loaded.value) loading.value = true;
  load();
});

function reload() {
  error.value = false;
  loading.value = true;
  load();
}

function goBack() {
  uni.navigateBack();
}
function goChat() {
  uni.navigateTo({ url: "/pages/chat/chat" });
}
</script>

<style scoped>
.page {
  /* ── 设计 token（深空紫 · 金线 · 冰蓝） ────────────── */
  --void-deepest: #05030f;
  --void-deep: #0a0820;
  --void-mid: #141030;
  --void-soft: #1d1840;
  --gold-bright: #f4d58d;
  --gold-primary: #d4a857;
  --gold-deep: rgba(212, 168, 87, 0.24);
  --ice-primary: #7fd0e6;
  --ice-glow: rgba(127, 208, 230, 0.25);
  --text-primary: #e9e6f5;
  --text-secondary: #a9a3c4;
  --text-tertiary: #6d6788;
  --font-display: "Noto Serif SC", "Songti SC", serif;
  --font-en: "Cormorant Garamond", "Georgia", serif;
  --font-body: "Noto Sans SC", "PingFang SC", -apple-system, sans-serif;

  min-height: 100vh;
  box-sizing: border-box;
  position: relative;
  font-family: var(--font-body);
  background: radial-gradient(ellipse at 50% 28%, var(--void-mid) 0%, var(--void-deep) 42%, var(--void-deepest) 100%);
}

/* ── 自定义导航栏 ─────────────────────────────── */
.navbar {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  padding: 24rpx 28rpx 8rpx;
}
.nav-back {
  color: var(--text-primary);
  font-size: 52rpx;
  width: 60rpx;
  line-height: 1;
  opacity: 0.85;
}
.nav-title {
  flex: 1;
  text-align: center;
  font-family: var(--font-display);
  color: var(--text-primary);
  font-size: 32rpx;
  letter-spacing: 0.2em;
}
.nav-right { width: 60rpx; }

.body {
  position: relative;
  z-index: 1;
  padding-bottom: 80rpx;
}

/* ── 加载 / 空态 ───────────────────────────────── */
.empty {
  position: relative;
  z-index: 1;
  color: var(--text-secondary);
  font-size: 28rpx;
  text-align: center;
  padding: 160rpx 60rpx;
}
.empty-main {
  display: block;
  font-family: var(--font-display);
  color: var(--text-primary);
  font-size: 34rpx;
  letter-spacing: 0.1em;
  margin-bottom: 16rpx;
}
.empty-sub {
  display: block;
  font-size: 24rpx;
  line-height: 1.8;
  color: var(--text-tertiary);
}
.go-chat {
  margin-top: 40rpx;
  background: linear-gradient(135deg, var(--gold-primary), #b98a3e);
  color: #201430;
  border-radius: 16rpx;
  font-size: 26rpx;
  font-weight: 600;
  letter-spacing: 0.1em;
  padding: 16rpx 48rpx;
}

/* ═══════════════════════════════════════════════
   顶部总览卡
   ═══════════════════════════════════════════════ */
.overview {
  position: relative;
  margin: 28rpx 28rpx 8rpx;
  padding: 36rpx 30rpx 30rpx;
  border-radius: 24rpx;
  background: linear-gradient(180deg, rgba(29, 24, 64, 0.55) 0%, rgba(10, 8, 32, 0.78) 100%);
  border: 1rpx solid var(--gold-deep);
  overflow: hidden;
}
/* 卡内银河 */
.overview::before {
  content: "";
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 260rpx 200rpx at 18% 0%, rgba(107, 91, 149, 0.28) 0%, transparent 70%),
    radial-gradient(ellipse 200rpx 160rpx at 86% 100%, rgba(155, 100, 130, 0.16) 0%, transparent 70%);
  mix-blend-mode: screen;
  pointer-events: none;
}
.ov-head { position: relative; text-align: center; }
.ov-line {
  font-family: var(--font-display);
  font-size: 34rpx;
  color: var(--text-primary);
  letter-spacing: 0.08em;
}
.ov-num {
  color: var(--gold-bright);
  font-family: var(--font-en);
  font-size: 54rpx;
  margin: 0 6rpx;
}
.ov-progress {
  position: relative;
  display: flex;
  gap: 4rpx;
  margin: 30rpx 0 20rpx;
}
.seg {
  flex: 1;
  height: 6rpx;
  border-radius: 3rpx;
  background: rgba(255, 255, 255, 0.06);
  transition: background 0.6s ease;
}
.seg.on {
  background: linear-gradient(90deg, var(--gold-primary), var(--gold-bright));
  box-shadow: 0 0 8rpx rgba(212, 168, 87, 0.5);
}
.ov-meta {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.ov-fraction {
  font-family: var(--font-en);
  font-size: 22rpx;
  color: var(--text-secondary);
  letter-spacing: 0.1em;
}
.ov-blind {
  font-size: 20rpx;
  color: var(--text-tertiary);
}
.ov-caption {
  position: relative;
  text-align: center;
  margin-top: 20rpx;
  font-family: var(--font-display);
  font-size: 22rpx;
  color: var(--text-secondary);
  font-style: italic;
  letter-spacing: 0.1em;
}
/* 触发行动图例（§4.2 +20）：金色 ✦ = 真做出来的角落 */
.ov-legend {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  margin-top: 16rpx;
}
.ov-legend-glyph {
  font-size: 26rpx;
  color: var(--gold-bright);
  text-shadow: 0 0 10rpx rgba(244, 213, 141, 0.9);
}
.ov-legend-text {
  font-size: 20rpx;
  color: var(--text-tertiary);
  letter-spacing: 0.08em;
}

/* ═══════════════════════════════════════════════
   区段标题（章节感：字更大、间距更足、与子类清晰分开）
   ═══════════════════════════════════════════════ */
.zone { margin-top: 80rpx; }
.zone:first-of-type { margin-top: 48rpx; }

/* zone 色相（只染光环，不染球身） */
.zone-planet { --aura: #e8c87a; --aura-soft: rgba(232, 200, 122, 0.30); --aura-glow: rgba(232, 200, 122, 0.30); }
.zone-house { --aura: #6fc3dd; --aura-soft: rgba(111, 195, 221, 0.30); --aura-glow: rgba(111, 195, 221, 0.30); }
.zone-sign { --aura: #e99aad; --aura-soft: rgba(233, 154, 173, 0.30); --aura-glow: rgba(233, 154, 173, 0.30); }

.zone-head {
  display: flex;
  align-items: center;
  gap: 30rpx;
  padding: 0 30rpx;
  margin-bottom: 54rpx;
}
.zh-line {
  flex: 1;
  height: 1rpx;
  background: linear-gradient(90deg, transparent, var(--gold-deep), transparent);
}
.zh-mid {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.zh-name {
  font-family: var(--font-display);
  font-size: 44rpx;
  color: var(--gold-primary);
  letter-spacing: 0.34em;
  text-indent: 0.34em;
  text-shadow: 0 0 20rpx rgba(212, 168, 87, 0.18);
}
.zh-sub {
  margin-top: 16rpx;
  font-size: 22rpx;
  color: var(--text-tertiary);
  letter-spacing: 0.14em;
}

/* ═══════════════════════════════════════════════
   水晶球阵（3 列，球距放宽）
   ═══════════════════════════════════════════════ */
.crystal-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 56rpx 22rpx;
  padding: 0 28rpx;
}

.crystal-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 0;
}

/* ── 球体容器 ────────────────────────────────── */
.ball-wrap {
  --ball-size: 168rpx;
  position: relative;
  width: var(--ball-size);
  height: var(--ball-size);
  cursor: pointer;
}

/* 上方光柱（lit / ascended） */
.beam {
  position: absolute;
  top: -152rpx;
  left: 50%;
  transform: translateX(-50%);
  width: 60rpx;
  height: 152rpx;
  background: linear-gradient(180deg, transparent 0%, var(--aura-soft) 45%, transparent 100%);
  filter: blur(10rpx);
  opacity: 0;
  transition: opacity 0.8s ease;
  pointer-events: none;
}
.ball-wrap.lit .beam,
.ball-wrap.ascended .beam { opacity: 0.5; }

/* 球体（玻璃质感：半透明，透出星云光） */
.ball {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background:
    radial-gradient(circle at 32% 28%, rgba(255, 255, 255, 0.85) 0%, rgba(255, 255, 255, 0.05) 24%, transparent 42%),
    radial-gradient(circle at 50% 55%, var(--aura) 0%, var(--aura-soft) 46%, transparent 74%),
    linear-gradient(160deg, rgba(255, 255, 255, 0.08) 0%, rgba(20, 16, 48, 0.78) 62%, rgba(8, 6, 24, 0.85) 100%);
  box-shadow:
    0 0 26rpx var(--aura-glow),
    0 0 12rpx var(--aura-soft);
  border: 1rpx solid var(--aura-soft);
  transition: all 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

/* 未点亮：半透明沉睡之球（星符以剪影出现） */
.ball-wrap.unlit .ball {
  background:
    radial-gradient(circle at 32% 28%, rgba(255, 255, 255, 0.10) 0%, transparent 26%),
    radial-gradient(circle at 50% 60%, rgba(120, 110, 180, 0.14) 0%, transparent 55%),
    linear-gradient(160deg, rgba(42, 36, 88, 0.5) 0%, rgba(16, 12, 44, 0.55) 60%, rgba(10, 8, 30, 0.6) 100%);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  box-shadow:
    0 0 20rpx rgba(120, 110, 180, 0.10),
    inset 0 0 20rpx rgba(0, 0, 0, 0.35);
  animation: breathe 6s ease-in-out infinite;
}

/* 升阶：更强的辉光 + 缓慢脉动 */
.ball-wrap.ascended .ball {
  box-shadow:
    0 0 34rpx var(--aura-glow),
    0 0 18rpx var(--aura-soft),
    inset 0 0 18rpx var(--aura-soft);
  animation: ascended-glow 3.2s ease-in-out infinite;
}

/* 触发行动（§4.2 +20）：level 4/5 = 真做出来的角落，球体染上皇家金 + 金色 ✦。
   纯 CSS / 文本字形，不新增任何图标状态（图标永久两态 default/active 已定稿）。 */
.ball-wrap.level-4 .ball,
.ball-wrap.level-5 .ball {
  box-shadow:
    0 0 44rpx rgba(244, 213, 141, 0.55),
    0 0 22rpx rgba(212, 168, 87, 0.42),
    inset 0 0 20rpx rgba(212, 168, 87, 0.28);
  border-color: rgba(244, 213, 141, 0.7);
}
.ball-wrap.level-5 .ball {
  animation: action-glow-ball 2.4s ease-in-out infinite;
}
/* 金色 ✦ 角标：level 4 起挂，level 5 更大更亮（呼吸闪烁） */
.action-star {
  position: absolute;
  top: -16rpx;
  left: -16rpx;
  width: 44rpx;
  height: 44rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 4;
  pointer-events: none;
}
.action-star-glyph {
  font-size: 28rpx;
  color: var(--gold-bright);
  text-shadow: 0 0 12rpx rgba(244, 213, 141, 0.95);
}
.ball-wrap.level-5 .action-star-glyph {
  font-size: 36rpx;
  animation: action-star-glow 2.2s ease-in-out infinite;
}

/* 中心意象：有 PNG 的子类 = 图即球体（active/default 两态由 :state 切图）；
   无 PNG 的 SVG 兜底 = 居中图标 */
.ball-core {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
}
/* PNG 铺满整个球（球形容器负责裁圆），SVG 兜底仍是 46rpx 居中图标 */
.ball-core .ball-icon.frag-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
.ball-icon {
  font-size: 46rpx;
  filter: drop-shadow(0 0 10rpx var(--aura-glow));
  transition: filter 0.5s ease, opacity 0.5s ease;
}
/* unlit：default 图已自带暗淡，这里补降透明度融入沉睡球 */
.ball-wrap.unlit .ball-icon {
  filter: none;
  opacity: 0.6;
}

/* 卫星（unlit）：3 颗绕转 */
.sat-orbit {
  position: absolute;
  inset: -12rpx;
  animation: spin linear infinite;
  pointer-events: none;
}
.sat-dot {
  position: absolute;
  left: 50%;
  top: -4rpx;
  width: 10rpx;
  height: 10rpx;
  margin-left: -5rpx;
  border-radius: 50%;
  background: var(--aura-soft);
  box-shadow: 0 0 10rpx var(--aura-glow);
  opacity: 0.85;
}
.so1 { animation-duration: 11s; }
.so2 { animation-duration: 15s; }
.so3 { animation-duration: 19s; }

/* 底座（lit / ascended） */
.pedestal {
  position: absolute;
  bottom: -28rpx;
  left: 50%;
  transform: translateX(-50%);
  width: 78%;
  height: 16rpx;
  background: linear-gradient(180deg, var(--aura-soft) 0%, transparent 100%);
  clip-path: polygon(12% 0%, 88% 0%, 100% 100%, 0% 100%);
  filter: blur(2rpx);
  opacity: 0;
  transition: opacity 0.6s ease;
  pointer-events: none;
}
.ball-wrap.lit .pedestal,
.ball-wrap.ascended .pedestal { opacity: 0.7; }

/* 升阶金环：细环 + 一束运行光点 */
.orbit-ring {
  position: absolute;
  inset: -14rpx;
  border-radius: 50%;
  border: 1rpx solid var(--gold-primary);
  opacity: 0.5;
  animation: spin 14s linear infinite;
  pointer-events: none;
}
.orbit-ring::after {
  content: "";
  position: absolute;
  left: 50%;
  top: -5rpx;
  width: 12rpx;
  height: 12rpx;
  margin-left: -6rpx;
  border-radius: 50%;
  background: var(--gold-bright);
  box-shadow: 0 0 12rpx var(--gold-bright);
}

/* 罗马数字级标（ascended） */
.level-badge {
  position: absolute;
  top: 0;
  right: -8rpx;
  width: 36rpx;
  height: 36rpx;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, var(--gold-bright), var(--gold-primary));
  box-shadow: 0 0 14rpx rgba(212, 168, 87, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 3;
}
.level-roman {
  font-family: var(--font-en);
  font-size: 20rpx;
  font-weight: 700;
  color: #201430;
}

/* 名字 */
.ball-name {
  margin-top: 20rpx;
  font-family: var(--font-display);
  font-size: 24rpx;
  color: var(--text-primary);
  letter-spacing: 0.06em;
  text-align: center;
  line-height: 1.4;
  transition: color 0.4s ease;
}
.ball-name.unlit { color: var(--text-tertiary); }

/* ═══════════════════════════════════════════════
   盲区即课题
   ═══════════════════════════════════════════════ */
.blind-card {
  position: relative;
  margin: 60rpx 28rpx 40rpx;
  padding: 40rpx 34rpx 36rpx;
  border-radius: 24rpx;
  background: linear-gradient(180deg, rgba(29, 24, 64, 0.5), rgba(10, 8, 32, 0.72));
  border-top: 2rpx solid rgba(127, 208, 230, 0.4);
  overflow: hidden;
  text-align: center;
}
.blind-card::after {
  content: "";
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse 220rpx 140rpx at 50% 0%, rgba(127, 208, 230, 0.10) 0%, transparent 70%);
  pointer-events: none;
}
.blind-sym {
  font-size: 46rpx;
  color: var(--ice-primary);
  opacity: 0.8;
  display: block;
  margin-bottom: 14rpx;
}
.blind-title {
  font-family: var(--font-display);
  font-size: 28rpx;
  color: var(--text-primary);
  letter-spacing: 0.24em;
  display: block;
  margin-bottom: 18rpx;
}
.blind-body {
  font-size: 24rpx;
  line-height: 1.9;
  color: var(--text-secondary);
  display: block;
  position: relative;
}
.blind-em { color: var(--ice-primary); font-weight: 500; }
.blind-quote {
  display: block;
  margin-top: 20rpx;
  font-family: var(--font-display);
  font-size: 22rpx;
  color: var(--text-tertiary);
  font-style: italic;
  letter-spacing: 0.06em;
  position: relative;
}

/* ── 动画 ─────────────────────────────────────── */
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes breathe { 0%, 100% { opacity: 0.72; } 50% { opacity: 0.92; } }
@keyframes ascended-glow {
  0%, 100% { box-shadow: 0 0 34rpx var(--aura-glow), 0 0 18rpx var(--aura-soft), inset 0 0 18rpx var(--aura-soft); }
  50% { box-shadow: 0 0 48rpx var(--aura-glow), 0 0 26rpx var(--aura-soft), inset 0 0 26rpx var(--aura-soft); }
}
/* 触发行动（§4.2 +20）：level 5 球的皇家金呼吸 + 金色 ✦ 闪烁 */
@keyframes action-glow-ball {
  0%, 100% { box-shadow: 0 0 44rpx rgba(244, 213, 141, 0.55), 0 0 22rpx rgba(212, 168, 87, 0.42), inset 0 0 20rpx rgba(212, 168, 87, 0.28); }
  50% { box-shadow: 0 0 60rpx rgba(244, 213, 141, 0.75), 0 0 32rpx rgba(212, 168, 87, 0.55), inset 0 0 28rpx rgba(212, 168, 87, 0.4); }
}
@keyframes action-star-glow {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.75; transform: scale(1.15); }
}

/* 尊重减少动态偏好 */
@media (prefers-reduced-motion: reduce) {
  .unlit .ball,
  .sat-orbit,
  .orbit-ring,
  .ball-wrap.ascended .ball,
  .ball-wrap.level-5 .ball,
  .ball-wrap.level-5 .action-star-glyph {
    animation: none !important;
  }
}

/* 窄屏收球 */
@media (max-width: 340px) {
  .ball-wrap { --ball-size: 152rpx; }
}
</style>
