<template>
  <view class="page">
    <view class="head">
      <text class="title">💌 星灵信箱</text>
      <text class="sub">来自星灵的信</text>
    </view>

    <view v-if="loading" class="empty">正在看信……</view>

    <view v-else>
      <view v-if="today" class="letter today">
        <text class="letter-sender">{{ today.sender_zh }}来信</text>
        <text class="letter-date">{{ today.letter_date }}</text>
        <text class="letter-body">{{ today.body }}</text>
      </view>

      <view class="history-title">过往的信</view>
      <view v-for="l in letters" :key="l.id" class="letter">
        <view class="letter-head">
          <text class="letter-sender">{{ l.sender_zh }}来信</text>
          <text class="letter-date">{{ l.letter_date }}</text>
        </view>
        <text class="letter-body">{{ l.body }}</text>
      </view>

      <button class="back" @tap="goChat">想聊点什么 →</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import api from "@/api/client";

const PERSON_KEY = "gs_person_id";
const loading = ref(true);
const today = ref<any>(null);
const letters = ref<any[]>([]);

onLoad(async () => {
  const pid = uni.getStorageSync(PERSON_KEY) as string;
  if (!pid) return uni.redirectTo({ url: "/pages/index/index" });
  try {
    today.value = await api.mailboxToday(pid);
    letters.value = await api.letters(pid);
    // 过往 = 去掉今天的（今天已展示在最上）
    letters.value = letters.value.filter((l) => l.id !== today.value.id);
  } catch (e: any) {
    letters.value = [];
  } finally {
    loading.value = false;
  }
});

function goChat() {
  uni.navigateTo({ url: "/pages/chat/chat" });
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: linear-gradient(180deg, #0d1f1a 0%, #14332a 60%, #1d4436 100%);
  padding: 48rpx 36rpx;
  box-sizing: border-box;
}
.head { margin-bottom: 32rpx; }
.title { color: #e8f5e9; font-size: 44rpx; font-weight: 600; }
.sub { color: rgba(232,245,233,.55); font-size: 26rpx; margin-top: 8rpx; display: block; }
.letter {
  background: rgba(255,255,255,.07);
  border-radius: 20rpx;
  padding: 28rpx;
  margin-bottom: 20rpx;
}
.letter.today { background: rgba(124,179,66,.15); border: 1rpx solid rgba(124,179,66,.4); }
.letter-head { display: flex; justify-content: space-between; margin-bottom: 8rpx; }
.letter-sender { color: #a5d6a7; font-size: 30rpx; font-weight: 600; }
.letter-date { color: rgba(232,245,233,.45); font-size: 22rpx; }
.letter-body { color: #e8f5e9; font-size: 28rpx; line-height: 1.8; white-space: pre-wrap; }
.history-title { color: rgba(232,245,233,.5); font-size: 26rpx; margin: 24rpx 0 16rpx; }
.empty { color: rgba(232,245,233,.6); font-size: 28rpx; text-align: center; padding: 100rpx 0; }
.back { margin-top: 20rpx; background: #7cb342; color: #fff; border-radius: 14rpx; }
</style>
