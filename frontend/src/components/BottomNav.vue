<template>
  <view class="bottom-nav" role="navigation" aria-label="主导航">
    <view
      v-for="item in items"
      :key="item.key"
      class="nav-item"
      :class="{ active: active === item.key }"
      @tap="go(item.key, item.path)"
    >
      <view class="nav-glyph-wrap">
        <text class="nav-glyph">{{ item.glyph }}</text>
        <text v-if="item.badge" class="nav-badge"></text>
      </view>
      <text class="nav-label">{{ item.label }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(defineProps<{
  active: "garden" | "mailbox" | "universe" | "me";
  letterBadge?: boolean;
  universeBadge?: boolean;
}>(), {
  letterBadge: false,
  universeBadge: false,
});

const items = computed(() => [
  { key: "garden" as const, label: "花园", glyph: "✦", path: "/pages/index/index", badge: false },
  { key: "mailbox" as const, label: "信箱", glyph: "✉", path: "/pages/mailbox/mailbox", badge: props.letterBadge },
  { key: "universe" as const, label: "宇宙", glyph: "◌", path: "/pages/universe/universe", badge: props.universeBadge },
  { key: "me" as const, label: "我的", glyph: "◒", path: "/pages/me/me", badge: false },
]);

function go(key: string, path: string) {
  // 当前 pages.json 使用自定义导航而非 tabBar，所以所有入口都走统一的页面导航。
  if (key === props.active) return;
  uni.navigateTo({ url: path });
}
</script>

<style scoped>
.bottom-nav {
  position: fixed;
  left: 24rpx;
  right: 24rpx;
  bottom: calc(20rpx + env(safe-area-inset-bottom));
  height: 108rpx;
  padding: 10rpx;
  box-sizing: border-box;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6rpx;
  z-index: 20;
  border: 1rpx solid rgba(255, 248, 224, 0.14);
  border-radius: 34rpx;
  background: rgba(9, 25, 21, 0.78);
  box-shadow: 0 18rpx 56rpx rgba(4, 16, 12, 0.24);
  backdrop-filter: blur(26px);
}
.nav-item {
  position: relative;
  min-width: 0;
  border-radius: 26rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3rpx;
  color: rgba(235, 243, 233, 0.48);
  transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease;
}
.nav-item:active { transform: scale(0.95); }
.nav-item.active {
  color: #fff5d6;
  background: linear-gradient(180deg, rgba(240, 210, 139, 0.16), rgba(240, 210, 139, 0.06));
  box-shadow: inset 0 1rpx 0 rgba(255, 248, 224, 0.12);
}
.nav-glyph-wrap { position: relative; line-height: 1; }
.nav-glyph { font-size: 30rpx; }
.nav-item.active .nav-glyph { text-shadow: 0 0 18rpx rgba(240, 210, 139, 0.8); }
.nav-label { font-size: 19rpx; letter-spacing: 0.08em; }
.nav-badge {
  position: absolute;
  right: -12rpx;
  top: -5rpx;
  width: 13rpx;
  height: 13rpx;
  border-radius: 50%;
  background: #ee8e75;
  box-shadow: 0 0 0 6rpx rgba(238, 142, 117, 0.12), 0 0 14rpx rgba(238, 142, 117, 0.65);
}
</style>
