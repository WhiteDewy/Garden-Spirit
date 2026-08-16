# 首页森屿舞台 · 插画生成提示词（island-stage 背景）

> 用途：替换首页 `island-stage` 的 CSS 渐变场景（CSS 版保留作兜底，插画就位后无缝升级）。
> 生成工具：即梦 / 豆包 / Midjourney 通用。
> 画幅：**约 7:6 横幅**（建议 1400×1200，对应 640rpx 高全宽舞台）。
> **重要**：只画「场景底图」，不要画星灵本体——星灵是前景元素（CSS/立绘叠加），画进去就没法换装和呼吸浮动了。

---

## 主提示词（直接复制使用）

```
治愈系插画背景，柔和磨砂水彩质感，圆润可爱轮廓，暖色调氛围光，细腻光影，留白干净。
一座柔软的小岛舞台：画面下方约三分之一是一座馒头形的草丘小岛，低饱和草木绿（鼠尾草绿到奶绿渐变），
岛顶有一小块浅色的圆形空地；上方三分之二是晨雾天空，奶白到浅雾蓝的柔和渐变，
两三朵扁平柔软的小云安静漂着，一层薄雾横过画面中部；
草丘上散落四五朵很小的野花和两三颗暖金色的光点（像萤火虫的微光），
整体明亮、安静、有呼吸感，大量留白，无任何角色、无文字、无水印，纯场景背景图。
色调参考：天空 #dcecf3→#f2f0e2，草地 #b7d3a6→#87a878，点缀金色 #f4d88a。
```

## 英文版（MJ / 国际工具）

```
healing illustration background, soft matte watercolor texture, rounded cute shapes,
warm ambient light, delicate shading, generous negative space.
a soft island stage: bottom third of the frame is a bun-shaped grassy hill in muted sage green,
with a small pale circular clearing on its top; upper two thirds is a morning-mist sky,
cream white to pale fog blue gradient, two or three flat soft clouds drifting quietly,
a thin layer of mist across the middle of the frame;
scattered tiny wildflowers and a few warm golden firefly sparkles on the hill,
bright, calm, breathing atmosphere, no character, no text, no watermark, pure background art.
color palette: sky #dcecf3 to #f2f0e2, grass #b7d3a6 to #87a878, golden accents #f4d88a.
--ar 7:6
```

## 负向提示词（支持负向的工具）

```
人物，角色，动物，文字，水印，签名，边框，复杂细节，暗色调，夜晚，星空，夸张透视，照片写实，3D渲染，噪点
```

---

## 夜晚版（可选第二张）

如果要做昼夜双版，用同一构图换色：天空换暖深绿 `#16302e→#22463a`，草丘加深，萤光点加亮加大（夜晚主角是光点）。提示词在上面主提示词里替换色彩段即可。

## 落位与接入

1. 文件放 `frontend/src/static/imgs/island_bg.png`（夜版 `island_bg_night.png`）。
2. 接入方式：`island-stage` 内加一层 `<image>`（`object-fit: cover`，绝对定位铺满），CSS 渐变层保留在下面作为加载兜底；云/雾/微光的 CSS 动画层可以先关掉，避免和插画打架。
3. 星灵、光晕、巢穴继续用现有 CSS 元素叠在插画上方（位置不用动，草丘顶部空地就是给它站的）。
