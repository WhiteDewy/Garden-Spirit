<template>
  <view class="page gs-time-page" :class="phaseClass">
    <view class="cosmos-glow" aria-hidden="true"></view>

    <!-- 星座散点 -->
    <view class="constellation" aria-hidden="true">
      <text v-for="(c, i) in stars" :key="i" class="c-dot" :style="{ left: c.x + '%', top: c.y + '%' }"></text>
    </view>

    <!-- 星轨核心 -->
    <view class="orbit-zone" aria-hidden="true">
      <view class="orbit one"></view>
      <view class="orbit two"></view>
      <view class="orbit three"></view>
    </view>
    <view class="core" @tap="goWheel"><text>你</text></view>
    <view class="planet p1" @tap="goWheel"><text>☾</text></view>
    <view class="planet p2" @tap="goConsult"><text>♀</text></view>
    <view class="planet p3" @tap="goWheel"><text>☿</text></view>
    <view class="planet p4" @tap="goConsult"><text>♂</text></view>

    <view class="head">
      <view>
        <text class="eyebrow">YOUR COSMOS</text>
        <text class="title">宇宙</text>
      </view>
    </view>
    <text class="sub">出生时形成的星图，是一张认识自己的地图。</text>

    <view class="copy">
      <text class="copy-h">你的宇宙，正在发光。</text>
      <text class="copy-p">星体不是命运的答案。\n它们只是帮助你理解自己的另一种语言。</text>
      <button class="explore" @tap="goWheel">探索我的星图　→</button>
    </view>

    <!-- 功能入口：星轨世界里的两座观星台 -->
    <view class="entries">
      <view class="entry" @tap="goWheel">
        <text class="entry-ico">☾</text>
        <view class="entry-body">
          <text class="entry-title">自我星盘轮</text>
          <text class="entry-sub">{{ litLabel }}</text>
          <text class="entry-desc">34 子类 · 3 星区 · 聊出来的内心地图</text>
        </view>
        <text class="entry-arrow">›</text>
      </view>
      <view class="entry" @tap="goConsult">
        <text class="entry-ico">♀</text>
        <view class="entry-body">
          <text class="entry-title">主题观星台</text>
          <text class="entry-sub">主题问题 · 后端证据链</text>
          <text class="entry-desc">只承接已沉淀的星图线索，不前端生成结论</text>
        </view>
        <text class="entry-arrow">›</text>
      </view>
      <view class="entry" @tap="goLifeRhythm">
        <text class="entry-ico">♄</text>
        <view class="entry-body">
          <text class="entry-title">人生章节</text>
          <text class="entry-sub">Life Rhythm · 法达主章节</text>
          <text class="entry-desc">本命承诺 / 年度辅助 / 未来 6 个月触发窗口</text>
        </view>
        <text class="entry-arrow">›</text>
      </view>
      <view class="entry" @tap="focusCalibration">
        <text class="entry-ico">✓</text>
        <view class="entry-body">
          <text class="entry-title">沉淀判断</text>
          <text class="entry-sub">{{ findingLabel }}</text>
          <text class="entry-desc">待验证 / 已确认的理解，会在这里继续校准</text>
        </view>
        <text class="entry-arrow">↓</text>
      </view>
    </view>

    <view v-if="calibrationVisible" id="calibration" class="calibration-panel">
      <view class="calibration-head">
        <text class="calibration-kicker">CALIBRATION · 沉淀判断</text>
        <text class="calibration-title">这些理解，需要你来校准。</text>
        <text class="calibration-copy">花园不会替你下定论。你点头或摇头，都会让之后的陪伴更贴近真实的你。</text>
      </view>

      <view v-if="pendingFindings.length" class="finding-list">
        <view v-for="f in pendingFindings" :key="f.id" class="finding-card pending">
          <view class="finding-top">
            <text class="finding-tag">待校准</text>
            <text class="finding-conf">{{ Math.round(f.confidence * 100) }}% 把握</text>
          </view>
          <text class="finding-statement">{{ f.statement }}</text>
          <view v-if="f.verification_notes?.length" class="finding-notes">
            <text v-for="(n, i) in f.verification_notes.slice(0, 2)" :key="i" class="finding-note">· {{ n }}</text>
          </view>
          <view class="finding-actions">
            <button class="finding-btn yes" :disabled="verifyingId === f.id" @tap.stop="verifyFinding(f, 'confirmed')">✓ 对上了</button>
            <button class="finding-btn no" :disabled="verifyingId === f.id" @tap.stop="verifyFinding(f, 'refuted')">✕ 不准确</button>
          </view>
        </view>
      </view>

      <view v-else class="calibration-empty">
        <text class="empty-title">暂时没有待验证判断</text>
        <text class="empty-copy">继续聊天或记录重要事件后，这里会出现可以一起校准的理解。</text>
      </view>

      <view v-if="verifiedFindings.length" class="verified-section">
        <text class="verified-title">已校准的理解</text>
        <view v-for="f in verifiedFindings.slice(0, 3)" :key="f.id" class="verified-card">
          <text class="verified-status">{{ f.feedback === 'confirmed' ? '✓ 已确认' : f.feedback === 'refuted' ? '✕ 已修正' : '⚡ 事件验证' }}</text>
          <text class="verified-text">{{ f.statement }}</text>
        </view>
      </view>
    </view>

    <text v-if="!loaded" class="hint">正在翻开你的宇宙……</text>
    <text v-else-if="!litCount && !findingCount" class="hint">
      先去聊一次，花园才能开始认识你。
    </text>

    <BottomNav active="universe" :universe-badge="pendingCount > 0" />
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import api, { type FindingOut } from "@/api/client";
import BottomNav from "@/components/BottomNav.vue";
import { useTimePhase } from "@/utils/timeTheme";
import { requireSelfPersonId } from "@/utils/account";

const litCount = ref(0);       // 已点亮的 34 子类数
const findingCount = ref(0);   // 沉淀判断总数（含待验证）
const pendingCount = ref(0);   // 待验证判断数（宇宙红点来源）
const findings = ref<FindingOut[]>([]);
const personId = ref("");
const verifyingId = ref("");
const calibrationVisible = ref(false);
const loaded = ref(false);

const pendingFindings = computed(() => findings.value.filter((f) => f.status === "unverified"));
const verifiedFindings = computed(() => findings.value.filter((f) => f.status === "verified"));

const litLabel = ref("34 子类 · 3 星区");
const findingLabel = ref("沉淀判断 · 待校准");
const { phaseClass, refreshPhase } = useTimePhase();

// 星座散点（固定伪随机，避免每次渲染跳位）
const stars = Array.from({ length: 12 }, (_, i) => ({
  x: [14, 28, 44, 65, 84, 75, 18, 34, 87, 53, 8, 70][i],
  y: [20, 29, 17, 23, 15, 37, 49, 58, 59, 71, 82, 88][i],
}));

onShow(async () => {
  refreshPhase();
  const pid = await requireSelfPersonId();
  if (!pid) return;
  personId.value = pid;

  // 并行拉两入口的统计，任一侧失败都不阻塞枢纽页
  const [frag, fids] = await Promise.allSettled([
    api.fragments(pid),
    api.findings(pid),
  ]);

  if (frag.status === "fulfilled") {
    const list = frag.value.fragments;
    litCount.value = list.filter((f) => f.depth > 0).length;
    const total = list.length || 34;
    litLabel.value = `已点亮 ${litCount.value}/${total}`;
  }

  if (fids.status === "fulfilled") {
    applyFindings(fids.value);
    calibrationVisible.value = findingCount.value > 0;
  }
  loaded.value = true;
});

function applyFindings(list: FindingOut[]) {
  findings.value = list;
  findingCount.value = findings.value.length;
  pendingCount.value = pendingFindings.value.length;
  findingLabel.value = pendingCount.value
    ? `待验证 ${pendingCount.value} 条 · 共 ${findingCount.value} 条沉淀判断`
    : findingCount.value
      ? `已有 ${findingCount.value} 条沉淀判断`
      : "等你一起校准的理解";
}

async function refreshFindings() {
  if (!personId.value) return;
  try {
    applyFindings(await api.findings(personId.value));
  } catch {
    applyFindings([]);
  }
}

function focusCalibration() {
  calibrationVisible.value = true;
  uni.pageScrollTo({ selector: "#calibration", duration: 260 });
}

async function verifyFinding(f: FindingOut, feedback: "confirmed" | "refuted") {
  if (!personId.value || verifyingId.value) return;
  verifyingId.value = f.id;
  try {
    await api.feedbackFinding(personId.value, f.id, feedback);
    await refreshFindings();
    calibrationVisible.value = true;
    uni.showToast({ title: feedback === "confirmed" ? "已确认这条理解" : "已记下修正", icon: "none" });
  } catch {
    uni.showToast({ title: "操作失败，请重试", icon: "none" });
  } finally {
    verifyingId.value = "";
  }
}

function goWheel() {
  uni.navigateTo({ url: "/pages/universe/wheel" });
}
function goConsult() {
  uni.navigateTo({ url: "/pages/universe/consult" });
}
function goLifeRhythm() {
  uni.navigateTo({ url: "/pages/universe/life-rhythm" });
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: radial-gradient(circle at 50% 38%, #244b4d 0%, #102a2b 46%, #081613 100%);
  padding: 48rpx 36rpx 170rpx;
  box-sizing: border-box;
  position: relative;
  overflow: hidden;
  color: #eef1ea;
}
.cosmos-glow { position: absolute; width: 600rpx; height: 600rpx; border-radius: 50%; left: 90rpx; top: 280rpx; background: rgba(154, 205, 186, 0.12); filter: blur(60rpx); pointer-events: none; }
.constellation { position: absolute; inset: 0; opacity: 0.75; pointer-events: none; }
.c-dot { position: absolute; width: 6rpx; height: 6rpx; border-radius: 50%; background: #eee7ce; box-shadow: 0 0 20rpx rgba(238, 231, 206, 0.7); animation: twinkle 4s ease-in-out infinite; }
@keyframes twinkle { 50% { opacity: 0.3; } }

/* 星轨核心（可点：进星盘轮） */
.orbit-zone { position: absolute; left: 50%; top: 36%; transform: translate(-50%, -50%); pointer-events: none; }
.orbit { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); border: 1rpx solid rgba(226, 222, 198, 0.18); border-radius: 50%; }
.orbit.one { width: 560rpx; height: 560rpx; rotate: 13deg; animation: slowSpin 60s linear infinite; }
.orbit.two { width: 410rpx; height: 410rpx; rotate: -22deg; animation: slowSpin 48s linear reverse infinite; }
.orbit.three { width: 250rpx; height: 250rpx; rotate: 32deg; animation: slowSpin 36s linear infinite; }
@keyframes slowSpin { to { transform: translate(-50%, -50%) rotate(360deg); } }
.core { position: absolute; left: 50%; top: 36%; transform: translate(-50%, -50%); width: 128rpx; height: 128rpx; border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #fff7dc, #bca873 58%, #576a77);
  box-shadow: 0 0 100rpx rgba(220, 205, 158, 0.35); display: flex; align-items: center; justify-content: center;
  font-family: Georgia, "Noto Serif SC", serif; font-size: 42rpx; color: #2c3e50; z-index: 2; }
.planet { position: absolute; width: 72rpx; height: 72rpx; border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font-size: 30rpx; background: rgba(255, 255, 255, 0.08); border: 1rpx solid rgba(255, 255, 255, 0.14); backdrop-filter: blur(8rpx); color: #eef1ea; z-index: 2; }
.planet:active { transform: scale(0.92); }
.p1 { left: 13%; top: 32%; }
.p2 { right: 12%; top: 44%; }
.p3 { left: 22%; top: 58%; }
.p4 { right: 21%; top: 66%; }

.head { position: relative; z-index: 3; display: flex; justify-content: space-between; align-items: flex-start; }
.eyebrow { display: block; font-size: 19rpx; letter-spacing: 0.16em; color: rgba(238, 241, 234, 0.45); font-weight: 800; }
.title { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 52rpx; font-weight: 600; color: #eef1ea; margin-top: 6rpx; }
.sub { display: block; position: relative; z-index: 3; font-size: 23rpx; color: rgba(238, 241, 234, 0.54); line-height: 1.7; margin-top: 12rpx; }

.copy { position: relative; z-index: 3; margin-top: 430rpx; margin-bottom: 34rpx; }
.copy-h { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 46rpx; font-weight: 600; color: #eef1ea; }
.copy-p { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 24rpx; color: rgba(238, 241, 234, 0.58); line-height: 1.8; margin: 16rpx 0 0; white-space: pre-line; }
.explore { margin-top: 28rpx; border: 1rpx solid rgba(255, 255, 255, 0.14); background: rgba(255, 255, 255, 0.06); color: #eef1ea;
  padding: 22rpx 30rpx; border-radius: 22rpx; font-size: 25rpx; display: inline-flex; align-items: center; }

/* 功能入口：观星台列表 */
.entries { position: relative; z-index: 3; display: grid; gap: 18rpx; }
.entry { display: flex; align-items: center; gap: 22rpx; padding: 30rpx 28rpx; border-radius: 28rpx;
  background: rgba(255, 255, 255, 0.05); border: 1rpx solid rgba(255, 255, 255, 0.09); }
.entry:active { background: rgba(255, 255, 255, 0.09); }
.entry-ico { width: 84rpx; height: 84rpx; flex-shrink: 0; border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font-size: 36rpx; background: rgba(255, 255, 255, 0.07); border: 1rpx solid rgba(255, 255, 255, 0.12); }
.entry-body { flex: 1; min-width: 0; }
.entry-title { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 32rpx; font-weight: 600; color: #eef1ea; }
.entry-sub { display: block; margin-top: 6rpx; font-size: 23rpx; color: #b9c8bd; }
.entry-desc { display: block; margin-top: 8rpx; font-size: 21rpx; color: rgba(238, 241, 234, 0.5); }
.entry-arrow { color: rgba(238, 241, 234, 0.4); font-size: 44rpx; }

.calibration-panel { position: relative; z-index: 3; margin-top: 22rpx; border-radius: 34rpx; padding: 30rpx 26rpx; background: rgba(255, 255, 255, 0.065); border: 1rpx solid rgba(185, 200, 189, 0.16); box-shadow: 0 22rpx 70rpx rgba(0, 0, 0, 0.12); }
.calibration-kicker { display: block; font-size: 19rpx; letter-spacing: 0.14em; color: rgba(185, 200, 189, 0.78); font-weight: 800; }
.calibration-title { display: block; margin-top: 12rpx; font-family: Georgia, "Noto Serif SC", serif; font-size: 31rpx; font-weight: 600; color: #f4ead7; }
.calibration-copy { display: block; margin-top: 10rpx; color: rgba(238, 241, 234, 0.56); font-size: 22rpx; line-height: 1.7; }
.finding-list { display: grid; gap: 16rpx; margin-top: 24rpx; }
.finding-card { padding: 24rpx; border-radius: 28rpx; background: rgba(8, 22, 19, 0.34); border: 1rpx solid rgba(240, 210, 139, 0.14); }
.finding-top { display: flex; justify-content: space-between; align-items: center; gap: 16rpx; }
.finding-tag { color: #f0d28b; font-size: 20rpx; font-weight: 700; }
.finding-conf { color: rgba(238, 241, 234, 0.48); font-size: 19rpx; }
.finding-statement { display: block; margin-top: 16rpx; color: #fff7e7; font-size: 25rpx; line-height: 1.7; }
.finding-notes { display: grid; gap: 8rpx; margin-top: 14rpx; }
.finding-note { color: rgba(238, 241, 234, 0.5); font-size: 20rpx; line-height: 1.6; }
.finding-actions { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14rpx; margin-top: 20rpx; }
.finding-btn { margin: 0; padding: 18rpx 0; border-radius: 999rpx; font-size: 22rpx; line-height: 1.2; border: 1rpx solid rgba(255, 255, 255, 0.12); }
.finding-btn::after { border: 0; }
.finding-btn.yes { background: rgba(240, 210, 139, 0.16); color: #f8e2a7; }
.finding-btn.no { background: rgba(255, 255, 255, 0.055); color: rgba(238, 241, 234, 0.68); }
.calibration-empty { margin-top: 24rpx; padding: 28rpx; border-radius: 26rpx; background: rgba(255, 255, 255, 0.045); border: 1rpx dashed rgba(238, 241, 234, 0.12); }
.empty-title { display: block; color: #eef1ea; font-size: 25rpx; font-weight: 650; }
.empty-copy { display: block; margin-top: 10rpx; color: rgba(238, 241, 234, 0.5); font-size: 21rpx; line-height: 1.6; }
.verified-section { margin-top: 26rpx; }
.verified-title { display: block; color: rgba(238, 241, 234, 0.66); font-size: 21rpx; font-weight: 700; }
.verified-card { margin-top: 14rpx; padding: 20rpx 22rpx; border-radius: 24rpx; background: rgba(255, 255, 255, 0.045); border: 1rpx solid rgba(255, 255, 255, 0.08); }
.verified-status { display: block; color: rgba(240, 210, 139, 0.74); font-size: 19rpx; }
.verified-text { display: block; margin-top: 8rpx; color: rgba(238, 241, 234, 0.68); font-size: 22rpx; line-height: 1.6; }

.hint { position: relative; z-index: 3; display: block; color: rgba(238, 241, 234, 0.6); font-size: 25rpx; text-align: center; padding: 40rpx 0; }
</style>
