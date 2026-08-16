<template>
  <view class="garden-v7">
    <view class="v7-sky" aria-hidden="true">
      <view class="v7-moon"></view>
      <view class="v7-glow glow-one"></view>
      <view class="v7-glow glow-two"></view>
      <view class="v7-horizon"></view>
      <view class="v7-star star-one">✦</view>
      <view class="v7-star star-two">✧</view>
      <view class="v7-star star-three">·</view>
    </view>

    <view class="v7-date">{{ shortDate }}</view>

    <view class="v7-companion" @tap="$emit('chat')">
      <view class="v7-aura"></view>
      <view class="v7-spark spark-one">✦</view>
      <view class="v7-spark spark-two">✧</view>
      <view class="v7-spirit-stage">
        <SpiritPortrait :planet="spiritPlanet" />
      </view>
      <text class="v7-name">{{ spiritName }}</text>
      <text class="v7-line">{{ spiritLine }}</text>
    </view>

    <button class="v7-chat-button" @tap.stop="$emit('chat')">和它聊聊 <text>→</text></button>

    <BottomNav
      active="garden"
      :letter-badge="!!gardenState?.letter_unread"
      :universe-badge="(gardenState?.pending_verifications ?? 0) > 0"
    />
  </view>
</template>

<script setup lang="ts">
import { computed } from "vue";
import BottomNav from "@/components/BottomNav.vue";
import SpiritPortrait from "@/components/SpiritPortrait.vue";
import type { GardenState } from "@/api/client";

const props = defineProps<{
  spiritName: string;
  spiritPlanet: string;
  spiritLine: string;
  gardenState: GardenState | null;
}>();

defineEmits<{ (event: "chat"): void }>();

const shortDate = computed(() => {
  const d = new Date();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${month} · ${day}`;
});
</script>

<style scoped>
.garden-v7 {
  position: relative;
  z-index: 1;
  min-height: calc(100vh - 166rpx);
  padding: 16rpx 36rpx 148rpx;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: center;
  overflow: hidden;
}
.v7-sky { position: absolute; inset: 0; overflow: hidden; pointer-events: none; }
.v7-sky::before { content: ''; position: absolute; inset: 0; background: linear-gradient(180deg, rgba(255,255,255,0.16), transparent 46%, rgba(21,66,51,0.12)); }
.v7-moon { position: absolute; right: 76rpx; top: 82rpx; width: 86rpx; height: 86rpx; border-radius: 50%; background: rgba(255, 242, 205, 0.84); box-shadow: 0 0 86rpx rgba(255, 227, 157, 0.34); opacity: 0; }
.v7-glow { position: absolute; border-radius: 50%; filter: blur(70rpx); }
.glow-one { width: 440rpx; height: 440rpx; right: -160rpx; top: -180rpx; background: rgba(244, 213, 144, 0.2); }
.glow-two { width: 420rpx; height: 360rpx; left: -180rpx; bottom: 50rpx; background: rgba(144, 200, 173, 0.16); }
.v7-horizon { position: absolute; left: -12%; right: -12%; bottom: -18%; height: 42%; border-radius: 50% 50% 0 0 / 28% 28% 0 0; background: linear-gradient(180deg, rgba(137, 171, 139, 0.42), rgba(70, 112, 83, 0.3)); filter: blur(1px); }
.v7-star { position: absolute; color: rgba(255, 239, 184, 0.75); text-shadow: 0 0 18rpx rgba(255, 223, 137, 0.72); }
.star-one { left: 18%; top: 24%; font-size: 22rpx; }
.star-two { right: 21%; top: 32%; font-size: 20rpx; }
.star-three { left: 30%; top: 58%; font-size: 32rpx; opacity: 0.5; }
.v7-date { position: relative; z-index: 2; align-self: flex-start; margin-top: 12rpx; color: rgba(255, 247, 231, 0.58); font-size: 21rpx; letter-spacing: 0.18em; }
.v7-companion { position: relative; z-index: 2; width: 100%; min-height: 560rpx; margin-top: 26rpx; display: flex; flex-direction: column; align-items: center; justify-content: center; cursor: pointer; }
.v7-aura { position: absolute; width: 430rpx; height: 430rpx; border-radius: 50%; background: radial-gradient(circle, rgba(255, 248, 220, 0.58), rgba(240, 210, 139, 0.16) 42%, transparent 70%); filter: blur(8rpx); animation: v7Aura 6s ease-in-out infinite; }
.v7-spirit-stage { position: relative; z-index: 2; width: 330rpx; height: 360rpx; display: flex; align-items: center; justify-content: center; border-radius: 48% 48% 42% 42%; background: radial-gradient(circle at 50% 18%, rgba(255,255,255,0.54), transparent 28%), linear-gradient(180deg, rgba(255, 248, 220, 0.2), rgba(123, 170, 139, 0.18)); border: 1rpx solid rgba(255,255,255,0.24); box-shadow: inset 0 1rpx rgba(255,255,255,0.3), 0 28rpx 90rpx rgba(22, 53, 45, 0.24); backdrop-filter: blur(8px); animation: v7Float 6s ease-in-out infinite; overflow: hidden; }
.v7-spirit-stage :deep(.portrait) { width: 88%; height: 88%; }
.v7-spirit-stage :deep(.portrait-image) { filter: drop-shadow(0 22rpx 20rpx rgba(30, 53, 42, 0.24)); }
.v7-spirit-stage :deep(.portrait-glyph) { font-size: 124rpx; color: rgba(255, 248, 220, 0.88); }
.v7-name { position: relative; z-index: 3; margin-top: 30rpx; color: #fff7e7; font-family: Georgia, "Noto Serif SC", serif; font-size: 38rpx; font-weight: 600; letter-spacing: 0.03em; text-shadow: 0 2rpx 22rpx rgba(17, 38, 31, 0.24); }
.v7-line { position: relative; z-index: 3; max-width: 560rpx; margin-top: 14rpx; color: rgba(255, 247, 231, 0.78); font-family: Georgia, "Noto Serif SC", serif; font-size: 25rpx; line-height: 1.65; text-align: center; }
.v7-spark { position: absolute; z-index: 4; color: #f3d58d; text-shadow: 0 0 18rpx rgba(243, 213, 141, 0.88); animation: v7Spark 4s ease-in-out infinite; }
.spark-one { left: 23%; top: 28%; font-size: 28rpx; }
.spark-two { right: 22%; top: 45%; font-size: 20rpx; animation-delay: -1.4s; }
.v7-chat-button { position: relative; z-index: 4; min-width: 260rpx; min-height: 82rpx; padding: 18rpx 34rpx; margin: 8rpx 0 0; border: 0; border-radius: 999rpx; background: #f0d28b; color: #254536; font-size: 25rpx; font-weight: 650; box-shadow: 0 18rpx 48rpx rgba(27, 58, 45, 0.24); }
.v7-chat-button text { margin-left: 8rpx; }
@keyframes v7Aura { 50% { transform: scale(1.08); opacity: 0.72; } }
@keyframes v7Float { 50% { transform: translateY(-10rpx); } }
@keyframes v7Spark { 50% { transform: translateY(-10rpx) rotate(8deg); opacity: 0.58; } }

:global(.stage-garden.phase-morning) .v7-sky::before { background: linear-gradient(180deg, rgba(248, 252, 243, 0.22), transparent 48%, rgba(89, 139, 94, 0.12)); }
:global(.stage-garden.phase-noon) .v7-sky::before { background: linear-gradient(180deg, rgba(255, 249, 214, 0.28), transparent 48%, rgba(85, 139, 82, 0.14)); }
:global(.stage-garden.phase-dusk) .v7-sky::before { background: linear-gradient(180deg, rgba(66, 57, 98, 0.3), rgba(235, 178, 149, 0.08) 50%, rgba(42, 73, 62, 0.2)); }
:global(.stage-garden.phase-night) .v7-sky::before { background: linear-gradient(180deg, rgba(34, 47, 70, 0.18), transparent 48%, rgba(24, 62, 53, 0.12)); }
:global(.stage-garden.phase-dusk) .v7-moon,
:global(.stage-garden.phase-night) .v7-moon { opacity: 1; }
:global(.stage-garden.phase-morning) .v7-name,
:global(.stage-garden.phase-noon) .v7-name { color: #29483a; text-shadow: none; }
:global(.stage-garden.phase-morning) .v7-line,
:global(.stage-garden.phase-noon) .v7-line { color: rgba(41, 72, 58, 0.72); }
:global(.stage-garden.phase-morning) .v7-chat-button,
:global(.stage-garden.phase-noon) .v7-chat-button { background: #416b4f; color: #fff7e7; }
</style>
