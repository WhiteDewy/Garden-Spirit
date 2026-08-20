<template>
  <view class="page">
    <view class="glow"></view>
    <view class="card">
      <text class="eyebrow">PHONE ACCOUNT</text>
      <text class="title">先确认这是你的花园</text>
      <text class="copy">手机号只绑定一个唯一本人档案。后续聊天、来信、手账和星盘解释都会归到这个本人档案下。</text>

      <view class="field">
        <text class="label">手机号</text>
        <input v-model="phone" class="input" type="number" placeholder="18513821306" maxlength="11" />
      </view>
      <view class="field">
        <text class="label">验证码</text>
        <input v-model="code" class="input" type="number" placeholder="开发环境请输入 000000" maxlength="6" />
      </view>

      <button class="primary" :disabled="busy" @tap="submit">
        {{ busy ? "正在进入…" : "登录 / 注册" }}
      </button>
      <text v-if="error" class="error">{{ error }}</text>
      <text class="dev-note">开发临时白名单：任意手机号 · 验证码 000000</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import api, { describeError, type AccountOut } from "@/api/client";
import { cacheAccount, loginWithDevPhone } from "@/utils/account";

const phone = ref("18513821306");
const code = ref("000000");
const busy = ref(false);
const error = ref("");

async function claimLegacyIfNeeded(account: AccountOut) {
  if (account.phone !== "18513821306" || !account.self_person_id) return;
  try {
    await api.claimXiatianLegacyData(account.account_id);
  } catch {
    // 旧数据认领是开发迁移兜底，失败不阻塞登录；后续可在档案列表手动重试。
  }
}

async function submit() {
  if (!phone.value.trim()) return (error.value = "请输入手机号");
  if (!code.value.trim()) return (error.value = "请输入验证码");
  busy.value = true;
  error.value = "";
  try {
    const account = await loginWithDevPhone(phone.value, code.value);
    cacheAccount(account);
    if (account.self_person_id) {
      await claimLegacyIfNeeded(account);
      uni.reLaunch({ url: "/pages/index/index?enter=garden" });
    } else {
      uni.redirectTo({ url: "/pages/onboarding/onboarding" });
    }
  } catch (e) {
    error.value = describeError(e);
  } finally {
    busy.value = false;
  }
}
</script>

<style scoped>
.page { min-height: 100vh; box-sizing: border-box; padding: 96rpx 40rpx; color: #edf1e9; background: radial-gradient(circle at 70% 10%, rgba(240, 210, 139, 0.18), transparent 28%), linear-gradient(170deg, #10271f 0%, #081613 100%); position: relative; overflow: hidden; }
.glow { position: absolute; width: 520rpx; height: 520rpx; border-radius: 50%; left: -220rpx; bottom: 120rpx; background: rgba(151, 196, 173, 0.13); filter: blur(70rpx); }
.card { position: relative; z-index: 1; padding: 44rpx 34rpx; border-radius: 38rpx; border: 1rpx solid rgba(240, 210, 139, 0.22); background: rgba(255, 255, 255, 0.055); box-shadow: 0 30rpx 90rpx rgba(0, 0, 0, 0.22); }
.eyebrow { display: block; font-size: 20rpx; letter-spacing: 0.18em; color: rgba(240, 210, 139, 0.7); font-weight: 800; }
.title { display: block; margin-top: 14rpx; font-family: Georgia, "Noto Serif SC", serif; font-size: 52rpx; font-weight: 600; color: #fff7e7; }
.copy { display: block; margin-top: 18rpx; color: rgba(237, 241, 233, 0.62); font-size: 25rpx; line-height: 1.75; }
.field { margin-top: 30rpx; }
.label { display: block; margin-bottom: 12rpx; color: rgba(237, 241, 233, 0.48); font-size: 22rpx; }
.input { height: 88rpx; border-radius: 24rpx; padding: 0 24rpx; box-sizing: border-box; color: #fff7e7; background: rgba(8, 22, 19, 0.36); border: 1rpx solid rgba(255, 255, 255, 0.11); font-size: 30rpx; }
.primary { margin-top: 38rpx; height: 92rpx; border-radius: 999rpx; border: 0; background: linear-gradient(135deg, #f2d58d, #b89448); color: #10271f; font-size: 29rpx; font-weight: 800; }
.error { display: block; margin-top: 18rpx; color: #ffcfbf; font-size: 23rpx; }
.dev-note { display: block; margin-top: 24rpx; color: rgba(237, 241, 233, 0.38); font-size: 21rpx; text-align: center; }
</style>
