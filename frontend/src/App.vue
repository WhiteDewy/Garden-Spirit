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
