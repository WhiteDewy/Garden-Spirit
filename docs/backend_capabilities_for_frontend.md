# 后端能力清单（供前端设计）

> 生成日期：2026-08-15  
> 用途：给前端视觉/交互任务做输入，不是后端施工 TODO。  
> 产品口径：Garden-Spirit 是「占星驱动的自我探索陪伴 Agent」。占星结论由 Domain 层确定性产出，LLM 只负责转述、疗愈语气与陪伴表达。

---

## 1. 总览：后端已经具备什么

后端已经不是单纯 `/chat` 问答服务，而是一套围绕「建档 → 咨询/随聊 → 记忆沉淀 → 成长反馈 → 回访」的 Agent 系统。

| 能力区 | 后端状态 | 前端设计价值 |
|---|---|---|
| 用户建档与星盘计算 | 已有建档、读取、删除、导出 | onboarding、档案卡、合规中心 |
| 主题观星台 Agent | 已有多模式字段、三层意图、宫位追问/深挖/确认闭环 | 咨询页、追问体验、证据链展示 |
| 随聊陪伴 | 已有情绪感知、请求类型、软牵引门控、记忆写回 | 聊天页可展示「被理解」和「轻邀请」 |
| 10 星灵人格 | 10 行星人格已配置，支持 `/chat` persona 参数 | 星灵切换器、星灵主页、今日推荐 |
| 记忆召回 | 已有 recall/opening/garden 记忆豆荚，支持 persona 镜头 | 首页「我记得你」、星灵开场白 |
| 自我星盘轮 | 34 子类、深度分、等级、行动次数、今日 top3 | universe / 内在宇宙成长可视化 |
| 来信式日记 / 信箱 | 每日来信、keepsake 来信、已读红点、推导链 | 信箱页、首页今日来信、成长回声 |
| 日记 | 建/查/改 + AI 摘要 + 信任信号 | 日记页、树洞/手账入口 |
| 画像与信任层 | 领域摘要、关键日期、验证判断、trust_level | 用户关系进度、可信记忆卡 |
| 待验证与人生事件 | findings、feedback、life events、timeline | 成长校准页、时间线、验证清单 |
| 合盘对象 | related person 持久化、列表、删除，chat 可带 related id | 合盘弹窗、关系人管理 |
| 偏好与推送 | preferences、web push 订阅/退订/触发 | 设置页、通知开关、人格偏好 |
| 合规 | 全量导出、全量删除 | 隐私中心、删除前导出 |

---

## 2. API 能力地图

### 2.1 基础与用户

| 方法 | 路径 | 作用 | 前端页面 |
|---|---|---|---|
| `GET` | `/health` | 服务健康、版本、LLM 可用性 | 调试/诊断 |
| `POST` | `/person` | 创建用户档案，提交出生信息 | onboarding |
| `GET` | `/person/{person_id}` | 读取用户档案 | 首页/设置/档案页 |
| `GET` | `/person/{person_id}/export` | 导出用户全量明文数据 | 隐私中心 |
| `DELETE` | `/person/{person_id}` | 删除用户全量数据 | 隐私中心 |

`PersonOut` 关键字段：

| 字段 | 含义 | 前端建议 |
|---|---|---|
| `id` | 用户 id | 全局持久化 |
| `name` | 用户名 | 问候、档案卡 |
| `gender` | 性别，可为空 | 档案展示；不要强制 |
| `place_name` | 出生地点展示名 | 档案卡 |
| `time_known` | 出生时间是否确定 | 星盘可信提示 |
| `house_system` | 宫制 | 高级设置/档案 |
| `created_at` | 建档时间 | 可选展示 |
| `is_premium` | 会员预留位 | 当前只是预留，不建议重 UI 投入 |

当前缺口：没有 `PUT/PATCH /person/{id}`，所以前端不能做完整档案编辑；出生数据冻结是当前设计。

---

### 2.2 Chat / Agent 主入口

| 方法 | 路径 | 作用 | 前端页面 |
|---|---|---|---|
| `POST` | `/chat` | 主题观星台 + 随聊陪伴 + 记忆写回 + 成长点亮 | chat / consult |

`ChatIn`：

| 字段 | 必填 | 含义 | 前端建议 |
|---|---:|---|---|
| `person_id` | 是 | 当前用户 | 从本地档案取 |
| `session_id` | 否 | 同一段多轮会话 id；留空后端生成 | 聊天页必须保存并复用 |
| `message` | 是 | 用户输入 | 输入框 |
| `persona` | 否 | 星灵人格，值为行星英文：`sun/moon/...` | 星灵切换器 |
| `mode` | 否 | 咨询模式：`quick/deep/annual/chart/free`，默认 `deep` | 建议先开放 quick/deep/free |
| `related_person_id` | 否 | 合盘对象 id | 合盘流程带入 |

`ChatOut`：

| 字段 | 含义 | 前端建议 |
|---|---|---|
| `answer` | Agent 回复正文 | 主气泡 |
| `session_id` | 本轮会话 id | 保存，后续轮次复用 |
| `intent_domain` | 识别出的领域 | 可作为气泡标签/埋点 |
| `needs_related_person` | 本轮需要对方出生信息 | 弹合盘对象表单 |
| `written_back` | 是否写回记忆/画像 | 可轻提示「已记住」 |
| `mode` | 实际生效模式 | 展示当前模式 |
| `trust_level` | `stranger/acquaintance/trusted/intimate` | 关系进度/首页 chip |
| `emotion` | 情绪感知结果 | 随聊气泡下情绪光点 |
| `request_type` | 用户诉求类型 | 判断是否展示建议/陪伴 UI |
| `lit_fragments` | 本轮点亮的 34 子类 | 展示「星尘 +1/+10」 |
| `seen_fragments` | 用户确认上一轮后补亮 +5 | 展示「被照见」反馈 |
| `keepsake_created` | 是否生成 keepsake 来信 | toast + 信箱入口 |
| `actioned_fragments` | 用户行动回报 +20 | 展示「真的做到了」成长反馈 |

前端最该接的不是更多文字，而是 `lit_fragments / seen_fragments / actioned_fragments / keepsake_created`。这些字段是成长复利现场反馈，能让用户看到「聊天正在点亮我的内在宇宙」。

V8 边界：`intent_domain`、`domain_summaries`、`FindingOut.domain`、`TimelineEventOut.domain` 等字段是后端内部语义分类 / API metadata，用来做召回、排序、证据链和埋点；前端不要直接把 `career/wealth/relationship` 或旧中文「事业/财富/感情」渲染成用户入口。需要展示时统一经过 V8 copy 适配层，转成「成就与方向 / 资源与价值 / 亲密与连接」等内在主题语言。

---

### 2.3 星灵 Persona 与今日推荐

| 方法 | 路径 | 作用 | 前端页面 |
|---|---|---|---|
| `GET` | `/person/{person_id}/recommended-spirits` | 推荐今天适合见的星灵 | 首页/星灵选择器 |
| `POST` | `/chat` with `persona` | 指定本轮回复人格 | 聊天页 |
| `GET` | `/person/{person_id}/recall?persona=...` | 用该星灵的记忆镜头排序/重述记忆豆荚 | 首页/星灵页 |
| `GET` | `/person/{person_id}/opening?persona=...` | 用该星灵口吻生成开场白 | 首页/聊天入口 |
| `GET` | `/garden?person_id=...&persona=...` | 首页聚合时套用星灵记忆镜头 | 首页 |

10 星灵已经配置在后端，分别是：

| persona key | 星灵 | 产品角色 |
|---|---|---|
| `sun` | 太阳 | 想被看见的我 |
| `moon` | 月亮 | 想被抱抱的我，默认兜底 |
| `mercury` | 水星 | 想说话的我 |
| `venus` | 金星 | 想爱与被爱的我 |
| `mars` | 火星 | 想要就冲的我 |
| `jupiter` | 木星 | 想飞的我 |
| `saturn` | 土星 | 想负责的我 |
| `uranus` | 天王星 | 想挣脱的我 |
| `neptune` | 海王星 | 想做梦的我 |
| `pluto` | 冥王星 | 想深挖的我 |

`RecommendedSpiritsOut`：

| 字段 | 含义 | 前端建议 |
|---|---|---|
| `spirits[]` | 推荐星灵列表，按分数降序 | 首页 top3 / 选择器 |
| `generated_at` | 生成时间 | 可选 |

`SpiritRecommendationOut`：`planet/name/healing_name/style/score/reason/is_default/is_firdaria_major_lord/is_firdaria_sub_lord`。

当前缺口：后端有 `all_personas()`，但没有 `GET /personas`；前端若要展示完整静态人格列表，短期可以本地写死 10 星，长期建议补端点。

---

### 2.4 Garden 首页聚合

| 方法 | 路径 | 作用 | 前端页面 |
|---|---|---|---|
| `GET` | `/garden?person_id=...&persona=...` | 首页聚合：今日来信、继续昨天、领域、红点、灵魂碎片、记忆 | 首页 |
| `GET` | `/person/{id}/opening?persona=...` | 独立开场白 | 首页/聊天页 |
| `GET` | `/person/{id}/recall?persona=...` | 独立记忆召回 | 首页/记忆页 |

`GardenState`：

| 字段 | 含义 | 前端建议 |
|---|---|---|
| `person_id` | 用户 id | - |
| `today` | 今日日期，盘主本地日 | 今日卡片 |
| `letter` | 今日星灵来信 | 首页信件卡 |
| `continue_from` | 最近会话摘要 `{conversation_id, summary, started_at}` | 「继续昨天」入口 |
| `domains` | 已有画像领域 | 我的宇宙/领域标签 |
| `trust_level` | 当前关系等级 | 信任 chip |
| `pending_verifications` | 待验证判断数 | 我的宇宙红点 |
| `letter_unread` | 今日来信是否未读 | 信箱红点 |
| `soul_fragments` | 今日 top3 灵魂碎片 | 首页星尘/小芽 |
| `recall` | 记忆豆荚 | 「我记得你」卡片 |

设计建议：首页不要再只是导航页。后端已经能支持「今日醒来的星灵 + 今日来信 + 继续昨天 + 记忆豆荚 + 今日碎片 + 待验证」的完整回家体验。

---

### 2.5 Recall / Opening 记忆能力

| 方法 | 路径 | 作用 |
|---|---|---|
| `GET` | `/person/{id}/recall?persona=...` | 返回确定性记忆豆荚 |
| `GET` | `/person/{id}/opening?persona=...` | 返回进入花园时的一句话开场 |

`RecallOut`：

| 字段 | 含义 |
|---|---|
| `items` | 记忆豆荚列表 |
| `has_memory` | 是否有可用记忆 |

`RecallItem.kind` 可能来源：

| kind | 含义 | UI 建议 |
|---|---|---|
| `key_date` | 画像关键日期 | 时间记忆卡 |
| `confirmed_finding` | 用户确认过的判断 | 「你确认过」卡 |
| `domain_summary` | 某领域摘要 | 领域记忆卡 |
| `top_fragment` | 点亮账本 top | 成长碎片卡 |
| `recent_topic` | 最近会话话题 | 继续昨天卡 |

记忆镜头是确定性排序/话术，不是 LLM 编造。不同 persona 只是选择「先想起哪类记忆」。

---

### 2.6 自我星盘轮 / 灵魂碎片

| 方法 | 路径 | 作用 | 前端页面 |
|---|---|---|---|
| `GET` | `/person/{id}/fragments` | 全部 34 子类 + 深度分 + 等级 + 行动次数 | universe / 自我星盘轮 |
| `GET` | `/person/{id}/soul-fragments/today` | 今日 top3 点亮碎片 | 首页/今日卡 |
| `POST` | `/chat` | 触发点亮、照见、行动反馈 | 聊天页 |

`FragmentOut`：

| 字段 | 含义 | 前端建议 |
|---|---|---|
| `id` | 子类 id | 图标映射 key |
| `zone` | `planet/house/sign` | 三个区层 |
| `name` | 展示名 | 卡片标题 |
| `triggers` | 为什么会点亮 | 详情说明 |
| `depth` | 深度分 | 亮度/成长值 |
| `level` | 0-5 成长级 | 形态/光晕，不必换图标 |
| `action_count` | 真实行动次数 | level 4/5 门槛提示 |

`SoulFragmentOut`：`id/name/zone/delta`，适合做「今天亮起来的三颗星」。

等级规则后端已经统一出，不建议前端再自己计算 `level`。

---

### 2.7 Mailbox / 来信式日记

| 方法 | 路径 | 作用 | 前端页面 |
|---|---|---|---|
| `POST` | `/mailbox/today` | 获取/生成今日来信，按天幂等 | 信箱/首页 |
| `GET` | `/person/{id}/letters` | 历史来信分页（20 条一页） | 信箱 |
| `POST` | `/person/{id}/letters/read-today` | 今日来信标记已读，消除首页红点 | 信箱 onLoad |
| `POST` | `/chat` | 倾诉/ memorable 时可能生成 keepsake 来信 | 聊天页 |

`GET /person/{id}/letters` 分页参数：`page`（默认 1）、`page_size`（默认 20）、`kind`（可选 `daily`=日推历史 / `keepsake`=记忆来信；省略=全部）。
响应为信封：`{ items: LetterOut[], total, page, page_size, has_more }`。日推按 `letter_date` 倒序（同一天内按创建先后）。

`LetterOut`：

| 字段 | 含义 | 前端建议 |
|---|---|---|
| `id/person_id/letter_date` | 基础标识 | 列表 key/日期 |
| `sender/sender_zh` | 发信星灵 | 头像/签名 |
| `title/body` | 标题与正文 | 主内容 |
| `kind` | `daily` / `keepsake` 等 | 分版式 |
| `created_at/read_at` | 创建/已读时间 | 红点/排序 |
| `primary_need` | 来信主需求 | keepsake 解释卡 |
| `healing_name` | 疗愈名落款 | 签名卡 |
| `soul_fragments` | 次需求点亮碎片 | 脚注/星尘 |
| `lit_fragments` | 当日随聊点亮碎片 | 关联到自我星盘轮 |
| `explain` | 为什么是这颗星的推导链 | 「为什么这封信」展开 |
| `entry` | 是否词条式来信 | 轻量版式 |

当前缺口：`consult_followup` 在模型注释里有，但生产路径尚未实现；前端不要把它当已稳定能力设计重流程。

---

### 2.8 Journal 日记

| 方法 | 路径 | 作用 | 前端页面 |
|---|---|---|---|
| `POST` | `/journal` | 创建日记，生成 AI 摘要，增加信任信号 | 日记页 |
| `GET` | `/person/{id}/journal` | 读取日记分页列表（20 条一页，`{ items, total, page, page_size, has_more }`） | 日记页 |
| `PUT` | `/journal/{entry_id}` | 修改日记内容/心情 | 日记页 |

`JournalIn`：`person_id/content/mood`。  
`JournalUpdate`：`content?/mood?`。  
`JournalOut`：`id/person_id/content/mood/ai_summary/created_at/updated_at`。

当前缺口：没有 `DELETE /journal/{id}`。如果前端需要删除日记，先补后端。

---

### 2.9 Profile / Findings / Timeline / Life Events

| 方法 | 路径 | 作用 | 前端页面 |
|---|---|---|---|
| `GET` | `/person/{id}/profile` | 读取画像、领域摘要、关键日期、验证判断、信任等级 | 我的宇宙/画像页 |
| `GET` | `/person/{id}/findings?pending_only=true/false` | 读取沉淀判断和验证状态 | 待验证清单 |
| `POST` | `/person/{id}/findings/{finding_id}/feedback` | 用户反馈 confirmed/refuted，校准信心 | 验证交互 |
| `POST` | `/person/{id}/events` | 记录人生事件并用法达回溯验证判断 | 成长事件录入 |
| `GET` | `/person/{id}/timeline` | 读取成长时间线 | 时间线页 |

`ProfileOut`：

| 字段 | 含义 |
|---|---|
| `domain_summaries` | 领域摘要 + confidence + evidence_notes |
| `verified_findings` | 已沉淀判断 |
| `key_dates` | 关键日期 |
| `trust_level` | 信任等级 |
| `updated_at` | 更新时间 |

`FindingOut`：`id/statement/domain/confidence/status/feedback/event_verified/verification_notes/confirmed_at`。

`LifeEventVerifyOut`：`event_id/label/period_major/period_sub/verifications/calibrated`。

`TimelineEventOut`：`id/occurred_at/label/kind/detail/related_conclusion_id/domain/need`。

设计建议：这组能力适合合成一个「成长档案 / 星尘年轮」页面，而不是散落在多个隐藏入口里。

---

### 2.10 Preferences / Push

| 方法 | 路径 | 作用 | 前端页面 |
|---|---|---|---|
| `GET` | `/person/{id}/preferences` | 读取用户偏好 | 设置页 |
| `PUT` | `/person/{id}/preferences` | 部分更新偏好 | 设置页 |
| `GET` | `/push/vapid-public-key` | 获取 Web Push 公钥 | 推送订阅流程 |
| `POST` | `/push/subscribe` | 保存浏览器 PushSubscription | 首页/设置 |
| `POST` | `/push/unsubscribe` | 删除订阅 | 设置页 |
| `POST` | `/push/trigger` | 外部 cron 触发每日推送 | 运维脚本，不给普通用户 UI |

`PreferenceIn` 支持：

| 字段 | 值 | 前端建议 |
|---|---|---|
| `push_frequency` | `daily/quiet/off` | 通知频率选择 |
| `sensitive_topics` | string list | 敏感话题设置 |
| `preferred_persona` | persona key | 默认星灵偏好 |

当前缺口：`preferred_persona` 可保存，但 agent 默认读取偏好这段还需要补；目前 `/chat` 显式传 `persona` 是可靠路径。

---

### 2.11 Related Person / 合盘

| 方法 | 路径 | 作用 | 前端页面 |
|---|---|---|---|
| `POST` | `/person/{id}/related` | 保存一个合盘对象出生信息 | 合盘弹窗 |
| `GET` | `/person/{id}/related` | 合盘对象列表，只返回名字等轻信息 | 关系人管理 |
| `DELETE` | `/person/{id}/related/{related_id}` | 删除合盘对象 | 关系人管理 |
| `POST` | `/chat` with `related_person_id` | 用指定合盘对象回答关系问题 | 聊天/咨询页 |

推荐流程：

1. 用户问关系/合盘，`ChatOut.needs_related_person=true`。
2. 前端弹出生信息表单。
3. `POST /person/{id}/related` 保存对方。
4. 拿返回的 `related_id`，下次 `/chat` 带 `related_person_id`。

---

## 3. 页面级消费建议

### 3.1 首页 / Garden

建议消费：

- `GET /garden`
- `GET /person/{id}/recommended-spirits`
- 可选 `GET /person/{id}/opening`

首页核心模块：

1. 今日醒来的星灵：recommended spirits top3。
2. 今日来信：`GardenState.letter`。
3. 继续昨天：`continue_from.summary`。
4. 我记得你：`recall.items`。
5. 今日灵魂碎片：`soul_fragments`。
6. 红点：`letter_unread`、`pending_verifications`。
7. 关系温度：`trust_level`。

### 3.2 Chat / 星灵散步式聊天

建议消费：

- `POST /chat`
- `GET /person/{id}/recommended-spirits`
- `POST /person/{id}/related` when needed

聊天气泡除了 `answer`，还应展示轻反馈：

- 点亮：`lit_fragments`
- 被照见：`seen_fragments`
- 行动达成：`actioned_fragments`
- 来信生成：`keepsake_created`
- 情绪识别：`emotion/request_type`
- 模式：`mode`

### 3.3 Universe / 自我星盘轮

建议消费：

- `GET /person/{id}/fragments`
- `GET /person/{id}/soul-fragments/today`
- `GET /person/{id}/profile`
- `GET /person/{id}/findings?pending_only=true`

视觉重点：后端已经给 `level` 和 `action_count`，前端只负责表现成长级，不要自行推导。

### 3.4 Mailbox / 树洞回声

建议消费：

- `POST /mailbox/today`
- `GET /person/{id}/letters`
- `POST /person/{id}/letters/read-today`

重点展示：

- `kind=daily`：每日来信。
- `kind=keepsake`：某次倾诉/值得记住时刻的回声。
- `explain/healing_name/primary_need/soul_fragments`：让「为什么这封信」可解释。

### 3.5 Growth / 时间线与验证

建议消费：

- `GET /person/{id}/timeline`
- `POST /person/{id}/events`
- `GET /person/{id}/findings`
- `POST /person/{id}/findings/{finding_id}/feedback`

适合做成一个「成长年轮」：用户记录人生事件，系统校准曾经的判断，形成可信度闭环。

### 3.6 Settings / 隐私与偏好

建议消费：

- `GET/PUT /person/{id}/preferences`
- `POST /push/unsubscribe`
- `GET /person/{id}/export`
- `DELETE /person/{id}`

必须有二次确认：删除用户数据不可逆。前端建议先引导导出再删除。

---

## 4. 已可用 vs 部分可用 vs 缺失

### 4.1 已可用，前端可直接设计

- `/chat` 主问答与富字段。
- `/garden` 首页聚合。
- `/opening` 与 `/recall` 记忆回访。
- `/recommended-spirits` 今日星灵推荐。
- `/fragments` 与 `/soul-fragments/today`。
- `/mailbox/today`、`/letters`、`/letters/read-today`。
- `/journal` 创建/列表/更新。
- `/profile`、`/findings`、`/events`、`/timeline`。
- `/preferences`、push subscribe/unsubscribe。
- related person 保存/列表/删除 + chat 带 `related_person_id`。
- export/delete 合规能力。

### 4.2 部分可用，前端可设计但要避坑

| 能力 | 当前状态 | 建议 |
|---|---|---|
| Persona 完整列表 | 后端有配置，无 `GET /personas` | 短期前端写死；后端后续补端点 |
| 默认人格偏好 | preferences 可存 `preferred_persona`，但 chat 默认还未完全读取 | 当前聊天页显式传 `persona` 最稳 |
| ConsultMode | API 接受 `quick/deep/annual/chart/free` | 先开放 quick/deep/free；annual/chart 先置灰 |
| 合盘 | related person 已持久化，chat 可恢复 | 前端必须保存 related 后把 id 带回 chat |
| Journal | 无 delete | 不设计删除，或等补后端 |
| Push trigger | 后端可触发 | 只给运维/cron，不做普通用户按钮 |

### 4.3 暂不应投入前端重流程

- `consult_followup` 来信：模型声明有，但没有生产路径。
- Person 完整编辑：没有 `PUT/PATCH /person/{id}`。
- `shared/models/garden.py`：不存在，`GardenState` 定义在 `application/api/main.py`。
- `Person.chart_cache`：内部预留，当前不出口。
- `DialogueTurn.latency_ms/tokens_used` 等内部/死字段：不要设计 UI。

---

## 5. 建议前端优先级

1. **聊天富字段反馈**：接 `lit_fragments/seen_fragments/actioned_fragments/keepsake_created`，最快体现成长感。
2. **首页 Garden 聚合重做**：把 `garden + recommended-spirits + recall` 变成每日回家体验。
3. **星灵选择器**：10 星灵人格 + 今日推荐 + `/chat.persona`。
4. **自我星盘轮增强**：用 `level/action_count/today fragments` 呈现成长复利。
5. **信箱深化**：daily/keepsake 分版式，展示推导链 explain。
6. **设置页**：push 退订、push_frequency、preferred_persona、敏感话题。
7. **成长时间线**：timeline + life events + findings feedback。
8. **日记页**：journal create/list/update。
9. **合盘对象管理**：related person 保存/选择/删除。
10. **隐私中心**：export/delete。

---

## 6. 设计硬线

- 不把占星结论写成前端静态文案；结论来自 `/chat` / Domain 输出。
- 不让 LLM 看盘或自由生成占星判断；前端也不要暗示「AI 自己算出来」。
- 成长点亮只表示「聊过/被照见/做过」，不声称用户人格被系统盖章。
- 删除数据不可逆，必须二次确认，最好先引导导出。
- `trust_level` 是关系温度，不是用户价值评分。
- 行动/验证是邀请式，不要设计成任务惩罚或打卡压力。
