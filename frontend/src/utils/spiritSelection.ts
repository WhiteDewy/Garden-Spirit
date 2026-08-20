import type { PersonaOut, SpiritRecommendationOut } from "@/api/client";

export interface SpiritSelectionInput {
  preferredPersona?: string | null;
  recommendations?: SpiritRecommendationOut[];
  personas?: PersonaOut[];
}

export interface SpiritSelection {
  planet: string;
  name: string;
  line: string;
  recommendation: SpiritRecommendationOut | null;
  profile: PersonaOut | null;
  todayRecommendation: SpiritRecommendationOut | null;
  isPreferredOverride: boolean;
}

function norm(value?: string | null) {
  return String(value || "").trim().toLowerCase();
}

/**
 * Canonical frontend selector for the companion shown across Home/Chat/Profile.
 * Priority: user's resident spirit -> today's recommendation -> Moon fallback.
 */
export function selectSpirit(input: SpiritSelectionInput): SpiritSelection {
  const recommendations = input.recommendations || [];
  const personas = input.personas || [];
  const preferred = norm(input.preferredPersona);
  const today = norm(recommendations[0]?.planet);
  const planet = preferred || today || "moon";
  const recommendation = recommendations.find((s) => norm(s.planet) === planet) || null;
  const profile = personas.find((p) => norm(p.key) === planet) || null;
  const todayRecommendation = recommendations[0] || null;

  return {
    planet,
    name: recommendation?.healing_name || profile?.healing_name || recommendation?.name || profile?.name || "星灵",
    line: recommendation?.style || profile?.style || todayRecommendation?.reason || "今天先轻轻落在这里，和它说一句话就好。",
    recommendation,
    profile,
    todayRecommendation,
    isPreferredOverride: !!preferred && !!today && preferred !== today,
  };
}
