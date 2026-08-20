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
      <button class="icon-btn" @tap="toggleSheet">?</button>
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
          <text>我和他还有可能吗？</text>
          <text>我现在该不该换工作？</text>
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
        <button class="primary-btn welcome-cta" @tap.stop="stage = 'register'">
          <text class="cta-star">✦</text>
          <text>遇见我的星灵</text>
        </button>
      </view>

      <view v-if="welcomeStarted && !typingDone" class="welcome-skip-fab" @tap.stop="skipWelcomeIntro">
        <text>跳过序章</text>
        <text class="skip-star">✦</text>
      </view>
    </view>

    <view v-else-if="stage === 'register'" class="screen register-screen create-chart-screen">
      <view class="register-sky" aria-hidden="true">
        <text v-for="n in 14" :key="`register-star-${n}`" :class="['sky-star', `sky-star-${n}`]">✦</text>
        <view class="constellation constellation-a">
          <view class="c-dot d1"></view><view class="c-dot d2"></view><view class="c-dot d3"></view><view class="c-dot d4"></view>
          <view class="c-line l1"></view><view class="c-line l2"></view><view class="c-line l3"></view>
        </view>
      </view>

      <view class="chart-orb" aria-hidden="true">
        <text class="chart-star s1">✦</text>
        <text class="chart-star s2">✧</text>
        <text class="chart-star s3">✦</text>
        <view class="chart-ring r1"></view>
        <view class="chart-ring r2"></view>
      </view>

      <view class="create-chart-hero">
        <text class="create-sigil">✦</text>
        <text class="create-title">让星灵认识你</text>
        <text class="create-copy">每一张星图，都从出生的那一刻开始。</text>
      </view>

      <view class="question-card">
        <view class="register-spirit" aria-hidden="true">
          <view class="spirit-stage">
            <view class="aura"></view>
            <view class="nest"></view>
            <view class="spirit"><view class="antenna"></view><view class="arm left"></view><view class="arm right"></view><view class="mouth"></view></view>
          </view>
        </view>

        <view :key="registerStep" class="prompt-swap">
          <text class="spirit-says">{{ registerPrompt }}</text>
          <text v-if="registerHint" class="question-hint">{{ registerHint }}</text>
        </view>

        <view :key="`answer-${registerStep}`" class="answer-block">
          <view v-if="registerStep === 1">
            <input v-model="form.name" class="answer-input name-input" placeholder="你的名字" confirm-type="next" />
            <view class="gender-row">
              <view :class="['gender-pill', { on: form.gender === 'female' }]" @tap="form.gender = 'female'"><text>她</text></view>
              <view :class="['gender-pill', { on: form.gender === 'male' }]" @tap="form.gender = 'male'"><text>他</text></view>
              <view :class="['gender-pill', { on: !form.gender }]" @tap="form.gender = ''"><text>先不说</text></view>
            </view>
            <text class="field-note">这是星灵以后称呼你的方式；称呼可选。</text>
          </view>

          <view v-else-if="registerStep === 2" class="date-answer">
            <picker mode="date" :value="form.date" @change="onDate">
              <view :class="['date-picker-card', { lit: justPicked === 'date' }]">
                <text v-if="birthDateParts" class="date-part year">{{ birthDateParts.year }}</text>
                <text v-if="birthDateParts" class="date-unit">年</text>
                <text v-if="birthDateParts" class="date-part">{{ birthDateParts.month }}</text>
                <text v-if="birthDateParts" class="date-unit">月</text>
                <text v-if="birthDateParts" class="date-part">{{ birthDateParts.day }}</text>
                <text v-if="birthDateParts" class="date-unit">日</text>
                <text v-else class="date-placeholder">选择出生日期</text>
              </view>
            </picker>
          </view>

          <view v-else-if="registerStep === 3" class="time-answer">
            <picker mode="time" :value="form.time" :disabled="form.time_unknown" @change="onTime">
              <view :class="['time-picker-card', { muted: form.time_unknown, lit: justPicked === 'time' }]">
                <text>{{ form.time_unknown ? '时间不确定' : (form.time || '选择时间') }}</text>
              </view>
            </picker>
            <text class="field-note">出生时间越准确，星图越精确。请确认你的选择：</text>
            <view class="time-confirm-row">
              <view :class="['confirm-pill', { on: !form.time_unknown && !!form.time }]" @tap="confirmTimeKnown">
                <text>确定这个时间</text>
              </view>
              <view :class="['confirm-pill', { on: form.time_unknown }]" @tap="toggleTimeUnknown">
                <text>时间不确定</text>
              </view>
            </view>
            <view v-if="dstAsk" class="dst-ask">
              <text class="dst-title">这段日期中国用过夏令时（时钟拨快 1 小时）</text>
              <view class="dst-options">
                <view :class="['dst-pill', { on: form.dst === 'dst' }]" @tap="form.dst = 'dst'"><text>按夏令时算</text></view>
                <view :class="['dst-pill', { on: form.dst === 'std' }]" @tap="form.dst = 'std'"><text>按标准时间算</text></view>
              </view>
              <text class="dst-note">不确定就选「按夏令时算」，之后可以在验证里校准。</text>
            </view>
          </view>

          <view v-else-if="registerStep === 4" class="place-answer">
            <picker mode="multiSelector" :range="birthRegionRange" :value="birthRegionValue" @columnchange="onBirthRegionColumn" @change="onBirthRegionConfirm">
              <view :class="['date-picker-card', { lit: justPicked === 'region' }]">
                <text v-if="form.regionLabel" class="date-part region-text">{{ form.regionLabel }}</text>
                <text v-else class="date-placeholder">选择出生省 / 市 / 区</text>
              </view>
            </picker>
            <button class="secondary-btn overseas-trigger" @tap="openOverseas">
              <text>海外出生 / 精确坐标 →</text>
            </button>
            <text class="field-note">国内用级联选择；海外用坐标定位，经纬度直接决定你的宫位。</text>
          </view>

          <view v-else class="residence-answer">
            <view class="same-as-birth" :class="{ on: sameAsBirth }" @tap="toggleSameAsBirth">
              <text>{{ sameAsBirth ? `同出生地 · ${form.regionLabel || form.city || '—'}` : '现居地和出生地不一样' }}</text>
            </view>
            <picker v-if="!sameAsBirth" mode="multiSelector" :range="resRegionRange" :value="resRegionValue" @columnchange="onResRegionColumn" @change="onResRegionConfirm">
              <view :class="['date-picker-card', { lit: justPicked === 'residence' }]">
                <text v-if="form.residenceLabel" class="date-part region-text">{{ form.residenceLabel }}</text>
                <text v-else class="date-placeholder">选择现居省 / 市 / 区</text>
              </view>
            </picker>
            <picker mode="selector" :range="tzOptions" @change="onTz">
              <view class="tz-card">
                <text class="tz-label">时区</text>
                <text class="tz-value">{{ form.tz }}</text>
              </view>
            </picker>
            <text class="field-note">现居地决定星灵每天什么时候来找你；时区默认东八区。</text>
          </view>
        </view>

        <view class="create-actions">
          <button v-if="registerStep > 1" class="secondary-btn back-btn" :disabled="busy" @tap="prevRegisterStep">上一颗星</button>
          <button class="primary-btn create-next" :disabled="busy" @tap="nextRegisterStep">
            {{ registerStep < 5 ? '继续' : (busy ? '正在绘制星图…' : '绘制我的星图') }}
          </button>
        </view>
        <text v-if="error" class="error create-error">{{ error }}</text>
        <view class="create-progress" aria-hidden="true"><text v-for="n in 5" :key="n" :class="['progress-dot', n <= registerStep ? 'on' : '']"></text></view>
        <text v-if="registerStep === 1" class="back-to-sky" @tap="stage = 'welcome'">← 回到星空</text>
      </view>
    </view>

    <view v-else-if="stage === 'awakening'" class="screen awakening-screen chart-drawing-screen">
      <view class="chart-sky" aria-hidden="true">
        <view class="drawing-milky"></view>
        <view class="birth-stream stream-date"><text>{{ form.date || '出生日期' }}</text></view>
        <view class="birth-stream stream-time"><text>{{ form.time_unknown ? '时间未知' : (form.time || '出生时间') }}</text></view>
        <view class="birth-stream stream-place"><text>{{ form.city || '出生地点' }}</text></view>
        <text class="draw-glyph sun">☉</text>
        <text class="draw-glyph moon">☽</text>
        <text class="draw-glyph venus">♀</text>
        <text class="draw-glyph saturn">♄</text>
        <view class="draw-aspect a1"></view><view class="draw-aspect a2"></view><view class="draw-aspect a3"></view>
      </view>

      <view :class="['orbit', 'chart-orbit', { found: awakeFound }]">
        <view class="chart-wheel-core">
          <view class="wheel-ring outer"></view>
          <view class="wheel-ring inner"></view>
          <view class="wheel-cross h"></view>
          <view class="wheel-cross v"></view>
          <view class="planet-dot p1"></view><view class="planet-dot p2"></view><view class="planet-dot p3"></view><view class="planet-dot p4"></view>
        </view>
        <view v-if="awakeFound" class="burst-ring r-one"></view>
        <view v-if="awakeFound" class="burst-ring r-two"></view>
        <view class="spirit-stage large chart-spirit">
          <view class="aura"></view>
          <view class="nest"></view>
          <view class="spirit"><view class="antenna"></view><view class="arm left"></view><view class="arm right"></view><view class="mouth"></view></view>
        </view>
      </view>

      <view class="card awake-card chart-awake-card">
        <text class="eyebrow">CREATE CHART</text>
        <text class="awake-title">正在为你绘制星图</text>
        <text class="card-copy">日期、时间和地点正在变成太阳、月亮、行星、宫位与相位。</text>
        <view class="steps chart-steps">
          <view class="step"><text>出生信息</text><text>{{ savedName || form.name || '你' }}</text></view>
          <view class="step"><text>出生星图</text><text>{{ gardenState ? '已生成' : '绘制中…' }}</text></view>
          <view class="step"><text>第一颗星灵</text><text>{{ recommendedSpirit ? `已找到 · ${spiritName}` : '寻找中' }}</text></view>
        </view>
        <view :class="['found-message', { lit: awakeFound }]">
          <text>「我找到你的星图了。」</text>
          <text>「以后，我会陪你一起读懂它。」</text>
        </view>
        <view class="awake-actions">
          <button class="primary-btn" @tap="enterHomeFromAwakening">进入我的花园</button>
          <button class="secondary-btn" @tap="goChat">先和它说句话</button>
        </view>
        <text v-if="error" class="error">{{ error }}</text>
      </view>
    </view>

    <GardenHome
      v-else
      :spirit-name="spiritName"
      :spirit-planet="spiritPlanet"
      :spirit-line="spiritLine"
      :garden-state="gardenState"
      @chat="goChat"
    />

    <view v-if="overseasOpen" class="sheet-mask" @tap="overseasOpen = false"></view>
    <view v-if="overseasOpen" class="overseas-sheet">
      <view class="sheet-handle"></view>
      <text class="sheet-eyebrow">OVERSEAS BIRTH</text>
      <text class="os-title">海外出生 · 精确坐标</text>
      <input v-model="overseasName" class="answer-input os-name" placeholder="城市名，如 东京 / London" confirm-type="done" />
      <picker mode="multiSelector" :range="latCols" :value="osLat" @change="onOsLat">
        <view class="os-row"><text class="os-label">纬度</text><text class="os-value">{{ latLabel }}</text></view>
      </picker>
      <picker mode="multiSelector" :range="lonCols" :value="osLon" @change="onOsLon">
        <view class="os-row"><text class="os-label">经度</text><text class="os-value">{{ lonLabel }}</text></view>
      </picker>
      <picker mode="selector" :range="tzOptions" :value="osTzIdx" @change="onOsTz">
        <view class="os-row"><text class="os-label">时区</text><text class="os-value">{{ tzOptions[osTzIdx] }}</text></view>
      </picker>
      <text class="os-note">滚轮粗选到度即可；分秒级差异对星盘的影响可以忽略。</text>
      <view class="sheet-actions">
        <button class="sheet-secondary" @tap="overseasOpen = false">取消</button>
        <button class="sheet-primary" @tap="confirmOverseas">确认坐标</button>
      </view>
    </view>

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
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { onShow } from "@dcloudio/uni-app";
import api, { ApiError, describeError, type GardenState, type SpiritRecommendationOut } from "@/api/client";
import { subscribePush } from "@/utils/push";
import GardenHome from "@/components/GardenHome.vue";

type HomeStage = "welcome" | "register" | "awakening" | "garden";

const form = reactive({
  name: "",
  date: "",
  time: "",
  city: "",
  time_unknown: false,
  gender: "",
  regionLabel: "",
  residenceLabel: "",
  residenceCity: "",
  tz: "GMT+8:00",
  dst: "" as "" | "dst" | "std",
});
const manualCity = ref("");
const manualGeo = ref<{ lat: number; lon: number; tz: string } | null>(null);
const sameAsBirth = ref(true);
const tzOptions = ["GMT-8:00", "GMT-5:00", "GMT+0:00", "GMT+1:00", "GMT+3:00", "GMT+5:30", "GMT+8:00", "GMT+9:00", "GMT+10:00", "GMT+12:00"];
const TZ_IANA: Record<string, string> = {
  "GMT-8:00": "America/Los_Angeles", "GMT-5:00": "America/New_York", "GMT+0:00": "Europe/London",
  "GMT+1:00": "Europe/Paris", "GMT+3:00": "Europe/Moscow", "GMT+5:30": "Asia/Kolkata",
  "GMT+8:00": "Asia/Shanghai", "GMT+9:00": "Asia/Tokyo", "GMT+10:00": "Australia/Sydney", "GMT+12:00": "Pacific/Auckland",
};
// 海外坐标弹框：纬度/经度各三列（半球、度、分），精度到分
const latCols = [["北纬", "南纬"], Array.from({ length: 90 }, (_, i) => `${i}°`), Array.from({ length: 60 }, (_, i) => `${i}′`)];
const lonCols = [["东经", "西经"], Array.from({ length: 180 }, (_, i) => `${i}°`), Array.from({ length: 60 }, (_, i) => `${i}′`)];
const overseasOpen = ref(false);
const overseasName = ref("");
const osLat = ref<[number, number, number]>([0, 35, 0]);
const osLon = ref<[number, number, number]>([0, 139, 0]);
const osTzIdx = ref(6);
const latLabel = computed(() => `${latCols[0][osLat.value[0]]} ${osLat.value[1]}°${osLat.value[2]}′`);
const lonLabel = computed(() => `${lonCols[0][osLon.value[0]]} ${osLon.value[1]}°${osLon.value[2]}′`);
const latVal = computed(() => (osLat.value[0] === 0 ? 1 : -1) * (osLat.value[1] + osLat.value[2] / 60));
const lonVal = computed(() => (osLon.value[0] === 0 ? 1 : -1) * (osLon.value[1] + osLon.value[2] / 60));
function openOverseas() {
  overseasName.value = manualCity.value;
  overseasOpen.value = true;
}
function onOsLat(e: any) { osLat.value = e.detail.value as [number, number, number]; }
function onOsLon(e: any) { osLon.value = e.detail.value as [number, number, number]; }
function onOsTz(e: any) { osTzIdx.value = Number(e.detail.value); }
function confirmOverseas() {
  const name = overseasName.value.trim() || "东京";
  manualCity.value = name;
  manualGeo.value = { lat: latVal.value, lon: lonVal.value, tz: tzOptions[osTzIdx.value] };
  form.city = "";
  form.regionLabel = `${name} · ${latLabel.value} ${lonLabel.value}`;
  overseasOpen.value = false;
  flashPick("region");
}
const registerStep = ref(1);
const busy = ref(false);
const error = ref("");
const stage = ref<HomeStage>("welcome");
const savedName = ref("");
const gardenState = ref<GardenState | null>(null);
const recommendedSpirit = ref<SpiritRecommendationOut | null>(null);
const sheetOpen = ref(false);
const lastLoadedPersonId = ref("");

const PERSON_KEY = "gs_person_id";
const SESSION_KEY = "gs_session_id";
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
  { text: "你可以问它感情。", tone: "example", scene: "questions", pauseAfter: 520 },
  { text: "我和他还有可能吗？", tone: "quote", scene: "questions", pace: "slow", pauseAfter: 800 },
  { text: "问它事业。", tone: "example", scene: "questions", pauseAfter: 520 },
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
  if (value === "register") void ensureRegionData();
  if (value !== "welcome") {
    stopWelcomeTyping();
    stopWelcomeVoice();
    stopWelcomeAmbient();
    return;
  }
  await nextTick();
  resetWelcomeIntro();
});

const DOMAIN_ZH: Record<string, string> = {
  career: "事业", relationship: "感情", wealth: "财富", health: "健康",
  emotion: "情绪", family: "家庭", learning: "学习", daily: "今日",
};
function domainZh(d: string) {
  return DOMAIN_ZH[d] || d;
}

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

const PLANET_ZH: Record<string, string> = {
  sun: "太阳星灵",
  moon: "月亮星灵",
  mercury: "水星星灵",
  venus: "金星星灵",
  mars: "火星星灵",
  jupiter: "木星星灵",
  saturn: "土星星灵",
  uranus: "天王星灵",
  neptune: "海王星灵",
  pluto: "冥王星灵",
};

const currentHour = ref(new Date().getHours());
const phase = computed(() => {
  const hour = currentHour.value;
  return hour < 11 ? "morning" : hour < 16 ? "noon" : hour < 20 ? "dusk" : "night";
});
// 注册与绘制星图固定使用夜空主题，与欢迎页深空序章保持同一章视觉
const phaseClass = computed(() => (stage.value === "register" || stage.value === "awakening" ? "phase-night" : `phase-${phase.value}`));
const stageClass = computed(() => `stage-${stage.value}`);
const appTitle = computed(() => stage.value === "welcome" ? "星灵花园" : stage.value === "register" ? "创建星图" : stage.value === "awakening" ? "绘制星图" : "花园");

const registerPrompt = computed(() => [
  "",
  "先告诉我，怎么称呼你？",
  "那么，你是什么时候来到这个世界的？",
  "还有一个很重要的时刻。\n你出生时，大约是几点？",
  "最后，告诉我你在哪里来到这个世界。",
  "你现在住在哪儿？",
][registerStep.value]);
const registerHint = computed(() => [
  "",
  "现在，轮到你了。",
  "这一天会成为星图的起点。",
  "不知道也没有关系，我们会进入简化星图。",
  "国内用级联选择，海外城市可以直接输入。",
  "让每日星信在合适的时候抵达，默认东八区。",
][registerStep.value]);
const birthDateParts = computed(() => {
  if (!form.date) return null;
  const [year, month, day] = form.date.split("-");
  return { year, month: String(Number(month)), day: String(Number(day)) };
});

const spiritName = computed(() => {
  const p = recommendedSpirit.value?.planet?.toLowerCase();
  return recommendedSpirit.value?.healing_name || recommendedSpirit.value?.name || (p ? PLANET_ZH[p] : "月亮星灵");
});
const spiritPlanet = computed(() => recommendedSpirit.value?.planet?.toLowerCase() || "moon");
const spiritReason = computed(() => recommendedSpirit.value?.reason || "它会先从安全感、情绪和归属感的角度陪你看今天。");
const SPIRIT_LINES: Record<string, string> = {
  sun: "今天也值得被看见一点。",
  moon: "我会先听你说，不急着给答案。",
  mercury: "想到什么说什么，我们一起整理。",
  venus: "先照顾好感受，再谈对错。",
  mars: "想说就去做，我陪你冲一次。",
  jupiter: "往远处看看，路比你以为的宽。",
  saturn: "慢慢来，我先把结构理清楚。",
  uranus: "不安分也没关系，自由是天赋。",
  neptune: "做梦很重要，我帮你留住它。",
  pluto: "深一点的真相，我们慢慢挖。",
};
const spiritLine = computed(() => SPIRIT_LINES[recommendedSpirit.value?.planet?.toLowerCase() || "moon"] || SPIRIT_LINES.moon);
const sheetCopy = computed(() => `${spiritReason.value}\n\n首页只保留一个醒来的星灵和一封私人星信；更细的解释放在这里，避免把陪伴变成数据面板。`);

onShow(async () => {
  currentHour.value = new Date().getHours();
  const pid = uni.getStorageSync(PERSON_KEY) as string;
  if (!pid) {
    // 只在「花园态却没有档案」时回欢迎页；注册/绘制中途切后台回来不清表单
    if (stage.value === "garden") stage.value = "welcome";
    return;
  }
  if (stage.value === "awakening" && lastLoadedPersonId.value === pid) return;
  await loadExistingGarden(pid);
  maybeSubscribePush(pid);
});

async function loadExistingGarden(pid: string) {
  error.value = "";
  try {
    const p = await api.getPerson(pid);
    savedName.value = p.name;
    lastLoadedPersonId.value = pid;
    await loadRecommendation(pid);
    await loadGarden(pid, recommendedSpirit.value?.planet);
  } catch (e) {
    // 只有「档案确实不存在(404)/不可解密(410)」才登出回欢迎页；
    // 网络抖动/后端重启不能清登录态踢人——保留状态，进花园兜底页等恢复
    const gone = e instanceof ApiError && (e.status === 404 || e.status === 410);
    if (gone) {
      uni.removeStorageSync(PERSON_KEY);
      stage.value = "welcome";
    } else if (stage.value !== "garden") {
      stage.value = "garden";
    }
    error.value = describeError(e);
    uni.showToast({ title: describeError(e), icon: "none", duration: 2200 });
  }
}

async function loadRecommendation(pid: string) {
  try {
    const rec = await api.recommendedSpirits(pid);
    recommendedSpirit.value = rec.spirits?.[0] || null;
  } catch {
    recommendedSpirit.value = null;
  }
}

async function loadGarden(pid: string, persona?: string) {
  try {
    gardenState.value = await api.garden(pid, persona);
  } catch (e) {
    gardenState.value = null;
    error.value = describeError(e);
  }
  stage.value = "garden";
}

async function loadAwakening(pid: string) {
  stage.value = "awakening";
  error.value = "";
  lastLoadedPersonId.value = pid;
  await loadRecommendation(pid);
  try {
    gardenState.value = await api.garden(pid, recommendedSpirit.value?.planet);
  } catch (e) {
    gardenState.value = null;
    error.value = describeError(e);
  }
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

function onDate(e: any) {
  form.date = e.detail.value;
  form.dst = "";
  flashPick("date");
}
function toggleTimeUnknown() {
  form.time_unknown = !form.time_unknown;
  if (form.time_unknown) form.dst = "";
}
function confirmTimeKnown() {
  if (!form.time) {
    error.value = "先在上方选择一个时间";
    return;
  }
  form.time_unknown = false;
  flashPick("time");
}
function onTime(e: any) {
  form.time = e.detail.value;
  flashPick("time");
}
function onRegion(e: any) {
  const [province, city] = e.detail.value || [];
  if (city) {
    form.city = String(city).replace(/市$/, "");
    const prov = String(province).replace(/(省|壮族自治区|回族自治区|维吾尔自治区|特别行政区|自治区)/g, "");
    form.regionLabel = prov === form.city ? form.city : `${prov} · ${form.city}`;
  }
  flashPick("region");
}

// 三级行政区划级联（省/市/区县）：H5 不支持 picker mode="region"，用 multiSelector + 区划数据包自实现
// 区划 JSON 约 300KB，动态 import 拆出首屏 chunk，进入注册阶段时再装载
interface RegionRow { code: string; name: string; province: string; city?: string }
const MUNICIPALITIES = new Set(["北京市", "天津市", "上海市", "重庆市"]);
const regionData = ref<{ provinces: RegionRow[]; cities: Map<string, { code: string; name: string }[]>; districts: Map<string, string[]> } | null>(null);
let regionLoadPromise: Promise<void> | null = null;
function ensureRegionData() {
  if (regionData.value || regionLoadPromise) return regionLoadPromise;
  regionLoadPromise = (async () => {
    const [p, c, a] = await Promise.all([
      import("province-city-china/dist/province.json"),
      import("province-city-china/dist/city.json"),
      import("province-city-china/dist/area.json"),
    ]);
    const provinces = (p as any).default as RegionRow[];
    const cities = new Map<string, { code: string; name: string }[]>();
    for (const row of (c as any).default as RegionRow[]) {
      const list = cities.get(row.province) || [];
      list.push({ code: row.city || "01", name: row.name });
      cities.set(row.province, list);
    }
    for (const prov of provinces) {
      if (MUNICIPALITIES.has(prov.name)) cities.set(prov.province, [{ code: "01", name: prov.name }]);
    }
    const districts = new Map<string, string[]>();
    for (const row of (a as any).default as RegionRow[]) {
      const key = `${row.province}:${row.city}`;
      const list = districts.get(key) || [];
      list.push(row.name);
      districts.set(key, list);
    }
    regionData.value = { provinces, cities, districts };
  })();
  return regionLoadPromise;
}
function citiesOf(provIdx: number): { code: string; name: string }[] {
  const d = regionData.value;
  const p = d?.provinces[provIdx];
  if (!d || !p) return [{ code: "01", name: "北京市" }];
  return d.cities.get(p.province) || [{ code: "01", name: p.name }];
}
function districtsOf(provIdx: number, cityCode: string): string[] {
  const d = regionData.value;
  const p = d?.provinces[provIdx];
  if (!d || !p) return ["北京市"];
  return d.districts.get(`${p.province}:${cityCode}`) || [p.name];
}
function cityShort(name: string): string {
  if (name.includes("直辖县级行政区划")) return "省直辖";
  return name.replace(/市$/, "");
}

const birthRegionIndex = ref<[number, number, number]>([0, 0, 0]);
const birthRegionRange = computed(() => {
  const provNames = regionData.value?.provinces.map(p => p.name) || ["北京市"];
  const cities = citiesOf(birthRegionIndex.value[0]);
  const c = cities[Math.min(birthRegionIndex.value[1], cities.length - 1)];
  return [provNames, cities.map(x => cityShort(x.name)), districtsOf(birthRegionIndex.value[0], c.code)];
});
const birthRegionValue = computed(() => [
  birthRegionIndex.value[0],
  Math.min(birthRegionIndex.value[1], birthRegionRange.value[1].length - 1),
  Math.min(birthRegionIndex.value[2], birthRegionRange.value[2].length - 1),
]);
function onBirthRegionColumn(e: any) {
  const { column, value } = e.detail;
  const i = birthRegionIndex.value;
  birthRegionIndex.value = column === 0 ? [Number(value), 0, 0] : column === 1 ? [i[0], Number(value), 0] : [i[0], i[1], Number(value)];
}
function onBirthRegionConfirm(e: any) {
  const v = (e.detail?.value || birthRegionValue.value) as number[];
  const cities = citiesOf(Number(v[0]));
  const c = cities[Math.min(Number(v[1]), cities.length - 1)];
  const districts = districtsOf(Number(v[0]), c.code);
  const d = districts[Math.min(Number(v[2]), districts.length - 1)];
  const direct = c.name.includes("直辖县级行政区划");
  form.city = direct ? d : `${c.name}${d}`;
  form.regionLabel = direct ? d : `${cityShort(c.name)} · ${d}`;
  manualCity.value = "";
  manualGeo.value = null;
  flashPick("region");
}

const resRegionIndex = ref<[number, number, number]>([0, 0, 0]);
const resRegionRange = computed(() => {
  const provNames = regionData.value?.provinces.map(p => p.name) || ["北京市"];
  const cities = citiesOf(resRegionIndex.value[0]);
  const c = cities[Math.min(resRegionIndex.value[1], cities.length - 1)];
  return [provNames, cities.map(x => cityShort(x.name)), districtsOf(resRegionIndex.value[0], c.code)];
});
const resRegionValue = computed(() => [
  resRegionIndex.value[0],
  Math.min(resRegionIndex.value[1], resRegionRange.value[1].length - 1),
  Math.min(resRegionIndex.value[2], resRegionRange.value[2].length - 1),
]);
function onResRegionColumn(e: any) {
  const { column, value } = e.detail;
  const i = resRegionIndex.value;
  resRegionIndex.value = column === 0 ? [Number(value), 0, 0] : column === 1 ? [i[0], Number(value), 0] : [i[0], i[1], Number(value)];
}
function onResRegionConfirm(e: any) {
  const v = (e.detail?.value || resRegionValue.value) as number[];
  const cities = citiesOf(Number(v[0]));
  const c = cities[Math.min(Number(v[1]), cities.length - 1)];
  const districts = districtsOf(Number(v[0]), c.code);
  const d = districts[Math.min(Number(v[2]), districts.length - 1)];
  const direct = c.name.includes("直辖县级行政区划");
  form.residenceCity = direct ? d : `${c.name}${d}`;
  form.residenceLabel = direct ? d : `${cityShort(c.name)} · ${d}`;
  flashPick("residence");
}
function onTz(e: any) {
  form.tz = tzOptions[Number(e.detail.value)] || form.tz;
}
function toggleSameAsBirth() {
  sameAsBirth.value = !sameAsBirth.value;
  if (sameAsBirth.value) {
    form.residenceCity = "";
    form.residenceLabel = "";
  }
}

// 1986–1991 年中国夏令时窗口（4 月中 ~ 10 月中）：这段日期出生要问一句钟表时间
const dstAsk = computed(() => {
  if (!form.date || form.time_unknown) return false;
  const [y, m] = form.date.split("-").map(Number);
  return y >= 1986 && y <= 1991 && m >= 4 && m <= 10;
});

// 选择确认反馈：日期/时间/城市选完后卡片短暂点亮，给「被记下了」的感觉
const justPicked = ref("");
let pickTimer: ReturnType<typeof setTimeout> | null = null;
function flashPick(key: "date" | "time" | "region" | "residence") {
  justPicked.value = key;
  if (pickTimer) clearTimeout(pickTimer);
  pickTimer = setTimeout(() => { justPicked.value = ""; }, 900);
}

// awakening：星灵找到的瞬间，星轮定格 + 星光扩散
const awakeFound = computed(() => stage.value === "awakening" && !!recommendedSpirit.value);

function prevRegisterStep() {
  error.value = "";
  registerStep.value = Math.max(1, registerStep.value - 1);
}

function nextRegisterStep() {
  error.value = "";
  if (registerStep.value === 1 && !form.name.trim()) {
    error.value = "先告诉星灵怎么称呼你";
    return;
  }
  if (registerStep.value === 2 && !form.date) {
    error.value = "需要选择你来到世界的日期";
    return;
  }
  if (registerStep.value === 3 && !form.time_unknown && !form.time) {
    error.value = "选择出生时间，或告诉星灵你不确定";
    return;
  }
  if (registerStep.value === 4 && !form.city && !manualCity.value.trim()) {
    error.value = "选择或输入一个出生城市";
    return;
  }
  if (registerStep.value < 5) {
    registerStep.value += 1;
    return;
  }
  void enterGarden();
}

async function enterGarden() {
  if (!form.name.trim()) return (error.value = "先告诉花园你的名字");
  if (!form.date) return (error.value = "需要出生日期");
  if (!form.time_unknown && !form.time) return (error.value = "需要出生时间（越精确越好）");
  busy.value = true;
  error.value = "";
  try {
    let time = form.time_unknown ? "12:00" : form.time;
    // 夏令时钟表时间 → 标准时间（拨回 1 小时），后端按标准时区换算 UTC
    if (form.dst === "dst" && !form.time_unknown && time) {
      const [h, m] = time.split(":").map(Number);
      time = `${String((h + 23) % 24).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
    }
    const overseas = !!(manualCity.value.trim() && manualGeo.value);
    const city = overseas ? manualCity.value.trim() : (form.city || "上海");
    const residence = sameAsBirth.value ? city : (form.residenceCity || city);
    const person = await api.createPerson({
      name: form.name.trim(),
      gender: form.gender || undefined,
      birth: {
        datetime_local: `${form.date}T${time}:00`,
        location: overseas
          ? {
              place_name: city,
              latitude: manualGeo.value!.lat,
              longitude: manualGeo.value!.lon,
              timezone_name: TZ_IANA[manualGeo.value!.tz] || "Asia/Tokyo",
            }
          : { place_name: city },
        time_known: !form.time_unknown,
      },
      // 现居地/时区：后端 Person 暂无字段，先随请求携带并留存本地，等后端落库
      residence_city: residence,
      timezone_label: form.tz,
    } as any);
    uni.setStorageSync(PERSON_KEY, person.id);
    uni.setStorageSync("gs_residence", residence);
    uni.setStorageSync("gs_timezone", form.tz);
    uni.removeStorageSync(SESSION_KEY);
    savedName.value = person.name;
    maybeSubscribePush(person.id);
    await loadAwakening(person.id);
  } catch (e) {
    error.value = describeError(e);
    stage.value = "register";
  } finally {
    busy.value = false;
  }
}

function enterHomeFromAwakening() {
  stage.value = "garden";
}
function toggleSheet() {
  sheetOpen.value = !sheetOpen.value;
}
function goChat() {
  sheetOpen.value = false;
  uni.navigateTo({ url: "/pages/chat/chat" });
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
.icon-btn { width: 76rpx; height: 76rpx; border-radius: 30rpx; border: 1rpx solid rgba(77, 92, 82, 0.12); background: rgba(255, 255, 255, 0.48); color: inherit; display: flex; align-items: center; justify-content: center; font-size: 30rpx; box-shadow: 0 12rpx 32rpx rgba(35, 40, 34, 0.08); }
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
.register-hero { margin-top: 52rpx; }
.create-chart-screen { position: relative; justify-content: center; overflow: hidden; background: radial-gradient(circle at 50% 12%, rgba(251, 238, 187, 0.36), transparent 26%), radial-gradient(circle at 20% 78%, rgba(180, 195, 255, 0.18), transparent 28%), linear-gradient(180deg, #fbf7ed 0%, #e8ebdf 48%, #d9ddd0 100%); }
.phase-night .create-chart-screen, .chart-drawing-screen { background: radial-gradient(circle at 50% 18%, rgba(239, 213, 139, 0.18), transparent 28%), radial-gradient(circle at 15% 76%, rgba(148, 171, 255, 0.16), transparent 32%), linear-gradient(180deg, #070b17 0%, #111827 54%, #1b211f 100%); color: #fff8eb; }
.chart-orb { position: absolute; inset: 0; pointer-events: none; opacity: 0.95; }
.chart-ring { position: absolute; left: 50%; top: 33%; border-radius: 50%; border: 1rpx solid rgba(101, 117, 104, 0.14); transform: translate(-50%, -50%) rotate(-14deg); }
.chart-ring.r1 { width: 560rpx; height: 560rpx; animation: spin 42s linear infinite; }
.chart-ring.r2 { width: 390rpx; height: 390rpx; border-style: dashed; animation: spin 28s linear reverse infinite; }
.chart-star { position: absolute; color: rgba(198, 165, 82, 0.64); text-shadow: 0 0 26rpx rgba(239, 213, 139, 0.5); animation: welcomeTwinkle 3.4s ease-in-out infinite; }
.chart-star.s1 { left: 16%; top: 22%; font-size: 28rpx; }
.chart-star.s2 { right: 18%; top: 18%; font-size: 22rpx; animation-delay: .8s; }
.chart-star.s3 { right: 24%; bottom: 22%; font-size: 26rpx; animation-delay: 1.6s; }
.create-chart-hero { position: relative; z-index: 1; display: grid; justify-items: center; gap: 16rpx; margin-top: 64rpx; text-align: center; }
.create-sigil { width: 64rpx; height: 64rpx; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff3c4; background: rgba(23, 37, 31, 0.86); box-shadow: 0 18rpx 54rpx rgba(23, 37, 31, 0.2), 0 0 36rpx rgba(239, 213, 139, 0.42); }
.create-title { display: block; font-size: 56rpx; font-weight: 860; letter-spacing: -0.055em; color: #17251f; }
.create-copy { max-width: 520rpx; color: rgba(23, 37, 31, 0.58); font-size: 25rpx; line-height: 1.7; }
.phase-night .create-title, .phase-night .create-copy { color: #fff8eb; }
.question-card { position: relative; z-index: 1; width: 100%; margin-top: 48rpx; padding: 48rpx 36rpx 40rpx; box-sizing: border-box; border-radius: 46rpx; border: 1rpx solid rgba(94, 109, 98, 0.15); background: rgba(255, 253, 247, 0.68); box-shadow: 0 28rpx 82rpx rgba(36, 39, 31, 0.14), inset 0 1rpx rgba(255, 255, 255, 0.74); backdrop-filter: blur(24rpx); }
.phase-night .question-card { background: rgba(255, 248, 235, 0.09); border-color: rgba(255, 255, 255, 0.13); box-shadow: 0 28rpx 82rpx rgba(0, 0, 0, 0.28); }
.spirit-says { display: block; white-space: pre-line; text-align: center; font-size: 36rpx; line-height: 1.45; font-weight: 830; letter-spacing: -0.035em; color: #17251f; }
.question-hint { display: block; margin-top: 22rpx; text-align: center; font-size: 23rpx; line-height: 1.6; color: rgba(23, 37, 31, 0.52); }
.phase-night .spirit-says { color: #fff8eb; }
.phase-night .question-hint { color: rgba(255, 248, 235, 0.62); }
.answer-block { margin-top: 46rpx; display: grid; gap: 20rpx; }
.answer-input { width: 100%; min-height: 104rpx; border-radius: 38rpx; border: 1rpx solid rgba(77, 92, 82, 0.14); background: rgba(255, 255, 255, 0.55); padding: 0 30rpx; box-sizing: border-box; color: #17251f; font-size: 30rpx; text-align: center; }
.name-input { font-size: 34rpx; font-weight: 760; letter-spacing: 0.04em; }
.field-note { display: block; text-align: center; color: rgba(23, 37, 31, 0.5); font-size: 22rpx; line-height: 1.6; }
.date-picker-card, .time-picker-card { min-height: 104rpx; border-radius: 42rpx; border: 1rpx solid rgba(77, 92, 82, 0.14); background: rgba(255, 255, 255, 0.56); display: flex; align-items: center; justify-content: center; gap: 12rpx; }
.date-part { font-size: 44rpx; font-weight: 860; color: #17251f; letter-spacing: -0.035em; }
.date-part.year { min-width: 108rpx; text-align: right; }
.date-unit, .date-placeholder { font-size: 24rpx; color: rgba(23, 37, 31, 0.52); }
.time-picker-card text { font-size: 48rpx; font-weight: 860; letter-spacing: 0.08em; color: #17251f; }
.time-picker-card.muted text { font-size: 32rpx; letter-spacing: 0; color: rgba(23, 37, 31, 0.46); }
.unknown-pill { justify-self: center; margin-top: 4rpx; border-radius: 999rpx; padding: 18rpx 24rpx; background: rgba(239, 213, 139, 0.16); border: 1rpx solid rgba(239, 213, 139, 0.28); color: rgba(23, 37, 31, 0.64); font-size: 23rpx; }
.unknown-pill.active { background: rgba(23, 37, 31, 0.86); color: #fff5dc; box-shadow: 0 14rpx 36rpx rgba(23, 37, 31, 0.18); }
.search-shell { min-height: 104rpx; border-radius: 32rpx; border: 1rpx solid rgba(77, 92, 82, 0.14); background: rgba(255, 255, 255, 0.55); display: flex; align-items: center; padding: 0 28rpx; gap: 14rpx; }
.search-icon { color: rgba(23, 37, 31, 0.38); font-size: 30rpx; }
.phase-night .search-icon { color: rgba(255, 248, 235, 0.4); }
/* 行内透明输入：不挂 answer-input，避免暗色覆盖把内层染出第二层边框 */
.city-input { flex: 1; min-height: 88rpx; border: 0; background: transparent; color: inherit; font-size: 28rpx; text-align: left; padding: 0; }
.create-actions { display: flex; grid-template-columns: auto 1fr; gap: 18rpx; align-items: center; justify-content: center; }
.create-actions .primary-btn, .create-actions .secondary-btn { margin-top: 0; }
.back-btn { min-width: 168rpx; padding-left: 22rpx; padding-right: 22rpx; }
.create-next { min-height: 60rpx; border-radius: 20rpx; }
.create-error { text-align: center; }
.create-progress { display: flex; justify-content: center; gap: 12rpx; margin-top: 36rpx; }
.create-progress .progress-dot { width: 12rpx; height: 12rpx; background: rgba(23, 37, 31, 0.18); transition: all .28s ease; }
.create-progress .progress-dot.on { width: 12rpx; background: #17251f; box-shadow: 0 0 20rpx rgba(239, 213, 139, 0.55); }
.phase-night .answer-input, .phase-night .date-picker-card, .phase-night .time-picker-card, .phase-night .search-shell { background: rgba(255, 255, 255, 0.08); border-color: rgba(255, 255, 255, 0.13); color: #fff8eb; }
.phase-night .date-part, .phase-night .time-picker-card text { color: #fff8eb; }
.phase-night .date-unit, .phase-night .date-placeholder, .phase-night .field-note, .phase-night .unknown-pill { color: rgba(255, 248, 235, 0.62); }
.phase-night .create-progress .progress-dot { background: rgba(255, 248, 235, 0.22); }
.phase-night .create-progress .progress-dot.on { background: #f3dfaa; }
.hero-title, .awake-title, .home-title { display: block; white-space: pre-line; font-weight: 800; letter-spacing: -0.055em; line-height: 1.14; }
.hero-title { margin-top: 22rpx; font-size: 64rpx; }
.hero-copy, .card-copy, .home-copy { display: block; margin-top: 18rpx; color: rgba(23, 37, 31, 0.62); font-size: 25rpx; line-height: 1.85; }
.phase-night .hero-copy, .phase-night .card-copy, .phase-night .home-copy { color: rgba(255, 248, 235, 0.66); }
.seed-wrap { height: 210rpx; display: flex; align-items: center; justify-content: center; margin: 26rpx 0 8rpx; }
.seed { width: 150rpx; height: 150rpx; border-radius: 44% 56% 50% 50%; background: radial-gradient(circle at 35% 24%, #fff, transparent 24%), linear-gradient(145deg, #d9d0f0, #efd58b 72%); box-shadow: inset -16rpx -20rpx 34rpx rgba(110, 94, 130, 0.12), 0 32rpx 80rpx rgba(128, 107, 67, 0.2); animation: float 5.6s ease-in-out infinite; }
.card { border: 1rpx solid rgba(77, 92, 82, 0.14); background: rgba(255, 253, 247, 0.74); backdrop-filter: blur(20rpx); border-radius: 40rpx; box-shadow: 0 22rpx 70rpx rgba(36, 39, 31, 0.15); }
.phase-night .card { background: rgba(255, 248, 235, 0.1); border-color: rgba(255, 255, 255, 0.13); }
.form-card { padding: 34rpx; }
.step-label, .mini-label, .letter-k { display: block; font-size: 19rpx; letter-spacing: 0.16em; color: rgba(23, 37, 31, 0.38); font-weight: 900; text-transform: uppercase; }
.card-title { display: block; margin: 12rpx 0 6rpx; font-size: 42rpx; font-weight: 800; letter-spacing: -0.035em; }
.field { margin-top: 24rpx; }
.field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 18rpx; }
.label { display: block; margin-bottom: 10rpx; color: rgba(23, 37, 31, 0.62); font-size: 23rpx; }
.input { min-height: 92rpx; border-radius: 34rpx; border: 1rpx solid rgba(77, 92, 82, 0.14); background: rgba(255, 255, 255, 0.56); padding: 0 28rpx; color: #17251f; font-size: 28rpx; display: flex; align-items: center; box-sizing: border-box; }
.input.muted { color: rgba(23, 37, 31, 0.5); }
.unknown-row { display: flex; align-items: center; gap: 12rpx; margin-top: 18rpx; color: rgba(23, 37, 31, 0.62); font-size: 24rpx; }
.privacy-row { display: flex; gap: 14rpx; align-items: flex-start; margin-top: 24rpx; }
.privacy-mark { color: #efd58b; }
.privacy-text { color: rgba(23, 37, 31, 0.62); font-size: 21rpx; line-height: 1.6; }
.primary-btn, .secondary-btn { border: 0; border-radius: 20rpx; padding: 20rpx 26rpx; font-size: 25rpx; font-weight: 700; line-height: 1; min-height: 80rpx; box-sizing: border-box; display: flex; align-items: center; justify-content: center; }
.primary-btn { margin-top: 28rpx; background: linear-gradient(180deg, #6c9179 0%, #5f826c 100%); color: #fff9ec; box-shadow: 0 16rpx 40rpx rgba(95, 130, 108, 0.32); }
.secondary-btn { margin-top: 28rpx; background: rgba(255, 255, 255, 0.42); color: #17251f; border: 1rpx solid rgba(77, 92, 82, 0.14); }
.primary-btn[disabled] { opacity: 0.6; }
.error { display: block; margin-top: 18rpx; color: #b85c54; font-size: 23rpx; line-height: 1.5; }
.progress { display: flex; gap: 10rpx; margin-top: 24rpx; }
.progress-dot { width: 14rpx; height: 14rpx; border-radius: 999rpx; background: rgba(23, 37, 31, 0.14); }
.progress-dot.on { width: 44rpx; background: #efd58b; box-shadow: 0 0 20rpx rgba(240, 213, 139, 0.7); }
.orbit { height: 420rpx; display: flex; align-items: center; justify-content: center; position: relative; margin-top: 76rpx; }
.orbit::before { content: ''; position: absolute; width: 390rpx; height: 390rpx; border-radius: 50%; border: 1rpx dashed rgba(143, 174, 151, 0.36); animation: spin 18s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.spirit-stage { position: relative; border: 1rpx solid rgba(77, 92, 82, 0.14); background: linear-gradient(180deg, rgba(255, 255, 255, 0.42), rgba(255, 255, 255, 0.14)); box-shadow: inset 0 1rpx rgba(255, 255, 255, 0.62), 0 22rpx 56rpx rgba(49, 57, 52, 0.12); display: flex; align-items: center; justify-content: center; overflow: hidden; }
.spirit-stage.large { width: 300rpx; height: 340rpx; border-radius: 72rpx; }
.spirit-stage.small { width: 220rpx; height: 270rpx; border-radius: 58rpx; flex-shrink: 0; }
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
.awake-card { padding: 36rpx; }
.chart-drawing-screen { position: relative; overflow: hidden; justify-content: flex-start; }
.chart-sky { position: absolute; inset: 0; overflow: hidden; pointer-events: none; }
.chart-sky::before { content: ''; position: absolute; inset: 0; background-image: radial-gradient(circle, rgba(255, 248, 235, 0.72) 0 1rpx, transparent 2rpx), radial-gradient(circle, rgba(160, 184, 255, 0.42) 0 1rpx, transparent 2rpx); background-size: 92rpx 92rpx, 138rpx 138rpx; opacity: 0.38; animation: starsDrift 22s linear infinite; }
.drawing-milky { position: absolute; left: -18%; top: 12%; width: 132%; height: 360rpx; transform: rotate(-18deg); background: radial-gradient(ellipse at center, rgba(255, 238, 179, 0.24), rgba(162, 180, 255, 0.12) 35%, transparent 70%); filter: blur(18rpx); animation: galaxyDrift 14s ease-in-out infinite; }
.birth-stream { position: absolute; left: 50%; top: 10%; transform: translateX(-50%); min-width: 180rpx; padding: 14rpx 22rpx; border-radius: 999rpx; border: 1rpx solid rgba(255, 248, 235, 0.12); background: rgba(255, 248, 235, 0.07); color: rgba(255, 248, 235, 0.62); text-align: center; font-size: 21rpx; animation: streamIntoChart 4.8s ease-in-out infinite; }
.stream-time { animation-delay: .9s; top: 17%; }
.stream-place { animation-delay: 1.8s; top: 24%; }
.draw-glyph { position: absolute; color: rgba(255, 241, 189, 0.86); text-shadow: 0 0 30rpx rgba(239, 213, 139, 0.72); font-size: 42rpx; animation: orbitGlyph 8.5s ease-in-out infinite; }
.draw-glyph.sun { left: 18%; top: 34%; }
.draw-glyph.moon { right: 18%; top: 30%; animation-delay: -1.4s; }
.draw-glyph.venus { left: 24%; top: 55%; animation-delay: -2.4s; }
.draw-glyph.saturn { right: 22%; top: 58%; animation-delay: -3.2s; }
.draw-aspect { position: absolute; height: 1rpx; background: linear-gradient(90deg, transparent, rgba(255, 231, 164, 0.45), transparent); transform-origin: center; opacity: 0.62; animation: aspectFlash 4.6s ease-in-out infinite; }
.draw-aspect.a1 { left: 21%; top: 43%; width: 58%; transform: rotate(14deg); }
.draw-aspect.a2 { left: 25%; top: 56%; width: 49%; transform: rotate(-31deg); animation-delay: 1.2s; }
.draw-aspect.a3 { left: 33%; top: 36%; width: 34%; transform: rotate(72deg); animation-delay: 2.1s; }
.chart-orbit { height: 500rpx; margin-top: -22rpx; }
.chart-wheel-core { position: absolute; width: 390rpx; height: 390rpx; border-radius: 50%; opacity: 0.72; animation: spin 30s linear infinite; }
.wheel-ring { position: absolute; inset: 0; border-radius: 50%; border: 1rpx solid rgba(255, 248, 235, 0.2); }
.wheel-ring.inner { inset: 86rpx; border-style: dashed; opacity: 0.72; }
.wheel-cross { position: absolute; left: 50%; top: 50%; background: rgba(255, 248, 235, 0.13); transform-origin: center; }
.wheel-cross.h { width: 340rpx; height: 1rpx; margin-left: -170rpx; }
.wheel-cross.v { width: 1rpx; height: 340rpx; margin-top: -170rpx; }
.planet-dot { position: absolute; width: 16rpx; height: 16rpx; border-radius: 50%; background: #f3dfaa; box-shadow: 0 0 24rpx rgba(243, 223, 170, 0.82); }
.planet-dot.p1 { left: 72rpx; top: 92rpx; }
.planet-dot.p2 { right: 80rpx; top: 128rpx; }
.planet-dot.p3 { left: 136rpx; bottom: 60rpx; }
.planet-dot.p4 { right: 118rpx; bottom: 86rpx; }
.chart-spirit { z-index: 2; transform: translateY(44rpx) scale(.74); opacity: 0.9; animation: spiritAwake 5.2s ease-in-out infinite; }
.chart-awake-card { position: relative; z-index: 1; background: rgba(255, 248, 235, 0.1); border-color: rgba(255, 255, 255, 0.14); color: #fff8eb; box-shadow: 0 30rpx 90rpx rgba(0, 0, 0, 0.32); }
.chart-awake-card .awake-title { color: #fff8eb; }
.chart-awake-card .card-copy { color: rgba(255, 248, 235, 0.68); }
.chart-awake-card .step { border-color: rgba(255, 255, 255, 0.12); color: rgba(255, 248, 235, 0.58); }
.chart-awake-card .step text:first-child { color: #fff8eb; }
.found-message { display: grid; gap: 10rpx; margin-top: 26rpx; padding: 22rpx 24rpx; border-radius: 34rpx; background: rgba(255, 248, 235, 0.08); border: 1rpx solid rgba(255, 248, 235, 0.1); }
.found-message text { color: rgba(255, 248, 235, 0.88); font-size: 25rpx; line-height: 1.6; }
@keyframes starsDrift { to { transform: translate3d(-80rpx, 100rpx, 0); } }
@keyframes streamIntoChart { 0%, 100% { opacity: 0; transform: translate(-50%, -24rpx) scale(.92); } 18%, 68% { opacity: 1; } 78% { opacity: 0; transform: translate(-50%, 245rpx) scale(.72); } }
@keyframes orbitGlyph { 50% { transform: translateY(-22rpx) scale(1.08); opacity: 0.72; } }
@keyframes aspectFlash { 0%, 100% { opacity: 0.14; } 45%, 60% { opacity: 0.78; } }
@keyframes spiritAwake { 50% { transform: translateY(28rpx) scale(.78); opacity: 1; } }
.awake-title { margin-top: 14rpx; font-size: 56rpx; }
.steps { display: grid; gap: 14rpx; margin-top: 30rpx; }
.step { display: flex; justify-content: space-between; gap: 18rpx; border-top: 1rpx solid rgba(77, 92, 82, 0.14); padding-top: 18rpx; font-size: 24rpx; color: rgba(23, 37, 31, 0.62); }
.step text:first-child { color: #17251f; font-weight: 760; }
.awake-actions, .home-actions, .letter-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 18rpx; }
.date-row { display: flex; justify-content: space-between; align-items: center; color: rgba(23, 37, 31, 0.62); font-size: 22rpx; margin: 18rpx 0 18rpx; }
.hero-row { display: grid; grid-template-columns: 1fr auto; gap: 24rpx; align-items: end; }
.home-title { margin-top: 16rpx; font-size: 54rpx; }
.home-actions { grid-template-columns: 1fr auto; }
.home-actions .primary-btn, .home-actions .secondary-btn, .letter-actions .primary-btn, .letter-actions .secondary-btn, .awake-actions .primary-btn, .awake-actions .secondary-btn { margin-top: 24rpx; }
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
/* 注册/绘制阶段：与欢迎页同章的深空视觉 */
/* 根节点与内容屏同底渐变，避免 page 级背景在屏幕边缘露出异色断层 */
.stage-register { background: linear-gradient(180deg, #02040d 0%, #060817 42%, #0a0e1d 70%, #04070d 100%); color: #f8f1de; }
.stage-awakening { background: linear-gradient(180deg, #070b17 0%, #111827 54%, #1b211f 100%); color: #fff8eb; }
.stage-register .bg-glow, .stage-awakening .bg-glow { display: none; }
.stage-register > .stars, .stage-awakening > .stars { display: none; }
.stage-register .grain { opacity: 0.055; background-image: radial-gradient(rgba(255, 248, 235, 0.38) 1rpx, transparent 1rpx); background-size: 18rpx 18rpx; }
.stage-register .create-chart-screen { background: radial-gradient(circle at 52% 24%, rgba(119, 105, 189, 0.16), transparent 30%), radial-gradient(circle at 82% 66%, rgba(59, 121, 143, 0.11), transparent 34%), linear-gradient(180deg, #02040d 0%, #060817 42%, #0a0e1d 70%, #04070d 100%); }
.stage-register .chart-ring { border-color: rgba(255, 248, 235, 0.13); }
.register-sky { position: absolute; inset: 0; pointer-events: none; overflow: hidden; }
.register-sky .constellation { opacity: 0.24; }
.register-spirit { position: absolute; right: -10rpx; top: -124rpx; width: 220rpx; height: 270rpx; transform: scale(0.6); transform-origin: top right; z-index: 3; pointer-events: none; }
.register-spirit .spirit-stage { width: 220rpx; height: 270rpx; border-radius: 58rpx; border-color: rgba(255, 248, 224, 0.16); background: radial-gradient(circle at 50% 22%, rgba(255, 255, 255, 0.5), transparent 35%), linear-gradient(180deg, rgba(255, 252, 232, 0.14), rgba(189, 181, 255, 0.07)); box-shadow: inset 0 1rpx rgba(255, 255, 255, 0.26), 0 28rpx 90rpx rgba(3, 7, 24, 0.5), 0 0 52rpx rgba(235, 204, 132, 0.12); backdrop-filter: blur(8rpx); }
.create-chart-screen .primary-btn, .create-chart-screen .secondary-btn, .chart-drawing-screen .primary-btn, .chart-drawing-screen .secondary-btn { display: flex; align-items: center; justify-content: center; background: linear-gradient(180deg, rgba(255, 248, 224, 0.16), rgba(255, 248, 224, 0.06)); border: 1rpx solid rgba(255, 238, 188, 0.32); color: rgba(255, 250, 230, 0.96); box-shadow: 0 22rpx 70rpx rgba(0, 0, 0, 0.26), 0 0 48rpx rgba(242, 205, 120, 0.13), inset 0 1rpx rgba(255, 255, 255, 0.14); }
.create-chart-screen .secondary-btn, .chart-drawing-screen .secondary-btn { background: rgba(255, 248, 224, 0.07); border: 1rpx solid rgba(255, 255, 255, 0.12); color: rgba(255, 248, 224, 0.72); box-shadow: none; }
.create-actions .primary-btn:first-child:last-child { grid-column: 1 / -1; }
.prompt-swap { animation: stepIn 0.5s cubic-bezier(0.2, 0.8, 0.2, 1) both; }
.answer-block { animation: stepIn 0.5s 0.06s cubic-bezier(0.2, 0.8, 0.2, 1) both; }
.answer-block > view { display: grid; gap: 52rpx; }
@keyframes stepIn { from { opacity: 0; transform: translateY(24rpx) scale(0.99); } }
.create-actions .primary-btn, .create-actions .secondary-btn, .awake-actions .primary-btn, .awake-actions .secondary-btn { min-height: 60rpx; }
.date-picker-card, .time-picker-card { transition: border-color 0.35s ease, box-shadow 0.35s ease; }
.date-picker-card.lit, .time-picker-card.lit { border-color: rgba(239, 213, 139, 0.55); box-shadow: 0 0 34rpx rgba(239, 213, 139, 0.22), inset 0 0 26rpx rgba(239, 213, 139, 0.1); }
.chart-orbit.found .chart-wheel-core { animation-play-state: paused; }
.burst-ring { position: absolute; width: 390rpx; height: 390rpx; border-radius: 50%; border: 2rpx solid rgba(243, 223, 170, 0.85); box-shadow: 0 0 44rpx rgba(243, 223, 170, 0.32); animation: burstRing 1.8s cubic-bezier(0.2, 0.8, 0.3, 1) forwards; pointer-events: none; }
.burst-ring.r-two { animation-delay: 0.35s; }
@keyframes burstRing { 0% { transform: scale(0.55); opacity: 0.95; } 100% { transform: scale(2.3); opacity: 0; } }
.found-message { transition: box-shadow 0.6s ease; }
.found-message.lit { animation: foundGlow 1.4s ease-out both; }
@keyframes foundGlow { 0% { box-shadow: 0 0 0 rgba(243, 223, 170, 0); } 35% { box-shadow: 0 0 46rpx rgba(243, 223, 170, 0.3); border-color: rgba(243, 223, 170, 0.35); } 100% { box-shadow: 0 0 0 rgba(243, 223, 170, 0); } }
.gender-row { display: flex; justify-content: center; gap: 20rpx;margin-bottom: 20rpx; }
.gender-pill { border-radius: 999rpx; border: 1rpx solid rgba(77, 92, 82, 0.14); background: rgba(255, 255, 255, 0.42); padding: 16rpx 34rpx; font-size: 23rpx; color: rgba(23, 37, 31, 0.6); }
.gender-pill.on { background: rgba(23, 37, 31, 0.86); border-color: transparent; color: #fff5dc; box-shadow: 0 12rpx 32rpx rgba(23, 37, 31, 0.2); }
.phase-night .gender-pill { background: rgba(255, 248, 235, 0.07); border-color: rgba(255, 255, 255, 0.12); color: rgba(255, 248, 235, 0.62); }
.phase-night .gender-pill.on { background: rgba(243, 223, 170, 0.92); color: #17251f; }
.dst-ask { display: grid; gap: 12rpx; margin-top: 6rpx; padding: 20rpx 22rpx; border-radius: 26rpx; border: 1rpx solid rgba(239, 213, 139, 0.3); background: rgba(239, 213, 139, 0.1); }
.dst-title { font-size: 22rpx; font-weight: 700; color: rgba(23, 37, 31, 0.78); }
.phase-night .dst-title { color: rgba(255, 248, 235, 0.85); }
.dst-options { display: flex; gap: 12rpx; }
.dst-pill { flex: 1; text-align: center; border-radius: 18rpx; border: 1rpx solid rgba(77, 92, 82, 0.14); background: rgba(255, 255, 255, 0.42); padding: 16rpx 0; font-size: 22rpx; color: rgba(23, 37, 31, 0.62); }
.dst-pill.on { background: rgba(23, 37, 31, 0.86); border-color: transparent; color: #fff5dc; }
.phase-night .dst-pill { background: rgba(255, 248, 235, 0.07); border-color: rgba(255, 255, 255, 0.12); color: rgba(255, 248, 235, 0.62); }
.phase-night .dst-pill.on { background: rgba(243, 223, 170, 0.92); color: #17251f; }
.dst-note { font-size: 20rpx; color: rgba(23, 37, 31, 0.5); }
.phase-night .dst-note { color: rgba(255, 248, 235, 0.5); }
.region-text { font-size: 30rpx; letter-spacing: 0.02em; line-height: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
.residence-answer { display: grid; gap: 16rpx; }
.same-as-birth { border-radius: 26rpx; border: 1rpx solid rgba(239, 213, 139, 0.32); background: rgba(239, 213, 139, 0.12); padding: 22rpx 24rpx; font-size: 24rpx; color: rgba(23, 37, 31, 0.72); text-align: center; }
.same-as-birth.on { background: rgba(23, 37, 31, 0.86); border-color: transparent; color: #fff5dc; box-shadow: 0 14rpx 36rpx rgba(23, 37, 31, 0.18); }
.phase-night .same-as-birth { color: rgba(255, 248, 235, 0.7); }
.phase-night .same-as-birth.on { background: rgba(243, 223, 170, 0.92); color: #17251f; }
.tz-card { min-height: 104rpx; border-radius: 30rpx; border: 1rpx solid rgba(77, 92, 82, 0.14); background: rgba(255, 255, 255, 0.42); display: flex; align-items: center; justify-content: space-between; padding: 0 28rpx; }
.phase-night .tz-card { background: rgba(255, 248, 235, 0.07); border-color: rgba(255, 255, 255, 0.12); }
.tz-label { font-size: 23rpx; color: rgba(23, 37, 31, 0.55); }
.phase-night .tz-label { color: rgba(255, 248, 235, 0.55); }
.tz-value { font-size: 30rpx; font-weight: 800; letter-spacing: 0.04em; color: #17251f; }
.phase-night .tz-value { color: #fff8eb; }
/* 序章跳过：底部居中胶囊，2.5s 后淡入，视觉权重高于旧顶部小字但不抢主视觉 */
.welcome-skip-fab { position: absolute; left: 50%; bottom: calc(env(safe-area-inset-bottom, 0rpx) + 44rpx); transform: translateX(-50%); z-index: 4; display: flex; align-items: center; gap: 10rpx; padding: 20rpx 40rpx; border-radius: 999rpx; border: 1rpx solid rgba(255, 238, 188, 0.32); background: rgba(255, 248, 224, 0.07); backdrop-filter: blur(14rpx); color: rgba(255, 248, 224, 0.82); font-size: 23rpx; letter-spacing: 0.08em; animation: skipFabIn 0.8s 2.5s cubic-bezier(0.2, 0.8, 0.2, 1) both; }
.skip-star { color: #ffe7a3; font-size: 20rpx; text-shadow: 0 0 16rpx rgba(255, 231, 163, 0.7); }
@keyframes skipFabIn { from { opacity: 0; transform: translate(-50%, 18rpx); } to { opacity: 1; transform: translate(-50%, 0); } }
/* 时间步显式二选一 */
.time-confirm-row { display: flex; justify-content: center; gap: 16rpx; }
.confirm-pill { flex: 1; text-align: center; border-radius: 18rpx; border: 1rpx solid rgba(77, 92, 82, 0.14); background: rgba(255, 255, 255, 0.42); padding: 18rpx 0; font-size: 23rpx; color: rgba(23, 37, 31, 0.62); }
.confirm-pill.on { background: rgba(23, 37, 31, 0.86); border-color: transparent; color: #fff5dc; box-shadow: 0 12rpx 32rpx rgba(23, 37, 31, 0.2); }
.phase-night .confirm-pill { background: rgba(255, 248, 235, 0.07); border-color: rgba(255, 255, 255, 0.12); color: rgba(255, 248, 235, 0.62); }
.phase-night .confirm-pill.on { background: rgba(243, 223, 170, 0.92); color: #17251f; }
/* 回到星空 */
.back-to-sky { display: block; margin-top: 26rpx; text-align: center; font-size: 22rpx; color: rgba(23, 37, 31, 0.44); padding: 8rpx; }
.phase-night .back-to-sky { color: rgba(255, 248, 235, 0.46); }
/* 海外坐标弹框 */
.overseas-trigger { width: 100%; margin-top: 0; }
.overseas-sheet { position: fixed; z-index: 31; left: 24rpx; right: 24rpx; bottom: 32rpx; border-radius: 46rpx; padding: 20rpx 30rpx 30rpx; background: rgba(13, 18, 34, 0.97); color: #fff8eb; box-shadow: 0 24rpx 72rpx rgba(0, 0, 0, 0.4); backdrop-filter: blur(24rpx); display: grid; gap: 16rpx; }
.os-title { font-size: 32rpx; font-weight: 800; }
.os-name { min-height: 92rpx; text-align: left; background: rgba(255, 248, 235, 0.07); border-color: rgba(255, 255, 255, 0.12); color: #fff8eb; }
.os-row { min-height: 92rpx; border-radius: 26rpx; border: 1rpx solid rgba(255, 255, 255, 0.12); background: rgba(255, 248, 235, 0.07); display: flex; align-items: center; justify-content: space-between; padding: 0 28rpx; }
.os-label { font-size: 23rpx; color: rgba(255, 248, 235, 0.55); }
.os-value { font-size: 28rpx; font-weight: 700; line-height: 1; color: #fff8eb; letter-spacing: 0.02em; }
.os-note { font-size: 20rpx; color: rgba(255, 248, 235, 0.5); line-height: 1.6; }
.overseas-sheet .sheet-actions { margin-top: 6rpx; }
/* 首页 · 全屏晨雾花园（V2 demo 化）：场景铺满整页，元素长在场景上 */
.stage-garden { background: linear-gradient(180deg, #a8c9c5 0%, #c8d8c4 38%, #d8d3b4 62%, #78966f 100%); color: #203d32; }
.stage-garden.phase-dusk { background: linear-gradient(180deg, #788d91 0%, #b9b99f 40%, #d2c7a9 64%, #788c70 100%); }
.stage-garden.phase-night { background: radial-gradient(circle at 68% 16%, rgba(240, 210, 139, 0.1), transparent 26%), linear-gradient(180deg, #0b1e26 0%, #10332d 48%, #1b4435 78%, #102a22 100%); color: #f2eee0; }
.stage-garden .bg-glow, .stage-garden > .stars { display: none; }
.stage-garden .eyebrow { color: rgba(35, 54, 51, 0.55); }
.stage-garden .app-title { color: #263d38; }
.stage-garden .icon-btn { border-color: rgba(40, 61, 53, 0.12); background: rgba(255, 255, 255, 0.18); color: #35483f; }
.stage-garden.phase-night .eyebrow { color: rgba(255, 248, 235, 0.45); }
.stage-garden.phase-night .app-title { color: #f2eee0; }
.stage-garden.phase-night .icon-btn { border-color: rgba(255, 248, 235, 0.14); background: rgba(255, 248, 235, 0.08); color: rgba(255, 248, 235, 0.7); }
.scene { position: absolute; inset: 0; overflow: hidden; pointer-events: none; z-index: 0; }
.scene-glow { position: absolute; width: 380rpx; height: 380rpx; border-radius: 50%; background: rgba(255, 237, 181, 0.4); filter: blur(56rpx); right: -20rpx; top: 60rpx; }
.phase-night .scene-glow { background: rgba(233, 216, 158, 0.14); }
.scene-moon { position: absolute; right: 100rpx; top: 150rpx; width: 100rpx; height: 100rpx; border-radius: 50%; background: #f7efcf; box-shadow: 0 0 90rpx rgba(255, 240, 183, 0.45); }
.phase-night .scene-moon { background: #e6e0c4; }
.scene-cloud { position: absolute; background: rgba(255, 255, 255, 0.18); filter: blur(36rpx); border-radius: 50%; animation: cloudDrift 46s ease-in-out infinite; }
.scene-cloud.a { width: 420rpx; height: 110rpx; left: -130rpx; top: 270rpx; }
.scene-cloud.b { width: 360rpx; height: 90rpx; right: -120rpx; top: 470rpx; animation-delay: -18s; animation-duration: 58s; }
.phase-night .scene-cloud { background: rgba(255, 248, 235, 0.06); }
.scene-hill { position: absolute; width: 124%; border-radius: 50% 50% 0 0 / 25% 25% 0 0; }
.scene-hill.back { bottom: 14%; height: 29%; background: #a7b89b; opacity: 0.7; left: -20%; }
.scene-hill.front { bottom: 0; height: 36%; background: linear-gradient(180deg, #9eae8d, #687f69); }
.phase-night .scene-hill.back { background: #24463a; opacity: 0.85; }
.phase-night .scene-hill.front { background: linear-gradient(180deg, #2c5243, #1d3a2e); }
.scene-flower { position: absolute; bottom: 24%; font-size: 34rpx; opacity: 0.75; }
.scene-flower.f1 { left: 13%; }
.scene-flower.f2 { left: 72%; bottom: 28%; }
.scene-flower.f3 { left: 88%; bottom: 19%; font-size: 24rpx; }
.garden-screen { position: relative; z-index: 1; display: flex; flex-direction: column; min-height: calc(100vh - 196rpx); }
.garden-date-row { display: flex; justify-content: space-between; align-items: center; }
.garden-date { font-size: 22rpx; letter-spacing: 0.1em; color: rgba(35, 54, 51, 0.7); }
.garden-trust { font-size: 20rpx; color: rgba(35, 54, 51, 0.5); }
.phase-night .garden-date { color: rgba(255, 248, 235, 0.6); }
.phase-night .garden-trust { color: rgba(255, 248, 235, 0.45); }
.garden-greeting { margin-top: 20rpx; }
.greeting-main { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 54rpx; font-weight: 600; letter-spacing: -0.02em; line-height: 1.4; color: #263d38; }
.greeting-sub { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 54rpx; font-weight: 600; letter-spacing: -0.02em; line-height: 1.4; color: #263d38; }
.phase-night .greeting-main, .phase-night .greeting-sub { color: #f2eee0; }
.garden-context-row { display: flex; flex-wrap: wrap; gap: 12rpx; margin-top: 22rpx; }
.context-chip { display: inline-flex; align-items: center; gap: 8rpx; min-height: 44rpx; padding: 0 16rpx; border-radius: 999rpx; background: rgba(255, 255, 255, 0.18); border: 1rpx solid rgba(255, 255, 255, 0.24); color: rgba(32, 61, 50, 0.7); font-size: 20rpx; }
.context-chip.warm { background: rgba(240, 210, 139, 0.18); border-color: rgba(240, 210, 139, 0.35); color: #735b29; }
.context-dot { width: 10rpx; height: 10rpx; border-radius: 50%; background: #96bd83; box-shadow: 0 0 12rpx rgba(150, 189, 131, 0.75); }
.phase-night .context-chip { background: rgba(255, 248, 235, 0.07); border-color: rgba(255, 248, 235, 0.13); color: rgba(255, 248, 235, 0.68); }
.phase-night .context-chip.warm { background: rgba(240, 210, 139, 0.13); border-color: rgba(240, 210, 139, 0.3); color: #f0d28b; }
.spirit-buddy { margin-top: 36rpx; display: flex; align-items: center; gap: 24rpx; }
.spirit-orb { width: 112rpx; height: 112rpx; flex-shrink: 0; border-radius: 50%;
  background: radial-gradient(circle at 38% 34%, #fff 0 4%, transparent 5%), radial-gradient(circle at 62% 34%, #fff 0 4%, transparent 5%), radial-gradient(circle at 50% 48%, rgba(255, 255, 255, 0.8) 0 17%, transparent 18%), radial-gradient(circle at 50% 65%, rgba(224, 235, 222, 0.8) 0 28%, transparent 29%), linear-gradient(145deg, #e8ece0, #879f94);
  box-shadow: 0 0 0 2rpx rgba(255, 255, 255, 0.3), 0 20rpx 70rpx rgba(45, 68, 58, 0.2); animation: orbBreath 4.6s ease-in-out infinite; transition: transform 0.18s ease; overflow: hidden; }
.spirit-buddy:active .spirit-orb { transform: scale(0.9); }
.spirit-buddy-name { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 32rpx; font-weight: 600; color: #263d38; }
.spirit-buddy-line { display: block; margin-top: 8rpx; font-size: 22rpx; color: rgba(38, 58, 52, 0.68); }
.phase-night .spirit-buddy-name { color: #f2eee0; }
.phase-night .spirit-buddy-line { color: rgba(255, 248, 235, 0.6); }
.garden-quote { margin-top: 36rpx; font-family: Georgia, "Noto Serif SC", serif; font-size: 40rpx; line-height: 1.75; color: #253c37; white-space: pre-line; }
.phase-night .garden-quote { color: rgba(242, 238, 224, 0.92); }
.chat-cta { margin-top: 30rpx; align-self: flex-start; border: 0; border-radius: 22rpx; padding: 20rpx 34rpx; min-height: 80rpx; box-sizing: border-box; display: flex; align-items: center; background: rgba(49, 72, 63, 0.82); color: #f2eee0; font-size: 25rpx; font-weight: 600; box-shadow: 0 16rpx 50rpx rgba(36, 56, 48, 0.18); }
.phase-night .chat-cta { background: rgba(243, 223, 170, 0.92); color: #1d3a2e; }
.weather-card { margin-top: auto; border: 1rpx solid rgba(255, 255, 255, 0.25); background: rgba(245, 247, 236, 0.25); backdrop-filter: blur(18rpx); border-radius: 32rpx; padding: 30rpx; display: flex; justify-content: space-between; gap: 24rpx; }
.phase-night .weather-card { background: rgba(20, 34, 30, 0.5); border-color: rgba(255, 248, 235, 0.12); }
.weather-main { min-width: 0; }
.weather-label { display: block; font-size: 19rpx; letter-spacing: 0.15em; color: rgba(35, 54, 51, 0.65); font-weight: 800; }
.phase-night .weather-label { color: rgba(255, 248, 235, 0.5); }
.weather-strong { display: block; margin-top: 10rpx; font-family: Georgia, "Noto Serif SC", serif; font-size: 36rpx; font-weight: 600; color: #30453e; }
.phase-night .weather-strong { color: #f2eee0; }
.weather-desc { display: block; margin-top: 8rpx; font-size: 22rpx; line-height: 1.6; color: #5e7069; }
.phase-night .weather-desc { color: rgba(255, 248, 235, 0.55); }
.weather-link { display: inline-block; margin-top: 14rpx; font-size: 22rpx; color: #3d5a4c; text-decoration: underline; }
.phase-night .weather-link { color: rgba(243, 223, 170, 0.85); }
.weather-side { display: flex; flex-direction: column; align-items: flex-end; justify-content: space-between; flex-shrink: 0; }
.weather-icon { font-size: 48rpx; color: #30453e; }
.phase-night .weather-icon { color: rgba(255, 248, 235, 0.7); }
.mini-stars { display: flex; gap: 8rpx; }
.mini-star { width: 10rpx; height: 10rpx; border-radius: 50%; background: rgba(217, 197, 142, 0.35); }
.mini-star.lit { background: #d9c58e; box-shadow: 0 0 16rpx rgba(217, 197, 142, 0.9); }
.dust-band { display: flex; gap: 16rpx; overflow-x: auto; margin-top: 24rpx; padding-bottom: 10rpx; }
.dust-chip { flex-shrink: 0; border: 1rpx solid rgba(255, 255, 255, 0.3); background: rgba(245, 247, 236, 0.28); backdrop-filter: blur(12rpx); border-radius: 999rpx; padding: 16rpx 26rpx; font-size: 22rpx; color: #33503f; }
.phase-night .dust-chip { background: rgba(255, 248, 235, 0.06); border-color: rgba(255, 248, 235, 0.14); color: rgba(255, 248, 235, 0.8); }
.nav-bar { display: none; }
.nav-item { position: relative; display: flex; flex-direction: column; align-items: center; gap: 4rpx; font-size: 20rpx; color: rgba(235, 241, 233, 0.48); }
.nav-item text:first-child { font-size: 30rpx; }
.nav-item.active { background: rgba(255, 255, 255, 0.1); color: #f2eee0; border-radius: 21rpx; }
.nav-item.active text:first-child { filter: drop-shadow(0 0 16rpx rgba(235, 216, 158, 0.7)); }
.nav-badge { position: absolute; top: 2rpx; right: 32rpx; width: 14rpx; height: 14rpx; background: #d66b5f; border-radius: 50%; box-shadow: 0 0 0 6rpx rgba(214, 107, 95, 0.14); }
@keyframes cloudDrift { 50% { transform: translateX(36rpx); } }
@keyframes orbBreath { 50% { transform: translateY(-6rpx) scale(1.03); } }

/* ─────────────────────────────────────────────────────────────
   首页花园态 V3：从“功能仪表盘”切换成“可以回来的地方”
   欢迎/注册态不使用这些选择器，保持原有序章视觉。
   ───────────────────────────────────────────────────────────── */
.stage-garden { padding-bottom: 154rpx; overflow: hidden; }
.stage-garden .scene {
  opacity: 1;
}
.stage-garden .scene::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(233, 245, 244, 0.08) 0%, rgba(249, 239, 205, 0.01) 46%, rgba(71, 117, 76, 0.1) 100%);
  z-index: 1;
}
.stage-garden.phase-morning { background: linear-gradient(180deg, #d7ecea 0%, #f6efd8 58%, #c5dcb8 100%); }
.stage-garden.phase-noon { background: linear-gradient(180deg, #b6e0e8 0%, #f7edc5 55%, #a7ca91 100%); }
.stage-garden.phase-dusk { background: linear-gradient(180deg, #8e91ac 0%, #d5b4a9 52%, #718776 100%); }
.stage-garden.phase-night { background: linear-gradient(180deg, #26354b 0%, #3e5c67 54%, #547765 100%); }
.stage-garden.phase-dusk .scene::before { background: linear-gradient(180deg, rgba(78, 65, 102, 0.28), rgba(242, 190, 147, 0.12) 45%, rgba(45, 71, 58, 0.36)); }
.stage-garden.phase-night .scene::before { background: linear-gradient(180deg, rgba(7, 20, 37, 0.2), rgba(14, 48, 47, 0.08) 48%, rgba(8, 34, 27, 0.18)); }
.stage-garden .scene-cloud,
.stage-garden .scene-hill,
.stage-garden .scene-flower { display: none; }
.stage-garden .scene-glow { z-index: 2; width: 480rpx; height: 480rpx; right: -90rpx; top: 40rpx; background: rgba(255, 230, 165, 0.28); filter: blur(72rpx); }
.stage-garden.phase-night .scene-glow { background: rgba(233, 211, 147, 0.12); }
.stage-garden .scene-moon { z-index: 2; opacity: 0; transition: opacity 0.6s ease; }
.stage-garden.phase-dusk .scene-moon,
.stage-garden.phase-night .scene-moon { opacity: 1; right: 92rpx; top: 158rpx; width: 84rpx; height: 84rpx; background: #fff2c9; box-shadow: 0 0 90rpx rgba(255, 237, 181, 0.48); }
.stage-garden.phase-night .scene-moon { background: #e9e3c7; }

.garden-screen { min-height: calc(100vh - 164rpx); padding-bottom: 18rpx; }
.garden-date-row { align-items: flex-start; }
.garden-phase-label { display: block; font-size: 18rpx; letter-spacing: 0.12em; color: rgba(39, 70, 57, 0.5); }
.garden-date { display: block; margin-top: 7rpx; font-size: 20rpx; letter-spacing: 0.08em; }
.phase-night .garden-phase-label, .phase-night .garden-date, .phase-dusk .garden-phase-label, .phase-dusk .garden-date { color: rgba(255, 247, 231, 0.62); }
.garden-trust { margin-top: 8rpx; padding: 9rpx 16rpx; border-radius: 999rpx; background: rgba(255, 255, 255, 0.2); border: 1rpx solid rgba(255, 255, 255, 0.24); }
.phase-night .garden-trust, .phase-dusk .garden-trust { background: rgba(255, 247, 231, 0.08); border-color: rgba(255, 247, 231, 0.14); color: rgba(255, 247, 231, 0.72); }
.garden-greeting { margin-top: 30rpx; }
.greeting-main { font-size: 48rpx; line-height: 1.28; }
.greeting-sub { margin-top: 2rpx; font-size: 34rpx; line-height: 1.35; opacity: 0.72; }

.garden-spirit-hero { position: relative; margin-top: 22rpx; min-height: 350rpx; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; cursor: pointer; }
.garden-spirit-hero:active .spirit-hero-stage { transform: translateY(5rpx) scale(0.97); }
.spirit-hero-halo { position: absolute; top: 8rpx; width: 286rpx; height: 286rpx; border-radius: 50%; background: radial-gradient(circle, rgba(255, 248, 219, 0.72) 0%, rgba(240, 210, 139, 0.22) 38%, transparent 72%); filter: blur(6rpx); animation: spiritHalo 5.2s ease-in-out infinite; }
.spirit-hero-stage { position: relative; z-index: 1; width: 226rpx; height: 226rpx; border-radius: 50% 50% 44% 44%; display: flex; align-items: center; justify-content: center; background: radial-gradient(circle at 50% 26%, rgba(255, 255, 255, 0.68), transparent 32%), linear-gradient(180deg, rgba(255, 252, 228, 0.34), rgba(144, 178, 143, 0.28)); border: 1rpx solid rgba(255, 255, 255, 0.42); box-shadow: inset 0 1rpx rgba(255, 255, 255, 0.54), 0 24rpx 70rpx rgba(45, 74, 55, 0.22); backdrop-filter: blur(8px); animation: spiritFloat 5.6s ease-in-out infinite; overflow: hidden; transition: transform 0.2s ease; }
.spirit-hero-stage::after { content: ''; position: absolute; left: 28rpx; right: 28rpx; bottom: 16rpx; height: 26rpx; border-radius: 50%; background: rgba(61, 91, 66, 0.16); filter: blur(9rpx); }
.spirit-hero-stage :deep(.portrait) { position: relative; z-index: 2; width: 78%; height: 78%; }
.spirit-hero-stage :deep(.portrait-image) { filter: drop-shadow(0 18rpx 18rpx rgba(44, 68, 47, 0.2)); }
.spirit-hero-stage :deep(.portrait-glyph) { font-size: 92rpx; color: rgba(255, 250, 225, 0.92); }
.spirit-hero-copy { position: relative; z-index: 2; margin-top: 12rpx; text-align: center; }
.spirit-hero-kicker { display: block; font-size: 17rpx; letter-spacing: 0.18em; color: rgba(43, 76, 59, 0.48); }
.spirit-hero-copy .spirit-buddy-name { margin-top: 5rpx; font-size: 30rpx; }
.spirit-hero-copy .spirit-buddy-line { margin-top: 5rpx; font-size: 21rpx; }
.phase-night .spirit-hero-kicker, .phase-dusk .spirit-hero-kicker { color: rgba(255, 247, 231, 0.52); }
.phase-night .spirit-hero-copy .spirit-buddy-name, .phase-dusk .spirit-hero-copy .spirit-buddy-name { color: #fff7e7; }
.phase-night .spirit-hero-copy .spirit-buddy-line, .phase-dusk .spirit-hero-copy .spirit-buddy-line { color: rgba(255, 247, 231, 0.68); }
.spirit-hero-spark { position: absolute; z-index: 3; color: #f5d792; text-shadow: 0 0 16rpx rgba(245, 215, 146, 0.88); animation: sparkFloat 3.8s ease-in-out infinite; }
.spirit-hero-spark.spark-a { top: 68rpx; left: 28%; font-size: 28rpx; }
.spirit-hero-spark.spark-b { top: 166rpx; right: 27%; font-size: 22rpx; animation-delay: -1.6s; }
.garden-quote { max-width: 620rpx; align-self: center; margin-top: 0; text-align: center; font-size: 30rpx; line-height: 1.65; opacity: 0.78; }
.home-action-row { display: flex; justify-content: center; align-items: center; gap: 16rpx; margin-top: 22rpx; }
.chat-cta { margin-top: 0; min-height: 76rpx; padding: 18rpx 28rpx; border-radius: 999rpx; background: #496f59; box-shadow: 0 14rpx 42rpx rgba(44, 80, 56, 0.22); }
.chat-cta text { margin-left: 8rpx; }
.phase-night .chat-cta, .phase-dusk .chat-cta { background: #f0d28b; color: #234033; }
.why-cta { min-height: 76rpx; padding: 18rpx 24rpx; border: 1rpx solid rgba(46, 79, 61, 0.24); border-radius: 999rpx; background: rgba(255, 255, 255, 0.2); color: rgba(39, 70, 57, 0.76); font-size: 22rpx; }
.phase-night .why-cta, .phase-dusk .why-cta { border-color: rgba(255, 247, 231, 0.2); background: rgba(255, 247, 231, 0.07); color: rgba(255, 247, 231, 0.78); }
.weather-card { margin-top: 30rpx; background: rgba(255, 251, 235, 0.34); border-color: rgba(255, 255, 255, 0.45); box-shadow: 0 16rpx 42rpx rgba(65, 91, 62, 0.12); }
.phase-night .weather-card, .phase-dusk .weather-card { background: rgba(10, 29, 29, 0.36); border-color: rgba(255, 247, 231, 0.15); }
.quiet-card { display: flex; align-items: center; gap: 18rpx; margin-top: 30rpx; padding: 24rpx 26rpx; border: 1rpx solid rgba(255, 255, 255, 0.3); border-radius: 28rpx; background: rgba(255, 251, 235, 0.2); backdrop-filter: blur(14px); }
.quiet-card-mark { width: 58rpx; height: 58rpx; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: rgba(240, 210, 139, 0.22); color: #b18b42; font-size: 28rpx; }
.quiet-card-title { display: block; font-family: Georgia, "Noto Serif SC", serif; font-size: 27rpx; color: #365743; }
.quiet-card-copy { display: block; margin-top: 5rpx; font-size: 21rpx; color: rgba(53, 87, 67, 0.62); }
.phase-night .quiet-card, .phase-dusk .quiet-card { background: rgba(10, 29, 29, 0.28); border-color: rgba(255, 247, 231, 0.14); }
.phase-night .quiet-card-title, .phase-dusk .quiet-card-title { color: #fff7e7; }
.phase-night .quiet-card-copy, .phase-dusk .quiet-card-copy { color: rgba(255, 247, 231, 0.62); }
.garden-empty-note { display: flex; justify-content: center; align-items: center; gap: 10rpx; margin-top: 26rpx; color: rgba(46, 79, 61, 0.54); font-size: 21rpx; }
.empty-note-mark { color: #c69e51; font-size: 28rpx; }
.phase-night .garden-empty-note, .phase-dusk .garden-empty-note { color: rgba(255, 247, 231, 0.56); }
@keyframes spiritHalo { 50% { transform: scale(1.08); opacity: 0.72; } }
@keyframes spiritFloat { 50% { transform: translateY(-8rpx); } }
@keyframes sparkFloat { 50% { transform: translateY(-10rpx) rotate(8deg); opacity: 0.62; } }
@media (max-width: 360px) {
  .hero-row, .dash-grid, .field-row, .home-actions, .awake-actions, .letter-actions { grid-template-columns: 1fr; }
  .spirit-stage.small { width: 100%; }
}
</style>
