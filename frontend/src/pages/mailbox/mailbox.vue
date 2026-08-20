<template>
  <view class="page gs-time-page" :class="phaseClass">
    <view class="sun-glow" aria-hidden="true"></view>

    <view class="head">
      <view>
        <text class="eyebrow">STAR MAILBOX</text>
        <text class="title">信箱</text>
      </view>
      <view class="icon-btn" aria-hidden="true">✦</view>
    </view>
    <text class="sub">这里不是消息列表，是花园替你保存的重要时刻。</text>

    <view class="asset-grid">
      <view class="asset-card today-asset" :class="{ active: activeFilter === 'today' }" @tap="activeFilter = 'today'">
        <text class="asset-num">{{ dailyTotal }}</text>
        <text class="asset-label">今日日推</text>
      </view>
      <view class="asset-card" :class="{ active: activeFilter === 'memory' }" @tap="activeFilter = 'memory'">
        <text class="asset-num">{{ keepsakeTotal }}</text>
        <text class="asset-label">记忆来信</text>
      </view>
      <view class="asset-card" :class="{ active: activeFilter === 'journal' }" @tap="activeFilter = 'journal'">
        <text class="asset-num">{{ journalTotal }}</text>
        <text class="asset-label">我的手账</text>
      </view>
      <view class="asset-card" :class="{ active: activeFilter === 'fragments' }" @tap="activeFilter = 'fragments'">
        <text class="asset-num">{{ todayFrags.length }}</text>
        <text class="asset-label">今日碎片</text>
      </view>
    </view>

    <view v-if="loading" class="empty">正在看信……</view>

    <view v-else>
      <view v-if="activeFilter === 'today'">
        <text class="section-label">TODAY DAILY · 今日日推</text>
        <!-- 全部日推倒序排列，最新一条即今日日推（不再区分今日/往日） -->
        <view v-if="!dailyLetters.length" class="empty small">今天还没有来信。花园正在等第一缕星光落下来。</view>
        <view v-for="l in dailyLetters" :key="l.id" class="mail-row today-row" @tap="openLetter(l)">
          <view class="mail-row-main">
            <view class="sender-wrap">
              <text class="mail-title">{{ l.title || '今日星灵日推' }}</text>
              <text class="entry-tag daily-tag">日推</text>
            </view>
            <text class="mail-preview">{{ dailyPushPreview(l) }}</text>
          </view>
          <view class="mail-row-side">
            <text class="paper-date">{{ l.letter_date }}</text>
            <text class="mail-open">查看</text>
          </view>
        </view>
        <view v-if="dailyLetters.length && dailyHasMore" class="load-more" @tap="loadDaily()">
          {{ dailyLoading ? "正在收信…" : "加载更早日推" }}
        </view>
      </view>

      <view v-else-if="activeFilter === 'memory'">
        <text class="section-label">MEMORY LETTERS · 记忆来信</text>
        <!-- 来信式日记（keepsake）→ 列表入口，详情里看完整纸页 -->
        <view v-if="!keepsakes.length" class="empty small">还没有记忆来信。聊到重要的时刻，它会被温柔地收进这里。</view>
        <view v-for="l in keepsakes" :key="l.id" class="mail-row keepsake-row" @tap="openLetter(l)">
          <view class="mail-row-main">
            <view class="sender-wrap">
              <text class="mail-title">「{{ l.healing_name || l.title || l.sender_zh }}」来信</text>
              <text v-if="l.entry" class="entry-tag">记忆词条</text>
            </view>
            <text class="mail-preview">{{ splitKeepsake(l).main }}</text>
          </view>
          <view class="mail-row-side">
            <text class="paper-date">{{ l.letter_date }}</text>
            <text class="mail-open">查看</text>
          </view>
        </view>
        <view v-if="keepsakes.length && keepsakeHasMore" class="load-more" @tap="loadKeepsakes()">
          {{ keepsakeLoading ? "正在收信…" : "查看更多记忆来信" }}
        </view>
      </view>

      <view v-else-if="activeFilter === 'journal'">
        <!-- 我的手账（journal）：用户亲手写下的时刻 -->
        <view class="section-label">MY NOTES · 我写下的</view>
        <view v-for="j in journals" :key="j.id" class="paper mine">
          <view class="paper-head">
            <text class="paper-date">{{ j.created_at?.slice(0, 10) || "" }}</text>
            <text class="paper-sender">我</text>
          </view>
          <text class="paper-body">{{ j.content }}</text>
        </view>
        <view v-if="journals.length && journalHasMore" class="load-more" @tap="loadJournals()">
          {{ journalLoading ? "正在收信…" : "查看更多手账" }}
        </view>
        <view v-if="!journals.length" class="empty small">还没有写过。右下角「＋」写下第一刻。</view>
      </view>

      <view v-else-if="activeFilter === 'fragments'">
        <text class="section-label">TODAY FRAGMENTS · 今日碎片</text>
        <view v-if="todayFrags.length" class="paper fragments">
          <view v-for="f in todayFrags" :key="f.id" class="fragment-line">
            <text class="fragment-dot">✦</text>
            <view class="fragment-copy">
              <text class="fragment-name">{{ f.name }}</text>
              <text class="fragment-meta">今天被花园轻轻点亮</text>
            </view>
          </view>
        </view>
        <view v-else class="empty small">今天还没有点亮碎片。和星灵聊聊，花园会慢慢记住你。</view>
      </view>

      <!-- 解释线索（从首页移入）→ 星图线索区 -->
      <view v-if="evidence.trigger" class="paper clue">
        <text class="section-label inner">今日光线 · 星图线索</text>
        <view class="star-line"><text class="star-ico">✦</text><text>{{ evidence.trigger }}</text></view>
        <view class="star-line"><text class="star-ico">☾</text><text>{{ evidence.memory }}</text></view>
        <view class="star-line"><text class="star-ico">✿</text><text>今日碎片只代表聊过、被照见、做过。</text></view>
      </view>
    </view>

    <button class="write-btn" @tap="writing = true">＋ 写下此刻</button>

    <view v-if="selectedLetter" class="detail-mask" @tap="selectedLetter = null"></view>
    <view v-if="selectedLetter" class="detail-sheet">
      <view class="detail-head">
        <view>
          <text class="eyebrow">LETTER DETAIL</text>
          <text class="detail-title">{{ detailTitle(selectedLetter) }}</text>
        </view>
        <view class="close-btn" @tap="selectedLetter = null">×</view>
      </view>

      <view v-if="selectedLetter.daily_push" class="paper today detail-paper">
        <view class="paper-head">
          <text class="paper-date">{{ selectedLetter.letter_date }}</text>
          <text class="paper-sender">{{ selectedLetter.title || '今日星灵日推' }}</text>
        </view>
        <text class="paper-body">{{ selectedLetter.body }}</text>
        <view v-if="selectedLetter.daily_push.items?.length" class="explain">
          <button class="explain-toggle" @tap.stop="toggleExplain(selectedLetter)">
            {{ isExplainShown(selectedLetter) ? "收起为什么提醒我 ▲" : "为什么提醒我？ ▼" }}
          </button>
          <view v-if="isExplainShown(selectedLetter)" class="daily-detail-list">
            <view v-for="(item, idx) in selectedLetter.daily_push.items" :key="idx" class="daily-item">
              <view class="daily-item-head">
                <text class="daily-time">{{ item.time_label }}</text>
                <text class="daily-level">L{{ item.level }}</text>
              </view>
              <text class="daily-scene">{{ item.scene }}</text>
              <text class="daily-copy">{{ item.reason }}</text>
              <text class="daily-advice">提醒：{{ item.advice }}</text>
              <view v-if="item.reason_chain?.length" class="reason-chain">
                <text class="foot-label">推导线索</text>
                <text v-for="(chain, cidx) in item.reason_chain" :key="cidx" class="chain-line">{{ cidx + 1 }}. {{ chain }}</text>
              </view>
            </view>
          </view>
        </view>
        <view v-if="todayFrags.length" class="foot-section">
          <text class="foot-label">◈ 今日灵魂碎片</text>
          <text class="foot-line">{{ fragNames }}</text>
        </view>
      </view>

      <view v-else-if="selectedLetter.kind === 'keepsake'" class="paper keepsake detail-paper">
        <view class="paper-head">
          <view class="sender-wrap">
            <text class="paper-sender serif">「{{ selectedLetter.healing_name || selectedLetter.title || selectedLetter.sender_zh }}」来信</text>
            <text v-if="selectedLetter.entry" class="entry-tag">记忆词条</text>
          </view>
          <text class="paper-date">{{ selectedLetter.letter_date }}</text>
        </view>
        <text class="paper-body">{{ splitKeepsake(selectedLetter).main }}</text>
        <view v-if="splitKeepsake(selectedLetter).footnote" class="foot-section">
          <text class="foot-label">◈ 今日灵魂碎片</text>
          <text class="foot-line">{{ splitKeepsake(selectedLetter).footnote }}</text>
        </view>
        <text v-if="splitKeepsake(selectedLetter).signature" class="keepsake-sig">{{ splitKeepsake(selectedLetter).signature }}</text>
        <view v-if="selectedLetter.explain" class="explain">
          <button class="explain-toggle" @tap.stop="toggleExplain(selectedLetter)">
            {{ isExplainShown(selectedLetter) ? "收起推导链 ▲" : "为什么是这颗星落款？ ▼" }}
          </button>
          <text v-if="isExplainShown(selectedLetter)" class="explain-body">{{ selectedLetter.explain }}</text>
        </view>
      </view>

      <view v-else class="paper detail-paper">
        <view class="paper-head">
          <text class="paper-date">{{ selectedLetter.letter_date }}</text>
          <text class="paper-sender">{{ selectedLetter.sender_zh }}来信</text>
        </view>
        <text class="paper-body">{{ selectedLetter.body }}</text>
      </view>
    </view>

    <view v-if="writing" class="write-mask" @tap="writing = false"></view>
    <view v-if="writing" class="write-sheet">
      <text class="write-title">写下此刻</text>
      <textarea v-model="writeDraft" class="write-area" placeholder="不用写给谁看，只是留给自己……" :maxlength="500"></textarea>
      <view class="write-actions">
        <button class="write-cancel" @tap="writing = false">收起</button>
        <button class="write-save" :disabled="saving || !writeDraft.trim()" @tap="saveJournal">
          {{ saving ? "正在收好…" : "收进手账" }}
        </button>
      </view>
    </view>

    <BottomNav active="mailbox" :letter-badge="false" :universe-badge="false" />
  </view>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import api, { ApiError, type LetterOut, type SoulFragmentOut } from "@/api/client";
import BottomNav from "@/components/BottomNav.vue";
import { useGardenBadges } from "@/utils/gardenBadges";
import { clearAccountCache, requireSelfPersonId } from "@/utils/account";
import { useTimePhase } from "@/utils/timeTheme";

const loading = ref(true);
const journals = ref<any[]>([]);
const activeFilter = ref<"today" | "memory" | "journal" | "fragments">("today");
const selectedLetter = ref<LetterOut | null>(null);

// 信箱分页（20 条一页，"加载更多"追加；切换 tab 重置到第一页）
const PAGE_SIZE = 20;
// 今日日推（kind=daily）：全部日推倒序排列，最新一条即今日日推
const dailyLetters = ref<LetterOut[]>([]);
const dailyPage = ref(1);
const dailyTotal = ref(0);
const dailyLoading = ref(false);
const dailyHasMore = computed(() => dailyLetters.value.length < dailyTotal.value);
// 记忆来信（kind=keepsake）
const keepsakes = ref<LetterOut[]>([]);
const keepsakePage = ref(1);
const keepsakeTotal = ref(0);
const keepsakeLoading = ref(false);
const keepsakeHasMore = computed(() => keepsakes.value.length < keepsakeTotal.value);
// 我的手账
const journalPage = ref(1);
const journalTotal = ref(0);
const journalLoading = ref(false);
const journalHasMore = computed(() => journals.value.length < journalTotal.value);

// 切换 tab → 重置到第一页（碎片 tab 是今日快照，不参与分页）
watch(activeFilter, (val) => {
  if (val === "today") loadDaily(true);
  else if (val === "memory") loadKeepsakes(true);
  else if (val === "journal") loadJournals(true);
});

// 今日灵魂碎片（§2.5 每日结算）：今天点亮的 top3，贴到今日来信脚注
const todayFrags = ref<SoulFragmentOut[]>([]);
const fragNames = computed(() => todayFrags.value.map((f) => f.name).join(" / "));
// 已展开的推导链（按 letter.id）。不用 Set：uni 模板对 Set.has 的响应式不稳定。
const shownExplain = ref<Record<string, boolean>>({});
// 解释线索（从首页移入）：行运触发理由 + 记忆镜头
const evidence = ref<{ trigger: string; memory: string }>({ trigger: "", memory: "" });
// 写日记 composer
const writing = ref(false);
const writeDraft = ref("");
const saving = ref(false);
const { phaseClass, refreshPhase } = useTimePhase();
const { markLetterBadgeRead, setGardenBadges } = useGardenBadges();

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

function isExplainShown(l: LetterOut | null): boolean {
  return !!(l?.id && shownExplain.value[l.id]);
}

function toggleExplain(l: LetterOut) {
  shownExplain.value = {
    ...shownExplain.value,
    [l.id]: !shownExplain.value[l.id],
  };
}

function openLetter(letter: LetterOut) {
  selectedLetter.value = letter;
  shownExplain.value = { ...shownExplain.value, [letter.id]: false };
}

function dailyPushPreview(letter: LetterOut): string {
  if (letter.daily_push?.summary) return letter.daily_push.summary;
  return (letter.body || "").replace(/\n+/g, " ").slice(0, 54);
}

function detailTitle(letter: LetterOut): string {
  if (letter.daily_push) return letter.title || "今日星灵日推";
  if (letter.kind === "keepsake") return `「${letter.healing_name || letter.title || letter.sender_zh}」来信`;
  return letter.title || `${letter.sender_zh}来信`;
}

const personId = ref("");
function pid(): string {
  return personId.value;
}

// 分页加载（20 条一页，追加到列表尾部；reset=true 回到第一页；读不到不阻断看信）
async function loadDaily(reset = false) {
  const personId = pid();
  if (!personId || (dailyLoading.value && !reset)) return;
  dailyLoading.value = true;
  try {
    if (reset) dailyPage.value = 1;
    const res = await api.letters(personId, { page: dailyPage.value, page_size: PAGE_SIZE, kind: "daily" });
    dailyLetters.value = reset || dailyPage.value === 1 ? res.items : [...dailyLetters.value, ...res.items];
    dailyTotal.value = res.total;
    dailyPage.value += 1;
  } catch {
    if (reset) dailyLetters.value = [];
  } finally {
    dailyLoading.value = false;
  }
}

async function loadKeepsakes(reset = false) {
  const personId = pid();
  if (!personId || (keepsakeLoading.value && !reset)) return;
  keepsakeLoading.value = true;
  try {
    if (reset) keepsakePage.value = 1;
    const res = await api.letters(personId, { page: keepsakePage.value, page_size: PAGE_SIZE, kind: "keepsake" });
    keepsakes.value = reset || keepsakePage.value === 1 ? res.items : [...keepsakes.value, ...res.items];
    keepsakeTotal.value = res.total;
    keepsakePage.value += 1;
  } catch {
    if (reset) keepsakes.value = [];
  } finally {
    keepsakeLoading.value = false;
  }
}

async function loadJournals(reset = false) {
  const personId = pid();
  if (!personId || (journalLoading.value && !reset)) return;
  journalLoading.value = true;
  try {
    if (reset) journalPage.value = 1;
    const res = await api.journalList(personId, journalPage.value, PAGE_SIZE);
    journals.value = reset || journalPage.value === 1 ? res.items : [...journals.value, ...res.items];
    journalTotal.value = res.total;
    journalPage.value += 1;
  } catch {
    if (reset) journals.value = [];
  } finally {
    journalLoading.value = false;
  }
}

async function saveJournal() {
  const content = writeDraft.value.trim();
  if (!content || saving.value) return;
  const personIdValue = pid();
  saving.value = true;
  try {
    await api.journalCreate({ person_id: personIdValue, content });
    writeDraft.value = "";
    writing.value = false;
    uni.showToast({ title: "已收进手账", icon: "none" });
    await loadJournals(true);
  } catch (e: any) {
    uni.showToast({ title: e?.message || "暂时没存上，再试一次", icon: "none" });
  } finally {
    saving.value = false;
  }
}

onLoad(async () => {
  refreshPhase();
  const selfId = await requireSelfPersonId();
  if (!selfId) return;
  personId.value = selfId;
  try {
    // 生成今日来信（幂等按天）——最新一条日推即今日日推
    await api.mailboxToday(selfId);
    // 分页列表（20 条一页）：今日日推 / 记忆来信 / 手账，互不阻断
    await Promise.allSettled([
      loadDaily(true),
      loadKeepsakes(true),
      loadJournals(true),
    ]);
    // 今日灵魂碎片（独立 try：读不到不影响看信，空碎片由模板兜底）
    try {
      const soul = await api.soulFragmentsToday(selfId);
      todayFrags.value = soul.fragments || [];
    } catch {
      todayFrags.value = [];
    }
    // 首页红点：看完今日来信 → 标记已读（本地先清红点，后端 fire-and-forget）
    markLetterBadgeRead();
    api.markLettersReadToday(selfId).catch(() => {});
    // 解释线索：今日星灵的行运理由 + 记忆镜头（读不到就安静隐藏整卡）
    try {
      const [rec, garden] = await Promise.all([
        api.recommendedSpirits(selfId),
        api.garden(selfId, undefined),
      ]);
      setGardenBadges({ ...garden, letter_unread: false });
      const trigger = rec.spirits?.[0]?.reason || "";
      const memoryItem = garden.recall?.items?.[0];
      const memory = memoryItem?.summary || memoryItem?.title || memoryItem?.text || "记忆镜头会优先取你确认过、最近聊过的内容";
      evidence.value = { trigger, memory };
    } catch {
      evidence.value = { trigger: "", memory: "" };
    }
  } catch (e: any) {
    if (e instanceof ApiError && (e.status === 404 || e.status === 410)) {
      clearAccountCache();
      uni.showToast({ title: e.status === 410 ? "当前档案已无法解密，请重新建档" : "这个花园已经找不到了", icon: "none" });
      uni.reLaunch({ url: "/pages/index/index" });
      return;
    }
    keepsakes.value = [];
    journals.value = [];
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
.sub { display: block; font-size: 23rpx; color: rgba(41, 59, 53, 0.55); margin: 10rpx 0 20rpx; position: relative; z-index: 1; }
.asset-grid { position: relative; z-index: 1; display: grid; grid-template-columns: repeat(4, 1fr); gap: 12rpx; margin: 0 0 26rpx; }
.asset-card { min-height: 104rpx; border-radius: 24rpx; background: rgba(250, 248, 235, 0.5); border: 1rpx solid rgba(255, 255, 255, 0.42); box-shadow: 0 12rpx 34rpx rgba(59, 76, 62, 0.1); display: flex; flex-direction: column; align-items: center; justify-content: center; transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease; }
.asset-card.today-asset { background: rgba(255, 247, 210, 0.6); }
.asset-card.active { transform: translateY(-4rpx); background: rgba(255, 247, 210, 0.72); border-color: rgba(173, 145, 84, 0.52); box-shadow: 0 16rpx 40rpx rgba(111, 90, 38, 0.16); }
.asset-card.active .asset-num { color: #8a6d1f; }
.asset-card.active .asset-label { color: rgba(64, 83, 75, 0.86); font-weight: 700; }
.asset-num { font-family: Georgia, "Noto Serif SC", serif; font-size: 34rpx; font-weight: 600; color: #4d6558; }
.asset-label { margin-top: 6rpx; color: rgba(41, 59, 53, 0.56); font-size: 19rpx; }
.mail-row { position: relative; z-index: 1; display: flex; justify-content: space-between; gap: 20rpx; padding: 28rpx 26rpx; margin-bottom: 18rpx; border-radius: 28rpx; background: rgba(250, 248, 235, 0.7); border: 1rpx solid rgba(255, 255, 255, 0.42); box-shadow: 0 16rpx 44rpx rgba(59, 76, 62, 0.12); }
.mail-row.today-row { background: rgba(255, 247, 210, 0.68); border-color: rgba(173, 145, 84, 0.36); }
.mail-row-main { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 10rpx; }
.mail-row-side { min-width: 112rpx; display: flex; flex-direction: column; align-items: flex-end; justify-content: space-between; gap: 18rpx; }
.mail-title { font-family: Georgia, "Noto Serif SC", serif; font-size: 29rpx; font-weight: 600; color: #40534b; }
.mail-preview { color: rgba(64, 83, 75, 0.66); font-size: 23rpx; line-height: 1.55; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.mail-open { color: #8a6d1f; font-size: 21rpx; }
.daily-tag { background: rgba(255, 247, 210, 0.78); }

/* 纸页：横线手账质感 */
.paper { position: relative; z-index: 1; border-radius: 32rpx; background: rgba(250, 248, 235, 0.73); backdrop-filter: blur(16rpx); padding: 34rpx 30rpx; margin-bottom: 24rpx; box-shadow: 0 18rpx 55rpx rgba(59, 76, 62, 0.15); overflow: hidden; }
.paper::after { content: ""; position: absolute; inset: 0; opacity: 0.15; pointer-events: none;
  background: repeating-linear-gradient(0deg, transparent 0 56rpx, rgba(92, 104, 85, 0.35) 56rpx 57rpx); }
.paper > view, .paper > text { position: relative; z-index: 1; }
.paper.today { border: 1rpx solid rgba(255, 255, 255, 0.5); }
.paper.keepsake { border-left: 8rpx solid #718c7c; }
.paper.mine { border-left: 8rpx solid #ad9154; }
.paper.clue { border: 1rpx dashed rgba(64, 81, 69, 0.25); }
.paper.fragments { border-left: 8rpx solid rgba(173, 145, 84, 0.68); }
.fragment-line { display: flex; align-items: flex-start; gap: 18rpx; padding: 14rpx 0; border-bottom: 1rpx solid rgba(64, 81, 69, 0.08); }
.fragment-line:last-child { border-bottom: 0; }
.fragment-dot { color: #ad9154; font-size: 30rpx; line-height: 1.5; }
.fragment-copy { display: flex; flex-direction: column; gap: 6rpx; }
.fragment-name { font-family: Georgia, "Noto Serif SC", serif; font-size: 27rpx; color: #40534b; }
.fragment-meta { font-size: 21rpx; color: rgba(64, 83, 75, 0.52); }
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
.explain { margin-top: 16rpx; position: relative; z-index: 3; }
.explain-toggle { display: inline-flex; align-items: center; width: auto; margin: 0; padding: 10rpx 0; border: 0; border-radius: 0; background: transparent; color: rgba(64, 83, 75, 0.56); font-size: 21rpx; line-height: 1.5; text-decoration: underline; text-align: left; }
.explain-toggle::after { border: 0; }
.explain-body { display: block; color: rgba(64, 83, 75, 0.7); font-size: 21rpx; line-height: 1.7; margin-top: 8rpx; background: rgba(255, 255, 255, 0.45); border-radius: 12rpx; padding: 14rpx 18rpx; }

/* 来信详情抽屉 */
.detail-mask { position: fixed; inset: 0; z-index: 30; background: rgba(24, 36, 32, 0.38); }
.detail-sheet { position: fixed; left: 20rpx; right: 20rpx; bottom: calc(20rpx + env(safe-area-inset-bottom)); z-index: 31; max-height: 82vh; overflow-y: auto; border-radius: 42rpx; padding: 30rpx 26rpx 34rpx; background: rgba(238, 239, 223, 0.98); box-shadow: 0 28rpx 80rpx rgba(25, 39, 33, 0.38); box-sizing: border-box; }
.detail-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 24rpx; margin-bottom: 18rpx; }
.detail-title { display: block; margin-top: 4rpx; font-family: Georgia, "Noto Serif SC", serif; font-size: 36rpx; line-height: 1.35; color: #293b35; }
.close-btn { width: 58rpx; height: 58rpx; border-radius: 50%; background: rgba(255, 255, 255, 0.55); color: rgba(41, 59, 53, 0.72); display: flex; align-items: center; justify-content: center; font-size: 42rpx; line-height: 1; }
.detail-paper { margin-bottom: 0; }
.daily-item { position: relative; z-index: 1; margin-top: 22rpx; padding: 22rpx 20rpx; border-radius: 22rpx; background: rgba(255, 255, 255, 0.46); border-left: 6rpx solid rgba(173, 145, 84, 0.58); display: flex; flex-direction: column; gap: 10rpx; }
.daily-item-head { display: flex; justify-content: space-between; align-items: center; }
.daily-time { color: #8a6d1f; font-size: 22rpx; font-weight: 700; }
.daily-level { color: rgba(64, 83, 75, 0.58); font-size: 20rpx; }
.daily-scene { font-family: Georgia, "Noto Serif SC", serif; font-size: 28rpx; color: #40534b; }
.daily-copy, .daily-advice, .chain-line, .disclaimer { display: block; color: rgba(64, 83, 75, 0.72); font-size: 23rpx; line-height: 1.7; }
.daily-advice { color: rgba(64, 83, 75, 0.86); }
.reason-chain { margin-top: 8rpx; padding: 16rpx 18rpx; border-radius: 16rpx; background: rgba(250, 248, 235, 0.62); }
.chain-line { margin-top: 6rpx; }
.disclaimer { position: relative; z-index: 1; margin-top: 18rpx; color: rgba(64, 83, 75, 0.56); }

/* 星图线索 */
.section-label { font-size: 19rpx; letter-spacing: 0.16em; color: rgba(41, 59, 53, 0.4); margin: 30rpx 0 16rpx; position: relative; z-index: 1; }
.section-label.inner { margin: 0 0 14rpx; }
.star-line { display: flex; align-items: flex-start; gap: 16rpx; font-family: Georgia, "Noto Serif SC", serif; font-size: 24rpx; line-height: 1.7; color: #40534b; padding: 8rpx 0; }
.star-ico { color: #ad9154; font-size: 30rpx; line-height: 1.4; }

.empty { color: rgba(41, 59, 53, 0.55); font-size: 27rpx; text-align: center; padding: 100rpx 0; position: relative; z-index: 1; }
.empty.small { padding: 20rpx 0 40rpx; font-size: 23rpx; text-align: left; }

/* 分页加载更多 */
.load-more { position: relative; z-index: 1; text-align: center; padding: 20rpx 0 6rpx; color: #8a6d1f; font-size: 23rpx; }

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
