import { ref } from "vue";
import api, { ApiError, type GardenState } from "@/api/client";
import { clearAccountCache, requireSelfPersonId } from "@/utils/account";

const gardenState = ref<GardenState | null>(null);
const loadingBadges = ref(false);

export const letterBadge = ref(false);
export const universeBadge = ref(false);

function applyGardenBadges(state: GardenState | null) {
  gardenState.value = state;
  letterBadge.value = !!state?.letter_unread;
  universeBadge.value = (state?.pending_verifications ?? 0) > 0;
}

export async function refreshGardenBadges(personId?: string, persona?: string) {
  const pid = personId || await requireSelfPersonId(false);
  if (!pid || loadingBadges.value) return gardenState.value;
  loadingBadges.value = true;
  try {
    const state = await api.garden(pid, persona);
    applyGardenBadges(state);
    return state;
  } catch (e) {
    if (e instanceof ApiError && (e.status === 404 || e.status === 410)) clearAccountCache();
    applyGardenBadges(null);
    return null;
  } finally {
    loadingBadges.value = false;
  }
}

export function setGardenBadges(state: GardenState | null) {
  applyGardenBadges(state);
}

export function markLetterBadgeRead() {
  letterBadge.value = false;
  if (gardenState.value) gardenState.value = { ...gardenState.value, letter_unread: false };
}

export function useGardenBadges() {
  return {
    gardenState,
    letterBadge,
    universeBadge,
    loadingBadges,
    refreshGardenBadges,
    setGardenBadges,
    markLetterBadgeRead,
  };
}
