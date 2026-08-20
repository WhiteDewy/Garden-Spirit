<template>
  <view class="page">
    <!-- 背景（共享组件） -->
    <Starfield />

    <!-- 自定义导航栏 -->
    <view class="navbar">
      <text class="nav-back" @tap="goBack">‹</text>
      <text class="nav-title">子类介绍</text>
      <view class="nav-right" />
    </view>

    <view v-if="loading" class="empty">
      <text class="empty-main">正在翻开这颗水晶球</text>
      <text class="empty-sub">星云缓缓转动……</text>
    </view>

    <view v-else-if="error" class="empty">
      <text class="empty-main">连接不到星灵花园</text>
      <text class="empty-sub">{{ errorMsg }}</text>
      <text class="empty-sub" @tap="reload">再试一次 →</text>
    </view>

    <view v-else-if="!frag" class="empty">
      <text class="empty-main">没有找到这颗星</text>
      <text class="empty-sub" @tap="goBack">← 返回星盘轮</text>
    </view>

    <view v-else class="body" :class="'zone-' + frag.zone">
      <!-- 中央大球 -->
      <view class="hero">
        <view class="hero-ball" :class="[state, { 'level-4': level >= 4 }]">
          <view class="beam" />
          <view v-if="state === 'ascended'" class="orbit-ring" />
          <view class="ball">
            <view class="ball-core">
              <FragmentIcon :id="frag.id" :state="state" class="ball-icon" />
            </view>
            <view v-if="state === 'unlit'" class="sat-orbit so1"><view class="sat-dot" /></view>
            <view v-if="state === 'unlit'" class="sat-orbit so2"><view class="sat-dot" /></view>
            <view v-if="state === 'unlit'" class="sat-orbit so3"><view class="sat-dot" /></view>
          </view>
          <view v-if="state !== 'unlit'" class="pedestal" />
          <view v-if="state === 'ascended'" class="level-badge">
            <text class="level-roman">{{ ROMAN[level] }}</text>
          </view>
          <!-- 触发行动（§4.2 +20）：金色 ✦ = 这个角落你真做出来过（纯 CSS 文本，不新增图标） -->
          <view v-if="level >= 4" class="action-star">
            <text class="action-star-glyph">✦</text>
          </view>
        </view>
      </view>

      <!-- 名字 + 归属 -->
      <view class="title-block">
        <text class="title">{{ frag.name }}</text>
        <text class="zone-line">{{ zone.name }} · {{ zone.en }} · {{ STATE_TEXT[state] }}</text>
      </view>

      <!-- 状态卡 -->
      <view class="state-card" :class="state">
        <text class="sc-main">
          {{
            state === 'unlit'
              ? '沉睡中的星子'
              : state === 'ascended'
                ? '已深潜点亮 · 探索深度 ' + frag.depth
                : '已被点亮 · 探索深度 ' + frag.depth
          }}
        </text>
        <text class="sc-sub">
          {{
            state === 'unlit'
              ? '它还在等你——聊到下面的话题，它就会醒来。'
              : '你曾在这里照见过自己，它还认得你的光。'
          }}
        </text>
      </view>

      <!-- 触发行动（§4.2 +20）：你不只聊过，还真的做出来过 -->
      <view v-if="(frag.action_count ?? 0) > 0" class="card action-card">
        <text class="card-label">✦ 你在这里做过一件事</text>
        <text class="action-main">这个角落的成长里，有一步是你真正走出来的——不只是聊到，是去做了。</text>
        <text class="action-count">你在这里的行动 × {{ frag.action_count }}</text>
      </view>

      <!-- 点亮它的话题 -->
      <view class="card">
        <text class="card-label">✦ 点亮它的话题</text>
        <view class="topic-row">
          <FragmentIcon :id="frag.id" :state="state" class="topic-icon" />
          <text class="topic-text">聊到{{ frag.triggers }}时会被照亮</text>
        </view>
      </view>

      <!-- 为什么点亮它（§6.2 推导链，来信式日记 → 记忆微星系） -->
      <view v-if="state !== 'unlit'" class="card why-card">
        <text class="card-label">✦ 为什么点亮它</text>

        <!-- 有来信：每封来信 = 一颗记忆星 -->
        <view v-if="keepsakes.length > 0" class="mem-constellation">
          <text class="mem-subtitle">记忆星 · 散落在你心里的光点</text>
          <view
            v-for="(k, i) in keepsakes"
            :key="k.id"
            class="mem-star"
            :class="{ 'not-first': i > 0 }"
          >
            <view v-if="i > 0" class="mem-trail" />
            <view class="mem-node" :class="{ first: i === 0 }" />
            <view class="mem-body">
              <view class="ms-head">
                <text class="ms-sender">{{ k.sender_zh }}·「{{ k.healing_name || k.title }}」</text>
                <text class="ms-date">{{ k.letter_date }}</text>
              </view>
              <text class="ms-explain">{{ k.explain }}</text>
              <text class="ms-snippet">{{ snippetOf(k.body) }}</text>
              <text class="ms-more" @tap="openMailbox">去信箱看完整来信 →</text>
            </view>
          </view>
        </view>

        <!-- 已点亮但无来信：星光在凝聚中 -->
        <view v-else class="mem-pending">
          <view class="mem-dim-dots">
            <view class="mem-dim-dot" />
            <view class="mem-dim-dot" />
            <view class="mem-dim-dot" />
            <view class="mem-dim-dot" />
          </view>
          <text class="mem-pending-text">
            「为什么」还在路上。这些日常的余光——聊到「{{ frag.triggers }}」时——正聚成一颗记忆星。等一次足够深的倾诉，它会凝结成这里的第一封信。
          </text>
        </view>
      </view>

      <!-- CTA -->
      <button class="go-chat" @tap="goChat">去和星灵聊聊这个方向 →</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import api, { ApiError, describeError, type FragmentOut, type LetterOut } from "@/api/client";
import Starfield from "@/components/Starfield.vue";
import FragmentIcon from "@/components/FragmentIcon.vue";
import {
  ROMAN,
  stateOf,
  zoneMeta,
  STATE_TEXT,
  type BallState,
} from "@/utils/fragments";
import { clearAccountCache, requireSelfPersonId } from "@/utils/account";

const loading = ref(true);
const error = ref(false);
const errorMsg = ref("");
const frag = ref<FragmentOut | null>(null);
const state = ref<BallState>("unlit");
const level = ref(1);
const zone = ref({ key: "", name: "", en: "", desc: "" });
// 为什么点亮它（§6.2 推导链）：keepsake 来信里含本子类的，都是点亮证据
const keepsakes = ref<LetterOut[]>([]);

let targetId = "";

onLoad((options) => {
  targetId = (options && options.id) || "";
  load();
});

async function load() {
  const personId = await requireSelfPersonId();
  if (!personId) return;

  try {
    const res = await api.fragments(personId);
    const found = res.fragments.find((f) => f.id === targetId);
    if (!found) {
      frag.value = null;
      return;
    }
    frag.value = found;
    state.value = stateOf(found.depth);
    level.value = found.level;   // 级数由后端统一出（§4.2）
    zone.value = zoneMeta(found.zone);
    // 为什么点亮它：来信式日记（§6.2 推导链）——keepsake 里含本子类的都是证据
    // 单独 try：来信读不到不影响看这颗星（空证据 ≠ 页面失败）
    try {
      const res = await api.letters(personId);
      const letters = res.items || [];
      keepsakes.value = letters.filter(
        (l) =>
          l.kind === "keepsake" &&
          ((l.soul_fragments || []).includes(found.id) ||
            (l.lit_fragments || []).includes(found.id))
      );
    } catch {
      keepsakes.value = [];
    }
  } catch (e) {
    // person 已不存在（后端重置/换库）→ 清空本地身份，回首页重建
    if (e instanceof ApiError && (e.status === 404 || e.status === 410)) {
      clearAccountCache();
      uni.showToast({ title: e.status === 410 ? "当前档案已无法解密，请重新登录建档" : "这个花园已经找不到了", icon: "none" });
      return uni.redirectTo({ url: "/pages/auth/login" });
    }
    error.value = true;
    errorMsg.value = describeError(e);
    frag.value = null;
  } finally {
    loading.value = false;
  }
}

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
function openMailbox() {
  uni.reLaunch({ url: "/pages/mailbox/mailbox" });
}
/** 来信正文摘录：只取星灵那段完整回复（去掉"今日灵魂碎片"脚注），超长截断。 */
function snippetOf(body: string): string {
  const text = body.split("\n\n◈")[0].trim();
  return text.length > 56 ? text.slice(0, 56) + "…" : text;
}
</script>

<style scoped>
.page {
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

/* zone 色相（只染光环） */
.zone-planet { --aura: #e8c87a; --aura-soft: rgba(232, 200, 122, 0.30); --aura-glow: rgba(232, 200, 122, 0.30); }
.zone-house { --aura: #6fc3dd; --aura-soft: rgba(111, 195, 221, 0.30); --aura-glow: rgba(111, 195, 221, 0.30); }
.zone-sign { --aura: #e99aad; --aura-soft: rgba(233, 154, 173, 0.30); --aura-glow: rgba(233, 154, 173, 0.30); }

/* ── 导航栏 ─────────────────────────────────── */
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
  padding: 40rpx 40rpx 80rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}

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
  color: var(--text-tertiary);
}

/* ── 中央大球 ───────────────────────────────── */
.hero {
  display: flex;
  justify-content: center;
  padding: 60rpx 0 20rpx;
}
.hero-ball {
  --ball-size: 300rpx;
  position: relative;
  width: var(--ball-size);
  height: var(--ball-size);
}

/* 上方光柱 */
.beam {
  position: absolute;
  top: -210rpx;
  left: 50%;
  transform: translateX(-50%);
  width: 90rpx;
  height: 210rpx;
  background: linear-gradient(180deg, transparent 0%, var(--aura-soft) 45%, transparent 100%);
  filter: blur(12rpx);
  opacity: 0;
  transition: opacity 0.8s ease;
  pointer-events: none;
}
.lit .beam,
.ascended .beam { opacity: 0.55; }

/* 球体（玻璃质感） */
.ball {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background:
    radial-gradient(circle at 32% 28%, rgba(255, 255, 255, 0.85) 0%, rgba(255, 255, 255, 0.05) 24%, transparent 42%),
    radial-gradient(circle at 50% 55%, var(--aura) 0%, var(--aura-soft) 46%, transparent 74%),
    linear-gradient(160deg, rgba(255, 255, 255, 0.08) 0%, rgba(20, 16, 48, 0.78) 62%, rgba(8, 6, 24, 0.85) 100%);
  box-shadow:
    0 0 42rpx var(--aura-glow),
    0 0 20rpx var(--aura-soft);
  border: 1rpx solid var(--aura-soft);
  overflow: hidden;
}
.unlit .ball {
  background:
    radial-gradient(circle at 32% 28%, rgba(255, 255, 255, 0.10) 0%, transparent 26%),
    radial-gradient(circle at 50% 60%, rgba(120, 110, 180, 0.14) 0%, transparent 55%),
    linear-gradient(160deg, rgba(42, 36, 88, 0.5) 0%, rgba(16, 12, 44, 0.55) 60%, rgba(10, 8, 30, 0.6) 100%);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  box-shadow:
    0 0 28rpx rgba(120, 110, 180, 0.10),
    inset 0 0 20rpx rgba(0, 0, 0, 0.35);
  animation: breathe 6s ease-in-out infinite;
}
.ascended .ball {
  box-shadow:
    0 0 52rpx var(--aura-glow),
    0 0 28rpx var(--aura-soft),
    inset 0 0 24rpx var(--aura-soft);
  animation: ascended-glow 3.2s ease-in-out infinite;
}
/* 触发行动（§4.2 +20）：level 4+ = 真做出来的角落，英雄球染皇家金 + 金色 ✦（纯 CSS） */
.hero-ball.level-4 .ball {
  box-shadow:
    0 0 66rpx rgba(244, 213, 141, 0.6),
    0 0 32rpx rgba(212, 168, 87, 0.45),
    inset 0 0 26rpx rgba(212, 168, 87, 0.3);
  border-color: rgba(244, 213, 141, 0.75);
}
.action-star {
  position: absolute;
  top: -22rpx;
  left: -22rpx;
  width: 56rpx;
  height: 56rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 4;
  pointer-events: none;
}
.action-star-glyph {
  font-size: 40rpx;
  color: var(--gold-bright);
  text-shadow: 0 0 14rpx rgba(244, 213, 141, 0.95);
}

.ball-core {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
}
/* PNG 图即球体：铺满整个英雄球；SVG 兜底仍是居中图标 */
.hero-ball .ball-icon.frag-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
.ball-icon {
  font-size: 120rpx;
  filter: drop-shadow(0 0 16rpx var(--aura-glow));
  transition: filter 0.5s ease, opacity 0.5s ease;
}
/* unlit：降到与沉睡球同频 */
.hero-ball.unlit .ball-icon {
  filter: none;
  opacity: 0.6;
}

/* 卫星（unlit） */
.sat-orbit {
  position: absolute;
  inset: -16rpx;
  animation: spin linear infinite;
  pointer-events: none;
}
.sat-dot {
  position: absolute;
  left: 50%;
  top: -5rpx;
  width: 12rpx;
  height: 12rpx;
  margin-left: -6rpx;
  border-radius: 50%;
  background: var(--aura-soft);
  box-shadow: 0 0 10rpx var(--aura-glow);
  opacity: 0.85;
}
.so1 { animation-duration: 11s; }
.so2 { animation-duration: 15s; }
.so3 { animation-duration: 19s; }

/* 底座 */
.pedestal {
  position: absolute;
  bottom: -40rpx;
  left: 50%;
  transform: translateX(-50%);
  width: 70%;
  height: 22rpx;
  background: linear-gradient(180deg, var(--aura-soft) 0%, transparent 100%);
  clip-path: polygon(12% 0%, 88% 0%, 100% 100%, 0% 100%);
  filter: blur(2rpx);
  opacity: 0;
  transition: opacity 0.6s ease;
  pointer-events: none;
}
.lit .pedestal,
.ascended .pedestal { opacity: 0.7; }

/* 升阶金环 */
.orbit-ring {
  position: absolute;
  inset: -20rpx;
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
  width: 14rpx;
  height: 14rpx;
  margin-left: -7rpx;
  border-radius: 50%;
  background: var(--gold-bright);
  box-shadow: 0 0 12rpx var(--gold-bright);
}

/* 级标 */
.level-badge {
  position: absolute;
  top: 0;
  right: -10rpx;
  width: 44rpx;
  height: 44rpx;
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
  font-size: 24rpx;
  font-weight: 700;
  color: #201430;
}

/* ── 名字 + 归属 ─────────────────────────────── */
.title-block {
  margin-top: 60rpx;
  text-align: center;
}
.title {
  font-family: var(--font-display);
  font-size: 48rpx;
  color: var(--text-primary);
  letter-spacing: 0.14em;
  text-indent: 0.14em;
}
.zone-line {
  display: block;
  margin-top: 20rpx;
  font-size: 22rpx;
  color: var(--text-tertiary);
  letter-spacing: 0.16em;
}

/* ── 状态卡 ─────────────────────────────────── */
.state-card {
  width: 100%;
  margin-top: 44rpx;
  padding: 30rpx 34rpx;
  border-radius: 20rpx;
  background: linear-gradient(180deg, rgba(29, 24, 64, 0.55), rgba(10, 8, 32, 0.78));
  border: 1rpx solid var(--gold-deep);
  text-align: center;
}
.state-card.unlit { border-color: rgba(255, 255, 255, 0.10); }
.state-card.lit { border-color: var(--aura-soft); }
.state-card.ascended { border-color: rgba(212, 168, 87, 0.5); }
.sc-main {
  font-family: var(--font-display);
  font-size: 30rpx;
  color: var(--gold-bright);
  letter-spacing: 0.08em;
  display: block;
}
.sc-sub {
  display: block;
  margin-top: 12rpx;
  font-size: 24rpx;
  line-height: 1.7;
  color: var(--text-secondary);
}

/* ── 触发行动卡（§4.2 +20）：真做出来的角落 ─────────────── */
.action-card {
  border: 1rpx solid rgba(244, 213, 141, 0.5);
  background: linear-gradient(180deg, rgba(58, 44, 24, 0.5), rgba(20, 14, 32, 0.78));
}
.action-main {
  display: block;
  font-size: 27rpx;
  line-height: 1.8;
  color: var(--text-primary);
}
.action-count {
  display: block;
  margin-top: 14rpx;
  font-size: 24rpx;
  color: var(--gold-bright);
  letter-spacing: 0.06em;
}

/* ── 点亮它的话题 ────────────────────────────── */
.card {
  width: 100%;
  margin-top: 24rpx;
  padding: 30rpx 34rpx;
  border-radius: 20rpx;
  background: linear-gradient(180deg, rgba(29, 24, 64, 0.55), rgba(10, 8, 32, 0.78));
  border: 1rpx solid var(--gold-deep);
}
.card-label {
  font-size: 22rpx;
  color: var(--text-tertiary);
  letter-spacing: 0.2em;
  display: block;
  margin-bottom: 20rpx;
}
.topic-row {
  display: flex;
  align-items: flex-start;
  gap: 22rpx;
}
.topic-icon {
  font-size: 44rpx;
  filter: drop-shadow(0 0 10rpx var(--aura-glow));
  flex-shrink: 0;
  margin-top: 4rpx;
}
.topic-text {
  font-size: 27rpx;
  line-height: 1.8;
  color: var(--text-secondary);
}

/* ── 为什么点亮它（§6.2 推导链，来信式日记 → 记忆微星系）── */
.mem-constellation { padding: 4rpx 0; }
.mem-subtitle {
  display: block;
  margin-bottom: 30rpx;
  font-size: 22rpx;
  color: var(--text-tertiary);
  letter-spacing: 0.16em;
}
/* 每颗记忆星：左侧 56rpx 槽位放光点 + 虚线连线 */
.mem-star {
  position: relative;
  padding-left: 56rpx;
}
.mem-star.not-first { padding-top: 40rpx; }
/* 星座连线：从这颗光点往下伸向下一颗 */
.mem-trail {
  position: absolute;
  left: 7rpx;
  top: 10rpx;
  bottom: -22rpx;
  width: 0;
  border-left: 2rpx dashed var(--gold-deep);
}
/* 记忆星本体：金色光点 + 径向光晕，与 Starfield 的金星同频 */
.mem-node {
  position: absolute;
  left: 0;
  top: 10rpx;
  width: 14rpx;
  height: 14rpx;
  border-radius: 50%;
  background: var(--gold-bright);
  box-shadow: 0 0 18rpx rgba(244, 213, 141, 0.8), 0 0 6rpx rgba(244, 213, 141, 0.9);
  animation: mem-glow 3.8s ease-in-out infinite;
}
.mem-node.first {
  width: 18rpx;
  height: 18rpx;
  box-shadow: 0 0 26rpx rgba(244, 213, 141, 0.95), 0 0 8rpx rgba(244, 213, 141, 1);
}
.mem-body { min-width: 0; }
.ms-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12rpx;
}
.ms-sender {
  font-family: var(--font-display);
  font-size: 28rpx;
  color: var(--gold-bright);
  letter-spacing: 0.06em;
}
.ms-date {
  font-size: 22rpx;
  color: var(--text-tertiary);
  font-family: var(--font-en);
}
.ms-explain {
  display: block;
  font-size: 24rpx;
  line-height: 1.8;
  color: var(--text-secondary);
}
.ms-snippet {
  display: block;
  margin-top: 12rpx;
  font-size: 25rpx;
  line-height: 1.7;
  color: var(--text-tertiary);
  overflow: hidden;
}
.ms-more {
  display: block;
  margin-top: 14rpx;
  font-size: 24rpx;
  color: var(--ice-primary);
  letter-spacing: 0.06em;
}
/* 已点亮但无来信：星光在凝聚中（星座还只亮起暗微光点） */
.mem-pending {
  padding: 12rpx 8rpx 4rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.mem-dim-dots {
  display: flex;
  gap: 18rpx;
  margin-bottom: 30rpx;
}
.mem-dim-dot {
  width: 8rpx;
  height: 8rpx;
  border-radius: 50%;
  background: var(--gold-primary);
  opacity: 0.25;
}
.mem-dim-dot:nth-child(2) { opacity: 0.16; }
.mem-dim-dot:nth-child(3) { opacity: 0.30; }
.mem-dim-dot:nth-child(4) { opacity: 0.12; }
.mem-pending-text {
  display: block;
  text-align: center;
  font-size: 27rpx;
  line-height: 1.9;
  color: var(--text-tertiary);
}
@keyframes mem-glow {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 1; }
}

/* ── CTA ────────────────────────────────────── */
.go-chat {
  width: 100%;
  margin-top: 44rpx;
  background: linear-gradient(135deg, var(--gold-primary), #b98a3e);
  color: #201430;
  border-radius: 16rpx;
  font-size: 27rpx;
  font-weight: 600;
  letter-spacing: 0.1em;
  padding: 18rpx 0;
}

/* ── 动画 ───────────────────────────────────── */
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes breathe { 0%, 100% { opacity: 0.72; } 50% { opacity: 0.92; } }
@keyframes ascended-glow {
  0%, 100% { box-shadow: 0 0 52rpx var(--aura-glow), 0 0 28rpx var(--aura-soft), inset 0 0 24rpx var(--aura-soft); }
  50% { box-shadow: 0 0 70rpx var(--aura-glow), 0 0 40rpx var(--aura-soft), inset 0 0 32rpx var(--aura-soft); }
}

@media (prefers-reduced-motion: reduce) {
  .unlit .ball,
  .sat-orbit,
  .orbit-ring,
  .ascended .ball,
  .mem-node {
    animation: none !important;
  }
}
</style>
