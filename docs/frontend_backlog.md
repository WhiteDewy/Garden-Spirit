# 前端未接功能盘点（Frontend Backlog）

> 生成日期：2026-08-10 · 数据来源：全量 API 盘点 + 前端调用点扫描（双 agent 交叉核对）
> 用途：后面前端接入的施工清单。每个条目给出「后端现状 / 前端缺口 / 接入所需工作 / 优先级」。
> 口径：**后端能返回 ≠ 前端已渲染**。以下全部是「后端有、前端没接」的部分。

---

## 总览

| # | 功能区 | 后端 | 前端 | 优先级 |
|---|--------|------|------|--------|
| 1 | 咨询模式选择（ConsultMode） | 全通，`ChatIn.mode` 接受 | 从不发送，恒为 `deep` | 🔴 高 |
| 2 | 星灵人格切换（Persona） | 10 份完整人格配置 | 无 UI、无 `GET /personas` | 🔴 高 |
| 3 | 聊天富字段展示 | 全部返回 | 只渲染 `answer` | 🔴 高 |
| 4 | 日记（Journal） | 建/查/改三端点 | 无页面，client 方法死代码 | 🟡 中 |
| 5 | 成长时间线（Timeline） | `GET /timeline` 就绪 | 无页面 | 🟡 中 |
| 6 | 人生事件录入（B1 学习层） | 全层就绪 | 无入口 | 🟡 中 |
| 7 | 偏好设置（含推送频率/退订） | 端点就绪 | 无设置页、无退订 UI | 🟡 中 |
| 8 | 关系人合盘多轮 | 触发逻辑在，restore 是 stub | 无 UI | 🟢 低 |
| 9 | 档案编辑（Person 更新） | **无 PUT/PATCH 端点** | — | 🟢 低 |
| 10 | `consult_followup` 来信 | 模型声明、**零生产路径** | — | 🟢 低 |

---

## 一、后端就绪、前端零接入的功能区

### 1. 星盘咨询模式选择（ConsultMode）— 🔴 高

**后端现状**
- `ChatIn.mode`（`application/api/main.py:102`）接受 `str | None`，`_parse_mode()`（main.py:913）默认 `DEEP`。
- 模式贯穿全链路：`runtime.py:181`（agent 入口）→ `relationship/service.py:159`（quick/deep 影响信任分权重）→ `runtime.py:357`（QUICK 跳过 decomposer 额外模块）。
- `ChatOut.mode` 恒回 `mode.value`（main.py:111）。
- 枚举 `shared/enums.py:269-279`：`quick` / `deep` / `annual`(框架保留) / `chart`(框架保留) / `free`(框架保留)。

**前端缺口**
- `client.ts` 的 `ChatIn` 类型（line 51-56）**没有 `mode` 字段**，chat.vue 从不发送 → 永远是 `deep`。

**接入所需工作**
1. `client.ts` 的 `ChatIn` 加 `mode?: string`。
2. chat.vue 加模式选择（quick/deep），随每次 `/chat` 发送。
3. （可选）`annual/chart/free` 前端置灰，等框架级实现。

### 2. 星灵人格切换（Persona）— 🔴 高

**后端现状**
- 10 个行星人格完整配置在 `application/conversation/persona.py:57-129`（名称/口吻/词汇表）。
- `PersonaType` 枚举 `shared/enums.py:294-311`；`all_personas()`（persona.py:141）**从未被任何端点调用**。
- `/chat` 接受 `ChatIn.persona`（main.py:101），无效值静默回退 `None` → `config.default_persona`。
- `preferred_persona` 是 `ChartProfile.preferences` 字段（profile.py:81），`ActionService.validate_preferences()` 校验（action/service.py:100-107），**但 agent 从不读取它**——始终走默认人格。

**前端缺口**
- `ChatIn` 无 `persona` 字段，无切换 UI，无 `GET /personas` 端点。

**接入所需工作**
1. 新增 `GET /personas` 端点（调 `all_personas()`，返回名称列表 + 默认项）。
2. `client.ts` 加 `getPersonas()`，`ChatIn` 加 `persona?: string`。
3. 建设置页或聊天页人格切换器；写入偏好 `preferred_persona`。
4. **后端补一段**：agent 读取 `profile.preferences.preferred_persona` 兜底（现在存了不读）。

### 3. 聊天富字段展示 — 🔴 高

**后端现状**（`/chat` 全部返回，main.py:108-124）
- `intent_domain` / `request_type` / `emotion` / `written_back` / `mode` / `needs_related_person`
- `lit_fragments`（本轮点亮）、`seen_fragments`（被照见 +5）、`actioned_fragments`（行动 +20）、`keepsake_created`（来信式日记落库）
- `trust_level`（chat.vue 已渲染，line 76）

**前端缺口**
- chat.vue（line 97-99）只读 `answer` + `session_id`，其余全丢弃。
- 这是 **Phase 2 成长复利 2A/2B 的现场反馈**：用户点亮了哪个碎片、被照见、做到行动、写了日记，聊天页毫无提示——用户看不到自己的成长在发生。

**接入所需工作**
1. chat.vue 读 `lit_fragments`/`seen_fragments`/`actioned_fragments` → 气泡下方轻提示（如「✨ 诚实」+5 被照见）。
2. `keepsake_created` → toast「已写下一封来信」+ 跳信箱。
3. `emotion`/`request_type` → 可选：情感感知可视化（Phase 1 情绪感知层落地，前端从未展示）。
4. `needs_related_person` → 见条目 8。

### 4. 日记（Journal）— 🟡 中

**后端现状**
- `POST /journal`（main.py:481）、`GET /person/{id}/journal`（main.py:495）、`PUT /journal/{id}`（main.py:500）。**无 DELETE 端点**。
- 创建时生成 AI 摘要 + 时间线事件。

**前端缺口**
- client.ts 有 `journalCreate`（207）/ `journalList`（206）**死方法，无页面调用**；**无 `journalUpdate`**。
- 无日记页。

**接入所需工作**
1. 新建日记页（写 + 列表）；或与 mailbox「来信式日记」打通入口。
2. `client.ts` 补 `journalUpdate`（PUT）。
3. 可选：后端补 `DELETE /journal/{id}`。

### 5. 成长时间线（Timeline）— 🟡 中

**后端现状**
- `GET /person/{id}/timeline`（main.py:713）返回 `list[TimelineEventOut]`（LifeEvent 成长事件）。

**前端缺口**
- client.ts 有 `timeline`（205）**死方法**，无页面渲染。

**接入所需工作**
- 建时间线页；或并入 universe 页（成长历程卡片）。`TimelineEventOut` 前端类型已存在。

### 6. 人生事件录入（B1 学习层）— 🟡 中

**后端现状**
- `POST /person/{id}/events`（main.py:595）→ `LearningService.record_life_event()`（learning/service.py:45）：firdaria 回溯 → `verify_all_findings()` → 校准置信度。
- `LifeEventIn` schema 完整。

**前端缺口**
- 无任何消费方（无页面、无 client 方法）。整个 B1 学习层只在测试里跑。

**接入所需工作**
- 建事件录入 UI（如「记一笔：换工作了/搬去上海」→ POST /events）。这是信任校准的关键闭环，用户侧价值高。

### 7. 偏好设置（含推送频率/退订）— 🟡 中

**后端现状**
- `GET/PUT /person/{id}/preferences`（main.py:634/641），部分更新。
- `push_frequency`（action/service.py:22）：`daily` / `quiet` / `off`；`push_trigger`（main.py:692）只推 `daily` 用户。
- `sensitive_topics`、`preferred_persona` 等由 `validate_preferences()` 校验。

**前端缺口**
- client.ts 有 `getPreferences`（201）/ `updatePreferences`（203）**死方法**。
- **推送订阅只进不出**：index.vue 1.5s 延迟自动订阅（PUSH_ASKED_KEY 只问一次），但 `pushUnsubscribe`（client.ts:228 + push.ts）**没有任何页面 import**——用户无法退订、无法改 `push_frequency`。
- 无设置页。

**接入所需工作**
1. 建设置页（或 index 页加折叠设置区）：推送频率选择、敏感话题编辑、人格偏好。
2. 加「停止推送」入口 → `api.pushUnsubscribe`（需有已存 subscription，前端需先 `push.ts` 提供读现存订阅的能力或后端按 person 全删）。
3. 打通：改 `push_frequency=off` → `push_trigger` 自动跳过。

### 8. 关系人合盘多轮 — 🟢 低

**后端现状**
- `ChatOut.needs_related_person`（main.py:109）由 `ctx.pending_related_person` 填充（main.py:754）。
- 触发：RELATIONSHIP 领域 + 有 `related_person` 槽 + `ctx.related_person is None` → 问对方出生信息（runtime.py:247-254）。
- **`_restore_related_person()`（main.py:1036-1038）是 stub `return None`**——注释明说「单会话合盘对象目前只活在内存里」。

**前端缺口**
- chat.vue 不读 `needs_related_person`，无收集对方出生信息的 UI。

**接入所需工作**
1. chat.vue 检测 `needs_related_person` → 弹出生数据表单，收集后连同消息发回。
2. **后端需要一起做**：`_restore_related_person` 真实实现（按 person 落库合盘对象），否则多轮跨请求仍断。

### 9. 档案编辑（Person 更新）— 🟢 低

**后端现状**
- **无 PUT/PATCH `/person/{id}` 端点**。`Person` 可改字段（`name`/`gender`/`notes`/`house_system`）全被锁死，birth data 冻结是设计。
- `PersonOut` 不含 `notes` / `updated_at`。

**接入所需工作**
- 后端先加 PUT/PATCH 端点 + `PersonOut` 补字段，前端再做编辑页/编辑弹窗。

### 10. `consult_followup` 来信 — 🟢 低

**后端现状**
- `shared/models/letter.py:24` 声明 `kind` 取值含 `consult_followup`，docstring 注明 V2。
- **零生产路径**：letter_service.py 只产 `daily` 和 `keepsake` 两种。
- 前端 mailbox.vue 已按 `keepsake` 分支渲染（line 27），`consult_followup` 会落默认分支。

**接入所需工作**
- 后端实现生产路径（咨询后跟进信），前端可复用 mailbox 渲染。

---

## 二、client.ts 死 API 方法（有方法、无调用方）

| 方法 | 行 | 对应端点 | 说明 |
|------|----|----------|------|
| `health` | 187 | `GET /health` | 无页面调用 |
| `getPreferences` | 201 | `GET /person/{id}/preferences` | 见条目 7 |
| `updatePreferences` | 203 | `PUT /person/{id}/preferences` | 见条目 7 |
| `timeline` | 205 | `GET /person/{id}/timeline` | 见条目 5 |
| `journalList` | 206 | `GET /person/{id}/journal` | 见条目 4 |
| `journalCreate` | 207 | `POST /journal` | 见条目 4 |
| `pushUnsubscribe` | 228 | `POST /push/unsubscribe` | 有实现无 UI 触发（见条目 7） |

> `journalUpdate`（PUT）在 client.ts **完全不存在**；`journalDelete` 后端也无端点。

---

## 三、已类型化、但前端未渲染的字段

> 前端 `GardenState`/`ChatOut` 等接口类型已声明这些字段，但没有任何页面读取展示。

### ChatOut（main.py:108-124，chat.vue 只读 answer/session_id/trust_level）

| 字段 | 含义 | 前端现状 |
|------|------|----------|
| `emotion` | 情感感知结果（Phase 1 情绪感知层） | ✗ 丢弃 |
| `request_type` | 本轮请求类型 | ✗ 丢弃 |
| `intent_domain` | 意图领域 | ✗ 丢弃 |
| `written_back` | 闲聊是否写回记忆 | ✗ 丢弃 |
| `mode` | 生效咨询模式 | ✗ 丢弃 |
| `needs_related_person` | 需要对方出生信息 | ✗ 丢弃（见条目 8） |
| `lit_fragments` | 本轮点亮的灵魂碎片 | ✗ 丢弃 |
| `seen_fragments` | 被照见 +5 的碎片 | ✗ 丢弃 |
| `actioned_fragments` | 行动 +20 的碎片 | ✗ 丢弃 |
| `keepsake_created` | 是否落库一封来信式日记 | ✗ 丢弃 |

### LetterOut（mailbox 端点）

| 字段 | 前端现状 |
|------|----------|
| `primary_need` | ✗ mailbox.vue 只读 `healing_name`，不读 primary_need |
| `soul_fragments` / `lit_fragments` | △ fragment.vue 用于过滤 keepsake（line 197-199）；但 mailbox.vue 从 `body` 字符串解析脚注，**未用类型化字段** |

### FindingOut（/findings）

| 字段 | 前端现状 |
|------|----------|
| `verification_notes` | ✗ consult.vue 从不展示 |
| `event_verified` | △ consult.vue 只看 `f.feedback` 显示状态（line 53），未显式消费布尔 |

### PersonOut（/person、/garden）

| 字段 | 前端现状 |
|------|----------|
| `gender` / `place_name` / `time_known` / `house_system` / `is_premium` | ✗ 类型有，页面不渲染 |

### TimelineEventOut

- 所有字段：无页面（见条目 5）。

### 类型不一致

- `JournalOut.updated_at`：后端声明（main.py:277），前端接口（client.ts:232-239）**遗漏该字段**——接入日记页时顺手补上。

---

## 四、后端有能力但缺端点/缺生产路径

| 项 | 位置 | 缺口 |
|----|------|------|
| `all_personas()` | persona.py:141 | 无 `GET /personas` 端点暴露（见条目 2） |
| `preferred_persona` 偏好 | profile.py:81 / action/service.py:100 | agent 从不读取，存了不生效 |
| `_restore_related_person` | main.py:1036-1038 | stub `return None`，多会话合盘断链 |
| Person 更新 | person.py:49-63 | 无 PUT/PATCH 端点，`name`/`gender`/`notes`/`house_system` 不可改 |
| `consult_followup` kind | letter.py:24 | 声明无生产路径 |
| 日记删除 | — | 无 `DELETE /journal/{id}` |

---

## 五、已废弃 / 死模型字段（不建议投入前端）

| 字段 | 位置 | 状态 |
|------|------|------|
| `DialogueTurn.latency_ms` / `tokens_used` | conversation.py:21-22 | 声明但**从不赋值**，纯死字段 |
| `Conversation.persona` | conversation.py:31 | 内存态，不落 API |
| `FragmentLight.session_id` | fragment_light.py:32 | 账本内部字段，不经 API 直接暴露（前端无需感知） |
| `ChartProfile.lord_states` / `trust_score` / `trust_signals` | profile.py:70/78/79 | 内部状态，仅 `trust_level` 派生值出 API |
| `Person.chart_cache` / `notes` / `updated_at` | person.py:57/61/63 | 存库不出口（若要编辑档案则升级到条目 9） |
| `JournalEntry.related_intent_id` / `related_conclusion_id` | journal.py:28-29 | 存库，`JournalOut` 不含（低价值，可不接） |
| `LifeEvent.related_journal_id` / `related_intent_id` | life_event.py:30-31 | 存库，`TimelineEventOut` 不含（时间线页可选展示来源） |

---

## 六、过时文档提醒

`docs/product_report_uiux.md` 第四节「缺口表」（line 286-304）是 **2026-08-06 的旧盘点**，其中多项已落地（日记部分、验证交互、推送、星盘轮）。接入时以本文件为准，勿按旧表施工。

---

## 建议接入顺序（供参考）

1. **条目 3（富字段展示）** — 纯前端、无后端改动、即时成长反馈，性价比最高。
2. **条目 2（人格切换）** — 需一个小端点 + 聊天页/设置 UI，产品亮点。
3. **条目 1（模式选择）** — 一行 ChatIn 改动 + 聊天页控件。
4. **条目 7（偏好/退订）** — 设置页，顺带解决推送「只进不出」。
5. **条目 5（时间线）** 与 **条目 6（事件录入）** — 可合成一个「成长」页。
6. **条目 4（日记）**、**条目 8-10** — 按排期后置。
