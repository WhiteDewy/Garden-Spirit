import { ref } from "vue";

export type TimePhase = "morning" | "noon" | "dusk" | "night";

export function getTimePhase(hour = new Date().getHours()): TimePhase {
  if (hour < 11) return "morning";
  if (hour < 16) return "noon";
  if (hour < 20) return "dusk";
  return "night";
}

export function timePhaseClass(hour = new Date().getHours()) {
  return `phase-${getTimePhase(hour)}`;
}

/** 页面重新显示时调用，避免跨过时段仍停留在旧光线。 */
export function useTimePhase() {
  const phaseClass = ref(timePhaseClass());
  const refreshPhase = () => { phaseClass.value = timePhaseClass(); };
  return { phaseClass, refreshPhase };
}
