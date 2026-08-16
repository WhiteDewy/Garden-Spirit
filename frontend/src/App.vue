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

/* 功能页四套真实光线：不是只换一层墨绿色，而是连天空、文字和玻璃层一起换。 */
.gs-time-page.phase-morning {
  background: radial-gradient(circle at 78% 8%, rgba(255, 251, 225, 0.92), transparent 28%),
    linear-gradient(160deg, #d8eee7 0%, #f5f0dc 56%, #c8dbbd 100%) !important;
  color: #29463a !important;
}
.gs-time-page.phase-noon {
  background: radial-gradient(circle at 76% 12%, rgba(255, 246, 188, 0.9), transparent 26%),
    linear-gradient(160deg, #b9e0e5 0%, #f5edc9 48%, #a9cb91 100%) !important;
  color: #29463a !important;
}
.gs-time-page.phase-dusk {
  background: radial-gradient(circle at 75% 16%, rgba(255, 208, 164, 0.7), transparent 24%),
    linear-gradient(160deg, #9c9fb9 0%, #d8b4a7 44%, #526c66 100%) !important;
  color: #fff7e7 !important;
}
.gs-time-page.phase-night {
  background: radial-gradient(circle at 70% 10%, rgba(232, 203, 130, 0.12), transparent 24%),
    linear-gradient(160deg, #0b1628 0%, #102a31 52%, #12392d 100%) !important;
  color: #f6f0df !important;
}
.gs-time-page.phase-morning .eyebrow,
.gs-time-page.phase-noon .eyebrow,
.gs-time-page.phase-morning .sub,
.gs-time-page.phase-noon .sub,
.gs-time-page.phase-morning .copy-p,
.gs-time-page.phase-noon .copy-p { color: rgba(41, 70, 58, 0.62) !important; }
.gs-time-page.phase-morning .title,
.gs-time-page.phase-noon .title,
.gs-time-page.phase-morning .copy-h,
.gs-time-page.phase-noon .copy-h { color: #29463a !important; }
.gs-time-page.phase-dusk .eyebrow,
.gs-time-page.phase-night .eyebrow,
.gs-time-page.phase-dusk .sub,
.gs-time-page.phase-night .sub,
.gs-time-page.phase-dusk .copy-p,
.gs-time-page.phase-night .copy-p { color: rgba(255, 247, 231, 0.62) !important; }
.gs-time-page.phase-dusk .title,
.gs-time-page.phase-night .title,
.gs-time-page.phase-dusk .copy-h,
.gs-time-page.phase-night .copy-h { color: #fff7e7 !important; }

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
