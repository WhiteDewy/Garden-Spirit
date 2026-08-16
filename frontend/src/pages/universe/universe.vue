<template>
  <view class="page">
    <view class="cosmos-glow" aria-hidden="true"></view>

    <!-- 星座散点 -->
    <view class="constellation" aria-hidden="true">
      <text v-for="(c, i) in stars" :key="i" class="c-dot" :style="{ left: c.x + '%', top: c.y + '%' }"></text>
    </view>

    <!-- 星轨核心 -->
    <view class="orbit-zone" aria-hidden="true">
      <view class="orbit one"></view>
      <view class="orbit two"></view>
      <view class="orbit three"></view>
    </view>
    <view class="core" @tap="goWheel"><text>你</text></view>
    <view class="planet p1" @tap="goWheel"><text>☾</text></view>
    <view class="planet p2" @tap="goConsult"><text>♀</text></view>
    <view class="planet p3" @tap="goWheel"><text>☿</text></view>
    <view class="planet p4" @tap="goConsult"><text>♂</text></view>

    <view class="head">
      <view>
        <text class="eyebrow">YOUR COSMOS</text>
        <text class="title">宇宙</text>
      </view>
    </view>
    <text class="sub">出生时形成的星图，是一张认识自己的地图。</text>

    <view class="copy">
      <text class="copy-h">你的宇宙，正在发光。</text>
      <text class="copy-p">星体不是命运的答案。\n它们只是帮助你理解自己的另一种语言。</text>
      <button class="explore" @tap="goWheel">探索我的星图　→</button>
    </view>

    <!-- 功能入口：星轨世界里的两座观星台 -->
    <view class="entries">
      <view class="entry" @tap="goWheel">
        <text class="entry-ico">☾</text>
        <view class="entry-body">
          <text class="entry-title">自我星盘轮</text>
          <text class="entry-sub">{{ litLabel }}</text>
          <text class="entry-desc">34 子类 · 3 星区 · 聊出来的内心地图</text>
        </view>
        <text class="entry-arrow">›</text>
      </view>
      <view class="entry" @tap="goConsult">
        <text class="entry-ico">♀</text>
        <view class="entry-body">
          <text class="entry-title">星盘咨询</text>
          <text class="entry-sub">{{ findingLabel }}</text>
          <text class="entry-desc">大领域 · 深度解读 · 带着星盘的视角看生活的难题</text>
        </view>
        <text class="entry-arrow">›</text>
      </view>
    </view>

    <text v-if="!loaded" class="hint">正在翻开你的宇宙……</text>
    <text v-else-if="!litCount && !findingCount" class="hint">
      先去聊一次，花园才能开始认识你。
    </text>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import api from "@/api/client";

const PERSON_KEY = "gs_person_id";

const litCount = ref(0);       // 已点亮的 34 子类数
const findingCount = ref(0);   // 沉淀判断总数（含待验证）
const loaded = ref(false);

const litLabel = ref("34 子类 · 3 星区");
const findingLabel = ref("大领域 · 深度解读");

// 星座散点（固定伪随机，避免每次渲染跳位）
const stars = Array.from({ length: 12 }, (_, i) => ({
  x: [14, 28, 44, 65, 84, 75, 18, 34, 87, 53, 8, 70][i],
  y: [20, 29, 17, 23, 15, 37, 49, 58, 59, 71, 82, 88][i],
}));

onShow(async () => {
  const personId = uni.getStorageSync(PERSON_KEY) as string;
  if (!personId) return uni.redirectTo({ url: "/pages/index/index" });

  // 并行拉两入口的统计，任一侧失败都不阻塞枢纽页
  const [frag, fids] = await Promise.allSettled([
    api.fragments(personId),
    api.findings(personId),
  ]);

  if (frag.status === "fulfilled") {
    const list = frag.value.fragments;
    litCount.value = list.filter((f) => f.depth > 0).length;
    const total = list.length || 34;
    litLabel.value = `已点亮 ${litCount.value}/${total}`;
  }

  if (fids.status === "fulfilled") {
    findingCount.value = fids.value.length;
    findingLabel.value = `已有 ${fids.value.length} 条沉淀判断`;
  }
  loaded.value = true;
});

function goWheel() {
  uni.navigateTo({ url: "/pages/universe/wheel" });
}
function goConsult() {
  uni.navigateTo({ url: "/pages/universe/consult" });
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: radial-gradient(circle at 50% 38%, #354d65 0%, #182638 52%, #0b111b 100%);
  padding: 48rpx 36rpx 60rpx;
  box-sizing: border-box;
  position: relative;
  overflow: hidden;
  color: #eef1ea;
}
.cosmos-glow { position: absolute; width: 600rpx; height: 600rpx; border-radius: 50%; left: 90rpx; top: 280rpx; background: rgba(154, 177, 202, 0.12); filter: blur(60rpx); pointer-events: none; }
.constellation { position: absolute; inset: 0; opacity: 0.75; pointer-events: none; }
.c-dot { position: absolute; width: 6rpx; height: 6rpx; border-radius: 50%; background: #eee7ce; box-shadow: 0 0 20rpx rgba(238, 231, 206, 0.7); animation: twinkle 4s ease-in-out infinite; }
@keyframes twinkle { 50% { opacity: 0.3; } }

/* 星轨核心（可点：进星盘轮） */
.orbit-zone { position: absolute; left: 50%; top: 42%; transform: translate(-50%, -50%); pointer-events: none; }
.orbit { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); border: 1rpx solid rgba(226, 222, 198, 0.18); border-radius: 50%; }
.orbit.one { width: 560rpx; height: 560rpx; rotate: 13deg; animation: slowSpin 60s linear infinite; }
.orbit.two { width: 410rpx; height: 410rpx; rotate: -22deg; animation: slowSpin 48s linear reverse infinite; }
.orbit.three { width: 250rpx; height: 250rpx; rotate: 32deg; animation: slowSpin 36s linear infinite; }
@keyframes slowSpin { to { transform: translate(-50%, -50%) rotate(360deg); } }
.core { position: absolute; left: 50%; top: 42%; transform: translate(-50%, -50%); width: 128rpx; height: 128rpx; border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #fff7dc, #bca873 58%, #576a77);
  box-shadow: 0 0 100rpx rgba(220, 205, 158, 0.35); display: flex; align-items: center; justify-content: center;
  font-family: Georgia, "Noto Serif SC", serif; font-size: 42rpx; color: #2c3e50; z-index: 2; }
.planet { position: absolute; width: 72rpx; height: 72rpx; border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font-size: 30rpx; background: rgba(255, 255, 255, 0.08); border: 1rpx solid rgba(255, 255, 255, 0.14); backdrop-filter: blur(8rpx); color: #eef1ea; z-index: 2; }
.planet:active { transform: scale(0.92); }
.p1 { left: 13%; top: 32%; }
.p2 { right: 12%; top: 44%; }
.p3 { left: 22%; top: 58%; }
.p4 { right: 21%; top: 66%; }

.head { position: relative; z-index: 3; display: flex; justify-content: space-between; align-items: flex-start; }
.eyebrow { display: block; font-size: 19rpx; letter-spacing: 0.16em; color: rgba(238, 241, 234, 0.45); font-weight: 800; }
.title { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 52rpx; font-weight: 600; color: #eef1ea; margin-top: 6rpx; }
.sub { display: block; position: relative; z-index: 3; font-size: 23rpx; color: rgba(238, 241, 234, 0.54); line-height: 1.7; margin-top: 12rpx; }

.copy { position: relative; z-index: 3; margin-top: 74vh; margin-bottom: 40rpx; }
.copy-h { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 46rpx; font-weight: 600; color: #eef1ea; }
.copy-p { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 24rpx; color: rgba(238, 241, 234, 0.58); line-height: 1.8; margin: 16rpx 0 0; white-space: pre-line; }
.explore { margin-top: 28rpx; border: 1rpx solid rgba(255, 255, 255, 0.14); background: rgba(255, 255, 255, 0.06); color: #eef1ea;
  padding: 22rpx 30rpx; border-radius: 22rpx; font-size: 25rpx; display: inline-flex; align-items: center; }

/* 功能入口：观星台列表 */
.entries { position: relative; z-index: 3; display: grid; gap: 18rpx; }
.entry { display: flex; align-items: center; gap: 22rpx; padding: 30rpx 28rpx; border-radius: 28rpx;
  background: rgba(255, 255, 255, 0.05); border: 1rpx solid rgba(255, 255, 255, 0.09); }
.entry:active { background: rgba(255, 255, 255, 0.09); }
.entry-ico { width: 84rpx; height: 84rpx; flex-shrink: 0; border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font-size: 36rpx; background: rgba(255, 255, 255, 0.07); border: 1rpx solid rgba(255, 255, 255, 0.12); }
.entry-body { flex: 1; min-width: 0; }
.entry-title { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 32rpx; font-weight: 600; color: #eef1ea; }
.entry-sub { display: block; margin-top: 6rpx; font-size: 23rpx; color: #b9c8bd; }
.entry-desc { display: block; margin-top: 8rpx; font-size: 21rpx; color: rgba(238, 241, 234, 0.5); }
.entry-arrow { color: rgba(238, 241, 234, 0.4); font-size: 44rpx; }

.hint { position: relative; z-index: 3; display: block; color: rgba(238, 241, 234, 0.6); font-size: 25rpx; text-align: center; padding: 40rpx 0; }
</style>
