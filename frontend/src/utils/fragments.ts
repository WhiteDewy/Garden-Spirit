// 34 子类点亮系统 · 前端共享工具（wheel.vue / fragment.vue 共用）
// 状态判定与后端 34 子类目录一一对应，勿发明新 id。
// 子类图标见 utils/fragmentIcons.ts（SVG 手绘线条，替换占星 unicode 符号）。

export const ROMAN = ["", "Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ"];

// ---------------------------------------------------------------------------
// 状态判定（§3.3 深度分 → 三态）+ 五层成长级（§4.2 1-5 级）
// ---------------------------------------------------------------------------

export type BallState = "unlit" | "lit" | "ascended";

export function stateOf(depth: number): BallState {
  if (depth <= 0) return "unlit";
  if (depth >= 10) return "ascended";
  return "lit";
}
// 五层成长级（§4.2 1-5 级）由后端统一出（FragmentOut.level），前端只渲染。

// 三区元信息（前端展示用）
export const ZONE_META: Array<{ key: string; name: string; en: string; desc: string }> = [
  { key: "planet", name: "行星动力", en: "PLANETS", desc: "你聊到的内在驱力" },
  { key: "house", name: "宫位舞台", en: "HOUSES", desc: "你聊到的生活领域" },
  { key: "sign", name: "星座风格", en: "SIGNS", desc: "你聊话题时的应对方式" },
];

export function zoneMeta(key: string) {
  return ZONE_META.find((z) => z.key === key) || ZONE_META[0];
}

export const STATE_TEXT: Record<BallState, string> = {
  unlit: "尚未点亮",
  lit: "已被点亮",
  ascended: "已深潜点亮",
};
