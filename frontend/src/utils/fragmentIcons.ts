// 34 子类 · 手绘线条图标（统一 viewBox 0 0 48 48，stroke currentColor）。
// 三区意象：
//   行星（内在驱力）· 宫位（生活领域）· 星座（应对方式）
// 每个子类一枚专属图标；点亮染金、未点亮呈剪影（颜色由外层 CSS 控制）。

export type Prim =
  | { t: "path"; d: string }
  | { t: "circle"; cx: number; cy: number; r: number }
  | { t: "ellipse"; cx: number; cy: number; rx: number; ry: number; transform?: string }
  | { t: "line"; x1: number; y1: number; x2: number; y2: number }
  | { t: "polyline"; points: string };

// 小四芒星（点光/星光装饰）
const STAR = (x: number, y: number): Prim => ({
  t: "path",
  d: `M${x} ${y - 4} l1.2 2.8 2.8 1.2 -2.8 1.2 -1.2 2.8 -1.2 -2.8 -2.8 -1.2 2.8 -1.2 Z`,
});

export const ICONS: Record<string, Prim[]> = {
  // ══════════ 行星动力（10）══════════════════════
  sun_core: [
    { t: "circle", cx: 24, cy: 24, r: 9 },
    { t: "line", x1: 24, y1: 9, x2: 24, y2: 5 },
    { t: "line", x1: 24, y1: 39, x2: 24, y2: 43 },
    { t: "line", x1: 9, y1: 24, x2: 5, y2: 24 },
    { t: "line", x1: 39, y1: 24, x2: 43, y2: 24 },
    { t: "line", x1: 32.5, y1: 15.5, x2: 35.5, y2: 12.5 },
    { t: "line", x1: 32.5, y1: 32.5, x2: 35.5, y2: 35.5 },
    { t: "line", x1: 15.5, y1: 32.5, x2: 12.5, y2: 35.5 },
    { t: "line", x1: 15.5, y1: 15.5, x2: 12.5, y2: 12.5 },
  ],
  moon_tide: [
    { t: "path", d: "M28 9 a12 12 0 1 0 0 25 a9.5 9.5 0 1 1 0 -25 Z" }, // 月牙
    { t: "path", d: "M13 39 q3.5 -3.5 7 0 t7 0" },                     // 潮汐
    { t: "path", d: "M17 44 q3.5 -3.5 7 0 t7 0" },
  ],
  mercury_maze: [
    { t: "path", d: "M30 13 a4 4 0 1 1 -4 4 a8 8 0 1 0 8 8 a12 12 0 1 1 -12 -12 a16 16 0 1 0 16 16" }, // 思维螺旋
  ],
  venus_love: [
    { t: "path", d: "M24 35 C14 27 12 19 15.5 15.5 C18.5 12.5 22 14 24 17 C26 14 29.5 12.5 32.5 15.5 C36 19 34 27 24 35 Z" },
    STAR(39, 8),
  ],
  mars_action: [
    { t: "path", d: "M24 7 C30 14 33 18 33 26 C33 33 29 37 24 37 C19 37 15 33 15 26 C15 18 18 14 24 7 Z" },
    { t: "path", d: "M24 16 C27 20 28 22 28 26 C28 30 26 33 24 33 C22 33 20 30 20 26 C20 22 21 20 24 16 Z" },
  ],
  jupiter_faith: [
    { t: "path", d: "M14 18 L24 6 L34 18" },        // 殿顶
    { t: "line", x1: 18, y1: 18, x2: 18, y2: 34 },   // 左柱
    { t: "line", x1: 30, y1: 18, x2: 30, y2: 34 },   // 右柱
    { t: "line", x1: 13, y1: 34, x2: 35, y2: 34 },   // 基座
    STAR(36, 3),
  ],
  saturn_order: [
    { t: "circle", cx: 24, cy: 24, r: 10 },
    { t: "ellipse", cx: 24, cy: 24, rx: 17, ry: 6, transform: "rotate(-18 24 24)" },
  ],
  uranus_awake: [
    { t: "path", d: "M27 5 L14 26 H22 L21 43 L34 20 H26 Z" },
  ],
  neptune_dream: [
    { t: "path", d: "M13 33 a5.5 5.5 0 0 1 .5 -11 a7 7 0 0 1 13 -2.5 a6 6 0 0 1 .5 13.5 Z" }, // 云
    STAR(38, 7),
  ],
  pluto_depth: [
    { t: "path", d: "M10 34 a14 14 0 0 0 28 0" }, // 深渊（外）
    { t: "path", d: "M15 28 a9 9 0 0 0 18 0" },   // （中）
    { t: "path", d: "M20 22 a4 4 0 0 0 8 0" },    // （内）
    STAR(36, 5),                                    // 上升星光
  ],

  // ══════════ 宫位舞台（12）══════════════════════
  house1_mask: [
    { t: "path", d: "M13 30 a11 11 0 0 1 22 0 l-3 6 H16 Z" }, // 面具
    { t: "circle", cx: 19, cy: 27, r: 2.2 },
    { t: "circle", cx: 29, cy: 27, r: 2.2 },
  ],
  house2_value: [
    { t: "circle", cx: 24, cy: 24, r: 14 },
    { t: "path", d: "M24 16 L31 24 L24 32 L17 24 Z" }, // 宝石
    { t: "line", x1: 24, y1: 16, x2: 24, y2: 32 },
    { t: "line", x1: 17, y1: 24, x2: 31, y2: 24 },
  ],
  house3_bridge: [
    { t: "path", d: "M8 34 Q24 8 40 34" },          // 桥拱
    { t: "line", x1: 8, y1: 34, x2: 40, y2: 34 },    // 桥面
    { t: "circle", cx: 18, cy: 25, r: 1.6 },         // 信号点
    { t: "circle", cx: 24, cy: 19, r: 1.6 },
    { t: "circle", cx: 30, cy: 25, r: 1.6 },
  ],
  house4_home: [
    { t: "path", d: "M12 27 L24 12 L36 27" },        // 屋顶
    { t: "path", d: "M15 26 V37 H33 V26" },          // 屋身
    { t: "path", d: "M24 34 C20.5 31.5 19 30 19 28.2 C19 26.9 20 26 21.2 26 C22.3 26 23.3 26.7 24 27.6 C24.7 26.7 25.7 26 26.8 26 C28 26 29 26.9 29 28.2 C29 30 27.5 31.5 24 34 Z" }, // 心
  ],
  house5_joy: [
    { t: "path", d: "M24 6 l3.2 7.8 7.8 3.2 -7.8 3.2 -3.2 7.8 -3.2 -7.8 -7.8 -3.2 7.8 -3.2 Z" },
    STAR(10, 14),
    STAR(38, 28),
  ],
  house6_daily: [
    { t: "circle", cx: 24, cy: 24, r: 14 },
    { t: "line", x1: 24, y1: 24, x2: 24, y2: 14 },
    { t: "line", x1: 24, y1: 24, x2: 32, y2: 28 },
  ],
  house7_mirror: [
    { t: "circle", cx: 18, cy: 24, r: 9 },
    { t: "circle", cx: 30, cy: 24, r: 9 },
  ],
  house8_crisis: [
    { t: "path", d: "M24 4 c3.2 3.8 5.2 6 5.2 8.6 a5.2 5.2 0 0 1 -10.4 0 c0 -2.6 2 -4.8 5.2 -8.6 Z" }, // 落泪
    { t: "path", d: "M12 27 a12 12 0 0 0 24 0" },
    { t: "path", d: "M16 34 a8 8 0 0 0 16 0" },
    { t: "path", d: "M20 41 a4 4 0 0 0 8 0" },
  ],
  house9_far: [
    { t: "path", d: "M18 14 V36" },
    { t: "path", d: "M30 14 V36" },
    { t: "path", d: "M18 26 H30" },
    { t: "path", d: "M20 14 H28 V8 H20 Z" },          // 灯室
    { t: "line", x1: 16, y1: 11, x2: 10, y2: 11 },     // 光
    { t: "line", x1: 32, y1: 11, x2: 38, y2: 11 },
    { t: "line", x1: 14, y1: 36, x2: 34, y2: 36 },     // 底座
    { t: "line", x1: 10, y1: 41, x2: 38, y2: 41 },     // 地面
  ],
  house10_career: [
    { t: "line", x1: 12, y1: 36, x2: 36, y2: 36 },     // 地面
    { t: "line", x1: 14, y1: 36, x2: 14, y2: 27 },
    { t: "line", x1: 24, y1: 36, x2: 24, y2: 18 },
    { t: "line", x1: 34, y1: 36, x2: 34, y2: 9 },
    { t: "line", x1: 12, y1: 27, x2: 36, y2: 27 },     // 阶
    { t: "line", x1: 14, y1: 18, x2: 36, y2: 18 },
    { t: "line", x1: 24, y1: 9, x2: 36, y2: 9 },
    STAR(34, 4),
  ],
  house11_net: [
    { t: "line", x1: 15, y1: 18, x2: 24, y2: 10 },
    { t: "line", x1: 24, y1: 10, x2: 34, y2: 16 },
    { t: "line", x1: 15, y1: 18, x2: 20, y2: 33 },
    { t: "line", x1: 34, y1: 16, x2: 30, y2: 31 },
    { t: "line", x1: 20, y1: 33, x2: 30, y2: 31 },
    { t: "line", x1: 15, y1: 18, x2: 34, y2: 16 },
    { t: "circle", cx: 15, cy: 18, r: 2.4 },
    { t: "circle", cx: 24, cy: 10, r: 2.4 },
    { t: "circle", cx: 34, cy: 16, r: 2.4 },
    { t: "circle", cx: 20, cy: 33, r: 2.4 },
    { t: "circle", cx: 30, cy: 31, r: 2.4 },
  ],
  house12_secret: [
    { t: "path", d: "M38 9 a5 5 0 1 0 0 10 a4 4 0 1 1 0 -10 Z" }, // 隐月
    { t: "line", x1: 20, y1: 42, x2: 20, y2: 26 },
    { t: "path", d: "M20 34 C14 33 12 27 12 26 C16 25 20 28 20 34 Z" },
    { t: "path", d: "M20 30 C26 29 28 23 28 22 C24 21 20 24 20 30 Z" },
    { t: "circle", cx: 20, cy: 21, r: 2.2 },
  ],

  // ══════════ 星座风格（12）══════════════════════
  aries_fire: [
    { t: "path", d: "M17 25 C13 20 15 14 20 13" },
    { t: "path", d: "M31 25 C35 20 33 14 28 13" },
    { t: "path", d: "M24 5 c2 2.4 3.2 3.8 3.2 5.2 a3.2 3.2 0 0 1 -6.4 0 c0 -1.4 1.2 -2.8 3.2 -5.2 Z" },
  ],
  taurus_earth: [
    { t: "path", d: "M14 22 C13 13 7 12 6 15 C5 18 9 19 10 22" },
    { t: "path", d: "M34 22 C35 13 41 12 42 15 C43 18 39 19 38 22" },
    { t: "path", d: "M14 26 a10 10 0 0 1 20 0 Z" },
  ],
  gemini_wind: [
    { t: "circle", cx: 17, cy: 13, r: 3 },
    { t: "circle", cx: 31, cy: 13, r: 3 },
    { t: "line", x1: 17, y1: 19, x2: 17, y2: 37 },
    { t: "line", x1: 31, y1: 19, x2: 31, y2: 37 },
    { t: "path", d: "M17 28 C24 23 24 33 31 28" },
  ],
  cancer_shell: [
    { t: "path", d: "M26 38 a9 9 0 1 1 9 -9 a6.5 6.5 0 1 1 -6.5 -6.5 a4 4 0 1 1 -4 -4" },
  ],
  leo_glory: [
    { t: "circle", cx: 24, cy: 24, r: 10 },
    { t: "line", x1: 24, y1: 14, x2: 24, y2: 8 },
    { t: "line", x1: 34, y1: 24, x2: 40, y2: 24 },
    { t: "line", x1: 24, y1: 34, x2: 24, y2: 40 },
    { t: "line", x1: 14, y1: 24, x2: 8, y2: 24 },
    { t: "line", x1: 31.1, y1: 16.9, x2: 34.6, y2: 13.4 },
    { t: "line", x1: 31.1, y1: 31.1, x2: 34.6, y2: 34.6 },
    { t: "line", x1: 16.9, y1: 31.1, x2: 13.4, y2: 34.6 },
    { t: "line", x1: 16.9, y1: 16.9, x2: 13.4, y2: 13.4 },
    { t: "circle", cx: 20, cy: 22, r: 1.6 },
    { t: "circle", cx: 28, cy: 22, r: 1.6 },
    { t: "path", d: "M24 26 l-1.8 2.2 h3.6 Z" },
  ],
  virgo_mirror: [
    { t: "line", x1: 24, y1: 40, x2: 24, y2: 14 },
    { t: "path", d: "M24 20 C18 18 14 14 14 10" },
    { t: "path", d: "M24 24 C18 22 14 18 14 14" },
    { t: "path", d: "M24 20 C30 18 34 14 34 10" },
    { t: "path", d: "M24 24 C30 22 34 18 34 14" },
    STAR(38, 6),
  ],
  libra_balance: [
    { t: "line", x1: 24, y1: 8, x2: 24, y2: 30 },
    { t: "line", x1: 11, y1: 15, x2: 37, y2: 15 },
    { t: "path", d: "M11 15 L8 25 H14 Z" },
    { t: "path", d: "M37 15 L34 25 H40 Z" },
    { t: "line", x1: 17, y1: 30, x2: 31, y2: 30 },
    { t: "path", d: "M17 30 V34 H31 V30" },
  ],
  scorpio_eye: [
    { t: "path", d: "M10 12 H16 L24 20 L32 12 H38" },
    { t: "path", d: "M24 20 c0 8 5 11 10 9 c5 -2 5 -7 2 -9 c-3 -2 -7 0 -7 3" },
  ],
  sagittarius_arrow: [
    { t: "line", x1: 10, y1: 36, x2: 34, y2: 12 },
    { t: "path", d: "M34 12 l-7 -2 l2 7 Z" },
    { t: "path", d: "M10 36 l-2 -7 l7 2 Z" },
  ],
  capricorn_peak: [
    { t: "path", d: "M8 36 L24 12 L40 36" },
    { t: "path", d: "M18 22 L24 12 L29 19" },
    STAR(32, 4),
  ],
  aquarius_star: [
    { t: "path", d: "M10 26 q4 -4 8 0 t8 0" },
    { t: "path", d: "M14 34 q4 -4 8 0 t8 0" },
    STAR(28, 8),
  ],
  pisces_sea: [
    { t: "path", d: "M13 19 q7 -5 14 0" },
    { t: "path", d: "M27 19 l5 -3" },
    { t: "path", d: "M13 29 q7 5 14 0" },
    { t: "path", d: "M27 29 l5 3" },
    { t: "path", d: "M7 24 q3 -3 6 0" },
  ],
};

// 未知 id 兜底：日芒
export const FALLBACK_ICON = ICONS.sun_core;
