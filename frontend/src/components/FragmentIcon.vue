<template>
  <image
    v-if="current"
    class="frag-img"
    :src="current"
    mode="aspectFit"
    @error="onError"
    aria-hidden="true"
  />
  <svg
    v-else
    class="frag-icon"
    viewBox="0 0 48 48"
    fill="none"
    stroke="currentColor"
    stroke-width="2.2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <template v-for="(p, i) in prims" :key="i">
      <circle v-if="p.t === 'circle'" :cx="p.cx" :cy="p.cy" :r="p.r" />
      <ellipse
        v-else-if="p.t === 'ellipse'"
        :cx="p.cx"
        :cy="p.cy"
        :rx="p.rx"
        :ry="p.ry"
        :transform="p.transform"
      />
      <line
        v-else-if="p.t === 'line'"
        :x1="p.x1"
        :y1="p.y1"
        :x2="p.x2"
        :y2="p.y2"
      />
      <polyline v-else-if="p.t === 'polyline'" :points="p.points" />
      <path v-else :d="p.d" />
    </template>
  </svg>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { ICONS, FALLBACK_ICON, type Prim } from "@/utils/fragmentIcons";
import { candidateImages } from "@/utils/fragmentImages";
import type { BallState } from "@/utils/fragments";

const props = defineProps<{ id: string; state?: BallState }>();

const candidates = computed<string[]>(() => candidateImages(props.id, props.state));
// idx：-1 = 所有候选图都失败 → 走 SVG 兜底
const idx = ref(0);
const current = computed<string | undefined>(() => candidates.value[idx.value]);

// id/state 变化时复位，重新走候选链
watch(() => [props.id, props.state], () => { idx.value = 0; });

function onError() {
  if (idx.value < candidates.value.length - 1) {
    idx.value += 1;
  } else {
    idx.value = -1;
  }
}

const prims = computed<Prim[]>(() => ICONS[props.id] || FALLBACK_ICON);
</script>

<style scoped>
/* PNG：尺寸由父级 font-size 控制（1em 缩放），放哪都能用 */
.frag-img {
  display: block;
  width: 1em;
  height: 1em;
}
/* SVG 兜底 */
.frag-icon {
  display: block;
  width: 1em;
  height: 1em;
  color: inherit;
}
</style>
