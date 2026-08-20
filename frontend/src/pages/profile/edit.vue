<template>
  <view class="page">
    <view class="head">
      <text class="eyebrow">{{ isSelf ? 'SELF PROFILE' : 'SYNASTRY PROFILE' }}</text>
      <text class="title">{{ title }}</text>
      <text class="sub">{{ isSelf ? '本人档案唯一，所有解释、来信、手账和记忆都归这里。' : '合盘档案只用于关系咨询，不能变成本人档案。' }}</text>
    </view>

    <view class="form-card">
      <view class="field">
        <text class="label">称呼</text>
        <input v-model="form.name" class="input" placeholder="怎么称呼这份档案" />
      </view>

      <view class="field">
        <text class="label">性别/称谓</text>
        <view class="pill-row">
          <view :class="['pill', { on: form.gender === 'female' || form.gender === 'F' }]" @tap="form.gender = 'female'">她</view>
          <view :class="['pill', { on: form.gender === 'male' || form.gender === 'M' }]" @tap="form.gender = 'male'">他</view>
          <view :class="['pill', { on: !form.gender }]" @tap="form.gender = ''">先不说</view>
        </view>
      </view>

      <view class="field">
        <text class="label">出生日期</text>
        <picker mode="date" :value="form.date" @change="onDate">
          <view class="picker-card">{{ form.date || '选择日期' }}</view>
        </picker>
      </view>

      <view class="field">
        <text class="label">出生时间</text>
        <picker mode="time" :value="form.time" :disabled="form.timeUnknown" @change="onTime">
          <view :class="['picker-card', { muted: form.timeUnknown }]">{{ form.timeUnknown ? '时间不确定' : (form.time || '选择时间') }}</view>
        </picker>
        <view class="check-row" @tap="form.timeUnknown = !form.timeUnknown">
          <text :class="['check', { on: form.timeUnknown }]">✓</text>
          <text>出生时间不确定</text>
        </view>
      </view>

      <view class="field">
        <text class="label">出生地</text>
        <input v-model="form.city" class="input" placeholder="例如 上海 / 北京 / Tokyo" />
      </view>

      <view v-if="isSelf" class="field">
        <text class="label">宫位制</text>
        <view class="pill-row">
          <view v-for="h in houses" :key="h.value" :class="['pill', { on: form.house_system === h.value }]" @tap="form.house_system = h.value">{{ h.label }}</view>
        </view>
      </view>

      <view class="field">
        <text class="label">备注</text>
        <textarea v-model="form.notes" class="textarea" placeholder="可选：补充你想记下的信息" />
      </view>

      <view v-if="isSelf && existed" class="danger">
        <text class="danger-title">修改本人档案会重置旧数据</text>
        <text class="danger-copy">出生信息、宫位制等会影响所有解释。保存前会再次确认；确认后旧聊天沉淀、来信、手账、碎片点亮和推送订阅会被清空。</text>
      </view>

      <button class="primary" :disabled="busy" @tap="save">{{ busy ? '正在保存…' : '保存档案' }}</button>
      <button class="secondary" @tap="back">返回</button>
      <text v-if="error" class="error">{{ error }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import api, { describeError, type AccountOut, type PersonIn, type RelatedPersonIn, type SelfProfileOut } from "@/api/client";
import { cacheAccount, clearChatSessionCache, resolveAccount } from "@/utils/account";

const mode = ref<'self' | 'related'>('self');
const relatedId = ref('');
const busy = ref(false);
const error = ref('');
const account = ref<AccountOut | null>(null);
const existed = ref(false);

const form = reactive({
  name: '',
  gender: '',
  date: '',
  time: '',
  timeUnknown: false,
  city: '',
  house_system: 'B',
  notes: '',
});

const houses = [
  { value: 'B', label: '阿卡比特' },
  { value: 'W', label: '整宫' },
  { value: 'P', label: '普拉西德' },
];

const isSelf = computed(() => mode.value === 'self');
const title = computed(() => isSelf.value ? (existed.value ? '修改本人档案' : '创建本人档案') : (relatedId.value ? '修改合盘档案' : '新增合盘档案'));

onLoad(async (query) => {
  mode.value = query?.mode === 'related' ? 'related' : 'self';
  relatedId.value = typeof query?.id === 'string' ? query.id : '';
  try {
    const acc = await resolveAccount();
    if (!acc) return uni.redirectTo({ url: '/pages/auth/login' });
    account.value = acc;
    if (isSelf.value) fillSelf(acc.self_profile);
    else if (relatedId.value) await loadRelated(acc);
  } catch (e) {
    error.value = describeError(e);
  }
});

function splitDateTime(dt: string | undefined | null) {
  const [d, t = ''] = String(dt || '').split('T');
  return { date: d || '', time: (t || '').slice(0, 5) };
}

function fillSelf(profile: SelfProfileOut | null | undefined) {
  if (!profile) return;
  existed.value = true;
  const parts = splitDateTime(profile.birth?.datetime_local);
  form.name = profile.name || '';
  form.gender = profile.gender || '';
  form.date = parts.date;
  form.time = parts.time;
  form.timeUnknown = !profile.birth?.time_known;
  form.city = profile.birth?.location?.place_name || profile.place_name || '';
  form.house_system = profile.house_system || 'B';
  form.notes = profile.notes || '';
}

async function loadRelated(acc: AccountOut) {
  const selfId = acc.self_person_id || '';
  if (!selfId) return uni.redirectTo({ url: '/pages/onboarding/onboarding' });
  const detail = await api.getRelatedPersonDetail(selfId, relatedId.value);
  const parts = splitDateTime(detail.birth?.datetime_local);
  existed.value = true;
  form.name = detail.name || '';
  form.gender = detail.gender || '';
  form.date = parts.date;
  form.time = parts.time;
  form.timeUnknown = !detail.birth?.time_known;
  form.city = detail.birth?.location?.place_name || '';
  form.notes = detail.notes || '';
}

function onDate(e: any) { form.date = e.detail.value; }
function onTime(e: any) { form.time = e.detail.value; form.timeUnknown = false; }

function payload(): PersonIn {
  const time = form.timeUnknown ? '12:00' : (form.time || '12:00');
  return {
    name: form.name.trim(),
    gender: form.gender || undefined,
    notes: form.notes || '',
    house_system: isSelf.value ? form.house_system : undefined,
    birth: {
      datetime_local: `${form.date}T${time}:00`,
      location: { place_name: form.city.trim() },
      time_known: !form.timeUnknown,
    },
  };
}

function validate() {
  if (!form.name.trim()) return '请填写称呼';
  if (!form.date) return '请选择出生日期';
  if (!form.timeUnknown && !form.time) return '请选择出生时间，或勾选时间不确定';
  if (!form.city.trim()) return '请填写出生地';
  return '';
}

function confirmSelfReset() {
  return new Promise<boolean>((resolve) => {
    if (!isSelf.value || !existed.value) return resolve(true);
    uni.showModal({
      title: '确认更新本人档案？',
      content: '一旦更新，以往所有数据将被删除，包括聊天沉淀、来信、手账、碎片点亮和推送订阅。',
      confirmText: '确认更新',
      confirmColor: '#b85b43',
      success: (res) => resolve(!!res.confirm),
      fail: () => resolve(false),
    });
  });
}

async function claimLegacyIfNeeded(acc: AccountOut) {
  if (acc.phone !== '18513821306' || !acc.self_person_id) return;
  try { await api.claimXiatianLegacyData(acc.account_id); } catch { /* 开发迁移兜底，不阻断保存 */ }
}

async function save() {
  const msg = validate();
  if (msg) return (error.value = msg);
  const acc = account.value || await resolveAccount();
  if (!acc) return uni.redirectTo({ url: '/pages/auth/login' });
  if (!(await confirmSelfReset())) return;
  busy.value = true;
  error.value = '';
  try {
    if (isSelf.value) {
      const saved = acc.self_person_id
        ? await api.updateSelfProfile(acc.account_id, payload())
        : await api.createSelfProfile(acc.account_id, payload());
      cacheAccount(saved);
      await claimLegacyIfNeeded(saved);
      clearChatSessionCache();
      uni.reLaunch({ url: '/pages/index/index?enter=garden' });
      return;
    }
    const selfId = acc.self_person_id || '';
    if (!selfId) return uni.redirectTo({ url: '/pages/onboarding/onboarding' });
    const body: RelatedPersonIn = payload();
    if (relatedId.value) await api.updateRelatedPerson(selfId, relatedId.value, body);
    else await api.createRelatedPerson(selfId, body);
    uni.showToast({ title: '合盘档案已保存', icon: 'none' });
    uni.redirectTo({ url: '/pages/profile/list' });
  } catch (e) {
    error.value = describeError(e);
  } finally {
    busy.value = false;
  }
}

function back() {
  uni.navigateBack({ fail: () => uni.redirectTo({ url: '/pages/profile/list' }) });
}
</script>

<style scoped>
.page { min-height: 100vh; padding: 54rpx 36rpx 130rpx; box-sizing: border-box; color: #edf1e9; background: radial-gradient(circle at 74% 8%, rgba(240, 210, 139, 0.14), transparent 28%), linear-gradient(170deg, #17362c 0%, #081613 100%); }
.head { margin-bottom: 28rpx; }
.eyebrow { display: block; color: rgba(240, 210, 139, 0.62); font-size: 19rpx; letter-spacing: 0.16em; font-weight: 800; }
.title { display: block; margin-top: 8rpx; font-family: Georgia, "Noto Serif SC", serif; font-size: 52rpx; color: #fff7e7; }
.sub { display: block; margin-top: 12rpx; color: rgba(237, 241, 233, 0.52); font-size: 24rpx; line-height: 1.65; }
.form-card { padding: 30rpx 28rpx; border-radius: 34rpx; border: 1rpx solid rgba(255, 255, 255, 0.1); background: rgba(255, 255, 255, 0.055); }
.field { margin-bottom: 26rpx; }
.label { display: block; margin-bottom: 12rpx; color: rgba(237, 241, 233, 0.48); font-size: 22rpx; }
.input, .picker-card, .textarea { width: 100%; box-sizing: border-box; border-radius: 24rpx; padding: 0 24rpx; color: #fff7e7; background: rgba(8, 22, 19, 0.36); border: 1rpx solid rgba(255, 255, 255, 0.11); font-size: 28rpx; }
.input, .picker-card { height: 84rpx; line-height: 84rpx; }
.picker-card.muted { color: rgba(237, 241, 233, 0.42); }
.textarea { height: 150rpx; padding-top: 22rpx; line-height: 1.55; }
.pill-row { display: flex; flex-wrap: wrap; gap: 14rpx; }
.pill { padding: 16rpx 24rpx; border-radius: 999rpx; color: rgba(237, 241, 233, 0.58); background: rgba(255, 255, 255, 0.06); border: 1rpx solid rgba(255, 255, 255, 0.1); font-size: 24rpx; }
.pill.on { color: #10271f; background: #ecd9a0; border-color: #ecd9a0; font-weight: 800; }
.check-row { display: flex; align-items: center; gap: 12rpx; margin-top: 14rpx; color: rgba(237, 241, 233, 0.5); font-size: 23rpx; }
.check { width: 34rpx; height: 34rpx; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; border: 1rpx solid rgba(255, 255, 255, 0.22); color: transparent; }
.check.on { color: #10271f; background: #ecd9a0; }
.danger { margin: 18rpx 0 28rpx; padding: 22rpx; border-radius: 24rpx; background: rgba(184, 91, 67, 0.13); border: 1rpx solid rgba(255, 170, 145, 0.22); }
.danger-title { display: block; color: #ffd1c2; font-size: 25rpx; font-weight: 800; }
.danger-copy { display: block; margin-top: 8rpx; color: rgba(255, 225, 214, 0.68); font-size: 22rpx; line-height: 1.65; }
.primary, .secondary { height: 88rpx; margin-top: 16rpx; border-radius: 999rpx; font-size: 27rpx; font-weight: 800; }
.primary { color: #10271f; background: linear-gradient(135deg, #f2d58d, #b89448); }
.secondary { color: #fff7e7; background: rgba(255, 255, 255, 0.07); border: 1rpx solid rgba(240, 210, 139, 0.28); }
.error { display: block; margin-top: 18rpx; color: #ffcfbf; font-size: 23rpx; }
</style>
