<template>
  <view class="page gs-time-page" :class="phaseClass">
    <view class="sun-glow" aria-hidden="true"></view>

    <view class="head">
      <view>
        <text class="eyebrow">INNER JOURNAL</text>
        <text class="title">日记</text>
      </view>
      <view class="icon-btn" aria-hidden="true">✦</view>
    </view>
    <text class="sub">星灵的信，和你写下的时刻，都收在这里。</text>

    <view v-if="loading" class="empty">正在看信……</view>

    <view v-else>
      <!-- 今日来信（每日行运快照，kind=daily）→ 今日纸页 -->
      <view v-if="today" class="paper today">
        <view class="paper-head">
          <text class="paper-date">{{ today.letter_date }}</text>
          <text class="paper-sender">{{ today.sender_zh }}来信</text>
        </view>
        <text class="paper-body">{{ today.body }}</text>
        <!-- 今日灵魂碎片（§2.5 每日结算）：数据卡脚注，不是正文 -->
        <view v-if="todayFrags.length" class="foot-section">
          <text class="foot-label">◈ 今日灵魂碎片</text>
          <text class="foot-line">{{ fragNames }}</text>
        </view>
      </view>

      <!-- 来信式日记（keepsake）→ 手账纸页 -->
      <view v-for="l in letters" :key="l.id" class="paper keepsake">
        <view class="paper-head">
          <view class="sender-wrap">
            <text class="paper-sender serif">「{{ l.healing_name || l.title || l.sender_zh }}」来信</text>
            <text v-if="l.entry" class="entry-tag">记忆词条</text>
          </view>
          <text class="paper-date">{{ l.letter_date }}</text>
        </view>

        <text class="paper-body">{{ splitKeepsake(l).main }}</text>

        <!-- 灵魂碎片 = 数据卡（脚注），不是正文（§6.1） -->
        <view v-if="splitKeepsake(l).footnote" class="foot-section">
          <text class="foot-label">◈ 今日灵魂碎片</text>
          <text class="foot-line">{{ splitKeepsake(l).footnote }}</text>
        </view>

        <text v-if="splitKeepsake(l).signature" class="keepsake-sig">{{ splitKeepsake(l).signature }}</text>

        <!-- 落款推导链（§6.2 显式可解释）：为什么是这颗星 -->
        <view v-if="l.explain" class="explain" @tap="toggleExplain(l)">
          <text class="explain-toggle">{{ shownExplain.has(l.id) ? "收起推导链 ▲" : "为什么是这颗星落款？ ▼" }}</text>
          <text v-if="shownExplain.has(l.id)" class="explain-body">{{ l.explain }}</text>
        </view>
      </view>

      <!-- 我的日记（journal）：用户亲手写下的时刻 -->
      <view class="section-label">MY DIARY · 我写下的</view>
      <view v-for="j in journals" :key="j.id" class="paper mine">
        <view class="paper-head">
          <text class="paper-date">{{ j.created_at?.slice(0, 10) || "" }}</text>
          <text class="paper-sender">我</text>
        </view>
        <text class="paper-body">{{ j.content }}</text>
      </view>
      <view v-if="!journals.length" class="empty small">还没有写过。右上角「＋」写下第一刻。</view>

      <!-- 解释线索（从首页移入）→ 星图线索区 -->
      <view v-if="evidence.trigger" class="paper clue">
        <text class="section-label inner">星图留下的线索</text>
        <view class="star-line"><text class="star-ico">✦</text><text>{{ evidence.trigger }}</text></view>
        <view class="star-line"><text class="star-ico">☾</text><text>{{ evidence.memory }}</text></view>
        <view class="star-line"><text class="star-ico">✿</text><text>今日碎片只代表聊过、被照见、做过。</text></view>
      </view>
    </view>

    <button class="write-btn" @tap="writing = true">＋ 写下此刻</button>

    <view v-if="writing" class="write-mask" @tap="writing = false"></view>
    <view v-if="writing" class="write-sheet">
      <text class="write-title">写下此刻</text>
      <textarea v-model="writeDraft" class="write-area" placeholder="不用写给谁看，只是留给自己……" :maxlength="500"></textarea>
      <view class="write-actions">
        <button class="write-cancel" @tap="writing = false">收起</button>
        <button class="write-save" :disabled="saving || !writeDraft.trim()" @tap="saveJournal">
          {{ saving ? "正在收好…" : "收进日记" }}
        </button>
      </view>
    </view>

    <BottomNav active="mailbox" />
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import api, { type SoulFragmentOut } from "@/api/client";
import BottomNav from "@/components/BottomNav.vue";
import { useTimePhase } from "@/utils/timeTheme";

const PERSON_KEY = "gs_person_id";
const loading = ref(true);
const today = ref<any>(null);
const letters = ref<any[]>([]);
const journals = ref<any[]>([]);
// 今日灵魂碎片（§2.5 每日结算）：今天点亮的 top3，贴到今日来信脚注
const todayFrags = ref<SoulFragmentOut[]>([]);
const fragNames = computed(() => todayFrags.value.map((f) => f.name).join(" / "));
// 已展开的"为什么是这颗星"推导链（按 letter.id）
const shownExplain = ref<Set<string>>(new Set());
// 解释线索（从首页移入）：行运触发理由 + 记忆镜头
const evidence = ref<{ trigger: string; memory: string }>({ trigger: "", memory: "" });
// 写日记 composer
const writing = ref(false);
const writeDraft = ref("");
const saving = ref(false);
const { phaseClass, refreshPhase } = useTimePhase();

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

async function loadJournals(pid: string) {
  try {
    journals.value = (await api.journalList(pid)) as any[];
  } catch {
    journals.value = [];
  }
}

async function saveJournal() {
  const content = writeDraft.value.trim();
  if (!content || saving.value) return;
  const pid = uni.getStorageSync(PERSON_KEY) as string;
  saving.value = true;
  try {
    await api.journalCreate({ person_id: pid, content });
    writeDraft.value = "";
    writing.value = false;
    uni.showToast({ title: "已收进日记", icon: "none" });
    await loadJournals(pid);
  } catch (e: any) {
    uni.showToast({ title: e?.message || "暂时没存上，再试一次", icon: "none" });
  } finally {
    saving.value = false;
  }
}

onLoad(async () => {
  refreshPhase();
  const pid = uni.getStorageSync(PERSON_KEY) as string;
  if (!pid) return uni.redirectTo({ url: "/pages/index/index" });
  try {
    today.value = await api.mailboxToday(pid);
    letters.value = await api.letters(pid);
    // 过往 = 去掉今天的（今天已展示在最上）
    letters.value = letters.value.filter((l) => l.id !== today.value.id);
    // 今日灵魂碎片（独立 try：读不到不影响看信，空碎片由模板兜底）
    try {
      const soul = await api.soulFragmentsToday(pid);
      todayFrags.value = soul.fragments || [];
    } catch {
      todayFrags.value = [];
    }
    // 首页红点：看完今日来信 → 标记已读（fire-and-forget，不阻塞看信）
    api.markLettersReadToday(pid).catch(() => {});
    // 解释线索：今日星灵的行运理由 + 记忆镜头（读不到就安静隐藏整卡）
    try {
      const [rec, garden] = await Promise.all([
        api.recommendedSpirits(pid),
        api.garden(pid, undefined),
      ]);
      const trigger = rec.spirits?.[0]?.reason || "";
      const memoryItem = garden.recall?.items?.[0];
      const memory = memoryItem?.summary || memoryItem?.title || memoryItem?.text || "记忆镜头会优先取你确认过、最近聊过的内容";
      evidence.value = { trigger, memory };
    } catch {
      evidence.value = { trigger: "", memory: "" };
    }
    await loadJournals(pid);
  } catch (e: any) {
    letters.value = [];
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: linear-gradient(160deg, #d6d7c8 0%, #b7c3b0 52%, #82967f 100%);
  padding: 48rpx 36rpx 140rpx;
  box-sizing: border-box;
  position: relative;
  color: #293b35;
}
.sun-glow { position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(circle at 78% 12%, rgba(255, 247, 210, 0.8), transparent 25%), radial-gradient(circle at 12% 75%, rgba(255, 255, 255, 0.24), transparent 30%); }
.head { display: flex; justify-content: space-between; align-items: flex-start; position: relative; z-index: 1; }
.eyebrow { display: block; font-size: 19rpx; letter-spacing: 0.16em; color: rgba(41, 59, 53, 0.45); font-weight: 800; }
.title { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 52rpx; font-weight: 600; color: #293b35; margin-top: 6rpx; }
.icon-btn { width: 72rpx; height: 72rpx; border-radius: 50%; border: 1rpx solid rgba(40, 61, 53, 0.12); background: rgba(255, 255, 255, 0.18); display: flex; align-items: center; justify-content: center; color: #35483f; font-size: 30rpx; }
.sub { display: block; font-size: 23rpx; color: rgba(41, 59, 53, 0.55); margin: 10rpx 0 30rpx; position: relative; z-index: 1; }

/* 纸页：横线手账质感 */
.paper { position: relative; z-index: 1; border-radius: 32rpx; background: rgba(250, 248, 235, 0.73); backdrop-filter: blur(16rpx); padding: 34rpx 30rpx; margin-bottom: 24rpx; box-shadow: 0 18rpx 55rpx rgba(59, 76, 62, 0.15); overflow: hidden; }
.paper::after { content: ""; position: absolute; inset: 0; opacity: 0.15; pointer-events: none;
  background: repeating-linear-gradient(0deg, transparent 0 56rpx, rgba(92, 104, 85, 0.35) 56rpx 57rpx); }
.paper > view, .paper > text { position: relative; z-index: 1; }
.paper.today { border: 1rpx solid rgba(255, 255, 255, 0.5); }
.paper.keepsake { border-left: 8rpx solid #718c7c; }
.paper.mine { border-left: 8rpx solid #ad9154; }
.paper.clue { border: 1rpx dashed rgba(64, 81, 69, 0.25); }
.paper-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16rpx; }
.sender-wrap { display: flex; align-items: center; flex-wrap: wrap; gap: 12rpx; flex: 1; }
.paper-date { font-size: 19rpx; letter-spacing: 0.14em; color: #7d887c; }
.paper-sender { font-family: Georgia, "Noto Serif SC", serif; font-size: 30rpx; font-weight: 600; color: #4d6558; }
.paper-sender.serif { color: #526d60; }
.entry-tag { color: #8a6d1f; font-size: 19rpx; background: rgba(173, 145, 84, 0.14); border: 1rpx solid rgba(173, 145, 84, 0.35); border-radius: 8rpx; padding: 2rpx 12rpx; }
.paper-body { display: block; margin-top: 18rpx; font-family: Georgia, "Noto Serif SC", serif; font-size: 28rpx; line-height: 2; color: #40534b; white-space: pre-wrap; }
.foot-section { margin-top: 22rpx; background: rgba(255, 255, 255, 0.5); border-radius: 16rpx; padding: 18rpx 22rpx; border-left: 6rpx solid rgba(173, 145, 84, 0.55); }
.foot-label { display: block; color: #8a6d1f; font-size: 21rpx; }
.foot-line { display: block; color: rgba(64, 83, 75, 0.8); font-size: 23rpx; margin-top: 6rpx; }
.keepsake-sig { display: block; color: rgba(82, 109, 96, 0.85); font-size: 23rpx; margin-top: 18rpx; text-align: right; font-family: Georgia, "Noto Serif SC", serif; }
.explain { margin-top: 16rpx; }
.explain-toggle { color: rgba(64, 83, 75, 0.5); font-size: 21rpx; text-decoration: underline; }
.explain-body { display: block; color: rgba(64, 83, 75, 0.7); font-size: 21rpx; line-height: 1.7; margin-top: 8rpx; background: rgba(255, 255, 255, 0.45); border-radius: 12rpx; padding: 14rpx 18rpx; }

/* 星图线索 */
.section-label { font-size: 19rpx; letter-spacing: 0.16em; color: rgba(41, 59, 53, 0.4); margin: 30rpx 0 16rpx; position: relative; z-index: 1; }
.section-label.inner { margin: 0 0 14rpx; }
.star-line { display: flex; align-items: flex-start; gap: 16rpx; font-family: Georgia, "Noto Serif SC", serif; font-size: 24rpx; line-height: 1.7; color: #40534b; padding: 8rpx 0; }
.star-ico { color: #ad9154; font-size: 30rpx; line-height: 1.4; }

.empty { color: rgba(41, 59, 53, 0.55); font-size: 27rpx; text-align: center; padding: 100rpx 0; position: relative; z-index: 1; }
.empty.small { padding: 20rpx 0 40rpx; font-size: 23rpx; text-align: left; }

/* 写下此刻 */
.write-btn { position: fixed; right: 36rpx; bottom: calc(148rpx + env(safe-area-inset-bottom)); border: 0; border-radius: 44rpx; padding: 24rpx 34rpx; background: linear-gradient(135deg, #6b9179, #426552); color: #fff; font-size: 25rpx; box-shadow: 0 16rpx 50rpx rgba(51, 74, 62, 0.28); z-index: 5; line-height: 1.4; }
.write-mask { position: fixed; inset: 0; z-index: 20; background: rgba(24, 36, 32, 0.35); }
.write-sheet { position: fixed; left: 24rpx; right: 24rpx; bottom: calc(32rpx + env(safe-area-inset-bottom)); z-index: 21; border-radius: 40rpx; padding: 34rpx 30rpx; background: rgba(250, 248, 235, 0.97); color: #293b35; box-shadow: 0 24rpx 72rpx rgba(30, 45, 38, 0.35); display: grid; gap: 20rpx; }
.write-title { font-family: Georgia, "Noto Serif SC", serif; font-size: 32rpx; font-weight: 600; color: #40534b; }
.write-area { min-height: 220rpx; border-radius: 24rpx; border: 1rpx solid rgba(64, 81, 69, 0.18); background: rgba(255, 255, 255, 0.7); padding: 22rpx 26rpx; font-size: 27rpx; line-height: 1.8; color: #40534b; width: 100%; box-sizing: border-box; }
.write-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 16rpx; }
.write-cancel { border: 1rpx solid rgba(64, 81, 69, 0.2); background: transparent; color: rgba(64, 81, 69, 0.6); border-radius: 20rpx; font-size: 25rpx; padding: 20rpx 0; margin: 0; }
.write-save { border: 0; background: #526d60; color: #fff; border-radius: 20rpx; font-size: 25rpx; padding: 20rpx 0; margin: 0; }
.write-save[disabled] { opacity: 0.5; }
</style>
