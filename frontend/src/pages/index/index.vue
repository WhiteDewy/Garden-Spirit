<template>
  <view class="page" :class="[phaseClass, stageClass]">
    <view class="bg-glow glow-a"></view>
    <view class="bg-glow glow-b"></view>
    <view class="grain"></view>
    <view class="stars"><text v-for="n in 5" :key="n" class="star-dot">✦</text></view>

    <view class="appbar" v-if="stage === 'garden'">
      <view>
        <text class="eyebrow">GARDEN SPIRIT</text>
        <text class="app-title">{{ appTitle }}</text>
      </view>
    </view>

    <view v-if="stage === 'welcome'" class="screen welcome-screen" @tap="onWelcomeTap">
      <view class="welcome-controls">
        <text class="prologue-mark">星灵花园 · 序章</text>
        <view class="control-actions">
          <button class="ghost-control sound-toggle" @tap.stop="toggleWelcomeSound">{{ soundEnabled ? '关闭星音' : '开启星音' }}</button>
        </view>
      </view>

      <view class="welcome-sky" :class="[`scene-${welcomeScene}`]" aria-hidden="true">
        <view class="void-layer"></view>
        <view class="milky-way"></view>
        <view class="chart-ghost">
          <text class="astro-glyph sun">☉</text>
          <text class="astro-glyph moon">☽</text>
          <text class="astro-glyph venus">♀</text>
          <text class="astro-glyph mars">♂</text>
          <text class="astro-glyph jupiter">♃</text>
          <text class="astro-glyph saturn">♄</text>
          <view class="aspect-line a1"></view><view class="aspect-line a2"></view><view class="aspect-line a3"></view>
        </view>
        <view class="falling-light"></view>
        <view class="shooting-star meteor-one"></view>
        <view class="shooting-star meteor-two"></view>
        <text v-for="n in 34" :key="`welcome-star-${n}`" :class="['sky-star', `sky-star-${n}`]">✦</text>
        <view class="constellation constellation-a">
          <view class="c-dot d1"></view><view class="c-dot d2"></view><view class="c-dot d3"></view><view class="c-dot d4"></view>
          <view class="c-line l1"></view><view class="c-line l2"></view><view class="c-line l3"></view>
        </view>
        <view class="constellation constellation-b">
          <view class="c-dot d1"></view><view class="c-dot d2"></view><view class="c-dot d3"></view><view class="c-dot d4"></view>
          <view class="c-line l1"></view><view class="c-line l2"></view><view class="c-line l3"></view>
        </view>
        <view class="question-whispers">
          <text>这段关系让我有点乱。</text>
          <text>这个选择我总是下不了决心。</text>
          <text>这个机会值得抓住吗？</text>
        </view>
      </view>

      <view class="welcome-hero">
        <view class="welcome-spirit-wrap appearing" :class="`scene-${welcomeScene}`">
          <view class="spirit-halo"></view>
          <view class="spirit-stage intro listening">
            <view class="aura"></view>
            <view class="nest"></view>
            <view class="spirit">
              <view class="spirit-hair"></view>
              <view class="spirit-robe"></view>
              <view class="antenna"></view>
              <view class="arm left"></view><view class="arm right"></view><view class="mouth"></view>
            </view>
          </view>
          <view class="sound-wave wave-a"></view>
          <view class="sound-wave wave-b"></view>
        </view>

        <view class="prologue-dialogue">
          <view class="welcome-lines typewriter-text">
            <view
              v-for="(line, index) in typedWelcomeLines"
              :key="`welcome-line-${index}`"
              :class="['spoken-line', line.tone, { active: line.active }]"
            >
              <text>{{ line.text }}</text><text v-if="line.active && !typingDone" class="typing-cursor">|</text>
            </view>
          </view>
        </view>
      </view>

      <view class="welcome-bottom" :class="{ ready: typingDone }">
        <text class="welcome-final">{{ typingDone ? '欢迎来到星灵花园。' : '点一下屏幕，听见星空。' }}</text>
        <button class="primary-btn welcome-cta" @tap.stop="continueAccountFlow">
          <text class="cta-star">✦</text>
          <text>遇见我的星灵</text>
        </button>
      </view>

      <view v-if="welcomeStarted && !typingDone" class="welcome-skip-fab" @tap.stop="skipWelcomeIntro">
        <text>跳过序章</text>
        <text class="skip-star">✦</text>
      </view>
    </view>

    <GardenHome
      v-else
      :spirit-name="spiritName"
      :spirit-planet="spiritPlanet"
      :spirit-line="spiritLine"
      :garden-state="gardenState"
      @chat="goChat"
      @explain="toggleSheet"
    />

    <view v-if="sheetOpen" class="sheet-mask" @tap="toggleSheet"></view>
    <view v-if="sheetOpen" class="bottom-sheet">
      <view class="sheet-handle"></view>
      <text class="sheet-eyebrow">WHY TODAY</text>
      <text class="sheet-title">为什么今天是 {{ spiritName }}？</text>
      <text class="sheet-copy">{{ sheetCopy }}</text>
      <view class="sheet-actions">
        <button class="sheet-primary" @tap="goChat">和它聊聊</button>
        <button class="sheet-secondary" @tap="toggleSheet">先收起来</button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { onLoad, onShow } from "@dcloudio/uni-app";
import api, { ApiError, describeError, type GardenState, type PersonaOut, type SpiritRecommendationOut } from "@/api/client";
import { clearAccountCache, resolveAccount } from "@/utils/account";
import { subscribePush } from "@/utils/push";
import { selectSpirit } from "@/utils/spiritSelection";
import { useGardenBadges } from "@/utils/gardenBadges";
import { useTimePhase } from "@/utils/timeTheme";
import GardenHome from "@/components/GardenHome.vue";

type HomeStage = "welcome" | "garden";

const error = ref("");
const stage = ref<HomeStage>("welcome");
const gardenState = ref<GardenState | null>(null);
const recommendedSpirit = ref<SpiritRecommendationOut | null>(null);
const spiritCatalog = ref<SpiritRecommendationOut[]>([]);
const personaCatalog = ref<PersonaOut[]>([]);
const preferredPersona = ref("");
const sheetOpen = ref(false);
const lastLoadedPersonId = ref("");
const backToSkyOnce = ref(false);
onLoad((query) => {
  // 建档页「回到星空」携带该标记：回首页序章时暂停一次「无本人档案→建档」漏斗
  if (query?.back === "sky") backToSkyOnce.value = true;
});

// Web Push：只主动请求一次权限（浏览器会记住结果，后续不再弹）
const PUSH_ASKED_KEY = "gs_push_asked";

type WelcomeLineTone = "hello" | "soft" | "focus" | "astro" | "example" | "quote" | "closing";
type WelcomeScene = "dark" | "galaxy" | "spirit" | "natal" | "garden" | "questions" | "closing";
type WelcomePace = "normal" | "slow" | "brand";

interface WelcomeLine {
  text: string;
  tone: WelcomeLineTone;
  scene: WelcomeScene;
  pace?: WelcomePace;
  pauseAfter?: number;
}

const WELCOME_LINES: WelcomeLine[] = [
  { text: "你好。", tone: "hello", scene: "spirit", pace: "slow", pauseAfter: 1500 },
  { text: "欢迎来到星灵花园。", tone: "closing", scene: "spirit", pace: "brand", pauseAfter: 1300 },
  { text: "你知道吗？", tone: "focus", scene: "galaxy", pace: "slow", pauseAfter: 1200 },
  { text: "在你出生的那一刻，", tone: "soft", scene: "galaxy", pauseAfter: 520 },
  { text: "星辰就已经为你留下了一张独一无二的星图。", tone: "soft", scene: "natal", pauseAfter: 1000 },
  { text: "你的月亮、太阳，", tone: "astro", scene: "natal", pauseAfter: 520 },
  { text: "还有每一颗行星，", tone: "astro", scene: "natal", pauseAfter: 520 },
  { text: "都在诉说着关于你的故事。", tone: "soft", scene: "natal", pauseAfter: 1200 },
  { text: "而我，会帮你读懂它。", tone: "focus", scene: "natal", pace: "slow", pauseAfter: 1300 },
  { text: "从你的本命星图，", tone: "astro", scene: "natal", pauseAfter: 520 },
  { text: "到此刻正在发生的行运。", tone: "astro", scene: "natal", pauseAfter: 520 },
  { text: "从宫位、相位，", tone: "astro", scene: "natal", pauseAfter: 520 },
  { text: "到那些微妙的关系与变化。", tone: "astro", scene: "natal", pauseAfter: 520 },
  { text: "我会一点一点，帮你找到正在发生的线索。", tone: "focus", scene: "natal", pace: "slow", pauseAfter: 1500 },
  { text: "而这些星辰，", tone: "soft", scene: "garden", pauseAfter: 620 },
  { text: "也会来到你的花园。", tone: "soft", scene: "garden", pauseAfter: 900 },
  { text: "在那里，", tone: "soft", scene: "garden", pauseAfter: 650 },
  { text: "会有属于你的星灵。", tone: "focus", scene: "garden", pace: "slow", pauseAfter: 1300 },
  { text: "你可以把一个关系里的困惑说给它听。", tone: "example", scene: "questions", pauseAfter: 520 },
  { text: "我和他还有可能吗？", tone: "quote", scene: "questions", pace: "slow", pauseAfter: 800 },
  { text: "把心里绕很久的选择交给它看。", tone: "example", scene: "questions", pauseAfter: 520 },
  { text: "我现在该不该换工作？", tone: "quote", scene: "questions", pace: "slow", pauseAfter: 800 },
  { text: "问它选择。", tone: "example", scene: "questions", pauseAfter: 520 },
  { text: "这个机会值得抓住吗？", tone: "quote", scene: "questions", pace: "slow", pauseAfter: 1100 },
  { text: "当然，", tone: "soft", scene: "questions", pauseAfter: 780 },
  { text: "你也可以什么都不问。", tone: "soft", scene: "questions", pauseAfter: 900 },
  { text: "只是告诉它……", tone: "soft", scene: "questions", pace: "slow", pauseAfter: 760 },
  { text: "我今天有一点迷茫。", tone: "quote", scene: "questions", pace: "brand", pauseAfter: 1500 },
  { text: "我会看见你的星图。", tone: "closing", scene: "closing", pace: "slow", pauseAfter: 1100 },
  { text: "也会听见你的声音。", tone: "closing", scene: "closing", pace: "slow", pauseAfter: 1300 },
  { text: "欢迎来到星灵花园。", tone: "closing", scene: "closing", pace: "brand", pauseAfter: 800 },
];
const WELCOME_FULL_TEXT = WELCOME_LINES.map((line) => line.text).join("\n");
const WELCOME_VOICE_SRC = "/static/audio/welcome_spirit.mp3"; // 配音资产缺位时自动回落到 WebAudio 星音
const typedWelcomeCount = ref(0);
const soundEnabled = ref(false);
const welcomeStarted = ref(false);
const welcomePreShow = ref(false);
const typingDone = computed(() => typedWelcomeCount.value >= WELCOME_FULL_TEXT.length);
const welcomeScene = computed<WelcomeScene>(() => {
  if (!welcomeStarted.value && typedWelcomeCount.value === 0) return "dark";
  if (welcomePreShow.value && typedWelcomeCount.value === 0) return "spirit";
  if (typingDone.value) return "closing";
  return WELCOME_LINES[welcomeLineIndex(typedWelcomeCount.value)]?.scene || "dark";
});
const typedWelcomeLines = computed(() => {
  if (!welcomeStarted.value && typedWelcomeCount.value === 0) return [];
  let remaining = typedWelcomeCount.value;
  const activeIndex = typingDone.value ? WELCOME_LINES.length - 1 : welcomeLineIndex(typedWelcomeCount.value);
  const visibleStart = Math.max(0, activeIndex - 4);
  return WELCOME_LINES.map((line, index) => {
    const count = Math.max(0, Math.min(line.text.length, remaining));
    remaining -= line.text.length + 1;
    return {
      text: line.text.slice(0, count),
      tone: line.tone,
      active: index === activeIndex && count < line.text.length && !typingDone.value,
      index,
    };
  }).filter((line) => line.index >= visibleStart && (line.text || line.active));
});
let welcomeTypingTimer: ReturnType<typeof setTimeout> | null = null;
let welcomeAudio: any = null;
let welcomeVoice: HTMLAudioElement | null = null;
let welcomeVoiceUnavailable = false;
let welcomeAmbient: { oscillator: any; gain: any } | null = null;
let lastWelcomeLineIndex = -1;

function welcomeLineIndex(count: number) {
  let cursor = 0;
  for (let index = 0; index < WELCOME_LINES.length; index += 1) {
    const lineLength = WELCOME_LINES[index].text.length;
    if (count <= cursor + lineLength) return index;
    cursor += lineLength + 1;
  }
  return WELCOME_LINES.length - 1;
}

function welcomeCharDelay(line: WelcomeLine, current: string) {
  if (current === "\n") return line.pauseAfter ?? 720;
  if (/[。！？]/.test(current)) return line.pace === "brand" ? 220 : line.pace === "slow" ? 170 : 120;
  if (/，|、|：|…/.test(current)) return line.pace === "brand" ? 190 : line.pace === "slow" ? 135 : 92;
  if (line.pace === "brand") return 178;
  if (line.pace === "slow") return 126;
  return 76;
}

function stopWelcomeTyping() {
  if (welcomeTypingTimer) clearTimeout(welcomeTypingTimer);
  welcomeTypingTimer = null;
}

function scheduleWelcomeTyping() {
  stopWelcomeTyping();
  if (!welcomeStarted.value || typingDone.value) return;
  const current = WELCOME_FULL_TEXT[typedWelcomeCount.value] || "";
  const line = WELCOME_LINES[welcomeLineIndex(typedWelcomeCount.value)] || WELCOME_LINES[0];
  const delay = welcomeCharDelay(line, current);
  welcomeTypingTimer = setTimeout(() => {
    typedWelcomeCount.value += 1;
    const nextLineIndex = welcomeLineIndex(typedWelcomeCount.value);
    if (nextLineIndex !== lastWelcomeLineIndex) {
      lastWelcomeLineIndex = nextLineIndex;
      playWelcomeCue(WELCOME_LINES[nextLineIndex]?.scene || "dark");
    }
    if (current && current !== "\n") playWelcomeTick(current, line.tone === "quote" ? 0.018 : 0.024);
    scheduleWelcomeTyping();
  }, delay);
}

function resetWelcomeIntro() {
  stopWelcomeTyping();
  typedWelcomeCount.value = 0;
  welcomeStarted.value = false;
  welcomePreShow.value = false;
  lastWelcomeLineIndex = -1;
}

function startWelcomePrologue() {
  if (welcomeStarted.value) return;
  welcomeStarted.value = true;
  welcomePreShow.value = true;
  typedWelcomeCount.value = 0;
  lastWelcomeLineIndex = -1;
  void enableWelcomeSound();
  playWelcomeCue("galaxy");
  welcomeTypingTimer = setTimeout(() => {
    welcomePreShow.value = false;
    playWelcomeCue("spirit");
    scheduleWelcomeTyping();
  }, 360);
}

function skipWelcomeIntro() {
  welcomeStarted.value = true;
  welcomePreShow.value = false;
  stopWelcomeTyping();
  stopWelcomeVoice();
  typedWelcomeCount.value = WELCOME_FULL_TEXT.length;
  playWelcomeCue("closing");
}

function onWelcomeTap() {
  if (!welcomeStarted.value) {
    startWelcomePrologue();
    return;
  }
  if (!soundEnabled.value) void enableWelcomeSound();
}

async function continueAccountFlow() {
  try {
    const account = await resolveAccount();
    if (!account) {
      uni.redirectTo({ url: "/pages/auth/login" });
      return;
    }
    const pid = account.self_person_id || account.self_profile?.id || "";
    if (!pid) {
      uni.redirectTo({ url: "/pages/onboarding/onboarding" });
      return;
    }
    await loadExistingGarden(pid);
    maybeSubscribePush(pid);
  } catch (e) {
    error.value = describeError(e);
    uni.redirectTo({ url: "/pages/auth/login" });
  }
}

async function toggleWelcomeSound() {
  if (soundEnabled.value) {
    soundEnabled.value = false;
    stopWelcomeVoice();
    stopWelcomeAmbient();
    return;
  }
  await enableWelcomeSound();
}

async function enableWelcomeSound() {
  try {
    const hasVoice = await startWelcomeVoice();
    soundEnabled.value = true;
    if (hasVoice) return;

    const AudioCtor = typeof window !== "undefined" ? ((window as any).AudioContext || (window as any).webkitAudioContext) : null;
    if (!AudioCtor) return;
    if (!welcomeAudio) welcomeAudio = new AudioCtor();
    if (welcomeAudio.state === "suspended") await welcomeAudio.resume();
    startWelcomeAmbient();
    playWelcomeCue("spirit");
  } catch {
    soundEnabled.value = false;
  }
}

async function startWelcomeVoice() {
  if (typeof Audio === "undefined" || welcomeVoiceUnavailable) return false;
  try {
    if (!welcomeVoice) {
      welcomeVoice = new Audio(WELCOME_VOICE_SRC);
      welcomeVoice.preload = "auto";
      welcomeVoice.volume = 0.86;
      welcomeVoice.addEventListener("error", () => {
        welcomeVoiceUnavailable = true;
        welcomeVoice = null;
      }, { once: true });
    }
    welcomeVoice.currentTime = 0;
    await welcomeVoice.play();
    stopWelcomeAmbient();
    return true;
  } catch {
    welcomeVoiceUnavailable = true;
    welcomeVoice = null;
    return false;
  }
}

function stopWelcomeVoice() {
  if (!welcomeVoice) return;
  try {
    welcomeVoice.pause();
    welcomeVoice.currentTime = 0;
  } catch {
    // 语音是增强体验，停止失败不影响主流程。
  }
}

function startWelcomeAmbient() {
  if (!soundEnabled.value || !welcomeAudio || welcomeAmbient) return;
  try {
    const oscillator = welcomeAudio.createOscillator();
    const gain = welcomeAudio.createGain();
    const now = welcomeAudio.currentTime;
    oscillator.type = "sine";
    oscillator.frequency.setValueAtTime(92, now);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.linearRampToValueAtTime(0.018, now + 2.8);
    oscillator.connect(gain);
    gain.connect(welcomeAudio.destination);
    oscillator.start(now);
    welcomeAmbient = { oscillator, gain };
  } catch {
    welcomeAmbient = null;
  }
}

function stopWelcomeAmbient() {
  if (!welcomeAmbient || !welcomeAudio) return;
  try {
    const now = welcomeAudio.currentTime;
    welcomeAmbient.gain.gain.linearRampToValueAtTime(0.0001, now + 0.8);
    welcomeAmbient.oscillator.stop(now + 0.9);
  } catch {
    // 静音降级，不影响主流程。
  }
  welcomeAmbient = null;
}

function playWelcomeCue(scene: WelcomeScene) {
  if (!soundEnabled.value || !welcomeAudio) return;
  const cue: Record<WelcomeScene, { frequency: number; volume: number; length: number }> = {
    dark: { frequency: 340, volume: 0.018, length: 0.12 },
    galaxy: { frequency: 520, volume: 0.028, length: 0.22 },
    spirit: { frequency: 880, volume: 0.052, length: 0.36 },
    natal: { frequency: 660, volume: 0.032, length: 0.24 },
    garden: { frequency: 740, volume: 0.038, length: 0.28 },
    questions: { frequency: 610, volume: 0.024, length: 0.18 },
    closing: { frequency: 960, volume: 0.042, length: 0.42 },
  };
  playWelcomeTone(cue[scene].frequency, cue[scene].volume, cue[scene].length);
}

function playWelcomeTone(frequency: number, volume: number, length: number) {
  if (!soundEnabled.value || !welcomeAudio) return;
  try {
    const oscillator = welcomeAudio.createOscillator();
    const gain = welcomeAudio.createGain();
    const now = welcomeAudio.currentTime;
    oscillator.type = "sine";
    oscillator.frequency.setValueAtTime(frequency, now);
    oscillator.frequency.exponentialRampToValueAtTime(frequency * 1.5, now + length);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(volume, now + 0.018);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + length);
    oscillator.connect(gain);
    gain.connect(welcomeAudio.destination);
    oscillator.start(now);
    oscillator.stop(now + length + 0.03);
  } catch {
    // 音效是增强体验，失败时保持安静不打断欢迎动画。
  }
}

function playWelcomeTick(char: string, volume = 0.024) {
  if (!soundEnabled.value || !welcomeAudio) return;
  const pitchSeed = char.charCodeAt(0) % 7;
  playWelcomeTone(720 + pitchSeed * 38, volume, 0.11);
}

onMounted(() => {
  if (stage.value === "welcome") resetWelcomeIntro();
});

onUnmounted(() => {
  stopWelcomeTyping();
  stopWelcomeVoice();
  stopWelcomeAmbient();
  if (welcomeAudio?.close) welcomeAudio.close();
});

watch(stage, async (value) => {
  if (value !== "welcome") {
    stopWelcomeTyping();
    stopWelcomeVoice();
    stopWelcomeAmbient();
    return;
  }
  await nextTick();
  resetWelcomeIntro();
});


// 信任等级（A2 关系层）中文标签
const TRUST_ZH: Record<string, string> = {
  stranger: "初遇 · 陌生",
  acquaintance: "相识 · 认识",
  trusted: "信任 · 知心",
  intimate: "深交 · 知己",
};
function trustZh(level: string) {
  return TRUST_ZH[level] || level;
}

const MOON_HOME_SPIRIT = {
  planet: "moon",
  name: "月亮星灵",
  line: "我会看见你的星图，也会听见你的声音。",
};

const homeSelection = computed(() => selectSpirit({
  preferredPersona: preferredPersona.value,
  recommendations: spiritCatalog.value,
  personas: personaCatalog.value,
}));
const homePersona = computed(() => MOON_HOME_SPIRIT.planet);
const spiritName = computed(() => MOON_HOME_SPIRIT.name);
const spiritPlanet = computed(() => MOON_HOME_SPIRIT.planet);
const spiritLine = computed(() => MOON_HOME_SPIRIT.line);
const sheetCopy = computed(() => {
  const reason = homeSelection.value.todayRecommendation?.reason || "今日暂无明显行运触动，花园先让月亮星灵陪你听见自己。";
  return `今日推荐星灵先收在后面。现在，月亮星灵会作为入口陪你展开花园。\n\n${reason}`;
});
const { refreshGardenBadges } = useGardenBadges();
const { phaseClass: livePhaseClass, refreshPhase } = useTimePhase();
// 注册与绘制星图固定使用夜空主题，与欢迎页深空序章保持同一章视觉
const phaseClass = computed(() => livePhaseClass.value);
const stageClass = computed(() => `stage-${stage.value}`);
const appTitle = computed(() => stage.value === "welcome" ? "星灵花园" : "花园");

onShow(async () => {
  refreshPhase();
  let pid = "";
  try {
    const account = await resolveAccount();
    if (!account) {
      // 首次访问必须先停在深空序章；点「遇见我的星灵」后再进入登录 / 注册。
      if (stage.value !== "welcome") stage.value = "welcome";
      return;
    }
    pid = account.self_person_id || account.self_profile?.id || "";
    if (!pid) {
      // 建档页「回到星空」只暂停一次自动建档，停回序章；其余场景照常漏斗建档
      if (backToSkyOnce.value) {
        backToSkyOnce.value = false;
        if (stage.value !== "welcome") stage.value = "welcome";
        return;
      }
      uni.redirectTo({ url: "/pages/onboarding/onboarding" });
      return;
    }
  } catch (e) {
    error.value = describeError(e);
    if (stage.value !== "welcome") stage.value = "welcome";
    return;
  }
  if (stage.value === "garden" && lastLoadedPersonId.value === pid) return;
  await loadExistingGarden(pid);
  maybeSubscribePush(pid);
});

async function loadExistingGarden(pid: string) {
  error.value = "";
  try {
    await api.getPerson(pid);
    lastLoadedPersonId.value = pid;
    await Promise.all([loadPreferredPersona(pid), loadRecommendation(pid), loadPersonas()]);
    await loadGarden(pid, homePersona.value);
  } catch (e) {
    // 只有「档案确实不存在(404)/不可解密(410)」才登出回欢迎页；
    // 网络抖动/后端重启不能清登录态踢人——保留状态，进花园兜底页等恢复
    const gone = e instanceof ApiError && (e.status === 404 || e.status === 410);
    if (gone) {
      clearAccountCache();
      uni.redirectTo({ url: "/pages/auth/login" });
      return;
    } else if (stage.value !== "garden") {
      stage.value = "garden";
    }
    error.value = describeError(e);
    uni.showToast({ title: describeError(e), icon: "none", duration: 2200 });
  }
}

async function loadPreferredPersona(pid: string) {
  try {
    const prefs = await api.getPreferences(pid);
    preferredPersona.value = String(prefs?.preferred_persona || "").toLowerCase();
  } catch {
    preferredPersona.value = "";
  }
}

async function loadRecommendation(pid: string) {
  try {
    const rec = await api.recommendedSpirits(pid);
    spiritCatalog.value = rec.spirits || [];
    recommendedSpirit.value = spiritCatalog.value[0] || null;
  } catch {
    spiritCatalog.value = [];
    recommendedSpirit.value = null;
  }
}

async function loadPersonas() {
  try {
    personaCatalog.value = await api.personas();
  } catch {
    personaCatalog.value = [];
  }
}

async function loadGarden(pid: string, persona?: string) {
  try {
    gardenState.value = await api.garden(pid, persona);
    void refreshGardenBadges(pid, persona);
  } catch (e) {
    gardenState.value = null;
    error.value = describeError(e);
  }
  stage.value = "garden";
}

// Web Push：延迟触发订阅（推送是增强能力，失败安静返回，绝不打断主页流程）。
// 只主动请求一次权限；granted → 直接订阅，denied/default → 不再打扰。
function maybeSubscribePush(pid: string) {
  if (uni.getStorageSync(PUSH_ASKED_KEY)) return;
  setTimeout(async () => {
    const ok = await subscribePush(pid);
    if (ok || (typeof Notification !== "undefined" && Notification.permission !== "default")) {
      uni.setStorageSync(PUSH_ASKED_KEY, true);
    }
  }, 1500);
}

function toggleSheet() {
  sheetOpen.value = !sheetOpen.value;
}
function goChat(message?: string) {
  sheetOpen.value = false;
  const query = message ? `?message=${encodeURIComponent(message)}` : "";
  uni.navigateTo({ url: `/pages/chat/chat${query}` });
}
</script>

<style scoped>
.page {
  position: relative;
  min-height: 100vh;
  overflow-x: hidden;
  color: #16211d;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
  background: radial-gradient(circle at 18% 10%, rgba(255, 255, 255, 0.98), transparent 32%), linear-gradient(160deg, #eef4f2 0%, #f7f3e8 58%, #e1eadf 100%);
  padding: 56rpx 36rpx 140rpx;
  box-sizing: border-box;
}
.stage-welcome {
  min-height: 100vh;
  padding: 30rpx 28rpx 44rpx;
  color: #f8f1de;
  background:
    radial-gradient(circle at 52% 24%, rgba(119, 105, 189, 0.16), transparent 30%),
    radial-gradient(circle at 82% 66%, rgba(59, 121, 143, 0.11), transparent 34%),
    linear-gradient(180deg, #02040d 0%, #060817 42%, #0a0e1d 70%, #04070d 100%);
}
.phase-noon { background: radial-gradient(circle at 26% 10%, rgba(255, 255, 255, 0.98), transparent 34%), linear-gradient(160deg, #f4f6ee 0%, #edf3ec 62%, #dce8dd 100%); }
.phase-dusk { background: radial-gradient(circle at 20% 12%, rgba(255, 255, 255, 0.76), transparent 31%), linear-gradient(160deg, #efe5d7 0%, #f3efe7 50%, #dfe8df 100%); }
.phase-night { background: radial-gradient(circle at 20% 10%, rgba(101, 89, 137, 0.34), transparent 34%), linear-gradient(160deg, #14192f 0%, #222946 54%, #162520 100%); color: #fff8eb; }
.stage-welcome.phase-dusk, .stage-welcome.phase-noon, .stage-welcome.phase-night {
  color: #f8f1de;
  background:
    radial-gradient(circle at 52% 24%, rgba(119, 105, 189, 0.16), transparent 30%),
    radial-gradient(circle at 82% 66%, rgba(59, 121, 143, 0.11), transparent 34%),
    linear-gradient(180deg, #02040d 0%, #060817 42%, #0a0e1d 70%, #04070d 100%);
}
.bg-glow { position: absolute; border-radius: 999rpx; filter: blur(18rpx); opacity: 0.46; pointer-events: none; }
.glow-a { width: 460rpx; height: 460rpx; left: -190rpx; top: 80rpx; background: rgba(255, 255, 255, 0.72); }
.glow-b { width: 420rpx; height: 420rpx; right: -190rpx; top: 440rpx; background: rgba(192, 207, 201, 0.42); }
.stage-welcome .glow-a { width: 620rpx; height: 620rpx; left: 50%; top: -260rpx; transform: translateX(-50%); background: rgba(214, 187, 255, 0.22); filter: blur(34rpx); }
.stage-welcome .glow-b { width: 520rpx; height: 520rpx; right: -220rpx; top: 48%; background: rgba(89, 177, 191, 0.18); filter: blur(42rpx); }
.grain { position: absolute; inset: 0; opacity: 0.025; pointer-events: none; background-image: radial-gradient(rgba(23, 37, 31, 0.28) 1rpx, transparent 1rpx); background-size: 22rpx 22rpx; }
.stage-welcome .grain { opacity: 0.055; background-image: radial-gradient(rgba(255, 248, 235, 0.38) 1rpx, transparent 1rpx); background-size: 18rpx 18rpx; }
.stars { position: absolute; inset: 0; pointer-events: none; }
.stage-welcome > .stars { display: none; }
.star-dot { position: absolute; color: rgba(139, 158, 150, 0.44); font-size: 14rpx; animation: twinkle 4s ease-in-out infinite; }
.star-dot:nth-child(1) { left: 20%; top: 18%; }
.star-dot:nth-child(2) { left: 78%; top: 24%; animation-delay: 1.2s; }
.star-dot:nth-child(3) { left: 58%; top: 70%; animation-delay: 2s; }
.star-dot:nth-child(4) { left: 14%; top: 62%; animation-delay: 2.8s; }
.star-dot:nth-child(5) { left: 84%; top: 76%; animation-delay: 3.4s; }
@keyframes twinkle { 50% { opacity: 0.25; transform: scale(0.72); } }
.appbar { position: relative; z-index: 3; display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 36rpx; }
.eyebrow { display: block; font-size: 20rpx; letter-spacing: 0.18em; color: rgba(23, 37, 31, 0.38); font-weight: 800; }
.phase-night .eyebrow { color: rgba(255, 248, 235, 0.46); }
.app-title { display: block; margin-top: 8rpx; font-size: 42rpx; font-weight: 750; letter-spacing: -0.03em; }
.screen { position: relative; z-index: 2; }
.welcome-screen { min-height: calc(100vh - 74rpx); display: flex; flex-direction: column; align-items: center; justify-content: space-between; gap: 22rpx; overflow: hidden; }
.welcome-controls { width: 100%; max-width: 720rpx; display: flex; align-items: center; justify-content: space-between; gap: 18rpx; z-index: 3; opacity: 0.72; }
.prologue-mark { font-size: 20rpx; color: rgba(255, 248, 225, 0.42); letter-spacing: 0.18em; font-weight: 700; }
.control-actions { display: flex; align-items: center; gap: 12rpx; }
.ghost-control { min-width: 96rpx; min-height: 52rpx; padding: 0 18rpx; border: 1rpx solid rgba(255, 242, 200, 0.16); border-radius: 999rpx; background: rgba(255, 248, 224, 0.045); color: rgba(255, 248, 224, 0.54); font-size: 20rpx; line-height: 52rpx; box-shadow: none; }
.ghost-control::after { display: none; }
.skip-control { min-width: 74rpx; color: rgba(255, 248, 224, 0.42); }
.welcome-sky { position: absolute; inset: -30rpx -28rpx -44rpx; z-index: -1; pointer-events: none; overflow: hidden; }
.void-layer { position: absolute; inset: 0; background: radial-gradient(circle at 50% 42%, transparent 0%, rgba(0, 0, 0, 0.24) 44%, rgba(0, 0, 0, 0.62) 100%); opacity: 0.9; }
.milky-way { position: absolute; left: -30%; top: 14%; width: 162%; height: 46%; transform: rotate(-22deg) translate3d(-80rpx, 42rpx, 0); opacity: 0.08; filter: blur(0.6rpx); background: radial-gradient(ellipse at 50% 50%, rgba(255, 249, 220, 0.28) 0%, rgba(177, 167, 236, 0.17) 30%, rgba(76, 146, 180, 0.08) 50%, transparent 74%); animation: galaxyDrift 19s ease-in-out infinite; transition: opacity 1.8s ease, transform 1.8s ease; }
.scene-galaxy .milky-way, .scene-spirit .milky-way, .scene-natal .milky-way, .scene-garden .milky-way, .scene-questions .milky-way, .scene-closing .milky-way { opacity: 0.72; transform: rotate(-18deg) translate3d(0, 0, 0); }
.scene-closing .milky-way { opacity: 0.86; }
.milky-way::after { content: ''; position: absolute; inset: 18% 8%; border-radius: 50%; background-image: radial-gradient(rgba(255, 249, 220, 0.72) 1rpx, transparent 1rpx), radial-gradient(rgba(185, 206, 255, 0.38) 1rpx, transparent 1rpx); background-size: 42rpx 34rpx, 63rpx 51rpx; opacity: 0.5; }
.sky-star { position: absolute; color: rgba(255, 248, 220, 0.82); font-size: 11rpx; text-shadow: 0 0 14rpx rgba(246, 223, 156, 0.8); animation: welcomeTwinkle 3.8s ease-in-out infinite; }
/* 星点大小做层级：均匀同尺寸会显得假，按 nth 分三档 + 少数亮星（保持克制，星是背景不是主角） */
.sky-star:nth-child(2n) { font-size: 8rpx; opacity: 0.72; text-shadow: 0 0 8rpx rgba(246, 223, 156, 0.5); }
.sky-star:nth-child(3n) { font-size: 13rpx; }
.sky-star:nth-child(7n) { font-size: 15rpx; text-shadow: 0 0 22rpx rgba(246, 223, 156, 0.9); animation-duration: 4.6s; }
.sky-star-1 { left: 8%; top: 9%; } .sky-star-2 { left: 18%; top: 19%; animation-delay: .4s; } .sky-star-3 { left: 31%; top: 8%; animation-delay: .9s; } .sky-star-4 { left: 43%; top: 16%; animation-delay: 1.4s; } .sky-star-5 { left: 63%; top: 8%; animation-delay: .7s; } .sky-star-6 { left: 82%; top: 15%; animation-delay: 1.8s; }
.sky-star-7 { left: 91%; top: 29%; animation-delay: 1.1s; } .sky-star-8 { left: 12%; top: 34%; animation-delay: 2.2s; } .sky-star-9 { left: 26%; top: 42%; animation-delay: 1.6s; } .sky-star-10 { left: 73%; top: 38%; animation-delay: .3s; } .sky-star-11 { left: 86%; top: 52%; animation-delay: 2.8s; } .sky-star-12 { left: 9%; top: 59%; animation-delay: 1.9s; }
.sky-star-13 { left: 20%; top: 72%; animation-delay: .8s; } .sky-star-14 { left: 37%; top: 66%; animation-delay: 2.4s; } .sky-star-15 { left: 58%; top: 72%; animation-delay: 1.2s; } .sky-star-16 { left: 79%; top: 78%; animation-delay: 2.9s; } .sky-star-17 { left: 50%; top: 28%; animation-delay: .2s; } .sky-star-18 { left: 68%; top: 24%; animation-delay: 2.5s; }
.sky-star-19 { left: 4%; top: 82%; animation-delay: 1.5s; } .sky-star-20 { left: 94%; top: 84%; animation-delay: .5s; } .sky-star-21 { left: 34%; top: 88%; animation-delay: 3.1s; } .sky-star-22 { left: 66%; top: 91%; animation-delay: 1.7s; } .sky-star-23 { left: 16%; top: 47%; animation-delay: 3.4s; } .sky-star-24 { left: 54%; top: 52%; animation-delay: .6s; }
.sky-star-25 { left: 45%; top: 5%; animation-delay: 2.1s; } .sky-star-26 { left: 97%; top: 7%; animation-delay: 2.7s; } .sky-star-27 { left: 2%; top: 22%; animation-delay: 3s; } .sky-star-28 { left: 40%; top: 35%; animation-delay: 1.3s; } .sky-star-29 { left: 61%; top: 43%; animation-delay: 2.6s; } .sky-star-30 { left: 30%; top: 56%; animation-delay: .1s; }
.sky-star-31 { left: 48%; top: 82%; animation-delay: 3.2s; } .sky-star-32 { left: 72%; top: 62%; animation-delay: 1s; } .sky-star-33 { left: 90%; top: 68%; animation-delay: 2s; } .sky-star-34 { left: 6%; top: 72%; animation-delay: .75s; }
.shooting-star { position: absolute; width: 190rpx; height: 2rpx; border-radius: 999rpx; background: linear-gradient(90deg, transparent, rgba(255, 250, 225, 0.96), transparent); transform: rotate(-24deg); opacity: 0; filter: drop-shadow(0 0 16rpx rgba(255, 232, 166, 0.75)); animation: meteor 7s linear infinite; }
.meteor-one { left: 72%; top: 18%; }
.meteor-two { left: 45%; top: 8%; animation-delay: 3.9s; animation-duration: 9s; }
.constellation { position: absolute; opacity: 0.08; filter: drop-shadow(0 0 12rpx rgba(190, 216, 255, 0.46)); transition: opacity 1.5s ease, transform 1.5s ease; }
.scene-galaxy .constellation, .scene-spirit .constellation, .scene-natal .constellation, .scene-garden .constellation, .scene-questions .constellation, .scene-closing .constellation { opacity: 0.48; }
.constellation-a { width: 210rpx; height: 170rpx; left: 9%; top: 15%; }
.constellation-b { width: 230rpx; height: 190rpx; right: 7%; top: 29%; transform: rotate(18deg); opacity: 0.06; }
.scene-galaxy .constellation-b, .scene-spirit .constellation-b, .scene-natal .constellation-b, .scene-garden .constellation-b, .scene-questions .constellation-b, .scene-closing .constellation-b { opacity: 0.34; }
.chart-ghost { position: absolute; left: 50%; top: 30%; width: 470rpx; height: 470rpx; margin-left: -235rpx; border-radius: 50%; opacity: 0; transform: scale(0.86); transition: opacity 1.1s ease, transform 1.1s ease; }
.scene-natal .chart-ghost, .scene-garden .chart-ghost, .scene-questions .chart-ghost, .scene-closing .chart-ghost { opacity: 0.62; transform: scale(1); }
.chart-ghost::before, .chart-ghost::after { content: ''; position: absolute; inset: 44rpx; border-radius: 50%; border: 1rpx solid rgba(255, 241, 192, 0.13); }
.chart-ghost::after { inset: 118rpx; border-style: dashed; opacity: 0.74; animation: spin 38s linear infinite; }
.astro-glyph { position: absolute; color: rgba(255, 237, 177, 0.68); font-size: 30rpx; text-shadow: 0 0 22rpx rgba(244, 214, 137, 0.28); }
.astro-glyph.sun { left: 50%; top: 4%; } .astro-glyph.moon { right: 7%; top: 27%; } .astro-glyph.venus { right: 18%; bottom: 13%; }
.astro-glyph.mars { left: 17%; bottom: 12%; } .astro-glyph.jupiter { left: 5%; top: 31%; } .astro-glyph.saturn { left: 46%; bottom: 0; }
.aspect-line { position: absolute; left: 50%; top: 50%; height: 1rpx; width: 260rpx; transform-origin: left center; background: linear-gradient(90deg, rgba(255, 239, 188, 0.28), transparent); }
.aspect-line.a1 { transform: rotate(28deg); } .aspect-line.a2 { transform: rotate(142deg); } .aspect-line.a3 { transform: rotate(252deg); }
.falling-light { position: absolute; left: 58%; top: 14%; width: 3rpx; height: 250rpx; border-radius: 999rpx; opacity: 0; background: linear-gradient(180deg, rgba(255, 250, 221, 0.96), rgba(239, 204, 122, 0.25), transparent); filter: drop-shadow(0 0 24rpx rgba(255, 229, 151, 0.7)); transform: translate3d(48rpx, -80rpx, 0) rotate(17deg); }
.scene-garden .falling-light { animation: fallingLight 3.2s ease-out infinite; }
.question-whispers { position: absolute; inset: 20% 8% auto; min-height: 420rpx; opacity: 0; pointer-events: none; }
.scene-questions .question-whispers { opacity: 1; }
.question-whispers text { position: absolute; max-width: 360rpx; padding: 16rpx 22rpx; border: 1rpx solid rgba(255, 242, 205, 0.13); border-radius: 999rpx; color: rgba(255, 248, 224, 0.36); background: rgba(255, 248, 224, 0.035); font-size: 22rpx; animation: whisperFloat 7.2s ease-in-out infinite; }
.question-whispers text:nth-child(1) { left: 4%; top: 16%; animation-delay: 0s; }
.question-whispers text:nth-child(2) { right: 0; top: 46%; animation-delay: 1.6s; }
.question-whispers text:nth-child(3) { left: 20%; top: 76%; animation-delay: 3.1s; }
.c-dot { position: absolute; width: 8rpx; height: 8rpx; border-radius: 50%; background: #fbf4ce; box-shadow: 0 0 18rpx rgba(251, 244, 206, 0.9); }
.c-line { position: absolute; height: 1rpx; background: linear-gradient(90deg, rgba(251, 244, 206, 0.16), rgba(251, 244, 206, 0.56), rgba(251, 244, 206, 0.1)); transform-origin: left center; }
.constellation .d1 { left: 10rpx; top: 28rpx; } .constellation .d2 { left: 72rpx; top: 62rpx; } .constellation .d3 { left: 138rpx; top: 34rpx; } .constellation .d4 { left: 188rpx; top: 128rpx; }
.constellation .l1 { left: 15rpx; top: 35rpx; width: 70rpx; transform: rotate(28deg); } .constellation .l2 { left: 78rpx; top: 65rpx; width: 74rpx; transform: rotate(-22deg); } .constellation .l3 { left: 143rpx; top: 41rpx; width: 104rpx; transform: rotate(62deg); }
.welcome-orbit, .orbit-ring { display: none; }
.welcome-hero { flex: 1; width: 100%; max-width: 700rpx; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 20rpx; padding-top: 0; box-sizing: border-box; }
.welcome-spirit-wrap { position: relative; width: 336rpx; height: 318rpx; display: flex; align-items: center; justify-content: center; opacity: 0; transform: translateY(34rpx) scale(0.72); filter: blur(18rpx); transition: opacity 1.4s ease, transform 1.4s ease, filter 1.4s ease; }
.welcome-spirit-wrap.scene-spirit, .welcome-spirit-wrap.scene-natal, .welcome-spirit-wrap.scene-garden, .welcome-spirit-wrap.scene-questions, .welcome-spirit-wrap.scene-closing { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
.welcome-spirit-wrap.appearing { animation: spiritMaterialize 2.6s cubic-bezier(.2,.8,.2,1) both; }
.spirit-halo { position: absolute; width: 320rpx; height: 320rpx; border-radius: 50%; background: radial-gradient(circle, rgba(250, 223, 159, 0.18), rgba(162, 146, 255, 0.08) 42%, transparent 70%); filter: blur(6rpx); animation: haloBreath 5.8s ease-in-out infinite; }
.spirit-stage.intro { width: 276rpx; height: 276rpx; border-radius: 96rpx; background: radial-gradient(circle at 50% 22%, rgba(255, 255, 255, 0.72), transparent 35%), linear-gradient(180deg, rgba(255, 252, 232, 0.26), rgba(189, 181, 255, 0.1)); border-color: rgba(255, 248, 224, 0.18); box-shadow: inset 0 1rpx rgba(255, 255, 255, 0.3), 0 28rpx 90rpx rgba(3, 7, 24, 0.44), 0 0 70rpx rgba(235, 204, 132, 0.14); backdrop-filter: blur(8rpx); }
.spirit-stage.intro .nest { bottom: 26rpx; background: radial-gradient(ellipse at center, rgba(244, 222, 157, 0.26), rgba(128, 145, 193, 0.1) 62%, transparent); }
.spirit-stage.intro .spirit { animation: listenFloat 5.8s ease-in-out infinite; }
.spirit-hair { position: absolute; left: 26rpx; top: -14rpx; width: 78rpx; height: 56rpx; border-radius: 70% 45% 60% 35%; background: linear-gradient(145deg, rgba(255, 255, 255, 0.7), rgba(204, 196, 246, 0.18)); opacity: 0.74; transform-origin: right bottom; animation: hairBreath 4.8s ease-in-out infinite; }
.spirit-robe { position: absolute; left: 20rpx; right: 18rpx; bottom: -16rpx; height: 68rpx; border-radius: 18rpx 18rpx 54rpx 54rpx; background: linear-gradient(180deg, rgba(255, 247, 219, 0.22), rgba(147, 165, 210, 0.16)); opacity: 0.78; animation: robeBreath 5.2s ease-in-out infinite; }
.spirit-stage.listening .mouth { animation: speakMouth 1.45s ease-in-out infinite; }
.spirit-stage.listening .arm.left { animation: waveLeft 4.8s ease-in-out infinite; transform-origin: right top; }
.spirit-stage.listening .arm.right { animation: waveRight 5.2s ease-in-out infinite; transform-origin: left top; }
.sound-wave { position: absolute; border-radius: 999rpx; border: 1rpx solid rgba(245, 222, 157, 0.14); opacity: 0; animation: soundPulse 4.4s ease-out infinite; }
.wave-a { width: 260rpx; height: 260rpx; }
.wave-b { width: 318rpx; height: 318rpx; animation-delay: 1.2s; }
.welcome-controls .sound-toggle { min-width: 132rpx; }
.prologue-dialogue { position: relative; width: 100%; max-width: 660rpx; min-height: 330rpx; padding: 0 12rpx; box-sizing: border-box; }
.welcome-lines { position: relative; z-index: 1; display: flex; flex-direction: column; align-items: stretch; justify-content: flex-end; gap: 13rpx; min-height: 330rpx; margin-top: 0; }
.spoken-line { width: fit-content; max-width: 100%; padding: 0 2rpx; font-size: 28rpx; line-height: 1.78; color: rgba(255, 248, 224, 0.62); font-weight: 460; letter-spacing: 0.01em; text-shadow: 0 10rpx 30rpx rgba(0, 0, 0, 0.34); transition: color .4s ease, opacity .4s ease, transform .4s ease; }
.spoken-line.active { color: rgba(255, 250, 230, 0.96); }
.spoken-line.hello { align-self: center; color: rgba(255, 249, 225, 0.96); font-size: 34rpx; font-weight: 760; letter-spacing: 0.04em; }
.spoken-line.focus { margin-left: auto; color: #fff4c8; font-weight: 780; text-align: right; text-shadow: 0 0 24rpx rgba(242, 211, 137, 0.26); }
.spoken-line.astro { color: rgba(220, 232, 255, 0.78); }
.spoken-line.example { color: rgba(255, 248, 224, 0.58); font-size: 25rpx; }
.spoken-line.quote { align-self: center; margin: 5rpx 0; padding: 17rpx 24rpx; border-radius: 999rpx; background: rgba(255, 244, 205, 0.075); border: 1rpx solid rgba(255, 238, 188, 0.13); color: rgba(255, 250, 229, 0.94); font-weight: 760; box-shadow: 0 18rpx 52rpx rgba(0, 0, 0, 0.16); }
.spoken-line.closing { align-self: flex-end; color: rgba(255, 244, 197, 0.96); font-weight: 780; text-align: right; }
.typing-cursor { display: inline-block; margin-left: 4rpx; color: #ffe7a3; animation: cursorBlink 0.8s steps(2, start) infinite; }
.welcome-poem { display: flex; flex-direction: column; gap: 10rpx; margin-top: 28rpx; }
.welcome-poem text { display: block; font-size: 26rpx; line-height: 1.64; color: rgba(24, 35, 31, 0.72); font-weight: 450; }
.welcome-poem .poem-gap { margin-top: 12rpx; }
.welcome-poem .quote { margin-top: 14rpx; padding: 18rpx 22rpx; border-radius: 28rpx; background: rgba(230, 235, 232, 0.76); color: rgba(24, 35, 31, 0.92); font-weight: 700; }
.welcome-bottom { width: 100%; max-width: 560rpx; display: grid; gap: 16rpx; padding-bottom: env(safe-area-inset-bottom); opacity: 0.42; transition: opacity .7s ease, transform .7s ease; transform: translateY(18rpx); pointer-events: none; }
.welcome-bottom.ready { opacity: 1; transform: translateY(0); pointer-events: auto; }
.welcome-final { display: block; text-align: center; font-size: 22rpx; font-weight: 620; color: rgba(255, 248, 224, 0.5); letter-spacing: 0.04em; }
.welcome-bottom.ready .welcome-final { color: rgba(255, 248, 224, 0.78); }
.primary-btn.welcome-cta { width: 100%; margin-top: 0; min-height: 88rpx; border-radius: 22rpx; color: rgba(255, 247, 221, 0.94); background: linear-gradient(180deg, rgba(255, 248, 224, 0.14), rgba(255, 248, 224, 0.055)); border: 1rpx solid rgba(255, 238, 188, 0.3); box-shadow: 0 22rpx 70rpx rgba(0, 0, 0, 0.26), 0 0 48rpx rgba(242, 205, 120, 0.13), inset 0 1rpx rgba(255, 255, 255, 0.14); letter-spacing: 0.08em; backdrop-filter: blur(18rpx); display: flex; align-items: center; justify-content: center; gap: 12rpx; }
.cta-star { color: #ffe7a3; font-size: 24rpx; text-shadow: 0 0 20rpx rgba(255, 231, 163, 0.8); animation: welcomeTwinkle 2.6s ease-in-out infinite; }
@keyframes listenFloat { 50% { transform: translateY(-14rpx) rotate(-1deg) scale(1.02); } }
@keyframes waveLeft { 50% { transform: rotate(34deg) translateY(-4rpx); } }
@keyframes waveRight { 50% { transform: scaleX(-1) rotate(34deg) translateY(-4rpx); } }
@keyframes hairBreath { 50% { transform: rotate(-4deg) translateY(-3rpx); opacity: 0.9; } }
@keyframes robeBreath { 50% { transform: translateY(5rpx) scaleX(1.05); opacity: 0.62; } }
@keyframes soundPulse { 0% { transform: scale(0.72); opacity: 0.32; } 72%, 100% { transform: scale(1.14); opacity: 0; } }
@keyframes galaxyDrift { 50% { transform: rotate(-15deg) translate3d(26rpx, 18rpx, 0); opacity: 0.58; } }
@keyframes welcomeTwinkle { 0%, 100% { opacity: 0.32; transform: scale(0.82); } 50% { opacity: 1; transform: scale(1.18); } }
@keyframes meteor { 0%, 36% { opacity: 0; transform: translate3d(0, 0, 0) rotate(-24deg); } 41% { opacity: 1; } 52% { opacity: 0; transform: translate3d(-440rpx, 210rpx, 0) rotate(-24deg); } 100% { opacity: 0; } }
@keyframes fallingLight { 0%, 35% { opacity: 0; transform: translate3d(48rpx, -80rpx, 0) rotate(17deg); } 45% { opacity: 0.8; } 72%, 100% { opacity: 0; transform: translate3d(-10rpx, 230rpx, 0) rotate(17deg); } }
@keyframes whisperFloat { 0%, 100% { opacity: 0; transform: translateY(12rpx); } 25%, 58% { opacity: 1; transform: translateY(0); } 78% { opacity: 0; transform: translateY(-16rpx); } }
@keyframes spiritMaterialize { 0% { opacity: 0; filter: blur(22rpx); transform: translateY(38rpx) scale(0.64); } 36% { opacity: 0.26; filter: blur(14rpx); } 62% { opacity: 0.72; filter: blur(5rpx); } 100% { opacity: 1; filter: blur(0); transform: translateY(0) scale(1); } }
@keyframes haloBreath { 50% { opacity: 0.54; transform: scale(1.08); } }
@keyframes speakMouth { 0%, 100% { height: 9rpx; transform: scaleX(0.72); } 50% { height: 17rpx; transform: scaleX(1.08); } }
@keyframes cursorBlink { 50% { opacity: 0; } }
.primary-btn { border: 0; border-radius: 20rpx; padding: 20rpx 26rpx; font-size: 25rpx; font-weight: 700; line-height: 1; min-height: 80rpx; box-sizing: border-box; display: flex; align-items: center; justify-content: center; margin-top: 28rpx; background: linear-gradient(180deg, #6c9179 0%, #5f826c 100%); color: #fff9ec; box-shadow: 0 16rpx 40rpx rgba(95, 130, 108, 0.32); }
.primary-btn[disabled] { opacity: 0.6; }
.spirit-stage { position: relative; border: 1rpx solid rgba(77, 92, 82, 0.14); background: linear-gradient(180deg, rgba(255, 255, 255, 0.42), rgba(255, 255, 255, 0.14)); box-shadow: inset 0 1rpx rgba(255, 255, 255, 0.62), 0 22rpx 56rpx rgba(49, 57, 52, 0.12); display: flex; align-items: center; justify-content: center; overflow: hidden; }
.aura { position: absolute; width: 210rpx; height: 210rpx; border-radius: 50%; background: radial-gradient(circle, rgba(240, 213, 139, 0.24), transparent 65%); animation: pulse 4.4s ease-in-out infinite; }
.nest { position: absolute; bottom: 34rpx; width: 170rpx; height: 58rpx; border-radius: 50%; background: radial-gradient(ellipse at center, rgba(240, 213, 139, 0.4), rgba(95, 130, 108, 0.1) 68%, transparent); }
.spirit { position: relative; width: 124rpx; height: 160rpx; border-radius: 48% 52% 45% 55% / 42% 44% 56% 58%; background: radial-gradient(circle at 35% 26%, rgba(255, 255, 255, 0.9), transparent 22%), linear-gradient(145deg, rgba(222, 214, 244, 0.96), rgba(238, 217, 152, 0.82) 70%, rgba(143, 174, 151, 0.45)); box-shadow: inset -18rpx -24rpx 38rpx rgba(110, 94, 130, 0.16), inset 16rpx 16rpx 34rpx rgba(255, 255, 255, 0.44), 0 22rpx 54rpx rgba(128, 107, 67, 0.22); animation: float 5.8s ease-in-out infinite; }
.spirit::before, .spirit::after { content: ''; position: absolute; top: 72rpx; width: 12rpx; height: 12rpx; border-radius: 50%; background: #24312c; }
.spirit::before { left: 40rpx; }
.spirit::after { right: 40rpx; }
.mouth { position: absolute; left: 50%; top: 94rpx; width: 26rpx; height: 14rpx; margin-left: -13rpx; border-bottom: 3rpx solid rgba(36, 49, 44, 0.72); border-radius: 0 0 999rpx 999rpx; }
.antenna { position: absolute; width: 64rpx; height: 48rpx; border-top: 3rpx solid rgba(240, 213, 139, 0.68); border-radius: 50%; top: -26rpx; left: 30rpx; }
.antenna::after { content: ''; position: absolute; right: 0; top: -2rpx; width: 12rpx; height: 12rpx; border-radius: 50%; background: #efd58b; box-shadow: 0 0 18rpx #efd58b; }
.arm { position: absolute; width: 46rpx; height: 30rpx; border: 5rpx solid rgba(255, 255, 255, 0.52); border-top: 0; border-left: 0; border-radius: 0 0 28rpx 0; top: 94rpx; }
.arm.left { left: -30rpx; transform: rotate(24deg); }
.arm.right { right: -30rpx; transform: scaleX(-1) rotate(24deg); }
@keyframes float { 50% { transform: translateY(-12rpx) rotate(-1.6deg); } }
@keyframes pulse { 50% { transform: scale(1.09); opacity: 0.52; } }
.home-title { margin-top: 16rpx; font-size: 54rpx; }
.home-actions { display: grid; grid-template-columns: 1fr auto; gap: 18rpx; }
.home-actions .primary-btn, .home-actions .secondary-btn, .letter-actions .primary-btn, .letter-actions .secondary-btn { margin-top: 24rpx; }
.why { white-space: nowrap; }
.wake-strip { display: flex; justify-content: space-between; gap: 24rpx; align-items: center; border-radius: 38rpx; padding: 22rpx 24rpx; margin-top: 22rpx; background: rgba(240, 213, 139, 0.14); border: 1rpx solid rgba(77, 92, 82, 0.14); }
.wake-title { display: block; font-size: 26rpx; font-weight: 800; }
.wake-copy { display: block; margin-top: 6rpx; font-size: 22rpx; color: rgba(23, 37, 31, 0.62); line-height: 1.5; }
.chip { border-radius: 999rpx; border: 1rpx solid rgba(77, 92, 82, 0.14); background: rgba(255, 255, 255, 0.38); padding: 12rpx 16rpx; font-size: 20rpx; color: rgba(23, 37, 31, 0.62); }
.letter-card { padding: 34rpx; margin-top: 22rpx; }
.letter-title { display: block; margin: 18rpx 0 10rpx; font-size: 42rpx; font-weight: 800; letter-spacing: -0.035em; }
.letter-body { display: block; font-size: 26rpx; line-height: 1.9; color: rgba(23, 37, 31, 0.62); }
.chip-row, .fragment-row { display: flex; flex-wrap: wrap; gap: 12rpx; margin-top: 20rpx; }
.dash-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18rpx; margin-top: 22rpx; }
.mini-card { border-radius: 28rpx; border: 1rpx solid rgba(77, 92, 82, 0.14); background: rgba(255, 255, 255, 0.38); padding: 26rpx; box-shadow: 0 12rpx 32rpx rgba(35, 40, 34, 0.08); }
.mini-title { display: block; margin: 14rpx 0 8rpx; font-family: Georgia, "Noto Serif SC", serif; font-size: 28rpx; font-weight: 750; letter-spacing: -0.02em; line-height: 1.35; }
.mini-copy { display: block; font-size: 22rpx; color: rgba(23, 37, 31, 0.62); line-height: 1.6; }
.frag-chip { border-radius: 999rpx; background: rgba(240, 213, 139, 0.2); padding: 10rpx 14rpx; color: rgba(23, 37, 31, 0.68); font-size: 20rpx; }
.recall-card, .evidence-card { margin-top: 20rpx; }
.recall-line { display: flex; gap: 18rpx; align-items: flex-start; }
.pulse-star { color: #efd58b; text-shadow: 0 0 20rpx rgba(240, 213, 139, 0.9); margin-top: 12rpx; }
.evidence-card { padding: 28rpx; }
.evidence-row { display: grid; grid-template-columns: 120rpx 1fr; gap: 18rpx; padding: 18rpx 0; border-top: 1rpx solid rgba(77, 92, 82, 0.14); font-size: 22rpx; color: rgba(23, 37, 31, 0.66); }
.evidence-row:first-of-type { margin-top: 14rpx; border-top: 0; }
.evidence-row text:first-child { text-transform: uppercase; letter-spacing: 0.12em; font-size: 18rpx; color: rgba(23, 37, 31, 0.38); }
.sheet-mask { position: fixed; inset: 0; z-index: 20; background: rgba(0, 0, 0, 0.08); }
.bottom-sheet { position: fixed; z-index: 21; left: 24rpx; right: 24rpx; bottom: 32rpx; border-radius: 52rpx; padding: 20rpx 30rpx 30rpx; background: rgba(17, 27, 24, 0.94); color: #fff8eb; box-shadow: 0 24rpx 72rpx rgba(0, 0, 0, 0.3); }
.sheet-handle { width: 72rpx; height: 8rpx; border-radius: 999rpx; background: rgba(255, 255, 255, 0.22); margin: 0 auto 24rpx; }
.sheet-eyebrow { display: block; font-size: 18rpx; letter-spacing: 0.2em; color: rgba(255, 248, 235, 0.42); }
.sheet-title { display: block; margin-top: 10rpx; font-size: 30rpx; font-weight: 800; }
.sheet-copy { display: block; margin-top: 14rpx; font-size: 24rpx; line-height: 1.75; color: rgba(255, 248, 235, 0.66); white-space: pre-line; }
.sheet-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 14rpx; margin-top: 22rpx; }
.sheet-primary, .sheet-secondary { border-radius: 22rpx; padding: 20rpx; font-size: 23rpx; }
.sheet-primary { background: #f3dfaa; color: #17251f; }
.sheet-secondary { background: rgba(255, 255, 255, 0.08); color: rgba(255, 248, 235, 0.78); border: 1rpx solid rgba(255, 255, 255, 0.1); }
.phase-night .date-row, .phase-night .wake-copy, .phase-night .letter-body, .phase-night .mini-copy, .phase-night .evidence-row, .phase-night .label, .phase-night .privacy-text { color: rgba(255, 248, 235, 0.66); }
.phase-night .wake-title, .phase-night .mini-title, .phase-night .letter-title, .phase-night .card-title, .phase-night .step text:first-child { color: #fff8eb; }
/* 序章跳过：底部居中胶囊，2.5s 后淡入，视觉权重高于旧顶部小字但不抢主视觉 */
.welcome-skip-fab { position: absolute; left: 50%; bottom: calc(env(safe-area-inset-bottom, 0rpx) + 44rpx); transform: translateX(-50%); z-index: 4; display: flex; align-items: center; gap: 10rpx; padding: 20rpx 40rpx; border-radius: 999rpx; border: 1rpx solid rgba(255, 238, 188, 0.32); background: rgba(255, 248, 224, 0.07); backdrop-filter: blur(14rpx); color: rgba(255, 248, 224, 0.82); font-size: 23rpx; letter-spacing: 0.08em; animation: skipFabIn 0.8s 2.5s cubic-bezier(0.2, 0.8, 0.2, 1) both; }
.skip-star { color: #ffe7a3; font-size: 20rpx; text-shadow: 0 0 16rpx rgba(255, 231, 163, 0.7); }
@keyframes skipFabIn { from { opacity: 0; transform: translate(-50%, 18rpx); } to { opacity: 1; transform: translate(-50%, 0); } }
/* 首页 · V8 今日花园场景：外层只负责统一时间光线，具体场景交给 GardenHome */
.stage-garden {
  padding: 0;
  overflow: hidden;
  background: linear-gradient(180deg, #d7ecea 0%, #f6efd8 58%, #c5dcb8 100%);
  color: #29483a;
}
.stage-garden.phase-morning { background: linear-gradient(180deg, #d7ecea 0%, #f6efd8 58%, #c5dcb8 100%); }
.stage-garden.phase-noon { background: linear-gradient(180deg, #b6e0e8 0%, #f7edc5 55%, #a7ca91 100%); }
.stage-garden.phase-dusk { background: linear-gradient(180deg, #8e91ac 0%, #d5b4a9 52%, #718776 100%); color: #fff7e7; }
.stage-garden.phase-night { background: linear-gradient(180deg, #26354b 0%, #3e5c67 54%, #547765 100%); color: #fff7e7; }
.stage-garden .bg-glow,
.stage-garden > .stars {
  display: none;
}
.stage-garden .appbar {
  display: none;
}
</style>
