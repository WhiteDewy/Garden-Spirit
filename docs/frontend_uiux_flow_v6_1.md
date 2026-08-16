# Garden-Spirit · V6.1 统一视觉规范与注册→欢迎→首页流程

> 状态：V6.1 收敛设计稿  
> 日期：2026-08-15  
> 范围：注册页、欢迎页、首页；不包含 `frontend/src/pages/universe/wheel.vue` 的视觉重构。  
> 设计方向：**Living Astro Companion / 会互动的私人星象伙伴**。  
> 产物用途：给后续 `index.vue` 重构、onboarding 拆页、静态 demo 与真实前端实现提供统一规则。

---

## 1. 方向结论

Garden-Spirit 不应该做成「占星报告 App」或「心理治疗 App」，而应该是：

> **一个每天有星灵醒来、会记得你、能把星盘语言转成自我理解的私人星象伙伴。**

V6.1 不推翻 V6，而是在 V6 的基础上做收敛：

- **一个主视觉焦点**：首页只出现一个今日醒来的星灵，不展示 10 个星灵 IP 阵列。
- **一条主叙事线**：今日星灵 → 私人星象来信 → 继续聊聊 → 记忆/碎片回声。
- **一套解释机制**：所有「为什么」进入 Bottom Sheet / Evidence Rows，不把首页做成数据面板。
- **一种生命感**：星灵有表情、靠近、倾听、回收星巢等动作；不依赖复杂插画师体系。
- **一种克制高级感**：明亮治愈但不糖水，星光/玻璃/软拟物只作为质感，不做元素堆叠。

---

## 2. 竞品启发如何落到本项目

### 2.1 Tolan：身体化伙伴，而不是聊天框

吸收点：

- 非人类、低复杂度、有身体的伙伴。
- 角色有表情和动作，用户先记住「它」再进入聊天。
- 世界感服务陪伴关系，不是假装真人。

落到 Garden-Spirit：

- 首页保留一个「今日醒来的星灵」作为主视觉。
- 星灵本体用 CSS / SVG / 简单 PNG 都能成立：软质发光体 + 表情 + 触角/手臂 + 呼吸动效。
- 星灵动作分 3 档即可：`idle` 呼吸、`listening` 靠近倾听、`withdraw` 回收星巢。

### 2.2 林间聊愈室：低门槛倾诉 + 被记得

吸收点：

- 用户入口不是「咨询」，而是「找一个懂情绪的伙伴说说」。
- 记忆星系/日记/聊天后的总结卡让用户感到被长期记得。
- 功能区清晰，不靠复杂数据解释制造负担。

落到 Garden-Spirit：

- 注册页话术避免「开始算命」，改成「让花园知道怎么称呼你、怎么读你的星图」。
- 首页必须有「我记得你」和「继续昨天」，让后端 recall/opening 能力可见。
- 聊天后的 `lit_fragments / seen_fragments / actioned_fragments / keepsake_created` 未来应成为轻反馈，而不是藏在字段里。

### 2.3 万象有灵：多内在人格，但首页不能变系统设定页

吸收点：

- 多人格/精神宇宙/每日唤醒适合 Garden-Spirit 的 10 星灵结构。
- 长期陪伴关系通过角色、空间、记忆持续沉淀。

需要避开：

- 概念密度过高、名词太重、系统解释压过陪伴感。
- 首页把多个角色、人格、图鉴、能量全塞满。

落到 Garden-Spirit：

- 首页只显示 top1 星灵，top3 推荐放 Bottom Sheet 或后续星灵选择器。
- 「10 星灵」是系统底层，不是第一屏的视觉负担。
- 未来用户偏好选择星灵可以放在设置/星灵选择器，不挤占首页。

---

## 3. 视觉原则

### 3.1 五条硬原则

1. **单焦点**：每屏只有一个主视觉对象；注册页是「第一颗星」，欢迎页是「星灵醒来」，首页是「今日星灵」。
2. **先陪伴，后解释**：用户先看到一句像朋友一样的话，再通过「为什么」查看证据链。
3. **轻奇幻，不玄学堆叠**：少用星座符号、水晶球、复杂星盘纹；多用光线、呼吸、纸感、微星尘。
4. **成长不 KPI 化**：碎片亮起代表聊过/被照见/做过，不代表人格被评分。
5. **明亮但克制**：白天不要糖果色；夜晚保留深色星光，但不全站深暗。

### 3.2 关键词选择

| 类别 | 采用 | 不采用 / 仅限制使用 |
|---|---|---|
| 布局 | Single-column、Z-pattern 首屏、轻 Split-screen、低密度 Dashboard、Card-based、Bottom Navigation | 首页 Infinite Scroll、首页 Data Table |
| 风格 | Minimalism 为底座、Material 层级/间距、少量 Glassmorphism、少量 Neumorphism | Brutalism 主风格、过度拟物、元素堆叠 |
| 组件 | Primary CTA、FAB、Bottom Sheet、Evidence Rows、软卡片、星灵状态按钮 | 大表格、复杂图鉴首屏、多角色阵列 |

---

## 4. Design Tokens

### 4.1 色彩系统

```css
:root {
  /* base */
  --gs-bg-morning: #E9EEF0;      /* 清冷晨雾 */
  --gs-bg-noon: #F1EFE4;         /* 中午奶油光 */
  --gs-bg-dusk: #E8CFAE;         /* 黄昏低饱和夕阳 */
  --gs-bg-night: #13182D;        /* 夜晚深蓝紫 */

  /* ink */
  --gs-ink: #17251F;
  --gs-ink-soft: rgba(23, 37, 31, 0.62);
  --gs-ink-faint: rgba(23, 37, 31, 0.38);

  /* surfaces */
  --gs-card: rgba(255, 253, 247, 0.74);
  --gs-card-solid: #FFFDF7;
  --gs-glass: rgba(255, 255, 255, 0.46);
  --gs-line: rgba(77, 92, 82, 0.14);

  /* accents */
  --gs-star: #F0D58A;
  --gs-moon: #D9D0F0;
  --gs-leaf: #8FAE97;
  --gs-sunset: #DDA46F;
  --gs-error: #B85C54;
  --gs-ok: #5E9276;
}
```

### 4.2 时间相位色彩

| 时间 | 氛围 | 背景 | 星灵光 | 使用场景 |
|---|---|---|---|---|
| 清晨 | 清冷、安静、空气感 | 雾蓝灰 + 奶白 | 冷月白 / 淡紫 | 默认新一天、轻唤醒 |
| 中午 | 明亮、治愈、呼吸感 | 奶油白 + 低饱和草绿 | 金白 / 叶绿 | 日间打开、行动鼓励 |
| 黄昏 | 温暖、夕阳、回收感 | 暖米色 + 低饱和橙 | 琥珀金 | 下班后、继续昨天 |
| 夜晚 | 星光、私密、安放 | 深蓝紫 + 星尘 | 月紫 / 星金 | 深聊、日记、信箱 |

### 4.3 字体与排版

- 中文正文：系统 sans，保持清晰；标题可用系统 serif 或轻宋风作为情绪点缀。
- 标题层级：H1 28–34px，H2 20–24px，正文 13–15px，说明 10–12px。
- 英文小字：大写、字距 0.12–0.22em，只用于 `PRIVATE TRANSIT LETTER` / `WHY TODAY` 这类仪式标签。
- 行高：正文 1.7–1.95，疗愈类内容宁愿更松。

### 4.4 圆角、阴影、玻璃

```css
:root {
  --gs-radius-xl: 34px;
  --gs-radius-lg: 28px;
  --gs-radius-md: 22px;
  --gs-radius-pill: 999px;
  --gs-shadow-card: 0 18px 46px rgba(36, 39, 31, 0.13);
  --gs-shadow-soft: 0 12px 32px rgba(35, 40, 34, 0.08);
  --gs-blur: blur(18px);
}
```

规则：

- 主卡片圆角 28–34px，按钮 18–22px，chip 胶囊。
- 玻璃只用于来信、解释层、记忆卡；不要全页面都 glass。
- 星灵本体可用 Neumorphism 的软阴影，但计算/信息区域不要新拟态。

---

## 5. 组件规范

### 5.1 App Bar

用途：展示当前空间，不抢主视觉。

结构：

- 左：小英文 eyebrow + 当前页中文名。
- 右：一个解释/设置/信箱图标，可带红点。
- 高度：72–88px，透明或轻玻璃，不要实色大导航栏。

### 5.2 Spirit Stage

用途：首页/欢迎页的主视觉。

状态：

| 状态 | 动作 | 场景 |
|---|---|---|
| `idle` | 轻呼吸、眼睛眨动、微漂浮 | 默认首页 |
| `listening` | 身体靠近、光圈扩大、手臂打开 | 用户准备聊天 |
| `withdraw` | 缩回星巢、光线变小 | 用户关闭解释/离开 |
| `sleeping` | 低亮度、眼睛闭合 | 夜间/欢迎前 |

最低实现：CSS shape + pseudo-elements，不强依赖插画师。

### 5.3 Primary CTA

首页必须有一个明确主按钮：

- 文案：`和今天醒来的星灵聊聊 →`
- 位置：Hero 下方，进入来信前。
- 目的：把首页从展示页变成陪伴入口。

次级按钮：

- `为什么是它`
- `存入日记`
- `继续这封信`

### 5.4 Letter Card

用途：承载私人定制日运/周运感，但不替代月运/年运模块。

内容：

- `PRIVATE TRANSIT LETTER` 标签。
- 今日标题。
- 1 段正文，来自 `GardenState.letter` 或 `/mailbox/today`。
- meta chips：发信星灵、触发主题、记忆镜头。
- CTA：继续这封信、存入日记/打开信箱。

规则：

- 首页只放一封今日来信，不放历史列表。
- 月运/年运放后续独立模块，不挤首页。

### 5.5 Evidence Rows

用途：解释「为什么今天是它 / 为什么这封信 / 为什么碎片亮了」。

样式：

```html
<div class="evidence-card">
  <div class="mini-label">Evidence Rows · 解释线索</div>
  <div class="evidence-row"><span>trigger</span><b>行运月亮触发安全感主题</b></div>
  <div class="evidence-row"><span>memory</span><b>记忆镜头优先取情绪 / 家庭 / 近期话题</b></div>
  <div class="evidence-row"><span>growth</span><b>今日碎片只代表聊过、被照见、做过</b></div>
</div>
```

规则：

- 不用 Data Table。
- 每次最多 3 行。
- 文案偏解释，不做占星断语。

### 5.6 Bottom Sheet

用途：承载解释、星灵 top3、隐私说明、出生时间未知说明。

规范：

- 底部浮层，圆角 28–32px。
- 顶部 handle。
- 最多 2 个主按钮。
- 解释语言：清楚、温柔、低压。

### 5.7 Bottom Navigation

建议 tab：

| Tab | 名称 | 目的 |
|---|---|---|
| Garden | 花园 | 今日回家：首页 |
| Chat | 星灵 | 聊天/咨询主入口 |
| Journal | 日记 | 自我书写 / keepsake 回声 |
| Universe | 宇宙 | 自我星盘轮 / 成长碎片 / 验证 |
| Me | 我的 | 偏好、隐私、推送、导出删除 |

当前 `pages.json` 还没有 journal/me 独立页；短期可先保持现有页面，但视觉规范按这个信息架构设计。

---

## 6. 注册→欢迎→首页完整流程

### 6.1 Flow Overview

```text
首次打开
  ↓
注册页 Step 1：怎么称呼你？
  ↓
注册页 Step 2：出生日期
  ↓
注册页 Step 3：出生时间 / 不知道准确时间
  ↓
注册页 Step 4：出生城市 + 隐私说明
  ↓ POST /person
欢迎页：星盘地形生成中
  ↓ GET /person/{id}/recommended-spirits + /garden
欢迎页：今日星灵醒来 + 第一封欢迎信
  ↓
首页 Garden：今日星灵 + 私人来信 + 继续昨天 + 我记得你 + 今日碎片
```

### 6.2 注册页：低压力建档

目标：让用户觉得是在「点亮第一颗星」，不是填占星问卷。

#### 页面结构

1. 顶部：`GARDEN SPIRIT` + `先为你点亮第一颗星`
2. 中部：单步卡片，每次只问一个问题。
3. 底部：进度星点 + 主按钮。
4. 解释入口：`为什么需要这些信息？` Bottom Sheet。

#### Step 1：昵称

文案：

- 标题：`星灵要怎么称呼你？`
- 说明：`这个名字只会用在花园里，让来信和开场白更像写给你。`
- 输入 placeholder：`比如：小夏 / Mary / 一个昵称`
- 按钮：`继续点亮 →`

#### Step 2：出生日期

文案：

- 标题：`你的星图从哪一天开始？`
- 说明：`出生日期会用来计算本命星盘，这是花园的地形。`
- 按钮：`下一步`

#### Step 3：出生时间

文案：

- 标题：`还记得出生时间吗？`
- 说明：`越准确，宫位和月亮相关信息越清晰。不知道也没关系，花园会先用较温柔的方式解读。`
- 控件：时间选择 + `我不知道准确时间`
- 若未知：显示 chip `会降低宫位细节，不影响陪伴和日记功能。`

#### Step 4：出生城市

文案：

- 标题：`最后，出生城市在哪里？`
- 说明：`城市用于换算时区和星盘位置。默认可先用上海，之后完整编辑能力需要后端补充。`
- 隐私提示：`你的数据只用于生成这座花园；你可以在设置里导出或删除。`
- 按钮：`走进花园`

#### 数据映射

| UI 字段 | API |
|---|---|
| 昵称 | `PersonIn.name` |
| 日期 + 时间 | `birth.datetime_local` |
| 不知道时间 | `birth.time_known=false`，时间默认 `12:00:00` |
| 城市 | `birth.location.place_name` |
| 提交 | `POST /person` |

---

### 6.3 欢迎页：花园生成与星灵醒来

目标：把「提交表单 → 进首页」变成一次有记忆点的过渡。

#### 状态 A：生成中

视觉：

- 背景是清晨雾光。
- 中央一颗未完全成形的软质星体。
- 星尘沿圆形轨迹慢慢聚合。

文案：

- 标题：`你的星图正在长成一座花园`
- 说明：`我们正在生成本命地形、今天的星灵和第一封来信。`
- loading steps：
  - `计算星图地形`
  - `寻找今天先醒来的星灵`
  - `整理第一封私人星信`

#### 状态 B：星灵醒来

视觉：

- 星灵从星巢里睁眼。
- 显示 top1 星灵，不展示 top3 列表。
- 旁边可有极小 `top 1` chip。

文案：

- 标题：`今天，月亮星灵先醒来了。`
- 说明：`它会先从安全感、情绪和归属感的角度陪你看今天。`
- 主按钮：`进入花园`
- 次按钮：`先和它说句话`
- 解释按钮：`为什么是月亮？`

#### 数据映射

| UI 内容 | API |
|---|---|
| 星灵 top1 | `GET /person/{id}/recommended-spirits` |
| 欢迎来信 | `GET /garden?person_id=...&persona=...` 的 `letter` |
| 开场白 | 可选 `GET /person/{id}/opening?persona=...` |
| 解释 | recommendation `reason` + recall lens |

---

### 6.4 首页 Garden：每日回家体验

目标：首页不是功能入口集合，而是「我今天回来，星灵已经在等我」。

#### 首屏结构

```text
App Bar
  GARDEN SPIRIT / 花园                 ?

Date Row
  清晨 · 星光醒来                      关系温度 · trusted

Hero
  左：今日主题标题 + 一句话陪伴
  右：今日醒来的星灵 Stage

Primary CTA
  和今天醒来的星灵聊聊 →               为什么是它

Wake Strip
  月亮星灵被唤醒 / 行运月亮触发安全感主题 / top 1
```

#### 下方结构

```text
今日来信 Letter Card
  PRIVATE TRANSIT LETTER
  标题 + 正文 + meta chips
  继续这封信 / 存入日记

轻仪表盘
  继续昨天
  今日碎片

我记得你
  recall item / confirmed finding / recent topic

Evidence Rows
  trigger / memory / growth
```

#### 数据映射

| 首页模块 | API / 字段 |
|---|---|
| 今日日期 | `GardenState.today` |
| 关系温度 | `GardenState.trust_level` |
| 今日来信 | `GardenState.letter` |
| 继续昨天 | `GardenState.continue_from.summary` |
| 我记得你 | `GardenState.recall`（当前 `client.ts` 类型缺 recall，后续需补类型） |
| 今日碎片 | `GardenState.soul_fragments` |
| 信箱红点 | `GardenState.letter_unread` |
| 宇宙红点 | `GardenState.pending_verifications` |
| 今日星灵 | `recommended-spirits` top1 |

#### 当前类型差异提醒

`docs/backend_capabilities_for_frontend.md` 说明 `GardenState` 有 `recall`，但 `frontend/src/api/client.ts` 当前 `GardenState` 类型只到 `soul_fragments`，缺少 `recall` 字段。进入生产实现前应补类型：

```ts
export interface GardenRecallItem {
  kind: string;
  title?: string;
  summary?: string;
  text?: string;
  domain?: string;
}

export interface GardenRecallOut {
  has_memory: boolean;
  items: GardenRecallItem[];
}

export interface GardenState {
  person_id: string;
  today: string;
  letter: LetterOut | null;
  continue_from: { conversation_id: string; summary: string; started_at?: string } | null;
  domains: string[];
  trust_level: string;
  pending_verifications: number;
  letter_unread: boolean;
  soul_fragments: SoulFragmentOut[];
  recall?: GardenRecallOut;
}
```

---

## 7. 页面文案系统

### 7.1 不说什么

避免：

- `AI 已经看透你`
- `系统判定你是……`
- `你的命运会……`
- `必须完成今日任务`
- `连续打卡才能成长`
- `心理治疗 / 诊断 / 疗效保证`

### 7.2 应该说什么

推荐：

- `这不是标签，只是一颗被你校准过的记忆星。`
- `如果你愿意，我们可以从这里继续。`
- `不知道准确出生时间也没关系，花园会先温柔一点。`
- `今日碎片只代表你聊过、被照见过、真的尝试过。`
- `占星结论来自你的星盘结构，星灵只是把它说得更像朋友。`

### 7.3 CTA 文案库

| 场景 | 主 CTA | 次 CTA |
|---|---|---|
| 注册开始 | `继续点亮 →` | `为什么需要这些信息？` |
| 注册提交 | `走进花园` | `稍后再填城市` |
| 欢迎生成完成 | `进入花园` | `先和它说句话` |
| 首页主入口 | `和今天醒来的星灵聊聊 →` | `为什么是它` |
| 今日来信 | `继续这封信 →` | `存入日记` |
| 继续昨天 | `接着昨天说` | `换个话题` |
| 记忆卡 | `看看它记得什么` | `这不准确` |

---

## 8. 动效规范

### 8.1 动效节奏

- 页面进入：280–420ms，淡入 + 微上移。
- 星灵呼吸：4–7s 循环，不要太快。
- 星尘漂浮：8–16s，低透明度。
- Bottom Sheet：220–280ms，ease-out。
- CTA 点击：缩放 0.98，80ms 即可。

### 8.2 不做

- 不做强弹跳、金币雨、过度粒子爆炸。
- 不用连续打卡火焰/排名/等级进度条刺激。
- 不让动效遮挡阅读。

---

## 9. 信息架构建议

### 9.1 短期：不大拆生产路由

当前 `pages.json` 已有：

- `pages/index/index`：注册 + 首页混合。
- `pages/chat/chat`：聊天。
- `pages/mailbox/mailbox`：信箱。
- `pages/universe/universe`：宇宙枢纽。
- `pages/universe/wheel`：自我星盘轮，不改。
- `pages/universe/consult`：星盘咨询。
- `pages/universe/fragment`：碎片详情。

短期建议：

- 先在 `index.vue` 内完成注册→欢迎→首页三状态，而不是立刻拆路由。
- 状态枚举：`creating | awakening | garden`。
- 这样改动小，也符合当前本地 storage 的 `PERSON_KEY` 逻辑。

### 9.2 中期：拆 onboarding

当视觉确认后可拆：

- `pages/onboarding/register`
- `pages/onboarding/awakening`
- `pages/index/index` 只做 Garden 首页
- `pages/me/me` 做偏好/隐私/导出删除
- `pages/journal/journal` 做日记列表和创建

---

## 10. 实现优先级

### P0：静态确认

- 新建 HTML flow demo，展示注册、欢迎、首页三屏。
- 保留 V6 / V6.1 原型文件，不覆盖旧 `prototype_home.html`。

### P1：生产首页状态重构

- `frontend/src/pages/index/index.vue`
  - 从 `creating: boolean` 升级为 `stage: 'register' | 'awakening' | 'garden'`。
  - 保留当前 `POST /person` 与 `GET /garden`。
  - 增加欢迎页过渡。
  - 首页接 `letter / continue_from / soul_fragments / letter_unread / pending_verifications`。

### P2：API 类型补齐

- `frontend/src/api/client.ts`
  - 补 `RecommendedSpiritsOut` / `SpiritRecommendationOut`。
  - 补 `api.recommendedSpirits(personId)`。
  - 补 `GardenState.recall` 类型。
  - `opening/garden/recall` 后续支持 persona 参数。

### P3：聊天富字段反馈

- `frontend/src/pages/chat/chat.vue`
  - 对 `lit_fragments / seen_fragments / actioned_fragments / keepsake_created` 做轻 toast / 星尘条。
  - 保持聊天为主，不把反馈做成打卡系统。

### P4：后续页面

- 信箱深化 daily/keepsake 分版式。
- 我的宇宙枢纽承接待验证、成长年轮。
- 设置页承接 push、偏好、导出删除。

---

## 11. 生产实现守则

必须遵守：

- 不改 `frontend/src/pages/universe/wheel.vue` 的视觉。
- 不覆盖 `frontend/prototype_home.html`。
- 不做 10 个星灵 IP 系统；当前只需要一个可复用星灵本体。
- 不把占星结论写成前端静态文案；结论来自 `/chat` / Domain。
- 不让 LLM 看盘或暗示「AI 自己算出来」。
- 删除数据不可逆，必须二次确认，最好先引导导出。
- `trust_level` 是关系温度，不是用户价值评分。
- 行动/验证是邀请式，不是任务惩罚。

---

## 12. 参考来源

- Tolan 官方站：https://www.tolans.com/
- Tolan About：https://www.tolans.com/about-tolan
- Tolan App Store：https://apps.apple.com/us/app/tolan-your-friendly-guide/id6477549878
- 林间聊愈室 App Store：https://apps.apple.com/cn/app/id6453689112
- 林间聊愈室观猹介绍：https://watcha.cn/products/lin-jian-liao-yu-shi
- 万象有灵 App Store：https://apps.apple.com/cn/app/id6743929899
- NoonWake / 万象有灵官网：https://noonwake.com/

---

## 13. 一句话给后续实现

> **先把注册做得像点亮第一颗星，把欢迎做得像星灵醒来，把首页做得像每天回到一个记得你的私人星象伙伴身边。**
