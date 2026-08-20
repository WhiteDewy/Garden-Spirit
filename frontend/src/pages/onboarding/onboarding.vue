<template>
  <view class="page">
    <!-- 建档向导：五步收集出生信息，最后一步绘制星图 -->
    <view v-if="phase === 'form'" class="screen create-chart-screen">
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
        <text v-if="registerStep === 1" class="back-to-sky" @tap="backToSky">← 回到星空</text>
      </view>
    </view>

    <!-- 绘制星图：创建本人档案的同时，星空定格 + 星光扩散 -->
    <view v-else class="screen chart-drawing-screen">
      <view class="chart-sky" aria-hidden="true">
        <view class="drawing-milky"></view>
        <view class="birth-stream stream-date"><text>{{ form.date || '出生日期' }}</text></view>
        <view class="birth-stream stream-time"><text>{{ form.time_unknown ? '时间未知' : (form.time || '出生时间') }}</text></view>
        <view class="birth-stream stream-place"><text>{{ form.city || manualCity || '出生地点' }}</text></view>
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
          <view class="step"><text>本人档案</text><text>{{ saved ? '已生成' : '绘制中…' }}</text></view>
          <view class="step"><text>第一颗星灵</text><text>{{ spiritName ? `已找到 · ${spiritName}` : '寻找中' }}</text></view>
        </view>
        <view :class="['found-message', { lit: awakeFound }]">
          <text>「我找到你的星图了。」</text>
          <text>「以后，我会陪你一起读懂它。」</text>
        </view>
        <view v-if="awakeFound" class="awake-actions">
          <button class="primary-btn" @tap="enterGardenFromAwakening">进入我的花园</button>
          <button class="secondary-btn" @tap="goChat">先和它说句话</button>
        </view>
        <text v-if="error" class="error">{{ error }}</text>
      </view>
    </view>

    <!-- 海外出生：坐标弹框（与 uni picker 同款深空玻璃底部弹层） -->
    <view v-if="overseasOpen" class="sheet-mask" @tap="overseasOpen = false"></view>
    <view v-if="overseasOpen" class="overseas-sheet">
      <view class="os-header">
        <text class="os-cancel" @tap="overseasOpen = false">取消</text>
        <text class="os-title">海外出生 · 精确坐标</text>
        <text class="os-confirm" @tap="confirmOverseas">确认</text>
      </view>
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
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import api, { describeError, type AccountOut, type GardenState, type PersonIn, type SpiritRecommendationOut } from "@/api/client";
import { cacheAccount } from "@/utils/account";

type Phase = "form" | "drawing";

const phase = ref<Phase>("form");
const registerStep = ref(1);
const busy = ref(false);
const error = ref("");
const account = ref<AccountOut | null>(null);

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

const PLANET_ZH: Record<string, string> = {
  sun: "太阳星灵", moon: "月亮星灵", mercury: "水星星灵", venus: "金星星灵", mars: "火星星灵",
  jupiter: "木星星灵", saturn: "土星星灵", uranus: "天星星灵", neptune: "海王星星灵", pluto: "冥王星星灵",
};

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

// 三级行政区划级联（省/市/区县）：H5 不支持 picker mode="region"，用 multiSelector + 区划数据包自实现
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

const justPicked = ref("");
let pickTimer: ReturnType<typeof setTimeout> | null = null;
function flashPick(key: "date" | "time" | "region" | "residence") {
  justPicked.value = key;
  if (pickTimer) clearTimeout(pickTimer);
  pickTimer = setTimeout(() => { justPicked.value = ""; }, 900);
}

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
  void createChart();
}

// 绘制星图：先切夜空绘制态，创建本人档案成功后定格星光
const saved = ref(false);
const savedName = ref("");
const gardenState = ref<GardenState | null>(null);
const recommendedSpirit = ref<SpiritRecommendationOut | null>(null);
const awakeFound = computed(() => phase.value === "drawing" && saved.value);
const spiritName = computed(() => {
  const s = recommendedSpirit.value;
  if (!s) return "";
  return s.healing_name || s.name || PLANET_ZH[s.planet?.toLowerCase()] || "月亮星灵";
});

async function createChart() {
  if (!form.name.trim()) return (error.value = "先告诉花园你的名字");
  if (!form.date) return (error.value = "需要出生日期");
  if (!form.time_unknown && !form.time) return (error.value = "需要出生时间（越精确越好）");
  if (!form.city && !manualCity.value.trim()) return (error.value = "选择或输入一个出生城市");
  const acc = account.value || await resolveAccountSafely();
  if (!acc) return uni.redirectTo({ url: "/pages/auth/login" });
  busy.value = true;
  error.value = "";
  phase.value = "drawing";
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
    const payload: PersonIn = {
      name: form.name.trim(),
      gender: form.gender || undefined,
      house_system: "B",
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
    };
    const savedAccount = acc.self_person_id
      ? await api.updateSelfProfile(acc.account_id, payload)
      : await api.createSelfProfile(acc.account_id, payload);
    cacheAccount(savedAccount);
    uni.setStorageSync("gs_residence", residence);
    uni.setStorageSync("gs_timezone", form.tz);
    savedName.value = payload.name;
    saved.value = true;
    const pid = savedAccount.self_person_id || savedAccount.self_profile?.id || "";
    if (pid) {
      try {
        const rec = await api.recommendedSpirits(pid);
        recommendedSpirit.value = rec.spirits?.[0] || null;
      } catch { /* 星灵推荐失败不影响建档完成 */ }
      try {
        gardenState.value = await api.garden(pid);
      } catch { /* 花园数据失败不阻塞进入 */ }
    }
  } catch (e) {
    error.value = describeError(e);
    phase.value = "form";
  } finally {
    busy.value = false;
  }
}

async function resolveAccountSafely() {
  try {
    const acc = await api.getAccount(uni.getStorageSync("gs_account_id") as string);
    return acc;
  } catch {
    return null;
  }
}

function enterGardenFromAwakening() {
  uni.reLaunch({ url: "/pages/index/index?enter=garden" });
}
function goChat() {
  uni.navigateTo({ url: "/pages/chat/chat" });
}
function backToSky() {
  uni.reLaunch({ url: "/pages/index/index?back=sky" });
}

onLoad(async () => {
  void ensureRegionData();
  try {
    account.value = await resolveAccountSafely();
  } catch {
    account.value = null;
  }
  if (!account.value) uni.redirectTo({ url: "/pages/auth/login" });
});
</script>

<style scoped>
.page {
  position: relative;
  min-height: 100vh;
  box-sizing: border-box;
  color: #fff8eb;
  overflow-x: hidden;
  background:
    radial-gradient(circle at 50% 18%, rgba(239, 213, 139, 0.18), transparent 28%),
    radial-gradient(circle at 15% 76%, rgba(148, 171, 255, 0.16), transparent 32%),
    linear-gradient(180deg, #070b17 0%, #111827 54%, #1b211f 100%);
}
.screen { position: relative; z-index: 2; }
.create-chart-screen { padding: 54rpx 36rpx 130rpx; justify-content: center; }

.register-sky { position: absolute; inset: 0; pointer-events: none; z-index: 0; overflow: hidden; }
.sky-star { position: absolute; color: rgba(255, 248, 220, 0.82); font-size: 11rpx; text-shadow: 0 0 14rpx rgba(246, 223, 156, 0.8); animation: welcomeTwinkle 3.8s ease-in-out infinite; }
.sky-star:nth-child(2n) { font-size: 8rpx; opacity: 0.72; text-shadow: 0 0 8rpx rgba(246, 223, 156, 0.5); }
.sky-star:nth-child(3n) { font-size: 13rpx; }
.sky-star:nth-child(7n) { font-size: 15rpx; text-shadow: 0 0 22rpx rgba(246, 223, 156, 0.9); animation-duration: 4.6s; }
.sky-star-1 { left: 8%; top: 9%; } .sky-star-2 { left: 18%; top: 19%; animation-delay: .4s; } .sky-star-3 { left: 31%; top: 8%; animation-delay: .9s; } .sky-star-4 { left: 43%; top: 16%; animation-delay: 1.4s; } .sky-star-5 { left: 63%; top: 8%; animation-delay: .7s; } .sky-star-6 { left: 82%; top: 15%; animation-delay: 1.8s; }
.sky-star-7 { left: 91%; top: 29%; animation-delay: 1.1s; } .sky-star-8 { left: 12%; top: 34%; animation-delay: 2.2s; } .sky-star-9 { left: 26%; top: 42%; animation-delay: 1.6s; } .sky-star-10 { left: 73%; top: 38%; animation-delay: .3s; } .sky-star-11 { left: 86%; top: 52%; animation-delay: 2.8s; } .sky-star-12 { left: 9%; top: 59%; animation-delay: 1.9s; }
.sky-star-13 { left: 20%; top: 72%; animation-delay: .8s; } .sky-star-14 { left: 37%; top: 66%; animation-delay: 2.4s; }
.constellation { position: absolute; opacity: 0.34; filter: drop-shadow(0 0 12rpx rgba(190, 216, 255, 0.46)); }
.constellation-a { width: 210rpx; height: 170rpx; left: 9%; top: 15%; }
.c-dot { position: absolute; width: 8rpx; height: 8rpx; border-radius: 50%; background: #fbf4ce; box-shadow: 0 0 18rpx rgba(251, 244, 206, 0.9); }
.c-line { position: absolute; height: 1rpx; background: linear-gradient(90deg, rgba(251, 244, 206, 0.16), rgba(251, 244, 206, 0.56), rgba(251, 244, 206, 0.1)); transform-origin: left center; }
.constellation .d1 { left: 10rpx; top: 28rpx; } .constellation .d2 { left: 72rpx; top: 62rpx; } .constellation .d3 { left: 138rpx; top: 34rpx; } .constellation .d4 { left: 188rpx; top: 128rpx; }
.constellation .l1 { left: 15rpx; top: 35rpx; width: 70rpx; transform: rotate(28deg); } .constellation .l2 { left: 78rpx; top: 65rpx; width: 74rpx; transform: rotate(-22deg); } .constellation .l3 { left: 143rpx; top: 41rpx; width: 104rpx; transform: rotate(62deg); }

.chart-orb { position: absolute; inset: 0; pointer-events: none; opacity: 0.95; z-index: 0; }
.chart-ring { position: absolute; left: 50%; top: 33%; border-radius: 50%; border: 1rpx solid rgba(255, 248, 235, 0.14); transform: translate(-50%, -50%) rotate(-14deg); }
.chart-ring.r1 { width: 560rpx; height: 560rpx; animation: spin 42s linear infinite; }
.chart-ring.r2 { width: 390rpx; height: 390rpx; border-style: dashed; animation: spin 28s linear reverse infinite; }
.chart-star { position: absolute; color: rgba(240, 213, 139, 0.72); text-shadow: 0 0 26rpx rgba(239, 213, 139, 0.5); animation: welcomeTwinkle 3.4s ease-in-out infinite; }
.chart-star.s1 { left: 16%; top: 22%; font-size: 28rpx; }
.chart-star.s2 { right: 18%; top: 18%; font-size: 22rpx; animation-delay: .8s; }
.chart-star.s3 { right: 24%; bottom: 22%; font-size: 26rpx; animation-delay: 1.6s; }

.create-chart-hero { position: relative; z-index: 1; display: grid; justify-items: center; gap: 16rpx; margin-top: 64rpx; text-align: center; }
.create-sigil { width: 64rpx; height: 64rpx; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff3c4; background: rgba(23, 37, 31, 0.86); box-shadow: 0 18rpx 54rpx rgba(23, 37, 31, 0.2), 0 0 36rpx rgba(239, 213, 139, 0.42); }
.create-title { display: block; font-size: 56rpx; font-weight: 860; letter-spacing: -0.055em; color: #fff8eb; }
.create-copy { max-width: 520rpx; color: rgba(255, 248, 235, 0.62); font-size: 25rpx; line-height: 1.7; }

.question-card { position: relative; z-index: 1; width: 100%; margin-top: 48rpx; padding: 48rpx 36rpx 40rpx; box-sizing: border-box; border-radius: 46rpx; border: 1rpx solid rgba(255, 255, 255, 0.13); background: rgba(255, 248, 235, 0.09); box-shadow: 0 28rpx 82rpx rgba(0, 0, 0, 0.28); backdrop-filter: blur(24rpx); }
.register-spirit { position: absolute; right: -10rpx; top: -124rpx; width: 220rpx; height: 270rpx; transform: scale(0.6); transform-origin: top right; z-index: 3; pointer-events: none; }
.register-spirit .spirit-stage { width: 220rpx; height: 270rpx; border-radius: 58rpx; border-color: rgba(255, 248, 224, 0.16); background: radial-gradient(circle at 50% 22%, rgba(255, 255, 255, 0.5), transparent 35%), linear-gradient(180deg, rgba(255, 252, 232, 0.14), rgba(189, 181, 255, 0.07)); box-shadow: inset 0 1rpx rgba(255, 255, 255, 0.26), 0 28rpx 90rpx rgba(3, 7, 24, 0.5), 0 0 52rpx rgba(235, 204, 132, 0.12); backdrop-filter: blur(8rpx); }
.prompt-swap { animation: stepIn 0.5s cubic-bezier(0.2, 0.8, 0.2, 1) both; }
.spirit-says { display: block; white-space: pre-line; text-align: center; font-size: 36rpx; line-height: 1.45; font-weight: 830; letter-spacing: -0.035em; color: #fff8eb; }
.question-hint { display: block; margin-top: 22rpx; text-align: center; font-size: 23rpx; line-height: 1.6; color: rgba(255, 248, 235, 0.62); }
.answer-block { margin-top: 46rpx; display: grid; gap: 20rpx; animation: stepIn 0.5s 0.06s cubic-bezier(0.2, 0.8, 0.2, 1) both; }
.answer-block > view { display: grid; gap: 52rpx; }
.answer-input { width: 100%; min-height: 104rpx; border-radius: 38rpx; border: 1rpx solid rgba(255, 255, 255, 0.13); background: rgba(255, 255, 255, 0.08); padding: 0 30rpx; box-sizing: border-box; color: #fff8eb; font-size: 30rpx; text-align: center; }
.name-input { font-size: 34rpx; font-weight: 760; letter-spacing: 0.04em; }
.field-note { display: block; text-align: center; color: rgba(255, 248, 235, 0.62); font-size: 22rpx; line-height: 1; }
.date-picker-card, .time-picker-card { min-height: 104rpx; border-radius: 42rpx; border: 1rpx solid rgba(255, 255, 255, 0.13); background: rgba(255, 255, 255, 0.08); display: flex; align-items: center; justify-content: center; gap: 12rpx; transition: box-shadow .3s ease, border-color .3s ease; }
.date-picker-card.lit, .time-picker-card.lit { border-color: rgba(243, 223, 170, 0.5); box-shadow: 0 0 34rpx rgba(239, 213, 139, 0.22); }
.date-part { font-size: 44rpx; font-weight: 860; color: #fff8eb; letter-spacing: -0.035em; }
.date-part.year { min-width: 108rpx; text-align: right; }
.date-unit, .date-placeholder { font-size: 24rpx; color: rgba(255, 248, 235, 0.62); }
.time-picker-card text { font-size: 48rpx; font-weight: 860; letter-spacing: 0.08em; color: #fff8eb; }
.time-picker-card.muted text { font-size: 32rpx; letter-spacing: 0; color: rgba(255, 248, 235, 0.46); }

.gender-row { display: flex; justify-content: center; gap: 14rpx; }
.gender-pill { border-radius: 999rpx; border: 1rpx solid rgba(255, 255, 255, 0.12); background: rgba(255, 248, 235, 0.07); padding: 16rpx 34rpx; font-size: 23rpx; color: rgba(255, 248, 235, 0.62); }
.gender-pill.on { background: rgba(243, 223, 170, 0.92); color: #17251f; font-weight: 800; }

.time-confirm-row { display: flex; justify-content: center; gap: 16rpx; }
.confirm-pill { flex: 1; text-align: center; border-radius: 18rpx; border: 1rpx solid rgba(255, 255, 255, 0.12); background: rgba(255, 248, 235, 0.07); padding: 18rpx 0; font-size: 23rpx; color: rgba(255, 248, 235, 0.62); }
.confirm-pill.on { background: rgba(243, 223, 170, 0.92); color: #17251f; font-weight: 800; }

.dst-ask { display: grid; gap: 12rpx; margin-top: 6rpx; padding: 20rpx 22rpx; border-radius: 26rpx; border: 1rpx solid rgba(239, 213, 139, 0.3); background: rgba(239, 213, 139, 0.1); }
.dst-title { font-size: 22rpx; font-weight: 700; color: rgba(255, 248, 235, 0.85); }
.dst-options { display: flex; gap: 12rpx; }
.dst-pill { flex: 1; text-align: center; border-radius: 18rpx; border: 1rpx solid rgba(255, 255, 255, 0.12); background: rgba(255, 248, 235, 0.07); padding: 16rpx 0; font-size: 22rpx; color: rgba(255, 248, 235, 0.62); }
.dst-pill.on { background: rgba(243, 223, 170, 0.92); color: #17251f; font-weight: 800; }
.dst-note { font-size: 20rpx; color: rgba(255, 248, 235, 0.5); }

.region-text { font-size: 30rpx; letter-spacing: 0.02em; line-height: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
.residence-answer { display: grid; gap: 16rpx; }
.same-as-birth { border-radius: 26rpx; border: 1rpx solid rgba(239, 213, 139, 0.32); background: rgba(239, 213, 139, 0.12); padding: 22rpx 24rpx; font-size: 24rpx; color: rgba(255, 248, 235, 0.7); text-align: center; }
.same-as-birth.on { background: rgba(243, 223, 170, 0.92); border-color: transparent; color: #17251f; font-weight: 800; }
.tz-card { min-height: 104rpx; border-radius: 30rpx; border: 1rpx solid rgba(255, 255, 255, 0.12); background: rgba(255, 248, 235, 0.07); display: flex; align-items: center; justify-content: space-between; padding: 0 28rpx; }
.tz-label { font-size: 23rpx; color: rgba(255, 248, 235, 0.55); }
.tz-value { font-size: 30rpx; font-weight: 800; letter-spacing: 0.04em; color: #fff8eb; }

.create-actions { display: flex; align-items: center; justify-content: center; gap: 18rpx; margin-top: 46rpx; }
.create-actions .primary-btn, .create-actions .secondary-btn { margin-top: 0; min-height: 60rpx; }
.create-actions .primary-btn { flex: 1; }
.back-btn { min-width: 168rpx; padding-left: 22rpx; padding-right: 22rpx; }
.create-next { min-height: 60rpx; border-radius: 20rpx; }
.create-error { text-align: center; }
.create-progress { display: flex; justify-content: center; gap: 12rpx; margin-top: 36rpx; }
.create-progress .progress-dot { width: 12rpx; height: 12rpx; border-radius: 999rpx; background: rgba(255, 248, 235, 0.22); transition: all .28s ease; }
.create-progress .progress-dot.on { background: #f3dfaa; box-shadow: 0 0 20rpx rgba(239, 213, 139, 0.55); }

.primary-btn, .secondary-btn { border: 0; border-radius: 20rpx; padding: 20rpx 26rpx; font-size: 25rpx; font-weight: 700; line-height: 1; min-height: 80rpx; box-sizing: border-box; display: flex; align-items: center; justify-content: center; }
.primary-btn { margin-top: 28rpx; background: linear-gradient(135deg, #f2d58d, #b89448); color: #10271f; box-shadow: 0 16rpx 40rpx rgba(95, 130, 108, 0.32); }
.secondary-btn { margin-top: 28rpx; background: rgba(255, 248, 235, 0.07); color: #fff8eb; border: 1rpx solid rgba(255, 255, 255, 0.14); }
.create-chart-screen .primary-btn, .create-chart-screen .secondary-btn, .chart-drawing-screen .primary-btn, .chart-drawing-screen .secondary-btn { background: linear-gradient(180deg, rgba(255, 248, 224, 0.16), rgba(255, 248, 224, 0.06)); border: 1rpx solid rgba(255, 238, 188, 0.32); color: rgba(255, 250, 230, 0.96); box-shadow: 0 22rpx 70rpx rgba(0, 0, 0, 0.26), 0 0 48rpx rgba(242, 205, 120, 0.13), inset 0 1rpx rgba(255, 255, 255, 0.14); }
.create-chart-screen .secondary-btn, .chart-drawing-screen .secondary-btn { background: rgba(255, 248, 224, 0.07); border: 1rpx solid rgba(255, 255, 255, 0.12); color: rgba(255, 248, 224, 0.72); box-shadow: none; }
.awake-actions .primary-btn, .awake-actions .secondary-btn { margin-top: 0; min-height: 60rpx; }
.primary-btn[disabled], .secondary-btn[disabled] { opacity: 0.6; }
.overseas-trigger { width: 100%; margin-top: 0; }
.error { display: block; margin-top: 18rpx; color: #ffcfbf; font-size: 23rpx; line-height: 1.5; }
.back-to-sky { display: block; margin-top: 26rpx; text-align: center; font-size: 22rpx; color: rgba(255, 248, 235, 0.46); padding: 8rpx; }

/* 海外坐标弹框 */
.sheet-mask { position: fixed; inset: 0; z-index: 30; background: rgba(0, 0, 0, 0.28); animation: maskFade 0.25s ease both; }
.overseas-sheet { position: fixed; z-index: 31; left: 0; right: 0; bottom: 0; padding: 0 30rpx calc(30rpx + env(safe-area-inset-bottom)); box-sizing: border-box; background: rgba(13, 18, 34, 0.97); border-top: 1rpx solid rgba(255, 238, 188, 0.14); box-shadow: 0 -20rpx 80rpx rgba(0, 0, 0, 0.5); backdrop-filter: blur(24px); display: grid; gap: 16rpx; animation: sheetUp 0.34s cubic-bezier(0.22, 0.9, 0.28, 1) both; }
.os-header { display: flex; align-items: center; justify-content: space-between; height: 88rpx; border-bottom: 1rpx solid rgba(255, 248, 235, 0.08); }
.os-cancel { padding: 0 6rpx; font-size: 28rpx; color: rgba(255, 248, 235, 0.55); }
.os-confirm { padding: 0 6rpx; font-size: 28rpx; color: #f3dfaa; font-weight: 700; }
.os-title { font-size: 30rpx; font-weight: 700; color: #fff8eb; }
.os-name { min-height: 92rpx; text-align: left; background: rgba(255, 248, 235, 0.07); border-color: rgba(255, 255, 255, 0.12); color: #fff8eb; }
.os-row { min-height: 92rpx; border-radius: 26rpx; border: 1rpx solid rgba(255, 255, 255, 0.12); background: rgba(255, 248, 235, 0.07); display: flex; align-items: center; justify-content: space-between; padding: 0 28rpx; }
.os-label { font-size: 23rpx; color: rgba(255, 248, 235, 0.55); }
.os-value { font-size: 28rpx; font-weight: 700; line-height: 1; color: #fff8eb; letter-spacing: 0.02em; }
.os-note { font-size: 20rpx; color: rgba(255, 248, 235, 0.5); line-height: 1.6; }

/* 绘制星图 */
.chart-drawing-screen { position: relative; overflow: hidden; justify-content: flex-start; min-height: 100vh; padding: 0 36rpx 90rpx; box-sizing: border-box; }
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
.orbit { height: 420rpx; display: flex; align-items: center; justify-content: center; position: relative; margin-top: 76rpx; }
.orbit::before { content: ''; position: absolute; width: 390rpx; height: 390rpx; border-radius: 50%; border: 1rpx dashed rgba(255, 248, 235, 0.24); animation: spin 18s linear infinite; }
.chart-orbit { height: 500rpx; margin-top: 40rpx; }
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
.burst-ring { position: absolute; border-radius: 50%; border: 1rpx solid rgba(243, 223, 170, 0.5); animation: burstOut 1.6s ease-out infinite; }
.burst-ring.r-one { width: 300rpx; height: 300rpx; }
.burst-ring.r-two { width: 380rpx; height: 380rpx; animation-delay: .5s; }

.spirit-stage { position: relative; border: 1rpx solid rgba(255, 248, 235, 0.14); background: linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.03)); box-shadow: inset 0 1rpx rgba(255, 255, 255, 0.14), 0 22rpx 56rpx rgba(0, 0, 0, 0.3); display: flex; align-items: center; justify-content: center; overflow: hidden; }
.spirit-stage.large { width: 300rpx; height: 340rpx; border-radius: 72rpx; }
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
.chart-spirit { z-index: 2; transform: translateY(44rpx) scale(.74); opacity: 0.9; animation: spiritAwake 5.2s ease-in-out infinite; }

.awake-card { padding: 36rpx; position: relative; z-index: 1; background: rgba(255, 248, 235, 0.1); border-color: rgba(255, 255, 255, 0.14); color: #fff8eb; box-shadow: 0 30rpx 90rpx rgba(0, 0, 0, 0.32); border: 1rpx solid rgba(255, 255, 255, 0.14); border-radius: 40rpx; backdrop-filter: blur(20rpx); }
.eyebrow { display: block; font-size: 19rpx; letter-spacing: 0.18em; color: rgba(255, 248, 235, 0.46); font-weight: 800; }
.awake-title { display: block; margin-top: 14rpx; white-space: pre-line; font-weight: 800; letter-spacing: -0.055em; line-height: 1.14; font-size: 56rpx; color: #fff8eb; }
.card-copy { display: block; margin-top: 18rpx; color: rgba(255, 248, 235, 0.68); font-size: 25rpx; line-height: 1.85; }
.steps { display: grid; gap: 14rpx; margin-top: 30rpx; }
.step { display: flex; justify-content: space-between; gap: 18rpx; border-top: 1rpx solid rgba(255, 255, 255, 0.12); padding-top: 18rpx; font-size: 24rpx; color: rgba(255, 248, 235, 0.58); }
.step text:first-child { color: #fff8eb; font-weight: 760; }
.found-message { display: grid; gap: 10rpx; margin-top: 26rpx; padding: 22rpx 24rpx; border-radius: 34rpx; background: rgba(255, 248, 235, 0.08); border: 1rpx solid rgba(255, 248, 235, 0.1); transition: box-shadow 0.6s ease; }
.found-message text { color: rgba(255, 248, 235, 0.88); font-size: 25rpx; line-height: 1.6; }
.found-message.lit { animation: foundGlow 1.4s ease-out both; }
.awake-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 18rpx; margin-top: 26rpx; }
.awake-actions .primary-btn, .awake-actions .secondary-btn { margin-top: 0; }

@keyframes spin { to { transform: rotate(360deg); } }
@keyframes float { 50% { transform: translateY(-12rpx) rotate(-1.6deg); } }
@keyframes pulse { 50% { transform: scale(1.09); opacity: 0.52; } }
@keyframes welcomeTwinkle { 0%, 100% { opacity: 0.32; transform: scale(0.82); } 50% { opacity: 1; transform: scale(1.18); } }
@keyframes starsDrift { to { transform: translate3d(-80rpx, 100rpx, 0); } }
@keyframes galaxyDrift { 50% { transform: rotate(-15deg) translate3d(26rpx, 18rpx, 0); opacity: 0.58; } }
@keyframes streamIntoChart { 0%, 100% { opacity: 0; transform: translate(-50%, -24rpx) scale(.92); } 18%, 68% { opacity: 1; } 78% { opacity: 0; transform: translate(-50%, 245rpx) scale(.72); } }
@keyframes orbitGlyph { 50% { transform: translateY(-22rpx) scale(1.08); opacity: 0.72; } }
@keyframes aspectFlash { 0%, 100% { opacity: 0.14; } 45%, 60% { opacity: 0.78; } }
@keyframes spiritAwake { 50% { transform: translateY(28rpx) scale(.78); opacity: 1; } }
@keyframes burstOut { 0% { transform: scale(.6); opacity: 0.9; } 100% { transform: scale(1.25); opacity: 0; } }
@keyframes foundGlow { 0% { box-shadow: 0 0 0 rgba(243, 223, 170, 0); } 35% { box-shadow: 0 0 46rpx rgba(243, 223, 170, 0.3); border-color: rgba(243, 223, 170, 0.35); } 100% { box-shadow: 0 0 0 rgba(243, 223, 170, 0); } }
@keyframes stepIn { from { opacity: 0; transform: translateY(24rpx) scale(0.99); } }
@keyframes sheetUp { from { opacity: 0; transform: translateY(72rpx); } to { opacity: 1; transform: translateY(0); } }
@keyframes maskFade { from { opacity: 0; } }
</style>
