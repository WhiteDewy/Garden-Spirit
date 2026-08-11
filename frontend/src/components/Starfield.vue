<template>
  <view class="starfield">
    <view class="nebula" />
    <view class="stars" />
    <view
      v-for="t in twinkles"
      :key="t.id"
      class="tw"
      :style="{ left: t.x, top: t.y, animationDelay: t.d + 's' }"
    />
    <view class="vignette" />
  </view>
</template>

<script setup lang="ts">
// 深空银河背景：星云漂移 + 静态星野 + 偶烁金星 + 边缘渐晕。
// 依赖父级 .page 提供的 CSS 变量（--gold-bright 等）。
const twinkles = [
  { id: 1, x: "8vw", y: "12vh", d: 0 }, { id: 2, x: "26vw", y: "6vh", d: 1.2 },
  { id: 3, x: "55vw", y: "18vh", d: 0.6 }, { id: 4, x: "72vw", y: "8vh", d: 1.8 },
  { id: 5, x: "90vw", y: "24vh", d: 0.3 }, { id: 6, x: "14vw", y: "46vh", d: 2.2 },
  { id: 7, x: "66vw", y: "58vh", d: 1.5 }, { id: 8, x: "38vw", y: "84vh", d: 0.9 },
  { id: 9, x: "84vw", y: "76vh", d: 2.0 }, { id: 10, x: "48vw", y: "32vh", d: 2.6 },
];
</script>

<style scoped>
.starfield {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}

/* 星云带：screen 叠加 + 极慢漂移 */
.nebula {
  position: absolute;
  inset: -12%;
  background:
    radial-gradient(ellipse 58% 44% at 16% 10%, rgba(107, 91, 149, 0.20) 0%, transparent 70%),
    radial-gradient(ellipse 44% 38% at 84% 28%, rgba(100, 140, 180, 0.13) 0%, transparent 70%),
    radial-gradient(ellipse 50% 42% at 66% 80%, rgba(155, 100, 130, 0.13) 0%, transparent 72%),
    radial-gradient(ellipse 38% 32% at 28% 92%, rgba(120, 90, 160, 0.11) 0%, transparent 70%);
  mix-blend-mode: screen;
  animation: drift 90s ease-in-out infinite alternate;
}

/* 静态星野 */
.stars {
  position: absolute;
  left: 0;
  top: 0;
  width: 3rpx;
  height: 3rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.7);
  box-shadow:
    8vw 6vh rgba(255, 255, 255, 0.55),
    20vw 14vh rgba(216, 226, 255, 0.45),
    33vw 4vh rgba(255, 255, 255, 0.35),
    45vw 11vh rgba(244, 213, 141, 0.45),
    58vw 7vh rgba(216, 226, 255, 0.4),
    70vw 15vh rgba(255, 255, 255, 0.6),
    82vw 5vh rgba(244, 213, 141, 0.35),
    92vw 12vh rgba(216, 226, 255, 0.45),
    5vw 32vh rgba(255, 255, 255, 0.4),
    15vw 45vh rgba(216, 226, 255, 0.55),
    28vw 38vh rgba(255, 255, 255, 0.35),
    40vw 30vh rgba(244, 213, 141, 0.45),
    52vw 48vh rgba(216, 226, 255, 0.45),
    63vw 35vh rgba(255, 255, 255, 0.6),
    75vw 42vh rgba(255, 255, 255, 0.4),
    88vw 33vh rgba(216, 226, 255, 0.5),
    10vw 62vh rgba(255, 255, 255, 0.45),
    24vw 72vh rgba(216, 226, 255, 0.35),
    36vw 58vh rgba(244, 213, 141, 0.5),
    48vw 68vh rgba(255, 255, 255, 0.4),
    60vw 64vh rgba(216, 226, 255, 0.5),
    72vw 76vh rgba(255, 255, 255, 0.35),
    85vw 60vh rgba(244, 213, 141, 0.4),
    95vw 70vh rgba(216, 226, 255, 0.4),
    6vw 88vh rgba(255, 255, 255, 0.5),
    18vw 95vh rgba(216, 226, 255, 0.4),
    32vw 84vh rgba(255, 255, 255, 0.35),
    46vw 92vh rgba(244, 213, 141, 0.4),
    58vw 86vh rgba(216, 226, 255, 0.5),
    70vw 94vh rgba(255, 255, 255, 0.4),
    83vw 88vh rgba(244, 213, 141, 0.5),
    90vw 97vh rgba(216, 226, 255, 0.35),
    11vw 22vh rgba(255, 255, 255, 0.5),
    66vw 28vh rgba(216, 226, 255, 0.4),
    39vw 52vh rgba(244, 213, 141, 0.5),
    82vw 72vh rgba(255, 255, 255, 0.35),
    26vw 90vh rgba(216, 226, 255, 0.45),
    54vw 22vh rgba(244, 213, 141, 0.4);
}

/* 偶烁金星 */
.tw {
  position: absolute;
  width: 5rpx;
  height: 5rpx;
  border-radius: 50%;
  background: rgba(244, 213, 141, 0.9);
  box-shadow: 0 0 10rpx rgba(244, 213, 141, 0.8);
  animation: twinkle 3.8s ease-in-out infinite;
}

/* 边缘渐晕：聚焦中心 */
.vignette {
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at 50% 34%, transparent 52%, rgba(4, 2, 12, 0.5) 100%);
}

@keyframes twinkle {
  0%, 100% { opacity: 0.15; transform: scale(1); }
  50% { opacity: 0.95; transform: scale(1.18); }
}
@keyframes drift {
  from { transform: translate3d(0, 0, 0) scale(1); }
  to { transform: translate3d(-3%, 2%, 0) scale(1.06); }
}

@media (prefers-reduced-motion: reduce) {
  .tw,
  .nebula { animation: none !important; }
}
</style>
