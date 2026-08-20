import api, { ApiError, type AccountOut } from "@/api/client";

export const ACCOUNT_KEY = "gs_account_id";
export const PERSON_KEY = "gs_person_id";
export const SESSION_KEY = "gs_session_id";

export function cacheAccount(account: AccountOut) {
  if (account.account_id) uni.setStorageSync(ACCOUNT_KEY, account.account_id);
  const selfId = account.self_person_id || account.self_profile?.id || "";
  if (selfId) uni.setStorageSync(PERSON_KEY, selfId);
  else uni.removeStorageSync(PERSON_KEY);
  return selfId;
}

export function clearAccountCache() {
  uni.removeStorageSync(ACCOUNT_KEY);
  uni.removeStorageSync(PERSON_KEY);
  clearChatSessionCache();
}

export function getChatSessionId() {
  return (uni.getStorageSync(SESSION_KEY) as string) || undefined;
}

export function cacheChatSessionId(sessionId: string) {
  if (sessionId) uni.setStorageSync(SESSION_KEY, sessionId);
}

export function clearChatSessionCache() {
  uni.removeStorageSync(SESSION_KEY);
}

export async function loginWithDevPhone(phone: string, code: string) {
  const account = await api.verifyPhone({ phone, code });
  cacheAccount(account);
  return account;
}

export async function resolveAccount() {
  const accountId = uni.getStorageSync(ACCOUNT_KEY) as string;
  if (!accountId) return null;
  try {
    const account = await api.getAccount(accountId);
    cacheAccount(account);
    return account;
  } catch (e) {
    if (e instanceof ApiError && (e.status === 404 || e.status === 410)) clearAccountCache();
    throw e;
  }
}

export async function requireSelfPersonId(redirect = true) {
  const accountId = uni.getStorageSync(ACCOUNT_KEY) as string;
  if (!accountId) {
    if (redirect) uni.redirectTo({ url: "/pages/auth/login" });
    return "";
  }
  const account = await resolveAccount();
  const selfId = account?.self_person_id || account?.self_profile?.id || "";
  if (selfId) return selfId;
  if (redirect) uni.redirectTo({ url: "/pages/onboarding/onboarding" });
  return "";
}
