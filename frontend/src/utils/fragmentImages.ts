// 34 子类 PNG 图标 · static/imgs 目录映射
// 图片放 `src/static/imgs/`，uni-app 自动托管到 `/static/imgs/`，纯丢文件即可。
// 命名（见 src/static/imgs/README.md）：{短名}_{default|active}.png
//   sun_core → sun；house1_mask → house_01；aries_fire → aries
//   unlit → _default；lit/ascended → 优先 _active，缺图回落 _default（光效由 CSS 补）
import type { BallState } from "@/utils/fragments";

// 子类 id → 短名（无需对照表，规则固定）
export function imageBase(id: string): string {
  const m = id.match(/^house(\d+)/);
  if (m) return `house_${m[1].padStart(2, "0")}`;
  return id.split("_")[0];
}

// 候选图片 URL（按优先级）：
//   unlit → [default]
//   lit/ascended → [active, default]（active 缺失时回落 default，由 @error 触发）
export function candidateImages(id: string, state?: BallState): string[] {
  const base = imageBase(id);
  if (state === "unlit") return [`/static/imgs/${base}_default.png`];
  return [`/static/imgs/${base}_active.png`, `/static/imgs/${base}_default.png`];
}
