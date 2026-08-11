<template>
  <view class="page">
    <view class="head">
      <text class="title">💌 星灵信箱</text>
      <text class="sub">来自星灵的信</text>
    </view>

    <view v-if="loading" class="empty">正在看信……</view>

    <view v-else>
      <!-- 今日来信（每日行运快照，kind=daily） -->
      <view v-if="today" class="letter today">
        <text class="letter-sender">{{ today.sender_zh }}来信</text>
        <text class="letter-date">{{ today.letter_date }}</text>
        <text class="letter-body">{{ today.body }}</text>
        <!-- 今日灵魂碎片（§2.5 每日结算）：数据卡脚注，不是正文 -->
        <view v-if="todayFrags.length" class="frag-card">
          <text class="frag-label">◈ 今日灵魂碎片</text>
          <text class="frag-names">{{ fragNames }}</text>
        </view>
      </view>

      <view class="history-title">过往的信</view>

      <!-- 来信式日记（§6.1/§6.2）：keepsake = 星灵那段完整回复原样成信，
           落款走"内容→情绪需求→疗愈名"推导链；词条式（entry）另加标记 -->
      <view v-for="l in letters" :key="l.id" class="letter" :class="l.kind === 'keepsake' ? 'keepsake' : ''">
        <template v-if="l.kind === 'keepsake'">
          <view class="letter-head">
            <view class="sender-wrap">
              <text class="keepsake-sender">「{{ l.healing_name || l.title || l.sender_zh }}」来信</text>
              <text v-if="l.entry" class="entry-tag">记忆词条</text>
            </view>
            <text class="letter-date">{{ l.letter_date }}</text>
          </view>

          <text class="letter-body">{{ splitKeepsake(l).main }}</text>

          <!-- 灵魂碎片 = 数据卡（脚注），不是正文（§6.1） -->
          <view v-if="splitKeepsake(l).footnote" class="frag-card">
            <text class="frag-label">◈ 今日灵魂碎片</text>
            <text class="frag-names">{{ splitKeepsake(l).footnote }}</text>
          </view>

          <text v-if="splitKeepsake(l).signature" class="keepsake-sig">{{ splitKeepsake(l).signature }}</text>

          <!-- 落款推导链（§6.2 显式可解释）：为什么是这颗星 -->
          <view v-if="l.explain" class="explain" @tap="toggleExplain(l)">
            <text class="explain-toggle">{{ shownExplain.has(l.id) ? "收起推导链 ▲" : "为什么是这颗星落款？ ▼" }}</text>
            <text v-if="shownExplain.has(l.id)" class="explain-body">{{ l.explain }}</text>
          </view>
        </template>

        <template v-else>
          <view class="letter-head">
            <text class="letter-sender">{{ l.sender_zh }}来信</text>
            <text class="letter-date">{{ l.letter_date }}</text>
          </view>
          <text class="letter-body">{{ l.body }}</text>
        </template>
      </view>

      <button class="back" @tap="goChat">想聊点什么 →</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import api, { type SoulFragmentOut } from "@/api/client";

const PERSON_KEY = "gs_person_id";
const loading = ref(true);
const today = ref<any>(null);
const letters = ref<any[]>([]);
// 今日灵魂碎片（§2.5 每日结算）：今天点亮的 top3，贴到今日来信脚注
const todayFrags = ref<SoulFragmentOut[]>([]);
const fragNames = computed(() => todayFrags.value.map((f) => f.name).join(" / "));
// 已展开的"为什么是这颗星"推导链（按 letter.id）
const shownExplain = ref<Set<string>>(new Set());

// §6.1 来信正文 = 星灵那段完整回复（+ 灵魂碎片脚注 + —— 疗愈名落款），
// 前端把脚注/落款拆出来当独立卡片渲染（数据卡不是正文）。
function splitKeepsake(l: any): { main: string; footnote: string; signature: string } {
  const body = l?.body || "";
  const marker = "◈ 今日灵魂碎片：";
  const idx = body.indexOf(marker);
  if (idx < 0) return { main: body, footnote: "", signature: "" };
  const main = body.slice(0, idx).replace(/\n+$/, "");
  const rest = body.slice(idx + marker.length);
  const lines = rest.split("\n").map((s: string) => s.trim()).filter(Boolean);
  const footnote = lines[0] || "";
  const sigLine = lines[lines.length - 1] || "";
  const signature = sigLine.includes("——") ? sigLine : "";
  return { main, footnote, signature };
}

function toggleExplain(l: any) {
  const next = new Set(shownExplain.value);
  if (next.has(l.id)) next.delete(l.id);
  else next.add(l.id);
  shownExplain.value = next;
}

onLoad(async () => {
  const pid = uni.getStorageSync(PERSON_KEY) as string;
  if (!pid) return uni.redirectTo({ url: "/pages/index/index" });
  try {
    today.value = await api.mailboxToday(pid);
    letters.value = await api.letters(pid);
    // 过往 = 去掉今天的（今天已展示在最上）
    letters.value = letters.value.filter((l) => l.id !== today.value.id);
    // 今日灵魂碎片（独立 try：读不到不影响看信，空碎片给希望态由模板兜底）
    try {
      const soul = await api.soulFragmentsToday(pid);
      todayFrags.value = soul.fragments || [];
    } catch {
      todayFrags.value = [];
    }
    // 首页红点：看完今日来信 → 标记已读（fire-and-forget，不阻塞看信）。
    // 失败也不影响：红点多亮一次而已，下次打开信箱会再标记。
    api.markLettersReadToday(pid).catch(() => {});
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

/* 每日来信 / 普通信 */
.letter {
  background: rgba(255,255,255,.07);
  border-radius: 20rpx;
  padding: 28rpx;
  margin-bottom: 20rpx;
}
.letter.today { background: rgba(124,179,66,.15); border: 1rpx solid rgba(124,179,66,.4); }

/* 来信式日记（keepsake）：疗愈名落款卡，比每日来信更"私信"质感 */
.letter.keepsake {
  background: linear-gradient(180deg, rgba(165,214,167,.12) 0%, rgba(255,255,255,.06) 100%);
  border: 1rpx solid rgba(165,214,167,.25);
  border-left: 6rpx solid #a5d6a7;
}
.letter-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10rpx; }
.sender-wrap { display: flex; align-items: center; flex-wrap: wrap; gap: 12rpx; flex: 1; }
.keepsake-sender { color: #a5d6a7; font-size: 30rpx; font-weight: 600; }
.entry-tag {
  color: #ffe082;
  font-size: 20rpx;
  background: rgba(255,224,130,.14);
  border: 1rpx solid rgba(255,224,130,.35);
  border-radius: 8rpx;
  padding: 2rpx 12rpx;
}
.letter-sender { color: #a5d6a7; font-size: 30rpx; font-weight: 600; }
.letter-date { color: rgba(232,245,233,.45); font-size: 22rpx; }
.letter-body { color: #e8f5e9; font-size: 28rpx; line-height: 1.8; white-space: pre-wrap; }

/* 灵魂碎片脚注卡（数据卡，不是正文） */
.frag-card {
  margin-top: 16rpx;
  background: rgba(255,255,255,.05);
  border-radius: 12rpx;
  padding: 14rpx 18rpx;
  border-left: 4rpx solid rgba(255,224,130,.5);
}
.frag-label { color: #ffe082; font-size: 22rpx; display: block; }
.frag-names { color: rgba(232,245,233,.75); font-size: 24rpx; margin-top: 6rpx; display: block; }

/* —— 疗愈名落款 */
.keepsake-sig { color: rgba(165,214,167,.85); font-size: 24rpx; margin-top: 16rpx; display: block; text-align: right; }

/* 落款推导链（§6.2 显式可解释） */
.explain { margin-top: 14rpx; }
.explain-toggle { color: rgba(232,245,233,.5); font-size: 22rpx; text-decoration: underline; }
.explain-body {
  color: rgba(232,245,233,.7);
  font-size: 22rpx;
  line-height: 1.7;
  margin-top: 8rpx;
  background: rgba(255,255,255,.04);
  border-radius: 10rpx;
  padding: 12rpx 16rpx;
  display: block;
}

.history-title { color: rgba(232,245,233,.5); font-size: 26rpx; margin: 24rpx 0 16rpx; }
.empty { color: rgba(232,245,233,.6); font-size: 28rpx; text-align: center; padding: 100rpx 0; }
.back { margin-top: 20rpx; background: #7cb342; color: #fff; border-radius: 14rpx; }
</style>
