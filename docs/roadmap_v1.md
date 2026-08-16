# 星灵 App v1 前后端完成规划（规划设计）

> 生成日期：2026-08-16 · 基于当日全量代码扫描（后端 ~30 端点 / 821 测试，前端 uni-app 8 页面）
> 用途：从「MVP 已闭环」走到「可上线产品」的施工总图。前端按此接功能，后端按此补端点。
> 上游依据：`docs/PRD.md`（产品定位）、`docs/architecture.md`（冻结架构）、`docs/frontend_backlog.md`（2026-08-10 盘点，部分条目已完成后端侧）、`docs/backend_capabilities_for_frontend.md`（2026-08-15 能力清单）。

---

## 一、现状盘点（能力地图）

### 1.1 后端已具备（无需重做）

架构已冻结且全部落地：`Application → Reasoning → Astrology → Foundation` 四层 + `shared/` 横切层，821 测试全绿，**无 LLM 也能完整出结论**（规则兜底全链路）。

| 能力区 | 状态 | 关键位置 |
|---|---|---|
| 星历计算 | ✅ pyswisseph：本命盘（8 宫制/次要相位/禀赋/互溶/象限/月亮相位）、行运、基础合盘 | `domain/astrology/calculation/` |
| 时间技法 | ✅ 法达、太阳/月亮回归、次限月亮、五层 timing stack、周度人生 K 线 | `domain/timeline/` |
| Domain Engine v2 | ✅ 11 领域语义场 + 三轨道合成器 + 宫位追问/证据链深挖 | `domain/astrology/interpretation/` |
| Agent 主循环 | ✅ 三层 LLM 意图（DEEP/QUICK/FREE）+ 规则兜底 + 策略 YAML 插件 | `application/agent/` |
| 疗愈层 | ✅ 叙事 5 步 + 危机词检测 + 硬护栏；10 行星人格 | `application/conversation/` |
| 关系层 | ✅ trust 陌生→深交四级 + 开场白 + 软牵引门控 | `application/relationship/` |
| 记忆层 | ✅ 写回 + recall 豆荚 + persona 记忆镜头 + 日记 AI 摘要 | `application/memory/` |
| 成长账本 | ✅ 34 子类碎片，+1/+3/+5/+10/+20 深度分、今日 top3 | `application/conversation/fragments.py` |
| 信箱 | ✅ 每日来信（幂等）+ keepsake/entry 来信 + 落款推导链 | `application/mailbox/` |
| 学习层 | ✅ 法达倒推验前事 + 置信度校准 + 待验证清单 | `application/learning/` |
| 行动层 | ✅ 偏好（推送频率/敏感话题/偏好人格）+ 偏好已生效 | `application/action/` |
| 推送 | ✅ Web Push VAPID 全链路 | `application/push/` |
| 合规 | ✅ 全量导出/删除 + PII Fernet 加密 + 密钥轮换 + 备份脚本 | `foundation/database/encryption.py`、`scripts/` |
| 基础设施 | ✅ SQLite WAL（10 表，原生 sqlite3 无 ORM）、AMAP 地理编码（离线兜底）、OpenAI 兼容 LLM 单客户端 | `foundation/` |

**后端 2026-08-10 盘点后已补齐的**（backlog 文档已过时的部分）：`GET /personas`、`_restore_related_person` 真实实现、`preferred_persona` 生效、`DELETE /person`、`GET /person/{id}/export`。

### 1.2 前端已具备

uni-app（Vue3 + TS + Vite）多端工程，H5/PWA 形态可跑（sw.js + manifest），视觉定稿「星灵森屿」。

| 页面 | 行数 | 现状 |
|---|---|---|
| `pages/index/index.vue` | 1767 | 首页聚合（garden）、onboarding 建档（含省市区+时区）、今日星灵、推送一次性询问 |
| `pages/chat/chat.vue` | 193 | **只发 `person_id/session_id/message`**，只渲染 `answer`；persona/mode 不发送，十余个成长反馈字段全部丢弃 |
| `pages/mailbox/mailbox.vue` | 264 | 信箱：今日来信 + keepsake 分支 + 已读红点 |
| `pages/universe/universe.vue` | 176 | 内在宇宙入口 |
| `pages/universe/wheel.vue` | 822 | 自我星盘轮（**视觉冻结**） |
| `pages/universe/consult.vue` | 189 | 待验证判断卡（findings feedback） |
| `pages/universe/fragment.vue` | 772 | 34 子类图鉴 |
| `pages/me/me.vue` | 140 | 档案卡 + 星灵图鉴 + 3 个「即将上线」死入口 |

`src/api/client.ts` 是唯一契约层（铁律：前端不含占星逻辑），已类型化但**无调用方**的方法：`getPreferences` / `updatePreferences` / `timeline` / `journalList` / `journalCreate` / `pushUnsubscribe` / `health`。合盘对象三个端点（`POST|GET /person/{id}/related`、`DELETE .../related/{rid}`）连 client 方法都没有。

### 1.3 核心差距（按严重度）

1. **无账户体系**：person_id 即令牌，CORS `*`，SQLite 单文件 —— 现在只能单人本机使用，无法多人上线。
2. **成长复利闭环断在前端**：点亮/被照见/行动/来信这四个即时反馈字段（`lit/seen/actioned_fragments`、`keepsake_created`）后端全返回、前端全丢弃 —— 用户感知不到「聊天正在点亮我的内在宇宙」，Phase 2 的产品核心体验缺失。
3. **B1 学习层零入口**：人生事件录入（信任校准的关键闭环）无页面无 client 方法，整个学习层只在测试里跑。
4. **设置缺失**：推送「只进不出」（无法退订/改频率），敏感话题、人格偏好不可改。
5. **后端小缺口**：无 `PUT/PATCH /person`（档案不可编辑）、无 `DELETE /journal/{id}`、`consult_followup` 来信零生产路径。
6. **部署缺项**：`/push/trigger` 需网络隔离、无速率限制、无监控告警、备份未 cron 化。

---

## 二、目标与分期

**v1 上线定义**：一个陌生用户可以在线注册 → 建档 → 与星灵多轮咨询/随聊 → 在前端看到自己的成长账本（碎片点亮、时间线、验证判断）→ 收到每日来信与推送 → 可退订、可导出、可删除。

| 阶段 | 主题 | 内容 | 依赖 |
|---|---|---|---|
| **C1** | 前端成长反馈闭环 | 富字段展示、人格切换、模式选择 | 无后端改动 |
| **C2** | 前端页面补全 | 设置页、成长页（时间线+事件录入）、日记页、合盘流程 | S1 两个小端点 |
| **S1** | 后端小端点 | `PUT /person`、`DELETE /journal/{id}`、`consult_followup` 生产路径、合盘 client 配套 | 无 |
| **S2** | 账户与部署安全 | 注册/登录/token、CORS 白名单、`/push/trigger` 防护、限流、备份 cron、监控 | 无（与 C1/C2 并行） |
| **V2** | 商业化与深度 | 会员体系（`is_premium` 已预留）、年/月报（`ConsultMode.ANNUAL` 已预留）、Composite/Davison 合盘、出生时间校正 | v1 上线后 |

排序理由：C1 性价比最高（纯前端、零后端改动、直接补产品核心体验）；S2 决定「能不能上线」，应尽早启动但不阻塞 C1/C2。

---

## 三、前端规划设计

### 3.1 信息架构（目标页面地图）

```
TabBar（现状无 tabBar 配置，首页即入口，维持现有导航模式）
├─ index     首页：garden 聚合 + 今日来信红点 + 今日星灵 + 记忆镜头        [已有，微调]
├─ chat      咨询/随聊：人格切换 + 模式选择 + 富字段反馈 + 合盘收集表单    [C1/C2 增强]
├─ mailbox   信箱：daily / keepsake / entry / consult_followup 四类渲染    [S1 后跟进一类]
├─ universe  内在宇宙：星盘轮(冻结) + 34 子类图鉴 + 待验证判断             [已有]
│   └─ growth★ 成长页：时间线 + 人生事件录入（并入 universe 子页）          [C2 新增]
├─ journal★  日记：写 + 列表 + AI 摘要（或并入 mailbox 作 tab）            [C2 新增]
└─ me        我的：档案卡 + 星灵图鉴                                       [已有]
    ├─ settings★ 设置：推送频率/退订、敏感话题、偏好人格、宫制              [C2 新增]
    └─ privacy★ 隐私：导出全量数据、删除账户（危险区）                      [C2 新增]
```

★ = 新增页面。全部走 `pages.json` 注册，遵循 `docs/frontend_ui_conventions.md` 硬约束与「星灵森屿」视觉规范（`docs/frontend_visual_refactor_spec.md`）。

### 3.2 C1：聊天页增强（成长反馈闭环）

改动集中在 `chat.vue` + `client.ts`，**零后端改动**：

1. **人格切换**：顶部星灵 orb 可点 → 弹出 10 星灵选择器（数据源 `GET /personas` 已就绪，client 需补 `getPersonas()`）；选中后本轮 `chat.persona` 发送；「跟随今日推荐」为默认项。
2. **模式选择**：输入区上方 quick/deep 轻切换（`annual/chart` 置灰标「即将上线」，`free` 可选），随 `/chat` 发送 `mode`。
3. **富字段反馈**（气泡下方的轻量「星尘条」，不打断对话）：
   - `lit_fragments` → 「✨ 点亮 ×N」+ 碎片名浮层；
   - `seen_fragments` → 「🌙 被照见 +5」；
   - `actioned_fragments` → 「🌱 真的做到了 +20」庆祝动效；
   - `keepsake_created` → toast「星灵为你写了一封信」+ 信箱红点入口；
   - `written_back` → 「已记住」轻提示（可折叠）。
4. **情绪感知**（可选低优先）：`emotion`/`request_type` 以气泡角落的光点/微标签呈现，不做大 UI。

验收：连续对话 5 轮，用户能口头复述「我点亮了什么、被照见了什么」。

### 3.3 C2：四个新页面

**settings（设置）** — `me.vue` 第三个死入口换真链接
- 推送：频率三选（daily/quiet/off，改 off 后 `/push/trigger` 自动跳过）+ 「停止推送」按钮（调 `pushUnsubscribe`，需 push.ts 提供读取现存订阅能力）。
- 偏好人格：单选 10 项 + 跟随推荐（写 `preferences.preferred_persona`，后端已生效）。
- 敏感话题：标签编辑（写 `sensitive_topics`；注：后端目前仅存储校验、不门控内容，UI 文案避免过度承诺）。

**growth（成长）** — universe 子页，合并 backlog 条目 5+6
- 上：时间线（`timeline()` 已有类型）按月分组渲染 LifeEvent 卡。
- 下：「记一笔」按钮 → 事件录入表单（`POST /person/{id}/events`，client 补 `createLifeEvent`）→ 提交后提示「星灵正在用这段时间校准对你的理解」，引导去 consult 页看 findings 变化。

**journal（日记）**
- 写：文本 + mood；列表：卡片 + AI 摘要折叠展开。
- client 补 `journalUpdate`；入口同时放 chat 页「倾诉后被问要不要写日记」与 mailbox 页 tab（与来信式日记区分：自己写的 vs 星灵写的）。

**privacy（隐私）** — 合规出口
- 导出：`GET /person/{id}/export` → 下载 JSON。
- 删除：二次确认（输入用户名）→ `DELETE /person/{id}` → 清空本地 storage → 回首页。

**合盘流程（chat 内嵌，不新页）**
- `needs_related_person=true` → 底部弹出对方出生信息表单（复用 onboarding 的出生组件）→ `POST /person/{id}/related` → 后续轮次带 `related_person_id`。
- me 页「星灵关系」入口 → 关系人列表（`GET related`）+ 删除。
- client 补三个方法：`createRelatedPerson` / `listRelatedPersons` / `deleteRelatedPerson`。

### 3.4 前端工程约定（延续现有模式）

- 无全局 store：延续 `PERSON_KEY` storage 模式 + 页面级 `ref`；仅当 3+ 页面共享人格选择状态时才引入轻量 composable（`usePersona`），不引 Pinia。
- 所有新 API 先进 `client.ts` 带类型，页面只消费类型（铁律一/二）。
- 60s 超时仅用于 chat/mailbox 类 LLM 端点，其余 15s。
- 视觉：新页面统一「星灵森屿」暗绿基调（参考 me.vue 现有色板），`wheel.vue` 冻结不动。

---

## 四、后端规划设计

### 4.1 S1：小端点补齐（对齐前端 C2）

| 端点 | 设计要点 |
|---|---|
| `PUT /person/{id}` | 仅允许改 `name/gender/notes/house_system`（birth 冻结是设计）；改动 `house_system` 时作废 `chart_cache_encrypted` 触发重算；`PersonOut` 补 `notes/updated_at` |
| `DELETE /journal/{id}` | 软删或硬删 + 关联 timeline 事件标记来源失效 |
| `consult_followup` 来信 | 生产路径：deep 模式会话结束后（当日首条咨询后的次日早班信）由 letter_service 生成，复用 daily 管道；`kind` 已声明 |
| 合盘增强（可选） | `_restore_related_person` 已真实化，确认多轮跨请求不断链后即可支撑前端 |

### 4.2 S2：账户体系（上线前提，推荐方案）

**推荐：轻量 token 方案（不引第三方身份服务）**

```
POST /auth/register   手机号/邮箱 + 密码（或验证码）→ 创建 account + 绑定 person
POST /auth/login      → 签发随机 API token（存 accounts 表，可吊销）
POST /auth/logout     → 吊销 token
```

- 中间件：token → person_id 注入请求；`person_id` 不再由前端明文携带（防越权：现在知道 id 即可读任何人数据）。
- 前端：client.ts 增加 token header + 401 统一跳登录；onboarding 流程后置注册（先体验后注册，符合陪伴类产品转化路径）。
- 密码 argon2/bcrypt 哈希；token 与 Fernet 加密体系并存（PII 加密不变）。
- 迁移：现有 `persons` 数据通过「首次设置密码」认领流程过渡。

**同期安全加固清单**：
1. CORS 从 `*` 收紧为部署域名白名单（`AppConfig` 增加配置项）。
2. `/push/trigger` 加共享密钥头 + 部署层仅内网/本机可达（cron 调用）。
3. 全局限流（slowapi 或 nginx 层）：`/chat` 按用户 10 次/分钟防 LLM 成本失控。
4. `scripts/backup_db.py` 进 cron（每日 VACUUM INTO + 保留 7 份）；`/health` 加磁盘与 DB 可写探活。
5. 结构化日志接告警（LLM 失败率、422 地理编码失败率）。

### 4.3 数据与容量

- **SQLite 保留至 ~500 活跃用户**：单机 + WAL + 每日备份足够；触发迁移 Postgres 的信号：并发写锁 (`database is locked`) 出现、或多实例部署需求。`foundation/database/store.py` 已收敛数据访问，迁移面可控。
- `foundation/cache/` 空置包处理：短期删除或并入 `chart_cache` 说明文档，避免误导；星盘计算已有加密缓存（版本化 key），暂无新增缓存需求。
- LLM 成本控制：`GS_LLM_DISABLE` 兜底已有；增加每用户日 token 预算字段（preferences 扩展），超限降级为纯规则模式。

### 4.4 明确不做（v1 范围外，防 scope creep）

塔罗、卜卦、恒星、Composite/Davison、出生时间校正、未成年人门控、年/月报（V2 预留位已够）。

---

## 五、里程碑与验收

| 里程碑 | 内容 | 验收标准 | 预估 |
|---|---|---|---|
| **M1** = C1 | 富字段 + 人格 + 模式 | 聊天页可见点亮/照见/行动/来信反馈；可切换 10 星灵与 quick/deep | 前端 3-4 人日 |
| **M2** = S1 | 三个小端点 + followup 信 | pytest 全绿 + 新增契约测试 | 后端 2-3 人日 |
| **M3** = C2 | 设置/成长/日记/隐私/合盘 UI | backlog 十项全部关闭；死方法清零 | 前端 6-8 人日 |
| **M4** = S2 | 账户 + 安全 + 部署 | 越权测试（A 的 token 读 B 的 person 返回 403）；限流生效；备份 cron 运行 | 后端 5-7 人日 |
| **M5** | 公测 | 真人 20 名试用 2 周：次日留存 ≥40%，每日来信打开率 ≥50% | 全员 |

依赖关系：M1 ∥ M2 ∥ M4 可并行；M3 依赖 M2（settings 用到 PUT /person 可后置，journal 删除可后置）；M5 依赖全部。

---

## 六、风险与决策点

| 决策点 | 推荐 | 备选 |
|---|---|---|
| 鉴权方案 | 自建轻量 token（§4.2） | 接微信登录（若走小程序端） |
| 数据库 | v1 继续 SQLite，写锁出现再迁 PG | 直接上 PG（多花 3-4 人日） |
| 多端策略 | v1 只发 H5/PWA；小程序作为 V2（占卜类目审核风险 + push 通道差异） | 首发小程序（需备审核被拒预案） |
| 日记入口 | 独立页 + mailbox 双入口 | 并入 mailbox 单 tab |

**风险**：① 出生数据属敏感 PII —— 加密已有，但需在隐私政策中明示并加未成年人确认（V2 门控前的临时文案）；② LLM 成本随用户量线性涨 —— 限流 + 日预算降级（§4.3）；③ `/chat` 60s 长耗时 —— 前端已有超时文案，后端考虑流式（SSE）作为 V2 体验优化。
