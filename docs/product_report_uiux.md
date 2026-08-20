# Garden-Spirit 产品形态与 Agent 能力报告

> **用途**：为前端 UI/UX 规划提供完整的能力基线 + 现状基线。
> **数据来源**：2026-08-06 基于当前 `main` 分支代码逐模块核实（API、前端 4 页、application/domain/foundation/shared 全部源码 + 342 测试）。
> **配套文档**：`docs/PRD.md`（产品需求）· `docs/architecture.md`（冻结架构）· `docs/consult_method.md`（咨询方法论）· `docs/interpretation_voice.md`（语气规范）· `docs/meng_method.md`（解盘技法）

---

## 目录

1. [产品定位与哲学](#一产品定位与哲学)
2. [Agent 能力全景](#二agent-能力全景)
3. [产品当前形态](#三产品当前形态)
4. [能力已具备但前端未接入（缺口表）](#四能力已具备但前端未接入)
5. [面向 UI/UX 的能力→界面映射](#五面向-uiux-的能力界面映射)
6. [对 UI 设计有约束的关键事实](#六对-ui-设计有约束的关键事实)
7. [V8 Report Compiler 契约](#七v8-report-compiler-契约)

---

## 一、产品定位与哲学

**一句话**：面向自我探索与情绪成长场景的 AI 陪伴产品——用领域知识引擎（占星）提供有依据的自我认知，用长期记忆与关系层建立持续陪伴，让人与星盘的相处方式从"无意识"走向"有意识"。

**三关键词（v1 定稿）**：
| 关键词 | 落地形态 |
|--------|---------|
| **理解** | AI 推理：真实星盘 + 可解释证据链 |
| **陪伴** | 星灵人格 / 每日来信 / 每天回来打开 |
| **成长** | 日记 + 长期画像 + 成长时间轴 |

**核心哲学链**：`信任 → 占星 → 疗愈 → 无意识 → 有意识 → 陪伴 → 成长`
- 占星 = 信任基石（确定性 Domain + Evidence，不可动摇）
- 星盘不是判决书，是一张地图；输出 风险/模式/资源/建议，绝不输出"命好坏/一定离婚"
- 成长 = 从无意识走向有意识；诚实承认有些课题更难

**设计硬线（不可变更）**：LLM 的自由度只在"怎么疗愈/怎么说话"，绝不在"占星对不对"；占星结论（权重/极性/吉凶/哪个宫位重要）全部由 Domain 确定性计算产生。

**三大产品承诺（差异化）**：
1. **算得真**——星盘来自 Swiss Ephemeris 真实计算，非 LLM 编造
2. **讲得清**——每个结论有可追溯证据链（哪个行星/宫位/相位支撑）
3. **陪伴暖**——十大星灵人格，多轮对话有温度

**六层 Agent 架构实际进度**：
| 层 | 能力 | 进度 |
|----|------|------|
| L1 理解层 | LLM+规则意图理解、追问消解、深度拆解 | ~85%（A1 已完成） |
| L2 推理层 | Strategy→Plan→Evidence→Conclusion 确定性推理 | ~90% |
| L3 叙事层 | 10 人格 + 咨询节奏 + 语气规范 + LLM 转述 | ~90% |
| L4 记忆层 | 跨会话画像、写回管线、**关系层 trust** | ~75%（W1+A2 已完成） |
| L5 学习层 | 验前事（用人生事件校准置信度） | ~10%（未写） |
| L6 行动层 | 主动推送/调度（来信有，推送无） | ~20% |

---

## 二、Agent 能力全景

### 2.1 对话理解能力（第一层）

**核心链路**：`用户消息 → Safety Gate → 闲聊检测 → LLM意图分类 → 规则兜底 → 深度拆解 → 策略选择 → 分析执行 → 证据合成 → 结论 → LLM人格化转述 → 回答`

**意图领域（8 大领域 + 闲聊）**：
| 领域 | 覆盖子场景 | 规则示例 |
|------|-----------|---------|
| **career 职业** | 换工作 / 升职 / 创业 / 职业倦怠 | 60+ 关键词规则 |
| **relationship 感情** | 伴侣特征 / 关系状态 / 开始 / 复合 / 承诺 | 同上 |
| **wealth 财富** | 财运 / 投资 / 收入 | 同上 |
| **health 健康** | 身体 / 疲劳 / 失眠 | 同上 |
| **emotion 情绪** | 低落 / 焦虑 / 心情 | 同上 |
| **family 家庭** | 原生家庭 / 亲子 | 同上 |
| **learning 学习** | 考试 / 考研 / 学业 | 同上 |
| **daily 今日/运势** | 今日运势（Daily.Chat 子领域接住闲聊） | 同上 |

**关键能力细节**：
- **LLM 分类优先 + 规则兜底**：LLM 只能从 9 个预定义领域中选择（不能发明），低于 0.5 置信度时置 `needs_clarification` 向用户追问；LLM 不可用/非法输出时回退确定性规则路由。
- **深度拆解（IntentDecomposer）**：LLM 把"人话困境"（如"闺蜜都二胎了我还单着"）映射到占星结构（7R/5R/月亮/土星）并富化分析任务。
- **追问消解**：识别"明年/下个月/下半年"等时间指代，继承上一轮活跃领域，注入 Timing 窗口偏移。
- **闲聊快路径**：10 字以内问候语直接温暖回应，不进 LLM、不进分析（省成本、快）。
- **合盘入口检测**：识别"男朋友/女朋友"等对象词 → 询问对方出生数据（多轮收数据）。

### 2.2 分析推理能力（第二层）

**统一接口**：`AnalysisModule.analyze(chart, person, params) → list[Fact]`，共 15 个分析模块。

**硬编码算术模块**（直接计算）：
| 模块 | 回答的问题 | 产出 |
|------|-----------|------|
| **CareerStrength** | 职业根基有多强？ | 主题综合评分（约 -10~+10） |
| **Finance** | 财务支撑力？（职业视角） | 二宫主/八宫主尊贵 + 财务相位评分 |
| **Opportunity** | 职业机会/贵人运？ | 吉星助力相位 + 11宫主/2宫主位势 |
| **Risk** | 换工作/创业有哪些风险？ | 凶星紧张相位 + 10宫主失势 + 12宫隐患 |
| **Timing** | 未来 N 个月哪些窗口有利/不利？ | 法达大限/子限 + 本轮问题 targets/helpers + 逐月行运触发 → 时间窗口 |
| **Daily** | 今天的能量天气？ | 今日快速行星对本命相位，映射到生活领域 |

**文法引擎驱动模块**（配置配方驱动，内容在 YAML）：
| 模块 | 回答的问题 | 核心结构 |
|------|-----------|---------|
| **PartnerTraits** | 你会被什么样的人吸引？ | 金/火/月相位 + 5/7/8宫 |
| **Psychology** | 职业心理状态/倦怠风险？ | 6宫工作量 + 12宫压力 + 月土/日土相位 |
| **RelationshipStatus** | 关系模式与健康度？ | 5/7宫 + 金/月/火 + 7宫主 |
| **RelationshipSynastry** | 这段双人关系是否匹配？ | 合盘相位 + 对方行星落你方5/7/8宫 |
| **MarriagePotential** | 婚姻潜力/承诺能力？ | 7宫 + 金/土/木 + 7宫主 + 时机 |
| **Wealth** | 财运格局？ | 2正财 + 8偏财 + 11进账 |
| **Health** | 身体健康概况？ | 1宫体质 + 6宫日常健康 |
| **Emotion** | 情绪模式？ | 月亮 + 4宫 + 12宫 |
| **Family** | 家庭根基/权威关系？ | 4宫 + 10宫 + 土星/月亮 |
| **Learning** | 学习天赋？ | 3宫 + 9宫 + 水星/木星 |

**Strategy 插件系统**：8 个领域默认策略（career 最重：Strength+Timing+Risk+Psychology 四模块 DAG）。新增技法 = 加 4 样东西（YAML 策略 + 分析模块/配方 + 知识库数据 + 注册），不改现有代码。

**结论生成（Reasoner，完全无 LLM）**：
- 证据按 polarity 分轨汇总：权重×置信度 形成有利/不利/中性/数据不足 verdict
- 核心模块失败 → 强制"数据不足"（宁可诚实不说，不硬造）
- 产出 `Conclusion`：摘要 + 最多 6 条 findings（含 polarity/confidence）+ 时间窗口 + 建议 + 数据缺口

**知识库规模（LLM 的"占星教材" + 确定性证据来源）**：20 个 YAML 约 4000 行——12宫语义场、10星性、尊贵/互溶/相位、飞星规则（120 条行星落宫 + 17 行星对 + 宫主）、转宫推导公式、交叉判断模板、时机规则、护栏。

### 2.3 时间技法（人生 K 线数据源）

| 技法 | 时间跨度 | 回答的问题 |
|------|---------|-----------|
| **法达 Firdaria** | ~10年大限 / ~1年子限 | 现在哪颗星在"管事"？这一章主题 |
| **日返 Solar Return** | 1 年（生日到生日） | 今年重点？ |
| **月返 Lunar Return** | ~27 天 | 这个月的氛围？ |
| **次限月亮 Progressed** | ~2.5 年/星座 | 当下的"情绪季节" |
| **三限月亮 Tertiary** | ~2.5 天/星座 | 细粒度情绪 |
| **行运窗口 WindowScanner** | 参数化（默认 12 个月，7 天/窗） | 每窗口机会分/压力分曲线 |

**Timeline 输出结构（前端 K 线的数据契约）**：
```
TimelineWindow: start / end / opportunity_score / pressure_score
                / quality(POSITIVE|NEGATIVE|NEUTRAL) / key_transits(top3) / net_score
Timeline: windows 序列 + best_window + worst_window + overall_quality
```

> `TimelineWindow.net_score` 是 WindowScanner 的内部/兼容聚合字段，用于窗口排序和旧前端契约；它不是用户可见的行星“净吉凶”，也不能覆盖 opportunity/pressure 双轨或法达权威。产品文案应展示窗口方向、证据与触发对象，不直接展示“净分”。
目前 `Timeline` 模型和 WindowScanner 计算引擎都已存在，但 **API 层尚未暴露**（见 §四）。

### 2.4 叙事能力（第三层）

**十大星灵人格**（人格只改语气，绝不改结论/极性）：
| 人格 | 定位 | 语气关键词 |
|------|------|-----------|
| 锆石 Zircon | 智慧导师 | 理性、引领、有分寸 |
| 黑曜石 Obsidian | 冷面守护 | 直接、简短、护短 |
| 紫水晶 Amethyst | 灵性直觉 | 诗意、洞察、超然 |
| 黄水晶 Citrine | 阳光鼓励 | 热情、乐观、赋能 |
| 粉晶 Rose Quartz | 温柔疗愈 | 柔软、共情、抚慰 |
| 绿松石 Turquoise | 冒险旅伴 | 好奇、鼓励尝试 |
| 月光石 Moonstone | 情绪映射 | 细腻、善变、流动 |
| 翡翠 Jade | 沉稳长者 | 平和、圆融、包容 |
| 石榴石 Garnet | 热血行动 | 果决、燃、推动 |
| 青金石 Lapis | 知识学者 | 考据、条理、深度 |

**回答长度**：deep 300-600 字；quick 120-180 字三段式（共情→核心判断→出路）。

**咨询节奏（consult_method 编译进 prompt）**：本命基调优先 → 当前章节（法达大限/子限）+ 本轮征象星/帮手星 → 对话验证（讲结构请用户核对）→ 验证通过才补行运触发时机。一轮只验证一条主线，给功课不给正确废话。

### 2.5 记忆能力（第四层）

**两层记忆**：
| 层 | 模型 | 内容 |
|----|------|------|
| 会话级 | Memory/MemoryItem | 谁在何时说了什么（逐条） |
| 长期画像 | ChartProfile | 跨会话累积的浓缩理解 |

**ChartProfile 画像内容**：
- `domain_summaries`：8 领域长期理解（summary + confidence + evidence_notes）
- `verified_findings`：已沉淀的占星判断（可被用户 confirmed/refuted 验证）
- `key_dates`：重要日期（"上次我们聊到…"）
- `lord_states`：行星/宫位层面累积观察
- `trust_score` + `trust_signals`：关系层数据

**写回管线**：咨询结束 → LLM 摘要（最多 12 轮）→ 增量合并画像 → 落库 → 生成成长事件（按 conclusion 去重，可安全重放）。

### 2.6 关系层（A2）——「像人」的关键

**信任等级（深度优先，一次深聊 > 十次闲聊）**：
| 等级 | 阈值 | 中文 |
|------|------|------|
| intimate | ≥ 20 | 深交 |
| trusted | ≥ 10 | 信任 |
| acquaintance | ≥ 3 | 认识 |
| stranger | ≥ 0 | 陌生 |

**信任信号权重**：深度咨询 6 · 验证判断确认 4 · 写日记 3 · 快速咨询 2 · 反驳判断 1 · 闲聊 0.5。

**关系行为**：
- **开场白**：首次见面自我介绍 / 老用户按等级前缀 + "上次聊到…"
- **邀请式引导**：信任 ≥ trusted 且回答不以问句结尾时 → "这件事我想给你细看，愿意的话我们做一次深入的推演"
- **验证判断**：用户对沉淀判断确认/反驳，确认是最大信任信号

### 2.7 内容陪伴能力

| 能力 | 后端状态 | 说明 |
|------|---------|------|
| **每日来信** | ✅ 完成 | 每天一封（幂等按天），sender 取当天最显著行运行星（月亮/太阳/木星…），100-150 字温暖信，LLM 或降级模板 |
| **花园日记** | ✅ 完成 | CRUD + AI 一句成长记录（≤40字）+ 自动记入成长时间轴 |
| **成长时间轴** | ✅ 完成 | LifeEvent 统一视图：人生事件 / 咨询 / 日记 / 行运 四类 |
| **咨询模式** | ✅ 完成 | quick（精简）/ deep（完整）/ annual / chart / free（后三者框架预留） |

### 2.8 安全与合规

- **危机检测**：22 个自伤/自杀关键词 → **阻断占星回答**，返回心理援助热线（400-161-9995）引导；6 个低落关键词 → 仅记日志
- **免责声明**：每条回答末尾带"不构成医疗/法律/财务建议"
- **未成年人保护**：代码预留，未实现
- **隐私**：出生数据 Fernet 加密存储、可删除；解密失败返回 410 引导重新建档

---

## 三、产品当前形态

### 3.1 技术栈

| 端 | 技术 | 说明 |
|----|------|------|
| 后端 | Python 3.11 + FastAPI + uvicorn | `application/api/main.py` 单一入口 |
| 前端 | uni-app（Vue3 + TS + Vite）| 一套代码可发 H5 / 小程序 / App |
| 占星引擎 | pyswisseph | Swiss Ephemeris，Moshier 回退 |
| 存储 | SQLite（`data/garden_spirit.db`）| 7 表，Fernet 加密 |
| LLM | openai 兼容协议（DeepSeek 已配通）| 只做意图分类 + 叙事转述 |
| 地图 | 高德 geocode（城市名→经纬度+时区）| 解析失败明确报错，不静默降级 |

### 3.2 用户旅程（当前已实现）

```
① 建档（frontend index 页）
   名字 + 出生日期 + 出生时间（可勾选"不知道"→正午降级）+ 城市
   → POST /person（加密落库）
   ↓
② 花园首页（index 页）
   今日来信预览 + 继续昨天的话题 + 我的宇宙领域数
   ↓
③ 对话（chat 页）← 核心循环
   开场白（按信任等级）→ 问问题 → 人格化回答 → 信任渐进升级
   ↓
④ 我的宇宙（universe 页）
   8 领域长期理解卡片 + 沉淀判断列表
   ↓
⑤ 信箱（mailbox 页）
   今日来信 + 过往信件
```

### 3.3 前端现状（4 页）

| 页面 | 路由 | 职责 | 现有 UI |
|------|------|------|---------|
| 花园/建档 | `pages/index/index` | 建档表单 + 花园聚合首页 | 表单 + 3 张信息卡 + 导航链接 |
| 对话 | `pages/chat/chat` | 与星灵对话 | 气泡聊天 + 信任标签 + 思考态 |
| 信箱 | `pages/mailbox/mailbox` | 每日来信 | 今日信卡片（高亮）+ 历史信列表 |
| 我的宇宙 | `pages/universe/universe` | 长期画像 | 领域卡片（把握%）+ 沉淀判断列表 |

**当前设计语言（功能验证型，待重构）**：
- 深绿渐变背景 `#0d1f1a → #14332a → #1d4436`
- 主色 `#7cb342`（绿）/ 辅色 `#a5d6a7` / 文字 `#e8f5e9`
- 玻璃拟态卡片（rgba 白 0.07）
- Emoji 视觉语言：🌙 🌿 💌 🪐 🌱（月光、花园、信件、宇宙意象）
- 全程自定义导航栏（navigationStyle: custom）
- 隐喻体系：花园=产品 · 星灵=Agent · 宇宙=画像 · 信箱=来信

### 3.4 API 契约（14 个端点）

| 端点 | 方法 | 用途 | 前端已接 |
|------|------|------|:---:|
| `/health` | GET | 存活 + LLM 可用性 | ✅ |
| `/person` | POST | 建档（加密落库） | ✅ |
| `/person/{id}` | GET | 读档 | ✅ |
| `/chat` | POST | 对话（核心）| ✅ |
| `/person/{id}/profile` | GET | 长期画像 | ✅ |
| `/person/{id}/opening` | GET | 开场白（按信任等级） | ✅ |
| `/person/{id}/timeline` | GET | 成长时间轴（LifeEvent）| ⬜ 未接 |
| `/person/{id}/findings/{fid}/feedback` | POST | 验证沉淀判断（confirmed/refuted）| ⬜ 未接 |
| `/journal` | POST | 写日记 | ⬜ 未接（无页面） |
| `/person/{id}/journal` | GET | 日记列表 | ⬜ 未接 |
| `/journal/{id}` | PUT | 编辑日记 | ⬜ 未接 |
| `/mailbox/today` | POST | 今日来信 | ✅ |
| `/person/{id}/letters` | GET | 信件列表 | ✅ |
| `/garden` | GET | 花园首页聚合 | ✅ |

**ChatOut 响应字段**：`answer`（纯文本）/ `session_id` / `intent_domain` / `needs_related_person` / `written_back` / `mode` / `trust_level`。

### 3.5 当前运行方式
- 后端：`uvicorn`，默认 `127.0.0.1:8756`
- 前端：uni-app H5 dev，`localhost:5173`，`VITE_API_BASE` 注入
- 环境变量：`GS_AMAP_KEY`（高德）· `GS_ENCRYPTION_KEY`（加密）· `LLM_*`（DeepSeek）· 测试用 `GS_LLM_DISABLE=1` + `GS_GEOCODE_OFFLINE=1`

---

## 四、能力已具备但前端未接入

**这是 UI/UX 规划最重要的输入**——以下能力的后端全部已就绪，前端尚未暴露，直接决定"能设计哪些界面、需要哪些后端配合"。

| # | 能力 | 后端 | 前端 | 缺口说明 |
|---|------|:---:|:---:|---------|
| 1 | **人生 K 线 / Timeline 可视化** | ✅ WindowScanner 引擎 + Timeline 模型 | ⬜ | **无 API 端点暴露曲线数据**，无图表页。PRD P1 明确任务 |
| 2 | **日记（Journal）** | ✅ CRUD 全通 | ⬜ | 无写日记页面、无日记列表页；`mood` 情绪标签字段闲置 |
| 3 | **咨询模式选择** | ✅ quick/deep/annual/chart/free | ⬜ | API 接收 `mode` 但前端从不传；无"今天想怎么聊"入口 |
| 4 | **星灵人格选择** | ✅ 10 人格完整 | ⬜ | API 接收 `persona` 但前端从不传；无选人格界面 |
| 5 | **合盘（相关方）** | ✅ 多轮收数据 + synastry 分析 | ⚠️ | `needs_related_person` 字段有返回但前端未处理；`_restore_related_person` 目前是 no-op（跨会话对象不恢复） |
| 6 | **沉淀判断验证** | ✅ feedback 端点 + 信任信号 | ⬜ | "我的宇宙"页展示了 findings 但无"对上了/不对"交互 |
| 7 | **成长时间轴** | ✅ `/person/{id}/timeline` 端点 | ⬜ | 无时间轴页面（区别于 K 线：这是人生事件回看） |
| 8 | **结构化结论数据** | ✅ Conclusion/Finding/TimePeriod 生成 | ⬜ | `/chat` 只返回纯文本 `answer`；findings、时间窗口、confidence 未暴露给前端（富交互证据卡需要后端加字段） |
| 9 | **星盘可视化** | ✅ Chart 计算器 | ⬜ | **无任何端点返回星盘原始数据**（行星/宫位/相位），前端看不到本命盘图形 |
| 10 | **每日推送** | ⬜ L6 未做 | ⬜ | 来信是拉取式（打开页面才生成）；定时推送未实现 |
| 11 | **验前事（学习层）** | ⬜ L5 未写 | ⬜ | 用人生事件校准置信度，尚未开始 |
| 12 | **出生时间矫正** | ⬜ | ⬜ | PRD v1.5 计划 |

---

## 五、面向 UI/UX 的能力→界面映射

> 基于后端已具备的能力，规划信息架构。核心原则：**先做"花园"的陪伴感，再做"宇宙"的深度**；所有内容性界面都要体现"证据可追溯"（讲得清）与"地图而非判决书"（给资源给出路）。

### 5.1 推荐信息架构（8 个界面区域）

| 界面 | 对应能力 | 后端依赖 | 优先级 |
|------|---------|---------|:---:|
| **花园首页**（现有 index 重构）| 今日来信 / 继续昨天 / 领域概览 / 信任等级 | `/garden` + `/opening` | P0 |
| **对话页**（现有 chat 重构）| 意图理解 + 推理 + 10 人格 + 咨询模式 + 邀请式引导 | `/chat` | P0 |
| **信箱页**（现有 mailbox 打磨）| 每日来信（行运映射）+ 信件时间线 | `/mailbox/today` + `/letters` | P0 |
| **我的宇宙页**（现有 universe 深化）| 领域画像 + 沉淀判断 + **验证交互** | `/profile` + feedback | P0 |
| **日记页**（新）| 写日记 + AI 成长记录 + 情绪标签 | `/journal` CRUD | P1 |
| **成长时间轴页**（新）| 人生事件 / 咨询 / 日记 / 行运 混合时间线 | `/person/{id}/timeline` | P1 |
| **人生 K 线页**（新）| 未来 12 月机会/压力曲线（今日/本月/今年/十年切尺度）| **需后端加 Timeline 端点** | P1 |
| **星盘页**（新，v0.5+）| 本命盘可视化（宫位/相位/尊贵）| **需后端加 Chart 端点** | P2 |

### 5.2 关键交互设计机会

1. **咨询模式入口**："今天想怎么聊？快速一句话 / 深度聊透 / 年度主题 / 看我的盘 / 自由聊聊"——后端已支持，前端只缺入口。
2. **星灵人格选择**：10 人格的"契约"要可视化（每个是一个说话风格 + 隐喻），可放建档后 or 花园页。
3. **信任等级的渐进解锁**：陌生→深交，UI 上做"星灵越来越了解你"的成长感（信任进度条/阶段徽章）；邀请式引导出现时给足仪式感。
4. **沉淀判断验证**："这条说的是你吗？对上了 / 不对"——这是关系层最大信任信号，也是"验前事"学习层的前置（用户反馈会校准置信度），UI 价值极高。
5. **证据可追溯**：回答中涉及"土星落九宫"等结论时，可点开看证据链（哪个相位/宫位支撑），兑现"讲得清"承诺。
6. **K 线可视化**：机会分/压力分双曲线 + 最好/最差窗口高亮 + 关键行运标注（"木星过十宫"），切 今日/本月/今年/十年。
7. **思考态设计**：LLM 回答 10s+，现有"正在查看你的星图……"需要升级为分阶段状态（理解问题中 → 查看星图 → 正在为你组织语言）。

### 5.3 视觉方向（基于现有隐喻的延续建议）

- 保持深绿夜境 + 月光意象，"花园"是产品母题（每日回来浇水=打开 App）
- 行星是核心视觉元素：信箱来信的 sender 用行星头像区分（月亮/太阳/木星…）
- 人格差异可做微视觉（同一条证据，锆石冷静排版 vs 粉晶温暖排版）
- 信任等级做"花园成熟度"隐喻（种子→幼苗→开花→果实），而非冷冰冰的等级条

---

## 六、对 UI 设计有约束的关键事实

1. **回答当前是纯文本**：`/chat` 只返回 `answer` 字符串。若想做气泡内的结构化组件（证据卡、K 线、时间窗按钮），**需要后端在 ChatOut 里附加结构化字段**（或新增只读端点），规划时要一并列入后端工作。
2. **星盘数据不外泄（原则一）**：Chart 永不跨层给 Application，前端永远拿不到原始星盘数值。星盘可视化需要后端设计"仅供展示的脱敏星盘视图"。
3. **LLM 延迟**：深聊 10s+（前端 chat 超时已放宽到 60s）。思考态 / 流式输出 / 缓冲文案是必需，不是锦上添花。
4. **LLM 缺失可用**：无 LLM key 时所有回答走降级模板（内容不变、语气朴素）。UI 不应依赖 LLM 特色。
5. **出生数据是敏感数据**：加密存储；UI 需有隐私授权、删除入口、精度声明（未知时间 → 宫位结论受限提示）。
6. **危机检测优先**：命中危机关键词时回答是固定求助引导，UI 应允许此场景"异常突出"（红色主题、暂停占星内容展示）。
7. **免责声明常驻**：每条回答末尾带免责；产品层需要"占星不构成决策依据"的持久感知。
8. **移动端优先**：uni-app 跨 H5/小程序/App，所有 UI 以单手拇指操作为主。
9. **多轮对话是有状态的**：追问消解 / 合盘收数据 / 邀请式引导都依赖多轮上下文，前端要保留 session_id 并支持"上一轮话题延续"的视觉提示。
10. **测试纪律**：342 测试全绿是硬约束，前端改动不破坏数据契约（`frontend/src/api/client.ts` 是唯一契约层）。

---

## 七、V8 Report Compiler 契约

> **V8 口径**：报告不是 Chat 的替代品，也不是前端拼出来的预测页。报告是 Domain 证据链、时间线、沉淀判断、来信记忆与多轮 Chat 主题被编排后的结构化资产。

本章用于承接 `docs/frontend_ia_uiux_v8.md` 的“主题观星台 / 小报告 / 标准报告 / 深度报告”规划，定义后端 Report Compiler 与前端展示之间的契约边界。当前阶段允许前端展示入口与“证据链待接入”状态，不允许生成未被后端支持的年运、月运、人生走向、婚运、桃花、事业、财富等预测结论。

### 7.1 产品分层

| 类型 | 用户问题 | 商品形态 | 当前支撑 | V8 建议 |
|---|---|---|---|---|
| 小报告 | “我最近事业卡在哪里？”“这段关系怎么看？” | 单点结构化解读，可保存，可继续聊 | `/chat` 已能给 Domain 驱动回答，但缺报告资产 API | 最先做 MVP：从一次主题 Chat / Finding 编排成短报告 |
| 标准报告 | 情感、事业、财富、学业、自我、家庭 / 亲子 | 完整主题章节、证据链、待验证点、建议、复盘入口 | 需要 Report Compiler | 第二阶段主力付费产品 |
| 深度报告 | 年运、月运、人生走向、0-100 岁人生规划 | 时间线、多章节、版本化、长期复盘、继续深聊上下文 | 需要 Report Compiler + 时间线契约 | 后置，不提前高价商业化 |

### 7.2 主题观星台分类与报告边界

| 主题 | 报告类型建议 | 必需证据 | 前端当前状态 |
|---|---|---|---|
| 年运 | 深度报告 | 年度时间窗、机会/压力双轨、关键行运、年度主题、复盘节点 | 只展示“将接入星图证据链” |
| 月运 | 小报告 / 深度报告切片 | 月度节律、情绪提醒、行动窗口、关键触发 | 只展示“将接入星图证据链” |
| 人生走向 | 深度报告 | 法达章节、长期阶段、关键转折、人生主题 | 只展示“将接入星图证据链” |
| 情感 | 小报告 / 标准报告 | 关系宫位、承载者、相关相位、模式与资源 | 可先从 Chat 沉淀小报告开始 |
| 事业 | 小报告 / 标准报告 | 事业语义场、承载者、机会/压力、行动建议 | 可先从 Chat 沉淀小报告开始 |
| 财富 | 小报告 / 标准报告 | 正财/偏财语义切片、资源流动、风险提醒 | 可先从 Chat 沉淀小报告开始 |
| 学业 | 小报告 / 标准报告 | 学习方式、考试/深造语义场、节律建议 | 可先从 Chat 沉淀小报告开始 |
| 自我 | 标准报告 | 自我星盘轮、灵魂碎片、人格主题、确认记录 | 与自我星盘轮联动 |
| 家庭 / 亲子 | 小报告 / 标准报告 | 原生家庭/父母/亲子语义场、承载者、模式与边界 | 可先从 Chat 沉淀小报告开始 |

### 7.3 Report Compiler 输入契约

Report Compiler 不直接“算命”。它只编排已有 Domain / Application 输出。

建议输入：

```ts
interface ReportCompileInput {
  person_id: string;
  report_type: "mini" | "standard" | "deep";
  theme: "annual" | "monthly" | "life" | "relationship" | "career" | "wealth" | "study" | "self" | "family";
  source: "chat" | "observatory" | "finding" | "letter" | "manual";
  session_id?: string;
  finding_ids?: string[];
  letter_ids?: string[];
  journal_ids?: string[];
  persona?: string;
  question?: string;
  time_range?: {
    start?: string;
    end?: string;
    scale?: "month" | "year" | "life_stage";
  };
}
```

输入来源优先级：

1. 明确用户问题和主题。
2. Domain 产生的 Conclusion / Finding / TimePeriod / Evidence。
3. 已确认记忆、来信、手账、碎片点亮。
4. Chat session 上下文。
5. 星灵 persona 只影响表达风格，不改变占星结论。

### 7.4 Report Compiler 输出契约

建议输出：

```ts
interface ReportOut {
  id: string;
  person_id: string;
  report_type: "mini" | "standard" | "deep";
  theme: string;
  title: string;
  status: "draft" | "ready" | "archived";
  created_at: string;
  updated_at: string;
  summary: string;
  sections: ReportSection[];
  evidence: ReportEvidence[];
  timeline?: ReportTimeline;
  verification_points: VerificationPoint[];
  continue_chat: {
    session_seed: string;
    suggested_prompts: string[];
  };
  disclaimers: string[];
}

interface ReportSection {
  key: string;
  title: string;
  body: string;
  source_refs: string[];
  confidence?: "low" | "medium" | "high";
}

interface ReportEvidence {
  id: string;
  label: string;
  kind: "finding" | "conclusion" | "time_window" | "fragment" | "letter" | "journal";
  summary: string;
  source_ref: string;
}

interface ReportTimeline {
  windows: Array<{
    start: string;
    end: string;
    quality: "positive" | "negative" | "neutral";
    opportunity_score?: number;
    pressure_score?: number;
    title: string;
    summary: string;
    key_transits: string[];
  }>;
}

interface VerificationPoint {
  id: string;
  text: string;
  source_ref: string;
  status: "unverified" | "confirmed" | "refuted";
}
```

关键边界：

- `body` 可以由 LLM 负责疗愈表达，但必须引用 `source_refs`。
- `evidence` 必须来自后端 Domain / Conclusion / Finding / Timeline / Memory，不由前端构造。
- `timeline.windows` 可以展示 `opportunity_score` 与 `pressure_score` 双轨，但不得把 `TimelineWindow.net_score` 暴露为“净吉凶分”。
- `continue_chat.session_seed` 是报告进入 Chat 的上下文种子，不是让前端重新生成报告。

### 7.5 推荐 API 端点

| 端点 | 方法 | 用途 | 备注 |
|---|---|---|---|
| `/person/{id}/reports` | GET | 已购 / 已生成报告列表 | 我的页只展示资产，不售卖预测入口 |
| `/reports/{report_id}` | GET | 报告详情 | 前端只读展示 `ReportOut` |
| `/reports/compile` | POST | 生成报告 | 后端编排 Domain 输出与记忆资产 |
| `/reports/{report_id}/continue-chat` | POST | 将报告带入 Chat | 返回 session_id 或 seed message |
| `/reports/{report_id}/verification/{point_id}` | POST | 验证报告中的判断点 | 与现有 Finding feedback 口径一致 |

### 7.6 前端展示规则

主题观星台当前只允许展示三种状态：

1. `证据链待接入`：后端无报告能力，展示占位。
2. `可生成小报告`：主题 Chat 或 Finding 已足够形成单点资产。
3. `已生成报告`：存在 ReportOut，可进入阅读与继续 Chat。

前端禁止：

- 根据主题名自行写预测结论。
- 在卡片上写“今年会升职 / 桃花很旺 / 必有婚姻机会”等未由后端输出的判断。
- 把商品页做成“报告越贵，结论越玄”。
- 为了售卖报告，故意让免费 Chat 回答变弱。

前端应该强调：

- 报告会把已经聊出的内容整理成可保存资产。
- 报告有章节、证据链、时间线、复盘点。
- 报告可以带回 Chat 继续深聊。
- 免费 Chat 仍然可以深入，只是不承担长期报告资产的完整编排。

### 7.7 小报告 MVP 建议

小报告优先从“Chat 后整理”切入，而不是从主题观星台直接硬卖。

推荐触发：

- Chat 已产生 `lit_fragments` / `seen_fragments` / `keepsake_created`。
- 同一主题连续追问 2 轮以上。
- 存在至少 1 条 `Finding` 或可引用的 `Conclusion`。
- 用户点击“整理成报告”。

小报告章节建议：

1. 这次问题的核心。
2. 星图里被触发的证据。
3. 你现在的资源与卡点。
4. 可以验证的一句话。
5. 接下来可以怎么做。
6. 带着这份报告继续问星灵。

### 7.8 标准报告建议

标准报告适合情感 / 事业 / 财富 / 学业 / 自我 / 家庭亲子。

章节建议：

1. 主题总览。
2. 关键证据链。
3. 主要模式。
4. 资源与优势。
5. 压力与风险。
6. 未来 1-3 个行动窗口（如果后端时间线支持）。
7. 待验证判断。
8. 复盘与继续 Chat。

### 7.9 深度报告建议

深度报告适合年运 / 月运 / 人生走向 / 0-100 岁人生规划。

人生规划不建议机械按平均 7 岁切段作为算法主轴。更合理的方式是：

- **占星主轴**：法达大限 / 子限、次限月亮、日返/月返、行运窗口。
- **产品阅读层**：童年根基、学习成长、关系探索、事业建立、家庭承诺、中年转向、长期沉淀。
- **展示策略**：先展示当前阶段、前一阶段、后一阶段，再允许用户展开更远时间段。
- **付费策略**：不要一上来售卖完整 0-100 岁高价报告；先验证年运 / 月运 / 单主题标准报告的留存和复盘价值。

### 7.10 与 Chat 的关系

报告和 Chat 的平衡口径：

```text
Chat 负责陪伴与探索。
报告负责整理与保存。
Chat 可以聊得很深，但它是流动的。
报告把重要内容变成可复盘资产。
```

用户拿报告继续 Chat 时：

- Chat 应读取报告摘要、章节 key、证据 refs、待验证点。
- Chat 不重新生成报告全文。
- Chat 可以围绕某一章节追问、解释、验证或转成行动建议。
- 新的确认、行动和记忆应继续回流到碎片 / Finding / 信箱。

### 7.11 Definition of Done

Report Compiler 阶段完成标准：

- 后端存在 `ReportCompileInput` → `ReportOut` 的稳定契约。
- 报告内容每段都有 `source_refs`。
- 前端主题观星台能区分“待接入 / 可生成 / 已生成”。
- 我的页只展示“已购报告 / 已生成报告”资产，不成为预测入口。
- Chat 的“整理成报告”不再只是 toast，而是进入小报告生成或报告草稿页。
- 所有报告都能继续进入 Chat，并保留证据链上下文。
- 用户可见时间线只展示 opportunity / pressure 双轨和解释，不展示 `net_score`。

---

*报告完 · V8 后续若进入报告实现，应先落 Report Compiler 后端契约，再接主题观星台与 Chat 小报告入口。*
