<template>
  <view class="page gs-time-page" :class="phaseClass">
    <view class="top-glow" aria-hidden="true"></view>

    <view class="header">
      <view class="spirit-orb" aria-hidden="true"><SpiritPortrait :planet="spiritPlanet" /></view>
      <view class="header-copy">
        <text class="spirit-name">{{ spiritName }}</text>
        <text class="spirit-status">{{ thinking ? '正在翻看你的星图…' : '正在听你说' }}</text>
      </view>
      <text v-if="trustLabel" class="trust-tag">信任 · {{ trustLabel }}</text>
    </view>

    <scroll-view class="messages" scroll-y :scroll-into-view="scrollTo">
      <view class="time-divider"><text>{{ todayStr }}</text></view>
      <view v-for="(m, i) in messages" :key="i" class="msg-row" :class="m.role">
        <view class="bubble" :class="m.role">
          <text class="msg-text">{{ m.text }}</text>
        </view>
      </view>
      <view v-if="thinking" class="msg-row assistant">
        <view class="bubble assistant">
          <text class="msg-text">🌙 正在查看你的星图……</text>
        </view>
      </view>
      <view v-if="feedbackNote" class="growth-note"><text>✦</text><text>{{ feedbackNote }}</text></view>

      <view v-if="!sentOnce && !thinking" class="quick-zone">
        <text class="quick-lead">不知道从哪开始，也可以：</text>
        <view class="quick-row">
          <button v-for="q in quickOptions" :key="q" class="quick-chip" @tap="sendQuick(q)">{{ q }}</button>
        </view>
      </view>
      <view id="bottom" />
    </scroll-view>

    <view class="composer">
      <input
        v-model="draft"
        class="composer-input"
        :placeholder="`和${spiritName}说说……`"
        confirm-type="send"
        @confirm="send"
      />
      <button class="composer-send" :disabled="thinking" @tap="send">↑</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import api, { ApiError } from "@/api/client";
import SpiritPortrait from "@/components/SpiritPortrait.vue";
import { useTimePhase } from "@/utils/timeTheme";

const PERSON_KEY = "gs_person_id";
const SESSION_KEY = "gs_session_id";

const spiritName = ref("星灵");
const draft = ref("");
const thinking = ref(false);
const scrollTo = ref("");
const trustLabel = ref("");
const sentOnce = ref(false);
const messages = ref<Array<{ role: "user" | "assistant"; text: string }>>([]);
const quickOptions = ["我最近有点累", "想问问工作的事", "随便聊聊"];
const persona = ref<string | undefined>();
const feedbackNote = ref("");
const spiritPlanet = ref("moon");
const { phaseClass, refreshPhase } = useTimePhase();

const todayStr = (() => {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `今天 ${p(d.getHours())}:${p(d.getMinutes())}`;
})();

// 信任等级中文名（A2 关系层，与后端 TrustLevel 对齐）
const TRUST_ZH: Record<string, string> = {
  stranger: "陌生",
  acquaintance: "认识",
  trusted: "信任",
  intimate: "深交",
};

const PLANET_ZH: Record<string, string> = {
  sun: "太阳星灵", moon: "月亮星灵", mercury: "水星星灵", venus: "金星星灵",
  mars: "火星星灵", jupiter: "木星星灵", saturn: "土星星灵", uranus: "天王星灵",
  neptune: "海王星灵", pluto: "冥王星灵",
};

onLoad(() => {
  refreshPhase();
  const pid = uni.getStorageSync(PERSON_KEY) as string;
  if (!pid) {
    uni.redirectTo({ url: "/pages/index/index" });
    return;
  }

  // 今日星灵（顶部身份与开场口吻与之对齐；失败安静回退默认人格）
  api
    .recommendedSpirits(pid)
    .then((rec) => {
      const top = rec.spirits?.[0];
      if (!top) return;
      persona.value = top.planet;
      spiritPlanet.value = top.planet.toLowerCase();
      spiritName.value = top.healing_name || top.name || PLANET_ZH[top.planet?.toLowerCase()] || "星灵";
      return api.opening(pid, persona.value);
    })
    .then((o) => {
      if (!o?.opening) return;
      messages.value = [{ role: "assistant", text: o.opening }];
      trustLabel.value = TRUST_ZH[o.trust_level] || "";
    })
    .catch(() => undefined)
    .finally(() => {
      if (!messages.value.length) {
        messages.value.push({ role: "assistant", text: "今天想聊点什么？事业、感情、还是最近的心情？" });
      }
    });
});

async function send() {
  const text = draft.value.trim();
  if (!text || thinking.value) return;
  draft.value = "";
  sentOnce.value = true;
  messages.value.push({ role: "user", text });
  thinking.value = true;
  scrollTo.value = "bottom";

  const pid = uni.getStorageSync(PERSON_KEY) as string;
  const session = (uni.getStorageSync(SESSION_KEY) as string) || undefined;
  try {
    const res = await api.chat({ person_id: pid, session_id: session, message: text, persona: persona.value });
    uni.setStorageSync(SESSION_KEY, res.session_id);
    messages.value.push({ role: "assistant", text: res.answer });
    const parts: string[] = [];
    if (res.lit_fragments?.length) parts.push(`点亮 ${res.lit_fragments.length} 个内在角落`);
    if (res.seen_fragments?.length) parts.push("星灵记住了你的确认");
    if (res.actioned_fragments?.length) parts.push("这次行动也被收进成长里");
    if (res.keepsake_created) parts.push("一封新的记忆来信已放进信箱");
    feedbackNote.value = parts.join(" · ");
    if (feedbackNote.value) setTimeout(() => { feedbackNote.value = ""; }, 5200);
  } catch (e: any) {
    if (e instanceof ApiError && e.status === 404) {
      // 用户档案过期/被清（如后端数据重建）→ 回建档页重新开始
      uni.removeStorageSync(PERSON_KEY);
      uni.removeStorageSync(SESSION_KEY);
      uni.reLaunch({ url: "/pages/index/index" });
      return;
    }
    messages.value.push({
      role: "assistant",
      text: e && e.message && e.message.includes("timeout")
        ? "星灵想得有点久，请再问一次。"
        : "花园暂时联系不上星灵，请稍后再试。（" + (e?.message || "网络错误") + "）",
    });
  } finally {
    thinking.value = false;
    scrollTo.value = "bottom";
  }
}

function sendQuick(q: string) {
  draft.value = q;
  void send();
}
</script>

<style scoped>
.page {
  height: 100vh;
  background: linear-gradient(180deg, #253a36 0%, #172824 68%, #14221f 100%);
  display: flex;
  flex-direction: column;
  position: relative;
}
.top-glow { position: absolute; width: 540rpx; height: 540rpx; border-radius: 50%; right: -160rpx; top: -140rpx; background: rgba(197, 183, 133, 0.13); filter: blur(70rpx); pointer-events: none; }
.header { display: flex; align-items: center; gap: 22rpx; padding: 34rpx 32rpx 26rpx; position: relative; z-index: 1; }
.spirit-orb { width: 96rpx; height: 96rpx; flex-shrink: 0; border-radius: 50%;
  background: radial-gradient(circle at 38% 34%, #fff 0 4%, transparent 5%), radial-gradient(circle at 62% 34%, #fff 0 4%, transparent 5%), radial-gradient(circle at 50% 48%, rgba(255, 255, 255, 0.8) 0 17%, transparent 18%), radial-gradient(circle at 50% 65%, rgba(224, 235, 222, 0.8) 0 28%, transparent 29%), linear-gradient(145deg, #e8ece0, #879f94);
  box-shadow: 0 0 0 2rpx rgba(255, 255, 255, 0.25), 0 16rpx 50rpx rgba(0, 0, 0, 0.25); overflow: hidden; }
.spirit-name { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 34rpx; font-weight: 600; color: #edf1e9; }
.spirit-status { display: block; margin-top: 6rpx; font-size: 21rpx; color: rgba(235, 241, 233, 0.4); }
.trust-tag { margin-left: auto; flex-shrink: 0; color: rgba(165, 214, 167, 0.9); font-size: 21rpx; background: rgba(124, 179, 66, 0.16); border: 1rpx solid rgba(165, 214, 167, 0.22); border-radius: 999rpx; padding: 8rpx 18rpx; }
.messages { flex: 1; padding: 12rpx 32rpx; box-sizing: border-box; position: relative; z-index: 1; }
.time-divider { text-align: center; font-size: 19rpx; color: rgba(235, 241, 233, 0.35); margin: 14rpx 0 30rpx; }
.msg-row { display: flex; margin-bottom: 26rpx; }
.msg-row.user { justify-content: flex-end; }
.bubble { max-width: 84%; border-radius: 40rpx 40rpx 40rpx 12rpx; padding: 28rpx 32rpx; }
.bubble.user { border-radius: 40rpx 40rpx 12rpx 40rpx; background: #637b6e; color: #f8f7ee; }
.bubble.assistant { background: rgba(255, 255, 255, 0.075); border: 1rpx solid rgba(255, 255, 255, 0.09); color: #edf1e9; }
.msg-text { font-family: Georgia, "Noto Serif SC", serif; font-size: 29rpx; line-height: 1.9; white-space: pre-wrap; word-break: break-word; }
.quick-zone { margin-top: 34rpx; padding-bottom: 10rpx; }
.quick-lead { display: block; font-size: 22rpx; color: rgba(235, 241, 233, 0.45); margin-bottom: 16rpx; }
.quick-row { display: flex; flex-wrap: wrap; gap: 16rpx; }
.quick-chip { border: 1rpx solid rgba(255, 255, 255, 0.14); background: rgba(255, 255, 255, 0.055); border-radius: 34rpx; padding: 16rpx 26rpx; font-size: 24rpx; color: rgba(255, 255, 255, 0.72); line-height: 1.4; margin: 0; }
.composer { display: flex; align-items: center; gap: 14rpx; padding: 22rpx 30rpx; padding-bottom: calc(22rpx + env(safe-area-inset-bottom)); position: relative; z-index: 1; }
.composer-input { flex: 1; min-height: 96rpx; background: rgba(255, 255, 255, 0.09); border: 1rpx solid rgba(255, 255, 255, 0.1); border-radius: 44rpx; padding: 0 36rpx; color: #edf1e9; font-size: 27rpx; }
.composer-send { width: 84rpx; height: 84rpx; flex-shrink: 0; border-radius: 30rpx; background: #b8c8b7; color: #253a36; font-size: 36rpx; font-weight: 700; display: flex; align-items: center; justify-content: center; padding: 0; margin: 0; line-height: 1; }
.composer-send[disabled] { opacity: 0.5; }
.growth-note { display: flex; align-items: center; justify-content: center; gap: 10rpx; margin: 6rpx 32rpx 12rpx; padding: 14rpx 18rpx; border: 1rpx solid rgba(240, 210, 139, 0.2); border-radius: 999rpx; background: rgba(240, 210, 139, 0.08); color: rgba(240, 210, 139, 0.82); font-size: 20rpx; }
</style>
