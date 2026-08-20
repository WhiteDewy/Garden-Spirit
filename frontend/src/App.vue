<script setup lang="ts">
import { onLaunch, onShow, onHide } from "@dcloudio/uni-app";
onLaunch(() => {
  console.log("App Launch");
});
onShow(() => {
  console.log("App Show");
});
onHide(() => {
  console.log("App Hide");
});
</script>
<style>
/* 星灵花园 · 跨页设计 token
 * 欢迎/注册保留深空序章，进入功能页后统一切换到“深林 + 月金 + 雾玻璃”语言。
 * 页面内仍可用局部变量做昼夜/星区变化，但不要再引入完全独立的底色体系。
 */
:root {
  --gs-forest-950: #081613;
  --gs-forest-900: #0d211c;
  --gs-forest-800: #15352b;
  --gs-forest-700: #244b3d;
  --gs-mist: #edf3e8;
  --gs-paper: #f8f5e8;
  --gs-gold: #f0d28b;
  --gs-gold-soft: rgba(240, 210, 139, 0.18);
  --gs-sage: #a8c9ad;
  --gs-ink: #203d32;
  --gs-muted: rgba(235, 243, 233, 0.58);
  --gs-line: rgba(255, 248, 224, 0.12);
  --gs-glass-dark: rgba(11, 30, 25, 0.72);
  --gs-glass-light: rgba(249, 247, 235, 0.72);
  --gs-radius-card: 30rpx;
  --gs-radius-pill: 999rpx;
  --gs-shadow-soft: 0 18rpx 60rpx rgba(4, 17, 13, 0.2);
  --gs-font-display: Georgia, "Noto Serif SC", "Songti SC", serif;
  --gs-font-body: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Microsoft YaHei", sans-serif;
}

page, body {
  background: var(--gs-forest-950);
  font-family: var(--gs-font-body);
}

/* 功能页只在这里领取昼夜变量；每个页面自己决定背景构图，避免全局样式抢控制权。 */
.gs-time-page {
  --gs-phase-text: #f6f0df;
  --gs-phase-muted: rgba(255, 247, 231, 0.62);
  --gs-phase-card: rgba(255, 255, 255, 0.06);
  --gs-phase-line: rgba(255, 248, 224, 0.12);
  --gs-phase-glow: rgba(232, 203, 130, 0.12);
}
.gs-time-page.phase-morning,
.gs-time-page.phase-noon {
  --gs-phase-text: #29463a;
  --gs-phase-muted: rgba(41, 70, 58, 0.62);
  --gs-phase-card: rgba(255, 255, 255, 0.32);
  --gs-phase-line: rgba(41, 70, 58, 0.12);
  --gs-phase-glow: rgba(255, 246, 188, 0.36);
}
.gs-time-page.phase-dusk,
.gs-time-page.phase-night {
  --gs-phase-text: #fff7e7;
  --gs-phase-muted: rgba(255, 247, 231, 0.62);
  --gs-phase-card: rgba(255, 255, 255, 0.06);
  --gs-phase-line: rgba(255, 248, 224, 0.12);
  --gs-phase-glow: rgba(232, 203, 130, 0.12);
}

button, input, textarea {
  font-family: inherit;
}

button::after { border: 0; }

/* 全局：把 uni-app H5 原生 picker 弹层染成深空玻璃风（App.vue 的样式才是真全局，页面级 style 块不会跨组件注入） */
.uni-picker-custom {
  background: rgba(13, 18, 34, 0.97) !important;
  border-top: 1rpx solid rgba(255, 238, 188, 0.14);
  box-shadow: 0 -20rpx 80rpx rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(24px);
}
.uni-picker-header { background: transparent !important; }
.uni-picker-action { color: rgba(255, 248, 235, 0.55) !important; }
.uni-picker-action-confirm { color: #f3dfaa !important; font-weight: 700; }
/* 白底主要来自 picker-view 列表面板与列本体，逐层透明化；字体色同样要强制穿透到条目 */
.uni-picker-container uni-picker-view,
.uni-picker-container .uni-picker-view-wrapper,
.uni-picker-container uni-picker-view-column,
.uni-picker-container uni-picker-view-column * {
  background: transparent !important;
  background-color: transparent !important;
  color: rgba(255, 248, 235, 0.88) !important;
}
.uni-picker-view-mask {
  background-image: linear-gradient(180deg, rgba(13, 18, 34, 0.92), rgba(13, 18, 34, 0.4)),
    linear-gradient(0deg, rgba(13, 18, 34, 0.92), rgba(13, 18, 34, 0.4)) !important;
}
.uni-picker-view-indicator { border-top-color: rgba(255, 238, 188, 0.22) !important; border-bottom-color: rgba(255, 238, 188, 0.22) !important; }

/* 晕动症保护：系统开启「减弱动态效果」时关闭装饰动画（打字机是 JS 驱动，内容不受影响） */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
</style>
