<template>
  <view class="page">
    <view class="head">
      <text class="eyebrow">PROFILES</text>
      <text class="title">档案列表</text>
      <text class="sub">本人档案唯一；新增档案只用于合盘，不会成为本人。</text>
    </view>

    <view v-if="loading" class="hint">正在读取档案…</view>
    <view v-else class="list">
      <view v-for="item in profiles" :key="`${item.role}-${item.id}`" class="profile-card" @tap="edit(item)">
        <view>
          <text class="role">{{ item.role === 'self' ? '本人档案' : '合盘档案' }}</text>
          <text class="name">{{ item.name }}</text>
          <text class="meta">{{ item.role === 'self' ? '所有解释与记忆都归这里' : '仅用于关系/合盘咨询' }}</text>
        </view>
        <text class="arrow">→</text>
      </view>

      <button class="primary" @tap="addRelated">新增合盘档案</button>
      <button v-if="isXiatian" class="secondary" :disabled="claiming" @tap="claimLegacy">
        {{ claiming ? '正在认领旧数据…' : '认领夏天旧测试数据' }}
      </button>
      <text v-if="!profiles.length" class="hint">还没有本人档案，先创建你的星图。</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import api, { describeError, type AccountOut, type ProfileListItemOut } from "@/api/client";
import { cacheAccount, resolveAccount } from "@/utils/account";

const loading = ref(true);
const claiming = ref(false);
const account = ref<AccountOut | null>(null);
const profiles = ref<ProfileListItemOut[]>([]);
const isXiatian = computed(() => account.value?.phone === "18513821306" && !!account.value?.self_person_id);

onShow(load);

async function load() {
  loading.value = true;
  try {
    const acc = await resolveAccount();
    if (!acc) return uni.redirectTo({ url: "/pages/auth/login" });
    account.value = acc;
    profiles.value = await api.listAccountProfiles(acc.account_id);
  } catch (e) {
    uni.showToast({ title: describeError(e), icon: "none" });
    uni.redirectTo({ url: "/pages/auth/login" });
  } finally {
    loading.value = false;
  }
}

function edit(item: ProfileListItemOut) {
  if (item.role === "self") uni.navigateTo({ url: "/pages/profile/edit?mode=self" });
  else uni.navigateTo({ url: `/pages/profile/edit?mode=related&id=${encodeURIComponent(item.id)}` });
}

function addRelated() {
  uni.navigateTo({ url: "/pages/profile/edit?mode=related" });
}

async function claimLegacy() {
  const accountId = account.value?.account_id;
  if (!accountId || claiming.value) return;
  claiming.value = true;
  try {
    await api.claimXiatianLegacyData(accountId);
    const acc = await api.getAccount(accountId);
    cacheAccount(acc);
    uni.showToast({ title: "旧数据已归并到本人档案", icon: "none" });
    await load();
  } catch (e) {
    uni.showToast({ title: describeError(e), icon: "none" });
  } finally {
    claiming.value = false;
  }
}
</script>

<style scoped>
.page { min-height: 100vh; padding: 54rpx 36rpx 120rpx; box-sizing: border-box; color: #edf1e9; background: linear-gradient(170deg, #17362c 0%, #081613 100%); }
.head { margin-bottom: 28rpx; }
.eyebrow { display: block; font-size: 19rpx; letter-spacing: 0.16em; color: rgba(240, 210, 139, 0.58); font-weight: 800; }
.title { display: block; margin-top: 8rpx; font-family: Georgia, "Noto Serif SC", serif; font-size: 52rpx; color: #fff7e7; }
.sub, .hint { display: block; margin-top: 12rpx; color: rgba(237, 241, 233, 0.52); font-size: 24rpx; line-height: 1.65; }
.list { display: flex; flex-direction: column; gap: 18rpx; }
.profile-card { display: flex; justify-content: space-between; align-items: center; gap: 24rpx; padding: 30rpx 28rpx; border-radius: 30rpx; border: 1rpx solid rgba(255, 255, 255, 0.1); background: rgba(255, 255, 255, 0.055); }
.role { display: block; color: rgba(240, 210, 139, 0.72); font-size: 20rpx; letter-spacing: 0.08em; }
.name { display: block; margin-top: 8rpx; color: #edf1e9; font-size: 34rpx; font-weight: 700; }
.meta { display: block; margin-top: 8rpx; color: rgba(237, 241, 233, 0.42); font-size: 22rpx; }
.arrow { color: rgba(240, 210, 139, 0.7); font-size: 36rpx; }
.primary, .secondary { height: 88rpx; margin-top: 18rpx; border-radius: 999rpx; font-size: 27rpx; font-weight: 800; }
.primary { color: #10271f; background: linear-gradient(135deg, #f2d58d, #b89448); }
.secondary { color: #fff7e7; background: rgba(255, 255, 255, 0.07); border: 1rpx solid rgba(240, 210, 139, 0.28); }
</style>
