<template>
  <view class="page">
    <view class="header">
      <text class="header-title">🌿 与星灵聊聊</text>
      <view class="header-sub-row">
        <text class="header-sub">{{ personName }}</text>
        <text v-if="trustLabel" class="trust-tag">信任 · {{ trustLabel }}</text>
      </view>
    </view>

    <scroll-view class="messages" scroll-y :scroll-into-view="scrollTo">
      <view v-for="(m, i) in messages" :key="i" class="msg-row" :class="m.role">
        <view class="bubble" :class="m.role">
          <text class="msg-text">{{ m.text }}</text>
        </view>
      </view>
      <view v-if="thinking" class="msg-row assistant">
        <view class="bubble assistant">
          <text class="msg-text">🌙 正在查看你的星图……</text>
        </view>
      </view>
      <view id="bottom" />
    </scroll-view>

    <view class="input-bar">
      <input
        v-model="draft"
        class="chat-input"
        placeholder="想问什么都可以，比如：我该不该离职？"
        confirm-type="send"
        @confirm="send"
      />
      <button class="send-btn" @tap="send">发送</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import api, { ApiError } from "@/api/client";

const PERSON_KEY = "gs_person_id";
const SESSION_KEY = "gs_session_id";

const personName = ref("");
const draft = ref("");
const thinking = ref(false);
const scrollTo = ref("");
const trustLabel = ref("");
const messages = ref<Array<{ role: "user" | "assistant"; text: string }>>([]);

// 信任等级中文名（A2 关系层，与后端 TrustLevel 对齐）
const TRUST_ZH: Record<string, string> = {
  stranger: "陌生",
  acquaintance: "认识",
  trusted: "信任",
  intimate: "深交",
};

onLoad(() => {
  const pid = uni.getStorageSync(PERSON_KEY) as string;
  if (!pid) {
    uni.redirectTo({ url: "/pages/index/index" });
    return;
  }
  api
    .getPerson(pid)
    .then((p) => (personName.value = p.name))
    .catch(() => undefined);

  // A2 关系层：开场白由后端按信任等级生成（首次见面自我介绍 / 老用户欢迎回来）
  api
    .opening(pid)
    .then((o) => {
      if (o.opening) messages.value.push({ role: "assistant", text: o.opening });
      trustLabel.value = TRUST_ZH[o.trust_level] || "";
    })
    .catch(() => {
      messages.value.push({
        role: "assistant",
        text: "今天想聊点什么？事业、感情、还是最近的心情？",
      });
    });
});

async function send() {
  const text = draft.value.trim();
  if (!text || thinking.value) return;
  draft.value = "";
  messages.value.push({ role: "user", text });
  thinking.value = true;
  scrollTo.value = "bottom";

  const pid = uni.getStorageSync(PERSON_KEY) as string;
  const session = (uni.getStorageSync(SESSION_KEY) as string) || undefined;
  try {
    const res = await api.chat({ person_id: pid, session_id: session, message: text });
    uni.setStorageSync(SESSION_KEY, res.session_id);
    messages.value.push({ role: "assistant", text: res.answer });
  } catch (e: any) {
    if (e instanceof ApiError && e.status === 404) {
      // 用户档案过期/被清（如后端数据重建）→ 回建档页重新开始
      uni.removeStorageSync(PERSON_KEY);
      uni.removeStorageSync(SESSION_KEY);
      uni.reLaunch({ url: "/pages/index/index" });
      return;
    }
    messages.value.push({
      role: "assistant",
      text: e && e.message && e.message.includes("timeout")
        ? "星灵想得有点久，请再问一次。"
        : "花园暂时联系不上星灵，请稍后再试。（" + (e?.message || "网络错误") + "）",
    });
  } finally {
    thinking.value = false;
    scrollTo.value = "bottom";
  }
}
</script>

<style scoped>
.page {
  height: 100vh;
  background: linear-gradient(180deg, #0d1f1a 0%, #14332a 60%, #1d4436 100%);
  display: flex;
  flex-direction: column;
}
.header {
  padding: 28rpx 36rpx;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.08);
}
.header-title {
  color: #e8f5e9;
  font-size: 36rpx;
  font-weight: 600;
}
.header-sub-row {
  display: flex;
  align-items: center;
  margin-top: 4rpx;
}
.header-sub {
  color: rgba(232, 245, 233, 0.5);
  font-size: 24rpx;
}
.trust-tag {
  color: #a5d6a7;
  font-size: 22rpx;
  margin-left: 16rpx;
  background: rgba(124, 179, 66, 0.18);
  border-radius: 8rpx;
  padding: 2rpx 12rpx;
}
.messages {
  flex: 1;
  padding: 32rpx 28rpx;
  box-sizing: border-box;
}
.msg-row {
  display: flex;
  margin-bottom: 24rpx;
}
.msg-row.user {
  justify-content: flex-end;
}
.bubble {
  max-width: 78%;
  border-radius: 20rpx;
  padding: 20rpx 26rpx;
  font-size: 30rpx;
  line-height: 1.6;
}
.bubble.user {
  background: #2e7d32;
  color: #e8f5e9;
}
.bubble.assistant {
  background: rgba(255, 255, 255, 0.1);
  color: #e8f5e9;
}
.msg-text {
  white-space: pre-wrap;
  word-break: break-word;
}
.input-bar {
  display: flex;
  align-items: center;
  padding: 20rpx 28rpx;
  padding-bottom: calc(20rpx + env(safe-area-inset-bottom));
  gap: 16rpx;
}
.chat-input {
  flex: 1;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 14rpx;
  padding: 18rpx 24rpx;
  color: #e8f5e9;
  font-size: 30rpx;
}
.send-btn {
  background: #7cb342;
  color: #fff;
  font-size: 28rpx;
  border-radius: 14rpx;
  margin: 0;
  padding: 0 32rpx;
  line-height: 2.4;
}
</style>
