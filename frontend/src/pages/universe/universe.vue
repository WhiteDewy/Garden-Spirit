<template>
  <view class="page">
    <view class="head">
      <text class="title">🪐 我的宇宙</text>
      <text class="sub">认识自己是一生的功课</text>
    </view>

    <!-- 入口一：自我星盘轮（34 子类 · 疗愈） -->
    <view class="entry card wheel" @tap="goWheel">
      <view class="entry-icon">🌌</view>
      <view class="entry-body">
        <text class="entry-title">自我星盘轮</text>
        <text class="entry-sub">{{ litLabel }}</text>
        <text class="entry-desc">34 子类 · 3 星区 · 聊出来的内心地图</text>
      </view>
      <text class="entry-arrow">›</text>
    </view>

    <!-- 入口二：星盘咨询（8 大领域 · 咨询预测） -->
    <view class="entry card consult" @tap="goConsult">
      <view class="entry-icon">🔭</view>
      <view class="entry-body">
        <text class="entry-title">星盘咨询</text>
        <text class="entry-sub">{{ findingLabel }}</text>
        <text class="entry-desc">大领域 · 深度解读 · 带着星盘的视角看生活的难题</text>
      </view>
      <text class="entry-arrow">›</text>
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
  background: linear-gradient(180deg, #0d1f1a 0%, #14332a 60%, #1d4436 100%);
  padding: 48rpx 36rpx;
  box-sizing: border-box;
}
.head { margin-bottom: 40rpx; }
.title { color: #e8f5e9; font-size: 44rpx; font-weight: 600; }
.sub { color: rgba(232, 245, 233, 0.55); font-size: 26rpx; margin-top: 8rpx; display: block; }

.card {
  background: rgba(255, 255, 255, 0.07);
  border-radius: 20rpx;
}
.entry {
  display: flex;
  align-items: center;
  padding: 32rpx 28rpx;
  margin-bottom: 24rpx;
  border-left: 6rpx solid transparent;
}
.entry.wheel { border-left-color: #ffcc80; }
.entry.consult { border-left-color: #80cbc4; }
.entry-icon { font-size: 52rpx; margin-right: 24rpx; }
.entry-body { flex: 1; }
.entry-title { color: #e8f5e9; font-size: 34rpx; font-weight: 600; display: block; }
.entry-sub { color: #a5d6a7; font-size: 24rpx; display: block; margin-top: 6rpx; }
.entry-desc { color: rgba(232, 245, 233, 0.5); font-size: 22rpx; display: block; margin-top: 8rpx; }
.entry-arrow { color: rgba(232, 245, 233, 0.4); font-size: 44rpx; margin-left: 12rpx; }

.hint { color: rgba(232, 245, 233, 0.6); font-size: 26rpx; text-align: center; display: block; padding: 40rpx 0; }
</style>
