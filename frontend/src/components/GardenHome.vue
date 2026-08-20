<template>
  <view class="garden-v8 moon-home">
    <view class="garden-scene" aria-hidden="true">
      <video
        class="scene-video"
        src="/static/videos/moon_spirit.mp4"
        :autoplay="true"
        :loop="true"
        :muted="true"
        :controls="false"
        :show-center-play-btn="false"
        :show-fullscreen-btn="false"
        :show-play-btn="false"
        :enable-progress-gesture="false"
        object-fit="cover"
        playsinline
        webkit-playsinline
      ></video>
      <view class="scene-veil"></view>
      <view class="scene-vignette"></view>
      <text v-for="n in 18" :key="`moon-star-${n}`" :class="['moon-star', `moon-star-${n}`]">✦</text>
    </view>

    <view class="moon-topline">
      <view>
        <text class="moon-kicker">星灵花园</text>
        <text class="moon-date">{{ shortDate }}</text>
      </view>
      <text class="moon-state">月亮星灵</text>
    </view>

    <view class="moon-dialogue" aria-label="月亮星灵的指引">
      <view
        v-for="(bubble, index) in guideBubbles"
        :key="bubble.key"
        :class="['guide-bubble', bubble.tone, { tappable: !!bubble.action }]"
        :style="{ animationDelay: `${index * 0.18}s` }"
        @tap.stop="handleBubbleTap(bubble)"
      >
        <text class="bubble-text">{{ bubble.text }}</text>
        <text v-if="bubble.hint" class="bubble-hint">{{ bubble.hint }}</text>
        <text v-if="bubble.action" class="bubble-arrow">→</text>
      </view>
    </view>

    <view class="moon-actions">
      <button class="moon-chat-button" @tap.stop="startMoonChat">
        <text class="button-glow">✦</text>
        <text>把今天说给月亮星灵听</text>
      </button>
      <text class="moon-caption">也可以什么都不问，只是慢慢靠近。</text>
    </view>

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
import type { GardenState } from "@/api/client";

interface GuideBubble {
  key: string;
  text: string;
  hint?: string;
  tone?: "hello" | "soft" | "memory" | "light" | "warn";
  action?: "chat" | "continue" | "mailbox" | "universe";
  prompt?: string;
}

const props = defineProps<{
  spiritName: string;
  spiritPlanet: string;
  spiritLine: string;
  gardenState: GardenState | null;
}>();

const emit = defineEmits<{
  (event: "chat", message?: string): void;
  (event: "explain"): void;
}>();

const shortDate = computed(() => {
  const d = new Date();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${month} · ${day}`;
});

const pendingCount = computed(() => props.gardenState?.pending_verifications ?? 0);
const fragmentCount = computed(() => props.gardenState?.soul_fragments?.length ?? 0);
const continueSummary = computed(() => {
  const text = props.gardenState?.continue_from?.summary?.trim() || "接上上次那段话";
  return text.length > 18 ? `${text.slice(0, 18)}…` : text;
});

const guideBubbles = computed<GuideBubble[]>(() => {
  const bubbles: GuideBubble[] = [
    { key: "hello", text: "你回来了。", tone: "hello" },
    { key: "listen", text: "可以问一个问题，也可以什么都不问。", tone: "soft" },
  ];

  if (props.gardenState?.continue_from) {
    bubbles.push({
      key: "continue",
      text: "昨天那句话，还可以继续说。",
      hint: continueSummary.value,
      tone: "memory",
      action: "continue",
    });
  }

  if (props.gardenState?.letter_unread) {
    bubbles.push({ key: "letter", text: "有一封今天的来信。", tone: "memory", action: "mailbox" });
  }

  if (fragmentCount.value > 0) {
    bubbles.push({
      key: "fragments",
      text: `${fragmentCount.value} 个地方，正在发光。`,
      tone: "light",
      action: "universe",
    });
  }

  if (pendingCount.value > 0) {
    bubbles.push({
      key: "pending",
      text: `${pendingCount.value} 条判断，想等你确认。`,
      tone: "warn",
      action: "universe",
    });
  }

  bubbles.push({
    key: "lost",
    text: "如果不知道从哪开始，就只说：我今天有一点迷茫。",
    tone: "soft",
    action: "chat",
    prompt: "我今天有一点迷茫，想和月亮星灵慢慢说说。",
  });

  return bubbles.slice(0, 7);
});

function startMoonChat() {
  emit("chat", "我想把今天的感觉，说给月亮星灵听。");
}

function continueYesterday() {
  const summary = props.gardenState?.continue_from?.summary?.trim();
  emit("chat", summary ? `我们接着上次聊到的：${summary}` : undefined);
}

function openMailbox() {
  uni.reLaunch({ url: "/pages/mailbox/mailbox" });
}

function openUniverse() {
  uni.reLaunch({ url: "/pages/universe/universe" });
}

function handleBubbleTap(bubble: GuideBubble) {
  if (!bubble.action) return;
  if (bubble.action === "chat") emit("chat", bubble.prompt);
  if (bubble.action === "continue") continueYesterday();
  if (bubble.action === "mailbox") openMailbox();
  if (bubble.action === "universe") openUniverse();
}
</script>

<style scoped>
.garden-v8 {
  position: relative;
  z-index: 1;
  min-height: 100vh;
  padding: 38rpx 34rpx calc(154rpx + env(safe-area-inset-bottom));
  box-sizing: border-box;
  overflow: hidden;
  color: #fff7e7;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 28rpx;
}
.garden-scene { position: fixed; inset: 0; overflow: hidden; pointer-events: none; background: #050914; }
.scene-video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; opacity: 0.96; transform: scale(1.01); }
.scene-veil { position: absolute; inset: 0; background: linear-gradient(180deg, rgba(2, 5, 15, 0.22), rgba(4, 11, 21, 0.12) 32%, rgba(3, 12, 19, 0.52) 72%, rgba(2, 8, 12, 0.78)); }
.scene-vignette { position: absolute; inset: 0; background: radial-gradient(circle at 50% 28%, rgba(255, 230, 171, 0.12), transparent 38%), radial-gradient(circle at 50% 58%, transparent 28%, rgba(1, 5, 11, 0.42) 100%); }
.moon-star { position: absolute; color: rgba(255, 239, 184, 0.72); font-size: 12rpx; text-shadow: 0 0 18rpx rgba(255, 223, 137, 0.82); animation: moonTwinkle 4.6s ease-in-out infinite; }
.moon-star:nth-child(2n) { font-size: 8rpx; opacity: 0.48; animation-duration: 5.8s; }
.moon-star:nth-child(3n) { font-size: 15rpx; opacity: 0.86; }
.moon-star-1 { left: 9%; top: 12%; } .moon-star-2 { left: 22%; top: 19%; animation-delay: .6s; } .moon-star-3 { left: 81%; top: 13%; animation-delay: 1.3s; }
.moon-star-4 { left: 68%; top: 24%; animation-delay: 2.2s; } .moon-star-5 { left: 14%; top: 34%; animation-delay: 1.6s; } .moon-star-6 { left: 91%; top: 38%; animation-delay: .3s; }
.moon-star-7 { left: 28%; top: 48%; animation-delay: 2.7s; } .moon-star-8 { left: 74%; top: 52%; animation-delay: 1.1s; } .moon-star-9 { left: 8%; top: 63%; animation-delay: 3s; }
.moon-star-10 { left: 88%; top: 67%; animation-delay: 1.9s; } .moon-star-11 { left: 36%; top: 74%; animation-delay: .9s; } .moon-star-12 { left: 61%; top: 82%; animation-delay: 2.4s; }
.moon-star-13 { left: 18%; top: 87%; animation-delay: 3.2s; } .moon-star-14 { left: 78%; top: 91%; animation-delay: .4s; } .moon-star-15 { left: 47%; top: 11%; animation-delay: 1.8s; }
.moon-star-16 { left: 54%; top: 36%; animation-delay: 2.9s; } .moon-star-17 { left: 39%; top: 58%; animation-delay: .2s; } .moon-star-18 { left: 94%; top: 82%; animation-delay: 2.1s; }
.moon-topline { position: relative; z-index: 3; display: flex; justify-content: space-between; align-items: flex-start; gap: 24rpx; }
.moon-kicker { display: block; font-size: 20rpx; letter-spacing: 0.2em; color: rgba(255, 247, 231, 0.46); font-weight: 800; }
.moon-date { display: block; margin-top: 8rpx; font-size: 20rpx; letter-spacing: 0.16em; color: rgba(255, 247, 231, 0.58); }
.moon-state { padding: 12rpx 18rpx; border-radius: 999rpx; border: 1rpx solid rgba(255, 247, 231, 0.16); background: rgba(8, 18, 28, 0.2); color: rgba(255, 247, 231, 0.72); font-size: 20rpx; letter-spacing: 0.12em; backdrop-filter: blur(18px); }
.moon-dialogue { position: relative; z-index: 3; width: 100%; display: flex; flex-direction: column; gap: 16rpx; margin-top: auto; margin-bottom: 12rpx; }
.guide-bubble { position: relative; max-width: 610rpx; align-self: flex-start; padding: 20rpx 26rpx; border-radius: 30rpx 30rpx 30rpx 10rpx; border: 1rpx solid rgba(255, 248, 224, 0.16); background: rgba(8, 18, 28, 0.36); box-shadow: 0 18rpx 52rpx rgba(0, 0, 0, 0.16), inset 0 1rpx 0 rgba(255, 255, 255, 0.08); backdrop-filter: blur(24px); opacity: 0; transform: translateY(18rpx); animation: bubbleIn 0.72s ease forwards; }
.guide-bubble:nth-child(2n) { align-self: flex-end; border-radius: 30rpx 30rpx 10rpx 30rpx; background: rgba(255, 248, 224, 0.12); }
.guide-bubble.hello { max-width: 320rpx; background: rgba(255, 248, 224, 0.14); }
.guide-bubble.memory { background: rgba(89, 104, 145, 0.28); }
.guide-bubble.light { background: rgba(240, 210, 139, 0.16); }
.guide-bubble.warn { background: rgba(238, 142, 117, 0.15); }
.guide-bubble.tappable:active { transform: translateY(18rpx) scale(0.98); }
.bubble-text { display: block; color: #fff8e8; font-family: Georgia, "Noto Serif SC", serif; font-size: 29rpx; line-height: 1.58; letter-spacing: 0.01em; text-shadow: 0 2rpx 20rpx rgba(0, 0, 0, 0.24); }
.bubble-hint { display: block; margin-top: 8rpx; color: rgba(255, 248, 232, 0.56); font-size: 21rpx; line-height: 1.45; }
.bubble-arrow { position: absolute; right: 22rpx; bottom: 14rpx; color: rgba(240, 210, 139, 0.82); font-size: 23rpx; }
.moon-actions { position: relative; z-index: 4; width: 100%; display: grid; gap: 14rpx; }
.moon-chat-button { position: relative; min-height: 96rpx; margin: 0; border: 0; border-radius: 999rpx; background: linear-gradient(135deg, rgba(255, 241, 185, 0.98), rgba(226, 187, 109, 0.98)); color: #23342f; font-size: 27rpx; font-weight: 800; letter-spacing: 0.02em; box-shadow: 0 22rpx 72rpx rgba(4, 12, 18, 0.34), 0 0 44rpx rgba(240, 210, 139, 0.34); display: flex; align-items: center; justify-content: center; gap: 12rpx; }
.moon-chat-button::after { display: none; }
.moon-chat-button:active { transform: scale(0.98); }
.button-glow { color: #5f4a1f; text-shadow: 0 0 16rpx rgba(255, 255, 255, 0.86); }
.moon-caption { text-align: center; color: rgba(255, 247, 231, 0.56); font-size: 21rpx; letter-spacing: 0.02em; }
@keyframes bubbleIn { to { opacity: 1; transform: translateY(0); } }
@keyframes moonTwinkle { 50% { opacity: 0.28; transform: scale(0.74); } }
</style>
