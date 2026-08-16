<template>
  <view class="portrait" :class="[`planet-${planet}`, { loaded: !!src }]">
    <image v-if="src" class="portrait-image" :src="src" mode="aspectFit" @error="onError" />
    <text v-else class="portrait-glyph">{{ glyph }}</text>
  </view>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";

const props = withDefaults(defineProps<{ planet?: string; active?: boolean }>(), {
  planet: "moon",
  active: true,
});

const GLYPHS: Record<string, string> = {
  sun: "☉", moon: "☽", mercury: "☿", venus: "♀", mars: "♂",
  jupiter: "♃", saturn: "♄", uranus: "♅", neptune: "♆", pluto: "♇",
};
// 星灵头像不再把 moon_active.png 当成月亮星灵立绘；真实立绘缺失时使用符号兜底。
const availablePlanetIcons = new Set(["sun", "mercury", "venus", "mars", "jupiter"]);
const tried = ref(0);
const src = ref(candidate(0));

function planetKey() { return (props.planet || "moon").toLowerCase(); }
function candidate(index: number) {
  const planet = planetKey();
  if (index === 0) return `/static/imgs/spirits/spirit_${planet}.png`;
  if (index === 1 && availablePlanetIcons.has(planet)) return `/static/imgs/${planet}_${props.active ? "active" : "default"}.png`;
  return "";
}
function onError() {
  tried.value += 1;
  src.value = candidate(tried.value);
}
watch(() => [props.planet, props.active], () => {
  tried.value = 0;
  src.value = candidate(0);
});

const glyph = GLYPHS[planetKey()] || "✦";
</script>

<style scoped>
.portrait { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; position: relative; }
.portrait-image { width: 100%; height: 100%; display: block; filter: drop-shadow(0 12rpx 18rpx rgba(24, 38, 30, 0.18)); }
.portrait-glyph { font-family: Georgia, "Noto Serif SC", serif; font-size: 42rpx; color: rgba(255, 248, 224, 0.84); text-shadow: 0 0 20rpx rgba(240, 210, 139, 0.58); }
</style>
