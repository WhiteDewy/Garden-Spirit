# 34 子类图标（PNG）

把所有 PNG **直接丢进这个文件夹**，uni-app 会自动托管到 `/static/imgs/`，纯丢文件、无需构建。

## 命名规则：`{短名}_{default|active}.png`

- **default**（未点亮）必给
- **active**（点亮/深潜）可选——不提供的话，点亮时会用 default 图 + 光效

短名对照（不用背，图里就这几类）：

| 区 | 短名 |
|---|---|
| 行星 | sun · moon · mercury · venus · mars · jupiter · saturn · uranus · neptune · pluto |
| 宫位 | house_01 … house_12 |
| 星座 | aries · taurus · gemini · cancer · leo · virgo · libra · scorpio · sagittarius · capricorn · aquarius · pisces |

示例：`sun_default.png`、`sun_active.png`、`house_01_default.png`、`aries_default.png` …
