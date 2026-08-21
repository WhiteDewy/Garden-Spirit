<template>
  <view class="page gs-time-page" :class="phaseClass">
    <view class="cosmos-glow" aria-hidden="true"></view>
    <view class="constellation" aria-hidden="true">
      <text v-for="(s, i) in stars" :key="i" class="c-dot" :style="{ left: s.x + '%', top: s.y + '%' }"></text>
    </view>

    <view class="navbar">
      <text class="nav-back" @tap="goBack">‹</text>
      <text class="nav-title">人生章节</text>
      <view class="nav-right" />
    </view>

    <view class="head">
      <text class="eyebrow">LIFE RHYTHM · 人生节律</text>
      <text class="title">看见你正在走的这一章。</text>
      <text class="sub">这里只渲染后端 Domain 给出的确定性素材：本命承诺、法达章节、年度小限辅助与未来触发窗口。</text>
    </view>

    <view v-if="loading" class="empty-card">正在翻开人生章节……</view>
    <view v-else-if="errorText" class="empty-card error">
      <text class="empty-title">暂时没能生成报告</text>
      <text class="empty-copy">{{ errorText }}</text>
      <button class="retry" @tap="loadRhythm">重试</button>
    </view>

    <view v-else-if="rhythm" class="body">
      <view class="hero-card">
        <view class="hero-top">
          <view class="chapter-orb"><text>♄</text></view>
          <view class="hero-main">
            <text class="chapter-kicker">TIMING AUTHORITY · {{ authorityLabel }}</text>
            <text class="chapter-title">{{ chapterTitle }}</text>
            <text class="chapter-sub">{{ chapterRange }}</text>
          </view>
        </view>
        <view class="rule-note">
          <text>法达是主章节；小限只作年度辅助，不替代时机权威。</text>
        </view>
        <view class="stat-row">
          <view class="stat"><text class="stat-num">{{ planetLabel(period?.major_lord) }}</text><text class="stat-label">大限主星</text></view>
          <view class="stat"><text class="stat-num">{{ planetLabel(period?.sub_lord) }}</text><text class="stat-label">子限主星</text></view>
          <view class="stat"><text class="stat-num">{{ rhythm.months }}</text><text class="stat-label">月触发</text></view>
        </view>
      </view>

      <view class="section-card">
        <view class="section-head">
          <text class="section-kicker">FIRDARIA · 当前章节</text>
          <text class="section-title">这一阶段怎样发生</text>
        </view>
        <view class="lord-grid">
          <view class="lord-card">
            <text class="lord-label">大限主星</text>
            <text class="lord-name">{{ planetLabel(period?.major_lord) }}</text>
            <text class="lord-copy">{{ majorCharacterLine }}</text>
            <view v-if="majorCharacter?.domains?.length" class="chip-row">
              <text v-for="d in majorCharacter.domains.slice(0, 4)" :key="d" class="soft-chip">{{ d }}</text>
            </view>
          </view>
          <view class="lord-card">
            <text class="lord-label">子限主星</text>
            <text class="lord-name">{{ planetLabel(period?.sub_lord) }}</text>
            <text class="lord-copy">{{ subCharacterLine }}</text>
            <view v-if="subCharacter?.behavior?.length" class="chip-row">
              <text v-for="b in subCharacter.behavior.slice(0, 4)" :key="b" class="soft-chip">{{ b }}</text>
            </view>
          </view>
        </view>
        <view class="theme-block">
          <text class="theme-title">章节主题线索</text>
          <view class="theme-list">
            <view v-for="item in chapterThemes" :key="themeKey(item)" class="theme-item">
              <text class="theme-word">{{ item.word }}</text>
              <text class="theme-evidence">{{ firstEvidence(item) }}</text>
            </view>
          </view>
        </view>
      </view>

      <view class="section-card annual-card">
        <view class="section-head">
          <text class="section-kicker">ANNUAL AUXILIARY · 年度辅助层</text>
          <text class="section-title">今年被点亮的宫位</text>
        </view>
        <view class="annual-main">
          <view class="annual-house"><text>{{ annual?.activation_house || '—' }}</text><small>宫</small></view>
          <view class="annual-copy">
            <text class="annual-line">{{ annualLine }}</text>
            <text class="annual-range">{{ dateRange(annual?.annual_start, annual?.annual_end) }}</text>
          </view>
        </view>
        <view v-if="annualThemes.length" class="theme-list compact">
          <view v-for="item in annualThemes" :key="themeKey(item)" class="theme-item">
            <text class="theme-word">{{ item.word }}</text>
            <text class="theme-evidence">{{ firstEvidence(item) }}</text>
          </view>
        </view>
      </view>

      <view class="section-card">
        <view class="section-head">
          <text class="section-kicker">NATAL PROMISE · 本命承诺</text>
          <text class="section-title">不是定论，是底色</text>
        </view>
        <view class="promise-list">
          <view v-for="stage in natalStages" :key="stage.domain" class="promise-card">
            <view class="promise-top">
              <text class="promise-domain">{{ stage.domain_label }}</text>
              <text class="promise-count">{{ stage.themes.length }} 条</text>
            </view>
            <view class="chip-row">
              <text v-for="item in stage.themes.slice(0, 3)" :key="themeKey(item)" class="theme-chip">{{ item.word }}</text>
            </view>
            <text v-if="stage.synapsis?.[0]" class="synapsis">{{ stage.synapsis[0].description_zh }}</text>
          </view>
        </view>
      </view>

      <view class="section-card">
        <view class="section-head">
          <text class="section-kicker">TRANSIT TRIGGERS · 未来窗口</text>
          <text class="section-title">接下来 {{ rhythm.months }} 个月哪些点会被触发</text>
        </view>
        <view class="trigger-list">
          <view v-for="row in rhythm.transit_triggers" :key="row.month" class="trigger-card">
            <view class="trigger-top">
              <text class="trigger-month">{{ formatMonth(row.month) }}</text>
              <text class="trigger-tag">{{ row.tag || '中性' }} · {{ scoreLabel(row.score) }}</text>
            </view>
            <view class="target-row">
              <text class="target-label">法达目标</text>
              <text class="target-value">{{ planetList(row.target_planets) }}</text>
            </view>
            <view class="target-row">
              <text class="target-label">辅助观察</text>
              <text class="target-value">{{ planetList(row.helper_target_planets) }}</text>
            </view>
            <view class="target-row muted">
              <text class="target-label">实际扫描</text>
              <text class="target-value">{{ planetList(row.scoring_target_planets) }}</text>
            </view>
          </view>
        </view>
      </view>

      <view class="footer-note">
        <text>报告页不前端推断吉凶或改写结论；如果想把某段经历校准进去，可以回到主题观星台继续聊。</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import api, { ApiError, describeError, type LifeRhythmOut, type LifeRhythmSignificationItem } from "@/api/client";
import { clearAccountCache, requireSelfPersonId } from "@/utils/account";
import { useTimePhase } from "@/utils/timeTheme";

const rhythm = ref<LifeRhythmOut | null>(null);
const loading = ref(true);
const errorText = ref("");
const personId = ref("");
const { phaseClass, refreshPhase } = useTimePhase();

const stars = Array.from({ length: 14 }, (_, i) => ({
  x: [8, 18, 30, 48, 65, 82, 90, 13, 34, 56, 72, 86, 23, 44][i],
  y: [17, 31, 19, 12, 24, 16, 39, 54, 66, 58, 72, 84, 86, 78][i],
}));

const PLANET_ZH: Record<string, string> = {
  sun: "太阳",
  moon: "月亮",
  mercury: "水星",
  venus: "金星",
  mars: "火星",
  jupiter: "木星",
  saturn: "土星",
  north_node: "北交点",
  south_node: "南交点",
};

const period = computed(() => rhythm.value?.firdaria_chapter?.period || null);
const annual = computed(() => rhythm.value?.annual_activation || null);
const majorCharacter = computed(() => rhythm.value?.firdaria_chapter?.major_character || null);
const subCharacter = computed(() => rhythm.value?.firdaria_chapter?.sub_character || null);
const authorityLabel = computed(() => rhythm.value?.timing_authority === "firdaria" ? "法达" : rhythm.value?.timing_authority || "—");
const chapterTitle = computed(() => `${planetLabel(period.value?.major_lord)}大限 · ${planetLabel(period.value?.sub_lord)}子限`);
const chapterRange = computed(() => dateRange(period.value?.sub_start, period.value?.sub_end));
const chapterThemes = computed(() => [
  ...(rhythm.value?.firdaria_chapter?.major || []),
  ...(rhythm.value?.firdaria_chapter?.sub || []),
].slice(0, 5));
const annualThemes = computed(() => annual.value?.themes?.slice(0, 4) || []);
const natalStages = computed(() => rhythm.value?.natal_promise?.slice(0, 5) || []);
const majorCharacterLine = computed(() => characterLine(majorCharacter.value));
const subCharacterLine = computed(() => characterLine(subCharacter.value));
const annualLine = computed(() => {
  const a = annual.value;
  if (!a) return "年度辅助层正在等待后端素材。";
  return `${a.age} 岁生日年 · ${a.activation_house} 宫被激活 · 辅助星 ${planetLabel(a.activation_lord)}`;
});

onLoad(async () => {
  refreshPhase();
  const pid = await requireSelfPersonId();
  if (!pid) return;
  personId.value = pid;
  await loadRhythm();
});

async function loadRhythm() {
  if (!personId.value) return;
  loading.value = true;
  errorText.value = "";
  try {
    rhythm.value = await api.lifeRhythm(personId.value, 6);
  } catch (e: any) {
    if (e instanceof ApiError && e.status === 410) {
      clearAccountCache();
      uni.showToast({ title: "当前档案已无法解密，请重新登录建档", icon: "none" });
      uni.redirectTo({ url: "/pages/auth/login" });
      return;
    }
    errorText.value = describeError(e);
  } finally {
    loading.value = false;
  }
}

function planetLabel(value?: string | null) {
  const key = String(value || "").toLowerCase();
  return PLANET_ZH[key] || value || "—";
}

function planetList(values?: string[] | null) {
  const list = (values || []).map(planetLabel).filter(Boolean);
  return list.length ? list.join(" / ") : "—";
}

function dateRange(start?: string | null, end?: string | null) {
  if (!start && !end) return "时间范围待生成";
  return `${shortDate(start)} — ${shortDate(end)}`;
}

function shortDate(value?: string | null) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value).slice(0, 10);
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}`;
}

function formatMonth(value?: string | null) {
  if (!value) return "—";
  const d = new Date(`${value}-01T00:00:00`);
  if (Number.isNaN(d.getTime())) return String(value);
  return `${d.getFullYear()}年${d.getMonth() + 1}月`;
}

function scoreLabel(score?: number | null) {
  if (score === undefined || score === null) return "触发度 —";
  return `触发度 ${Math.round(score * 100)}%`;
}

function characterLine(character?: { tone?: string; effort?: string; nature?: string } | null) {
  if (!character) return "后端暂未给出本命条件素材。";
  const parts = [character.tone, character.effort, character.nature].filter(Boolean);
  return parts.length ? parts.join(" · ") : "已接入时间领主本命条件。";
}

function themeKey(item: LifeRhythmSignificationItem) {
  return `${item.house}-${item.word}-${item.polarity}`;
}

function firstEvidence(item: LifeRhythmSignificationItem) {
  return item.evidence?.[0] || `${item.house} 宫 · ${item.polarity}`;
}

function goBack() {
  uni.navigateBack();
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: radial-gradient(circle at 72% 10%, rgba(240, 210, 139, 0.13), transparent 28%), linear-gradient(180deg, #081613 0%, #10271f 52%, #17362c 100%);
  padding: 0 36rpx 80rpx;
  box-sizing: border-box;
  color: #eef1ea;
  position: relative;
  overflow: hidden;
}
.cosmos-glow { position: absolute; width: 620rpx; height: 620rpx; border-radius: 50%; left: -180rpx; top: 250rpx; background: rgba(154, 205, 186, 0.12); filter: blur(70rpx); pointer-events: none; }
.constellation { position: absolute; inset: 0; opacity: 0.68; pointer-events: none; }
.c-dot { position: absolute; width: 6rpx; height: 6rpx; border-radius: 50%; background: #eee7ce; box-shadow: 0 0 20rpx rgba(238, 231, 206, 0.72); animation: twinkle 4.5s ease-in-out infinite; }
@keyframes twinkle { 50% { opacity: 0.28; } }

.navbar { position: relative; z-index: 2; display: flex; align-items: center; padding: 24rpx 0; border-bottom: 1rpx solid rgba(255, 255, 255, 0.06); }
.nav-back { color: #e8f5e9; font-size: 52rpx; width: 60rpx; line-height: 1; }
.nav-title { flex: 1; text-align: center; color: #e8f5e9; font-size: 32rpx; font-weight: 600; }
.nav-right { width: 60rpx; }
.head { position: relative; z-index: 2; margin: 34rpx 0 28rpx; }
.eyebrow { display: block; font-size: 19rpx; letter-spacing: 0.16em; color: rgba(240, 210, 139, 0.68); font-weight: 800; }
.title { display: block; margin-top: 14rpx; font-family: Georgia, "Noto Serif SC", serif; color: #fff7e7; font-size: 46rpx; font-weight: 600; line-height: 1.25; }
.sub { display: block; margin-top: 14rpx; color: rgba(238, 241, 234, 0.58); font-size: 24rpx; line-height: 1.75; }
.body { position: relative; z-index: 2; }
.empty-card { position: relative; z-index: 2; padding: 50rpx 34rpx; border-radius: 34rpx; background: rgba(255, 255, 255, 0.06); border: 1rpx solid rgba(255, 255, 255, 0.1); color: rgba(238, 241, 234, 0.66); font-size: 26rpx; text-align: center; }
.empty-card.error { display: grid; gap: 14rpx; text-align: left; }
.empty-title { color: #fff7e7; font-size: 30rpx; font-weight: 700; }
.empty-copy { color: rgba(238, 241, 234, 0.58); font-size: 23rpx; line-height: 1.7; }
.retry { margin: 16rpx 0 0; border-radius: 999rpx; background: rgba(240, 210, 139, 0.16); color: #f8e2a7; font-size: 23rpx; }
.retry::after { border: 0; }

.hero-card, .section-card { border-radius: 34rpx; padding: 30rpx 26rpx; background: rgba(255, 255, 255, 0.065); border: 1rpx solid rgba(185, 200, 189, 0.16); box-shadow: 0 22rpx 70rpx rgba(0, 0, 0, 0.12); margin-bottom: 22rpx; }
.hero-top { display: flex; gap: 22rpx; align-items: center; }
.chapter-orb { width: 106rpx; height: 106rpx; border-radius: 50%; flex-shrink: 0; display: flex; align-items: center; justify-content: center; background: radial-gradient(circle at 35% 28%, #fff7dc, #d2b86f 56%, #426765); box-shadow: 0 0 62rpx rgba(240, 210, 139, 0.22); color: #17362c; font-size: 46rpx; }
.hero-main { flex: 1; min-width: 0; }
.chapter-kicker, .section-kicker { display: block; color: rgba(240, 210, 139, 0.72); font-size: 19rpx; letter-spacing: 0.14em; font-weight: 800; }
.chapter-title { display: block; margin-top: 12rpx; font-family: Georgia, "Noto Serif SC", serif; font-size: 36rpx; color: #fff7e7; font-weight: 650; }
.chapter-sub { display: block; margin-top: 8rpx; color: rgba(238, 241, 234, 0.5); font-size: 21rpx; }
.rule-note { margin-top: 24rpx; padding: 18rpx 22rpx; border-radius: 24rpx; background: rgba(8, 22, 19, 0.26); border: 1rpx solid rgba(240, 210, 139, 0.12); color: rgba(255, 247, 231, 0.62); font-size: 22rpx; line-height: 1.6; }
.stat-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14rpx; margin-top: 22rpx; }
.stat { padding: 22rpx 10rpx; text-align: center; border-radius: 24rpx; background: rgba(255, 255, 255, 0.055); border: 1rpx solid rgba(255, 255, 255, 0.08); }
.stat-num { display: block; color: #f5df9f; font-size: 28rpx; font-weight: 800; }
.stat-label { display: block; margin-top: 6rpx; color: rgba(238, 241, 234, 0.44); font-size: 19rpx; }

.section-head { margin-bottom: 22rpx; }
.section-title { display: block; margin-top: 10rpx; font-family: Georgia, "Noto Serif SC", serif; color: #fff7e7; font-size: 32rpx; font-weight: 650; line-height: 1.35; }
.lord-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16rpx; }
.lord-card, .promise-card, .trigger-card { padding: 24rpx; border-radius: 28rpx; background: rgba(8, 22, 19, 0.3); border: 1rpx solid rgba(255, 255, 255, 0.08); }
.lord-label { color: rgba(238, 241, 234, 0.48); font-size: 20rpx; }
.lord-name { display: block; margin-top: 8rpx; color: #f0d28b; font-size: 30rpx; font-weight: 800; }
.lord-copy { display: block; margin-top: 10rpx; color: rgba(238, 241, 234, 0.62); font-size: 21rpx; line-height: 1.6; }
.chip-row { display: flex; flex-wrap: wrap; gap: 10rpx; margin-top: 14rpx; }
.soft-chip, .theme-chip { display: inline-flex; padding: 7rpx 13rpx; border-radius: 999rpx; background: rgba(255, 255, 255, 0.07); border: 1rpx solid rgba(255, 255, 255, 0.08); color: rgba(238, 241, 234, 0.66); font-size: 19rpx; }
.theme-block { margin-top: 24rpx; }
.theme-title { display: block; color: rgba(240, 210, 139, 0.82); font-size: 22rpx; font-weight: 800; }
.theme-list { display: grid; gap: 14rpx; margin-top: 14rpx; }
.theme-list.compact { margin-top: 22rpx; }
.theme-item { padding: 18rpx 20rpx; border-radius: 22rpx; background: rgba(255, 255, 255, 0.045); border: 1rpx solid rgba(255, 255, 255, 0.07); }
.theme-word { display: block; color: #fff7e7; font-size: 24rpx; font-weight: 650; }
.theme-evidence { display: block; margin-top: 7rpx; color: rgba(238, 241, 234, 0.46); font-size: 20rpx; line-height: 1.55; }

.annual-card { border-color: rgba(240, 210, 139, 0.16); background: linear-gradient(145deg, rgba(240, 210, 139, 0.09), rgba(255, 255, 255, 0.055)); }
.annual-main { display: flex; align-items: center; gap: 22rpx; }
.annual-house { width: 112rpx; height: 112rpx; border-radius: 50%; display: flex; align-items: baseline; justify-content: center; gap: 4rpx; flex-shrink: 0; background: rgba(240, 210, 139, 0.18); border: 1rpx solid rgba(240, 210, 139, 0.28); color: #f8e2a7; }
.annual-house text { font-size: 54rpx; font-family: Georgia, "Noto Serif SC", serif; line-height: 112rpx; }
.annual-house small { font-size: 20rpx; }
.annual-copy { min-width: 0; }
.annual-line { display: block; color: #fff7e7; font-size: 26rpx; font-weight: 650; line-height: 1.55; }
.annual-range { display: block; margin-top: 8rpx; color: rgba(238, 241, 234, 0.46); font-size: 20rpx; }

.promise-list, .trigger-list { display: grid; gap: 16rpx; }
.promise-top, .trigger-top { display: flex; align-items: center; justify-content: space-between; gap: 16rpx; }
.promise-domain { color: #fff7e7; font-size: 27rpx; font-weight: 700; }
.promise-count, .trigger-tag { color: rgba(238, 241, 234, 0.48); font-size: 20rpx; }
.synapsis { display: block; margin-top: 14rpx; color: rgba(238, 241, 234, 0.48); font-size: 20rpx; line-height: 1.6; }
.trigger-month { color: #f0d28b; font-size: 27rpx; font-weight: 800; }
.target-row { display: flex; gap: 18rpx; margin-top: 14rpx; }
.target-row.muted { opacity: 0.72; }
.target-label { width: 128rpx; flex-shrink: 0; color: rgba(238, 241, 234, 0.42); font-size: 20rpx; }
.target-value { flex: 1; color: rgba(238, 241, 234, 0.72); font-size: 21rpx; line-height: 1.5; }
.footer-note { padding: 16rpx 10rpx 24rpx; color: rgba(238, 241, 234, 0.42); font-size: 20rpx; line-height: 1.7; text-align: center; }
</style>
