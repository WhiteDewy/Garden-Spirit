<template>
  <view class="page gs-time-page" :class="phaseClass">
    <view class="privacy-glow" aria-hidden="true"></view>

    <view class="navbar">
      <text class="nav-back" @tap="goBack">‹</text>
      <text class="nav-title">隐私与安全</text>
      <view class="nav-right" />
    </view>

    <view class="head">
      <text class="eyebrow">TRUST CENTER · 数据与安全</text>
      <text class="title">你的花园，由你决定留下什么。</text>
      <text class="sub">这里只接合规工具与推送偏好；不会前端生成占星报告，也不会在未确认时删除任何数据。</text>
    </view>

    <view v-if="loading" class="empty">正在打开安全工具……</view>

    <view v-else class="body">
      <view class="status-card">
        <view>
          <text class="status-kicker">CURRENT PROFILE</text>
          <text class="status-title">{{ personName }}</text>
          <text class="status-sub">档案 ID：{{ shortPersonId }}</text>
        </view>
        <text class="status-badge">本机登录</text>
      </view>

      <view class="section-card">
        <view class="section-head">
          <text class="section-kicker">PUSH · 推送偏好</text>
          <text class="section-title">让花园在重要时刻提醒你</text>
        </view>
        <text class="section-copy">推送用于今日来信、回家看看和复盘提醒。浏览器不支持或你拒绝通知时，会安静关闭，不影响主体验。</text>
        <view class="action-row">
          <button class="primary-action" :disabled="pushBusy" @tap="enablePush">{{ pushBusy ? '处理中…' : '开启推送' }}</button>
          <button class="ghost-action" :disabled="pushBusy" @tap="disablePush">关闭推送</button>
        </view>
        <text v-if="pushMessage" class="hint-line">{{ pushMessage }}</text>
      </view>

      <view class="section-card">
        <view class="section-head">
          <text class="section-kicker">EXPORT · 数据导出</text>
          <text class="section-title">先把你的记忆带走</text>
        </view>
        <text class="section-copy">导出会聚合出生档案、画像、聊天沉淀、来信、手账、碎片账本、推送订阅与合盘对象，适合删除前留档。</text>
        <button class="primary-action full" :disabled="exporting" @tap="exportData">{{ exporting ? '正在导出…' : '导出我的数据' }}</button>

        <view v-if="exportReady" class="export-result">
          <text class="result-title">导出已准备好</text>
          <text class="result-copy">生成时间：{{ exportedAtLabel }}</text>
          <view class="mini-grid">
            <view v-for="item in exportStats" :key="item.label" class="mini-stat">
              <text class="mini-num">{{ item.value }}</text>
              <text class="mini-label">{{ item.label }}</text>
            </view>
          </view>
          <button class="ghost-action full" @tap="copyExportJson">复制 JSON 到剪贴板</button>
        </view>
      </view>

      <view class="danger-card">
        <view class="section-head">
          <text class="section-kicker danger">DELETE · 全量删除</text>
          <text class="section-title">删除前，请先确认你已导出</text>
        </view>
        <text class="section-copy">删除会清空业务表并移除本人档案，包括聊天沉淀、来信、手账、碎片点亮、推送订阅和合盘对象。这个操作不可逆。</text>
        <view class="danger-check" @tap="exportAcknowledged = !exportAcknowledged">
          <text :class="['check-box', { on: exportAcknowledged }]">{{ exportAcknowledged ? '✓' : '' }}</text>
          <text class="check-copy">我已经导出或确认不需要保留备份</text>
        </view>
        <button class="danger-action" :disabled="deleting || !exportAcknowledged" @tap="deleteAccountData">
          {{ deleting ? '正在删除…' : '删除我的全部数据' }}
        </button>
      </view>

      <view class="note-card">
        <text class="note-title">密钥安全说明</text>
        <text class="note-copy">记忆库使用服务端密钥加密保存。若密钥丢失，历史加密数据无法恢复；若档案出现无法解密，页面会引导你重新建档。</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import api, { ApiError, describeError, type PersonExportOut, type PersonOut } from "@/api/client";
import { clearAccountCache, requireSelfPersonId } from "@/utils/account";
import { subscribePush, unsubscribePush } from "@/utils/push";
import { useTimePhase } from "@/utils/timeTheme";

const { phaseClass, refreshPhase } = useTimePhase();
const personId = ref("");
const person = ref<PersonOut | null>(null);
const loading = ref(true);
const pushBusy = ref(false);
const pushMessage = ref("");
const exporting = ref(false);
const exportPayload = ref<PersonExportOut | null>(null);
const exportJson = ref("");
const exportAcknowledged = ref(false);
const deleting = ref(false);

const personName = computed(() => person.value?.name || "我的花园档案");
const shortPersonId = computed(() => personId.value ? `${personId.value.slice(0, 8)}…${personId.value.slice(-4)}` : "—");
const exportReady = computed(() => !!exportPayload.value && !!exportJson.value);
const exportedAtLabel = computed(() => formatDateTime(exportPayload.value?.exported_at));
const exportStats = computed(() => {
  const data = exportPayload.value;
  if (!data) return [];
  return [
    { label: "会话", value: data.conversations?.length || 0 },
    { label: "来信", value: data.letters?.length || 0 },
    { label: "手账", value: data.journal_entries?.length || 0 },
    { label: "碎片账本", value: data.fragment_lights?.length || 0 },
  ];
});

onLoad(async () => {
  refreshPhase();
  const pid = await requireSelfPersonId();
  if (!pid) return;
  personId.value = pid;
  try {
    person.value = await api.getPerson(pid);
  } catch (e: any) {
    if (e instanceof ApiError && e.status === 410) {
      clearAccountCache();
      uni.showToast({ title: "当前档案已无法解密，请重新登录建档", icon: "none" });
      return uni.redirectTo({ url: "/pages/auth/login" });
    }
    uni.showToast({ title: describeError(e), icon: "none" });
  } finally {
    loading.value = false;
  }
});

async function enablePush() {
  if (!personId.value || pushBusy.value) return;
  pushBusy.value = true;
  pushMessage.value = "";
  try {
    const ok = await subscribePush(personId.value);
    pushMessage.value = ok ? "推送已开启。" : "当前环境暂不支持推送，或你尚未允许通知。";
  } finally {
    pushBusy.value = false;
  }
}

async function disablePush() {
  if (!personId.value || pushBusy.value) return;
  pushBusy.value = true;
  pushMessage.value = "";
  try {
    const ok = await unsubscribePush(personId.value);
    pushMessage.value = ok ? "推送已关闭。" : "当前环境没有可关闭的浏览器推送。";
  } finally {
    pushBusy.value = false;
  }
}

async function exportData() {
  if (!personId.value || exporting.value) return;
  exporting.value = true;
  try {
    const data = await api.exportPerson(personId.value);
    exportPayload.value = data;
    exportJson.value = JSON.stringify(data, null, 2);
    exportAcknowledged.value = true;
    uni.showToast({ title: "导出已生成，可复制保存", icon: "none" });
  } catch (e: any) {
    if (e instanceof ApiError && e.status === 410) {
      clearAccountCache();
      uni.showToast({ title: "当前档案已无法解密，请重新登录建档", icon: "none" });
      return uni.redirectTo({ url: "/pages/auth/login" });
    }
    uni.showToast({ title: describeError(e), icon: "none" });
  } finally {
    exporting.value = false;
  }
}

function copyExportJson() {
  if (!exportJson.value) return;
  uni.setClipboardData({
    data: exportJson.value,
    success: () => uni.showToast({ title: "已复制导出 JSON", icon: "none" }),
    fail: () => uni.showToast({ title: "复制失败，请重试", icon: "none" }),
  });
}

function confirmModal(title: string, content: string, confirmText: string, confirmColor = "#b85b43") {
  return new Promise<boolean>((resolve) => {
    uni.showModal({
      title,
      content,
      confirmText,
      confirmColor,
      success: (res) => resolve(!!res.confirm),
      fail: () => resolve(false),
    });
  });
}

async function deleteAccountData() {
  if (!personId.value || deleting.value || !exportAcknowledged.value) return;
  const first = await confirmModal(
    "确认删除全部数据？",
    "这会删除档案、聊天沉淀、来信、手账、碎片账本、推送订阅和合盘对象。建议先导出 JSON 备份。",
    "继续删除"
  );
  if (!first) return;
  const second = await confirmModal(
    "最后一次确认",
    "删除后无法恢复。确认要离开这座花园并清空全部数据吗？",
    "确认删除"
  );
  if (!second) return;

  deleting.value = true;
  try {
    await api.deletePerson(personId.value);
    clearAccountCache();
    uni.showToast({ title: "数据已删除", icon: "none" });
    uni.reLaunch({ url: "/pages/auth/login" });
  } catch (e: any) {
    uni.showToast({ title: describeError(e), icon: "none" });
  } finally {
    deleting.value = false;
  }
}

function formatDateTime(value?: string | null) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function pad(n: number) {
  return String(n).padStart(2, "0");
}

function goBack() {
  uni.navigateBack({ fail: () => uni.reLaunch({ url: "/pages/me/me" }) });
}
</script>

<style scoped>
.page { min-height: 100vh; padding: 0 36rpx 80rpx; box-sizing: border-box; color: #edf1e9; background: radial-gradient(circle at 82% 10%, rgba(240, 210, 139, 0.14), transparent 30%), linear-gradient(170deg, #17362c 0%, #10271f 58%, #081613 100%); position: relative; overflow: hidden; }
.privacy-glow { position: absolute; width: 560rpx; height: 560rpx; right: -220rpx; top: 150rpx; border-radius: 50%; background: rgba(183, 164, 113, 0.13); filter: blur(64rpx); pointer-events: none; }
.navbar { position: relative; z-index: 2; display: flex; align-items: center; padding: 24rpx 0; border-bottom: 1rpx solid rgba(255, 255, 255, 0.06); }
.nav-back { width: 60rpx; color: #e8f5e9; font-size: 52rpx; line-height: 1; }
.nav-title { flex: 1; text-align: center; color: #e8f5e9; font-size: 32rpx; font-weight: 650; }
.nav-right { width: 60rpx; }
.head { position: relative; z-index: 1; margin: 34rpx 0 28rpx; }
.eyebrow { display: block; font-size: 19rpx; letter-spacing: 0.16em; color: rgba(240, 210, 139, 0.66); font-weight: 800; }
.title { display: block; margin-top: 14rpx; font-family: Georgia, "Noto Serif SC", serif; font-size: 43rpx; line-height: 1.3; color: #fff7e7; font-weight: 600; }
.sub { display: block; margin-top: 14rpx; color: rgba(235, 241, 233, 0.56); font-size: 24rpx; line-height: 1.7; }
.body, .empty { position: relative; z-index: 1; }
.empty { text-align: center; padding: 100rpx 0; color: rgba(235, 241, 233, 0.58); font-size: 27rpx; }
.status-card, .section-card, .danger-card, .note-card { border-radius: 34rpx; padding: 30rpx 26rpx; background: rgba(255, 255, 255, 0.06); border: 1rpx solid rgba(255, 255, 255, 0.1); box-shadow: 0 22rpx 70rpx rgba(0, 0, 0, 0.12); margin-bottom: 22rpx; }
.status-card { display: flex; align-items: center; justify-content: space-between; gap: 20rpx; background: linear-gradient(145deg, rgba(240, 210, 139, 0.13), rgba(255, 255, 255, 0.045)); border-color: rgba(240, 210, 139, 0.2); }
.status-kicker, .section-kicker { display: block; font-size: 19rpx; letter-spacing: 0.14em; color: rgba(240, 210, 139, 0.72); font-weight: 800; }
.status-title { display: block; margin-top: 12rpx; font-family: Georgia, "Noto Serif SC", serif; font-size: 34rpx; color: #fff7e7; font-weight: 600; }
.status-sub { display: block; margin-top: 8rpx; color: rgba(235, 241, 233, 0.44); font-size: 20rpx; }
.status-badge { flex-shrink: 0; padding: 8rpx 18rpx; border-radius: 999rpx; background: rgba(165, 214, 167, 0.14); color: rgba(190, 235, 192, 0.88); font-size: 20rpx; }
.section-head { margin-bottom: 16rpx; }
.section-title { display: block; margin-top: 12rpx; font-size: 30rpx; color: #edf1e9; font-weight: 700; }
.section-copy { display: block; color: rgba(235, 241, 233, 0.58); font-size: 23rpx; line-height: 1.72; }
.action-row { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14rpx; margin-top: 24rpx; }
.primary-action, .ghost-action, .danger-action { margin: 0; border-radius: 999rpx; padding: 20rpx 0; font-size: 23rpx; line-height: 1.2; }
.primary-action::after, .ghost-action::after, .danger-action::after { border: 0; }
.primary-action { background: linear-gradient(135deg, #f5df9f, #d6efc5); color: #17362c; font-weight: 800; }
.ghost-action { background: rgba(255, 255, 255, 0.055); color: rgba(238, 241, 234, 0.72); border: 1rpx solid rgba(255, 255, 255, 0.1); }
.full { width: 100%; margin-top: 24rpx; }
.hint-line { display: block; margin-top: 14rpx; color: rgba(240, 210, 139, 0.7); font-size: 21rpx; line-height: 1.5; }
.export-result { margin-top: 22rpx; padding: 22rpx; border-radius: 28rpx; background: rgba(8, 22, 19, 0.3); border: 1rpx solid rgba(240, 210, 139, 0.12); }
.result-title { display: block; color: #f5df9f; font-size: 25rpx; font-weight: 800; }
.result-copy { display: block; margin-top: 8rpx; color: rgba(235, 241, 233, 0.5); font-size: 21rpx; }
.mini-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10rpx; margin-top: 18rpx; }
.mini-stat { text-align: center; border-radius: 20rpx; padding: 16rpx 8rpx; background: rgba(255, 255, 255, 0.055); }
.mini-num { display: block; color: #f0d28b; font-size: 30rpx; font-weight: 800; }
.mini-label { display: block; margin-top: 5rpx; color: rgba(235, 241, 233, 0.48); font-size: 18rpx; }
.danger-card { border-color: rgba(184, 91, 67, 0.34); background: linear-gradient(145deg, rgba(184, 91, 67, 0.14), rgba(255, 255, 255, 0.045)); }
.section-kicker.danger { color: rgba(255, 175, 150, 0.85); }
.danger-check { display: flex; align-items: center; gap: 14rpx; margin: 22rpx 0; padding: 18rpx; border-radius: 22rpx; background: rgba(8, 22, 19, 0.24); }
.check-box { width: 34rpx; height: 34rpx; border-radius: 10rpx; display: flex; align-items: center; justify-content: center; border: 1rpx solid rgba(255, 255, 255, 0.2); color: #17362c; font-size: 22rpx; font-weight: 900; }
.check-box.on { background: #f5df9f; border-color: #f5df9f; }
.check-copy { flex: 1; color: rgba(235, 241, 233, 0.68); font-size: 22rpx; line-height: 1.5; }
.danger-action { width: 100%; background: rgba(184, 91, 67, 0.84); color: #fff7f0; font-weight: 800; }
.danger-action[disabled] { opacity: 0.45; }
.note-card { background: rgba(8, 22, 19, 0.26); border-style: dashed; }
.note-title { display: block; color: rgba(240, 210, 139, 0.76); font-size: 24rpx; font-weight: 800; }
.note-copy { display: block; margin-top: 10rpx; color: rgba(235, 241, 233, 0.5); font-size: 21rpx; line-height: 1.7; }
</style>
