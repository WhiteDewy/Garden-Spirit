# Garden-Spirit 重构规划（v3：唯一引擎 + 看盘范式 + 静态落库）

> 状态：**定稿，核心阶段已落地（2026-08-16），剩余项按后续迭代管理**。本文档同时保留历史诊断与当前实现状态，阅读时以“当前实现”标注为准。
> 关系：演进 `docs/architecture.md`（四层不变，边界不变）与 `docs/domain_engine_v2.md`（语义场 v2 保留其“语义场唯一真相源”原则，本文档修正其“governors 写死”的历史实现方式）。
> 硬线不变：**占星结论全由 Domain 出，LLM 自由度只在“怎么疗愈 / 怎么陪伴”，绝不在“占星对不对”。**

---

## 0. 一句话总纲

**12 宫定主题、10 星定角色、12 星座定方式；任何领域 = 宫主星 + 宫内星 + 先天征象星（一套固定范式，进 prompt）；每个承载者走唯一 `assess_planet` 算状态、经 `classify` 串连接、落 `scenario_maps` 出证据链；结论永远可解释，LLM 只转述。**

---

## 1. 核心诊断（问题全清单，按根因排序）

> **阅读口径**：本节保留重构启动时的历史基线，说明“为什么改”；删除线或“✅”表示已经迁移。当前运行时事实以 §10 阶段状态、`docs/v3_phase0_inventory.md` 与代码为准，不能把下表旧位置/旧公式当成 active implementation。

### 1.1 三大根因（用户核心批判，必须执行）

| # | 根因 | 表现 | 动作 |
|---|---|---|---|
| R1 | **时机链双声部冲突** | 年主星（profections，宫激活）与法达（firdaria，行星周期）被并行输出成两个矛盾的"when"信号，且年主星被误当结婚征象星（`targets={year_lord,SUN}`） | **彻底删除**年主星（理由：单一权威时机链，非"技法不准"） |
| R2 | **法达只看大限不看子限** | 时机判断漏掉 ~1 年粒度的子限章节 | 法达**大限 + 子限双领主**进时机判定 |
| R3 | **只看 7 宫主，不看互溶接纳/相位** | 7R 受克时不会找帮手星 | 征象星受克 → **找互溶/接纳帮手星**（接纳链） |

### 1.2 架构层面问题

| # | 问题 | 现状 | 动作 |
|---|---|---|---|
| R4 | **静态盘每次重算** | 本命盘/法达盘出生即定，却每次 `compute(person)`（runtime.py:302/325/378、planner:52、main.py:641） | 注册时预计算落库，运行时读缓存 |
| R5 | **规则散落、无单一权威** | 年主星硬编码 timing.py、法达在 firdaria.py、互溶接纳在 reception.py、语义场在 yaml、LLM prompt 又写一套 | 看盘范式进 prompt/方法论文档（唯一权威） |
| R6 | **"现学现编"** | 每个引擎各写各的评估公式 | 唯一 `assess_planet`，确定性方法 |
| R7 | **4 套状态评估逻辑矛盾** | 同一颗星 4 个引擎 4 个答案 | 抽离合并成唯一引擎 |

### 1.3 4 套状态评估逻辑（R7 详表）

| # | 函数 | 位置 | 尊贵权重 | 吉凶星 | 刑冲惩罚 | 次要相位 | 世代修正 | 调用点 |
|---|---|---|---|---|---|---|---|---|
| 1 | `planet_strength` | common.py:111 | ×0.35 | ±0.8 | 接纳0.3/未接纳0.5 | ❌ | ❌ | `_governor_quality` |
| 2 | `_house_quality_dual` | signification.py:102 | ×0.4 | ±1.0 | 接纳0.4/未接纳0.8 | ❌ | ❌ | `interpret` 内部 |
| 3 | `_quality` | dispositor.py:81 | 落陷+1.0 | — | 接纳0.4/世代0.5/硬碰0.8 | ✅ | ✅(outer) | `dispositor_interpretations` |
| 4 | `_aspect_partners` | planet_profile.py:201 | — | — | 只分类不计分 | ✅ | ✅(outer) | `read_planet` → LLM |

**矛盾点**：尊贵 0.35/0.4；吉凶星 ±0.8/±1.0；刑冲 0.3/0.5 vs 0.4/0.8 vs 0.4/0.5/0.8；次要相位仅 3、4 排除；世代修正仅 3、4 有。

### 1.4 重复 / 死数据

| # | 问题 | 动作 |
|---|---|---|
| R8 | 体系一（house_significations 语义场）与体系二（house_nature 路由）两套并行宫位体系 | ✅ 已合并：路由进 house_significations，转宫进 house_derived，house_nature 已删 |
| R9 | `theme_map.core_planets` / `intent_profiles.core_planets` / `planet_nature.domain_signals` **三处**重复定义"领域核心星" | ✅ 已收口：`planet_nature.domain_signals` 为唯一角色源；`intent_profiles/theme_map` 不再保存或覆盖核心星 |
| R10 | ~~`house_significations` 写死 governors（婚姻→金星、合作→木星、对手→火星）~~ | ✅ 已改通用范式：运行时从实盘宫主、宫内星、领域征象星与 ConsultCallPlan enrichment 动态解析承载者 |
| R11 | `signs.yaml` 的 `behavior_style`/`domains` 字段死数据（loader 不解析） | 补活，喂给落座方式 |
| R12 | 互溶接纳每次现场重算（ReceptionEngine.detect 结果只打日志，未写进 Chart） | 算一次落库，动态层单独算 |

---

## 2. 架构定稿（目标结构）

```
【知识层 · 静态词典】 全部 YAML，只出"字典"不出"计算"
  ├ 宫位主题 WHERE   house_significations.yaml  → 多义词切片（承载者由运行时动态解析，不写死 governors）
  ├ 行星角色 WHAT     planets.yaml（先天征象星+结构）+ planet_nature（domain_signals 唯一角色源）
  ├ 星座方式 HOW      signs.yaml（补活 behavior_style）
  ├ 数值表           dignity.yaml / reception.yaml / aspects.yaml / affliction_quality.yaml
  ├ 定位路由         house_significations.route_keywords / route_secondary（体系二唯一来源）
  ├ 转宫关系         house_derived.yaml（X宫主落Y宫 → X之derived）
  └ 证据链模板       natal_composition.yaml（交叉判断/场景映射/输出结构/护栏）

【看盘范式 · 权威 prompt】 唯一一份（见 §3），LLM 与引擎共同遵循

【数据层 · 静态落库】 出生即定，注册算一次，永远读缓存
  Person.chart_cache
    └ natal:v1:{house_system}:{zodiac}   → 本命 Chart（含 receptions 互溶接纳表）
  （法达不落库——纯函数运行时 O(9) 算，见 §6.1/§6.4）

【计算层 · 唯一引擎】
  ├ assess_planet(chart, planet)           ← 唯一状态评估（4 套抽离合并，资产全保留）
  ├ ConnectionClassifier.classify           ← 承载者连接分级（互溶/接纳/相位/飞宫/同宫）
  └ HouseSignificationEngine.interpret      ← 薄层：选切片 + 解析承载者 + 调 assess_planet

【定位层 · 路由】 可扩展，新增话题只加这里
  IntentRouter（规则）+ ConsultResolver（话题 → 宫/星/征象星）

【动态层 · 现算不存】
  transit / solar_return / lunar_return / progressed / 帮手星（动态接纳链）

【输出层 · 证据链 → 转述】
  ConclusionBuilder（无 LLM）→ response.py（LLM 只转述，硬线）
```

**数据流**：用户说事 → 定位层秒定主题/承载者/方式 → 静态缓存取盘 → 唯一 `assess_planet` 算承载者状态 + `classify` 算连接 → `scenario_maps` 出证据链 → 结论 → LLM 转述。

---

## 3. 看盘通用范式（进 prompt，唯一一份）

> 这是"固定范式"，**不写进任何 YAML**，写在方法论文档 + LLM prompt。任何领域都套它，没有第二套。

```
对任意领域 X（婚姻/事业/财运/健康/学业…）：

  主题   = X 对应的宫位（7/10/2/6/3…）

  承载者 = ① 后天宫主：XR（动态，每人不同）
           ② 宫内星：落在 X 宫的行星（动态）
           ③ 先天征象星：X 领域的天然代表星（静态词典）

  对每个承载者，走同一套完整证据：
     掌宫（管哪些宫）→ 飞宫（落哪宫）→ 落座（落哪个星座）
     → 尊贵（庙旺陷/三分界面）→ 相位（吉凶 + 有无接纳）
     → 互溶接纳（谁帮它）→ 逆行 → 燃烧/日核
     → 角续果宫 → 世代修正 → 劫夺 → 昼夜

  承载者之间的连接：互溶 / 接纳 / 相位 / 飞宫 / 同宫 → 交叉判断

  输出：证据链 → 结论
```

**关键**：这套范式的实例化（"婚姻看金星"）不是写死的规则，而是范式在婚姻这个领域上的**动态展开**——婚姻承载者 = 7R（可能是火星）+ 7 宫内星 + 先天征象星金星。若 7R 就是火星，婚姻伴侣就是火星特质的人；若 7 宫内有火星，婚姻就带火星特质 + 火星掌宫特质。

### 3.1 先/后天征象星（定义 + 静态词典）

- **先天征象星** = 行星本身的固定象征（太阳=父亲、月亮=母亲、金星=恋爱模式、火星=性/行动）。出生即定、人人相同，是"行星角色"词典（planets.yaml）的一部分。
- **后天征象星** = 宫主星（XR），因各人宫头星座而异，每人不同，动态解析。

**先天征象星对照表（静态词典，唯一按领域填的部分）**：

| 领域/主题 | 宫位征象 | 先天征象星 |
|---|---|---|
| 婚姻/伴侣 | 7宫 | 金星(吸引)/火星(被打动)/月亮(依赖)/土星(稳重承诺)/太阳或月亮(性别征象星) |
| 恋爱/桃花 | 5宫 | 金星、火星 |
| 事业 | 10宫 | 太阳(被看见)/土星(地位)/火星(行动) |
| 财运 | 2宫 | 木星(扩张)/金星(价值观)/水星(信息差) |
| 健康 | 1宫/6宫 | 太阳(生命力)/月亮(身心)/火星(炎症)/土星(慢性) |
| 学业(初等) | 3宫 | 水星 |
| 深造(高等) | 9宫 | 木星 |
| 父亲 | 4宫 | 太阳 |
| 母亲 | 10宫 | 月亮 |
| 子女 | 5宫 | 太阳、木星 |
| 朋友/人脉 | 11宫 | 木星 |

> 此表是"唯一按领域填的部分"——其余（宫主星、宫内星、看盘范式、证据引擎）全通用。**新增领域 = 定位层加一条 + 此表加一行，范式/引擎/输出零改动。**

---

## 4. 唯一证据引擎 `assess_planet`

**全项目只留一个函数**，10 星 / 12 宫主 / 征象星 / 帮手星 / 宫内星一视同仁：

```
assess_planet(chart, planet) -> PlanetState
```

**历史设计字段清单（保留阶段0权重讨论；当前实现以 `assess_planet` 与盘点索引为准）**：

| 维度 | 判定口径 | 数据来源 | 当前状态 / 后续边界 |
|---|---|---|---|
| 先天尊贵 | 庙+5/旺+4/三分+3/界+2/面+1；落陷-5/失势-4 | dignity.yaml + `DignityEngine.compute` | dignity.yaml scores（无争议，直接用） |
| 吉凶星性 | 吉星(木金) / 凶星(火土)，按 sect 调制 | `common.BENEFICS/MALEFICS` + chart.sect | ✅ `assess_planet.accidental` 已接线；场景层不得另写系数 |
| 掌宫 | 掌哪些宫（含劫夺） | `house_rulers`（非 house_lord） | 无系数，纯事实 |
| 飞宫 | 落哪宫（含宫头末度） | `effective_house` | 无系数，纯事实 |
| 落座 | 落哪个星座 | `cp.sign.sign` | 无系数，纯事实 |
| 逆行 | 逆行作为境遇压力/力量内收 | `cp.speed`（负值=逆行） | ✅ `assess_planet.accidental` 已接线 |
| 燃烧/日核/日光下 | 燃烧/日光下为压力；日核为强支撑 | `cp.is_combust/is_cazimi/is_under_beams` | ✅ `assess_planet.accidental` 已接线 |
| 相位 | 和谐/动态相位分轨；动态相看有无接纳 | `aspects_to` + `aspect_score` + `is_received` | ✅ `assess_planet.relational` 已接线；minor dynamic 已排除 |
| 互溶接纳 | 是否被接纳/互溶（帮手星判定） | `ConnectionClassifier.is_received` + receptions | 无系数，布尔判定 |
| 角续果宫 | 角宫/续宫显化强，果宫弱 | houses.yaml angularity | ✅ `assess_planet.accidental` 已接线 |
| 世代修正 | 天海冥/南北交/莉莉丝刑冲=外部压力，不按传统实星硬克同权 | affliction_quality.outer | ⚠️ 原则已定，部分场景层已消费；后续继续统一外行星/虚点压力映射 |
| 昼夜 sect | 昼夜生影响三分主、吉凶星性、日月得时 | chart.sect | ✅ `assess_planet` 已消费吉凶星 sect 与日月 sect light；更细得时/失时权重后续只可在此处调整 |

> **刑冲三档语义统一（当前边界）**：active 口径把行星状态放在 `assess_planet.relational`；飞星、行星档案、场景层只做标签或 scenario threshold，不再形成第二套行星状态评分。

**权重系数的修改边界**：行星状态权重只允许在 `assess_planet` 一处变更；场景层可以保留阈值/标签映射，但不得重新计算“第二套行星状态分”。

---

## 5. 三层语义词典合并

### 5.1 12 宫（主题 WHERE）—— 3 文件真合并

| 旧文件 | 旧字段 | 合并后字段名 | 去向 |
|---|---|---|---|
| `houses.yaml` | angularity / natural_sign / natural_planet / keywords_zh | （不变） | **保留**（结构属性，assess 用 angularity） |
| `house_significations.yaml` | word / domains / polarity / intensity / resonance / gated | 字段保留；承载者不写进词条，由运行时动态解析；route keywords 继续承担定位 | 已改造 |
| `house_nature.yaml` | label / themes / topic_keywords / as_derived | ✅ 已完成：route_keywords/route_secondary 并入 house_significations；as_derived 独立为 house_derived.yaml；label/themes 删除 | **已删文件** |

**承载者引用格式**：无引用格式——承载者（宫主星 + 宫内星 + 先天征象星）由**看盘范式**（§3）统一决定，不写死在任何 YAML。先天征象星由 §3.1 静态词典按**子领域粒度**给出（婚姻→金星、对手→火星、合作→木星）。

**as_derived 与 houses.yaml 的关系**：不重复。houses.yaml = 宫位**结构属性**（角续果/天然行星）；house_derived.yaml = 宫位**转宫关系**（"X宫看Y宫是什么"，12×12 条）。维度不同，不存在新重复。

**themes 去重结果**：以 house_significations 的 word 切片为准（结构化、带 domains/polarity）；旧 themes 已随 house_nature 删除，不再作为运行时或 prompt 来源。

### 5.2 10 星（角色 WHAT）—— 3 文件理分工（不是删）

| 文件 | 现状 | 去向 |
|---|---|---|
| `planets.yaml` | 天文/尊贵/征象 significations_zh | **保留**（结构 + 先天征象星） |
| `planet_nature.yaml` | domain_signals + special_rules + relation_role | **保留**（domain_signals 定唯一角色源；special_rules 是证据规则；relation_role 是转述模板） |
| `planet_sign_style.yaml` | 行星×落座风格 120 条 | **保留**（角色×方式交叉） |

三者是三维度（星是什么 / 在话题里当什么 / 怎么运作），**不重复**。历史重复点（domain_signals 与 theme_map/intent_profiles 的 core_planets）已在 R9 收口：运行时统一从 `planet_nature.domain_signals` 派生领域角色。

### 5.3 12 星座（方式 HOW）—— 1 文件补活

| 文件 | 现状 | 去向 |
|---|---|---|
| `signs.yaml` | 元素/模式/守护星 + behavior_style 死数据 | **补活** behavior_style，loader 解析进 SignInfo，喂给 PlanetProfile 落座读法 |

---

## 6. 静态落库 + 动态现算

### 6.1 静态落库（出生即定，注册算一次）

| 数据 | 内容 | 落库 or 派生 |
|---|---|---|
| 本命 Chart | 行星落宫落座/相位/尊贵/日月升/宫头/交点/逆行/福点 + receptions | **落库**（唯一需 Swiss Ephemeris 的） |
| 互溶接纳表 | receptions + acceptances | 写进本命 Chart 缓存（修复"只打日志没缓存"） |
| 命主星 + 后天宫主表 | Asc 守护星 + 1~12 宫主（含劫夺） | 派生（`house_rulers` O(12)，运行时从 Chart 算，不单独落库） |
| 飞星表 | 12 宫主各落哪宫 | 派生（`dispositor` O(12)） |
| 行星档案 | 10 星落座风格/落宫/尊贵/帮手/压力/掌宫 | 派生（`read_all_planets`） |
| 法达表 | — | **不落库**（纯函数 `compute_firdaria` 0.034ms，运行时 O(9) 算） |

**性能基线（实测 2026-08-13）**：
- `NatalChartCalculator.compute(person)` = **0.6 ms/次**
- `compute_firdaria(birth_utc, sect)` = **0.034 ms/次**（纯函数）

**结论**：静态落库的核心收益**不是性能**（0.6ms 可忽略），而是**架构正确性 + 一致性**——本命盘是 Person 的固有属性，出生即定，应归属 Person 而非每次请求临时算。法达是纯函数，微秒级，**根本不需要"0~120 岁逐段展开落库"**（那是过度设计）。真正落库的最小单位 = 本命 Chart（含 receptions）。

### 6.2 动态现算（用到才算，不存）

| 数据 | 何时算 | 谁触发 |
|---|---|---|
| 行运 transit | 每日信、时机触发点、星灵推荐 | 程序 |
| 日返/月返 | 聊天深入时（"最近/今年/这个月"） | 程序 |
| 次限/三限 | 聊天深入时（心态/情绪季节） | 程序 |
| 太阳弧 | v3，未实现 | — |

### 6.3 调用方式

- **程序调用，不是 prompt 调用**。新增 `ChartProvider` 统一封装：查 `Person.chart_cache` → 命中返回 → 未命中 `compute` + 写回。所有现有调用点（runtime:302/325/378、planner:52、main:641、每日信、星灵推荐、学习层）全改走它。
- **LLM 永远不直接读 Chart**——只收到程序格式化好的转述素材（结论+行星档案+证据卡）。
- "prompt 调用"仅两处：①路由关键词进意图 prompt；②转述层叙事结构。占星结论内容永不进 prompt 让 LLM 决定。

### 6.4 法达子限与完整周期（用户确认的产品规则）

- **非节点大运**：子限 = 大限总年数 **÷7**（非 1 年 1 星），子限主从大限主开始按迦勒底序排。各段长度随大限主不同（太阳 10 年→约 1.43 年/段、月亮 9 年→约 1.29 年、木星 12 年→约 1.71 年、火星 7 年→1 年）。
- **节点大运例外**：北交点 3 年、南交点 2 年各自作为完整章节，**不切七段**；出口保持 `sub_lord == major_lord`、`sub_start == major_start`、`sub_end == major_end`。
- **循环边界**：完整法达周期为 **75 年**（七颗传统行星 70 年 + 北交 3 年 + 南交 2 年），75 年后按产品方法循环；“100 年”只能是报告展示或查询范围，不是算法周期。
- **夜生产品顺序**：月亮 → 土星 → 木星 → 火星 → 北交 → 南交 → 太阳 → 金星 → 水星；`NODES_AT_END` 仅保留为兼容 preset，本轮不改传统口径。

**存储决策**：法达是**纯确定性时间函数**（`compute_firdaria(birth_utc, sect, reference)`），大限 O(9) + 非节点子限 O(7)，微秒级。**不落库、不预展开**——运行时直接算。birth_utc（Person 已存）+ sect（Chart 已存）就是全部输入；某时刻所处的大限/子限可直接求得，无需查表。

---

## 7. 帮手星 / 接纳链（已落地）

- **当前实现**：`ConnectionClassifier.helpers_of()` / `ally_timeline()` 已把互溶与相位接纳整理为可审计的直接帮手链；`assess_planet` 关系轴和 `Timing._helper_targets()` 均已消费。
- **时机接线**：Timing 把 direct targets 与 helper targets 分开记录，实际评分目标为二者并集；帮手星只表示“有托住/有兑现通道”，不得盖过直接征象星或抹去本质弱项。
- **缓存**：优先使用本命 `Chart.receptions` / `Chart.acceptances` 快照；旧缓存缺字段或损坏时才懒计算并写回。
- **后续边界**：当前稳定口径是直接帮手；最多 2 跳的 chain tracking 与更复杂 scenario map 属于独立增强，不阻塞 v3 核心收口，也不在本文假定已完成。

---

## 8. 时机链重写（已落地：删年主星 + 法达子限 + 接纳链帮手星）

> **当前实现口径**：active Timing 以 `compute_firdaria(birth_utc, sect, reference)` 的法达大限/子限为 timing authority；direct targets = 大限主/子限主 + 本轮 enrichment 的 `focus_planets` / `focus_house_lords` / `focus_houses` 实际宫主；helper targets = `ConnectionClassifier.ally_timeline()` 找到的直接互溶/激活接纳帮手星。行运只作为触发窗口扫描，payload 分开记录 direct/helper/scoring targets，并返回 `timing_authority="firdaria"`。annual profection/year-lord 不再参与 active 判断。

**当前判断链**：

```
问题（啥时候结婚）
 ① 征象星/宫主星 = ConsultCallPlan enrichment 解析出的 7宫主 + 金星 + 5宫主等本轮承载者
 ② 法达章节 = 当前大限主 + 子限主，作为时间主轴与 direct targets
 ③ 帮手星 = 本命互溶/激活接纳里能托住 direct targets 的 ally/helper
 ④ 行运触发点 = 候选窗口内行运相位打到 direct targets ∪ helper targets
 ⑤ 叠层验证 = 法达主轴 + 本轮承载者 + 接纳帮手 + 行运触发同向时，窗口置信度更高
```

**删年主星——历史迁移清单（已完成，不代表当前代码仍存在）**：

| 历史残留类型 | 当时位置 | 当前边界 |
|---|---|---|
| 年主星函数 / 固定目标星 | `domain/analysis/timing.py` 曾有 `_year_lord()` 与 `targets={year_lord, SUN}` | 已迁移为法达 major/sub + enrichment targets + helper targets；不再用固定太阳兜底 |
| Timeline 年主星字段 | `domain/timeline/timing_stack.py` 曾输出 `year_lord` | active 输出以 `timing_authority="firdaria"` 和 direct/helper/scoring targets 为准 |
| Response / docs 旧措辞 | 曾把「法达/年主星」并列，或把年度小限说成时机权威 | 活跃产品口径只展示法达章节、触发对象与证据；旧称呼只可出现在历史迁移说明里 |
| 枚举 / 测试残留 | `ANNUAL_PROFECTION` 与 year_lord 断言 | active API/序列化不再声明年度小限为活跃图型；若历史数据导入需要兼容，另走导入层迁移 |

---

## 9. 现有资产保护清单（抽出来再删，一条不丢）

以下判断逻辑是反复实盘推演验证过的**资产**，抽取时**原样保留**，只收敛矛盾系数：

1. **吉凶两论**——正负分开累积、不抵消（`_house_quality_dual`）
2. **per-signification 调制**——词级基础 × 动态承载者对应正/负轴 × 宫结构贡献（`_strength`）
3. **飞宫增强**（`_flight_boost`）
4. **event 门控收敛**——gated + strong_count 强连接门槛
5. **接纳三档**——磨合 / 外部压力 / 硬碰（dispositor `_quality`）
6. **世代修正**——天海冥/虚点不硬碰（outer_set）
7. **次要相位排除**——半刑/八分相/梅花

---

## 10. 落地顺序（6 阶段，不返工）

依赖：`assess_planet` 是地基 → 定位点/帮手星/时机链建立其上；静态落库是独立优化，改动面大，放 assess 稳定后。

| 阶段 | 当前状态 | 做什么 | 改/删 | 验证 |
|---|---|---|---|---|
| **0 抽取盘点** | ✅ 已完成，转为 `v3_phase0_inventory` 持续维护 | 4 套证据判断逻辑逐条列出（公式+系数+阈值+门控+来源行号）成资产清单 | 只读不删 | 当前工作树索引持续维护 |
| **1 立 assess_planet** | ✅ 核心已落地，后续只补新增技法 | 抽离合并 4 套 → 唯一函数；本质/境遇/关系三轴保留正负证据 | common.py 成为行星状态入口；`planet_strength` 仅兼容 wrapper | combustion/sect/house/dispositor/profile/career 回归 |
| **2 定位点整理** | ✅ 核心已落地，领域词汇仍可迭代 | house_significations 承载语义场；house_derived 承载转宫；planet_nature/domain_signals 做领域自然征象 | YAML + resolver/enrichment | 婚姻/事业/技能/宫位切片定位正确 |
| **3 静态落库** | ✅ 生产 cache 已落地，预热策略后置 | `NatalChartCache` + 本命/互溶接纳快照；法达纯函数不落库 | Application 注入 ChartProvider；旧缓存懒迁移 | storage/runtime/API 回归 |
| **4 帮手星/证据链** | ✅ 直接 helper/ally 已落地；2 跳 chain 后置 | `ally_timeline` 接纳链，scenario/timing 消费 helper | reception + timing targets | helper/ally/timing helper targets 回归 |
| **5 时机链重写** | ✅ 已落地 | 删年主星，法达大限+子限+征象星/帮手星窗口 | timing.py / timing_stack / docs | Firdaria + timing_stack + career timing 回归 |
| **6 全量回归** | ✅ 已有全量基线；本轮文档收口仍需 targeted 验证 | pytest 修破坏 + 新增阶段测试 | — | 当前已知基线 845 passed；文档收口后跑 targeted/diff check |

---

## 11. 查漏补缺对照表（PM/占星师补充项）

| # | 补充项 | 是否已在规划 | 落地阶段 |
|---|---|---|---|
| S1 | 宫位制 & 黄道制进缓存 key（natal:ALCABITIUS:TROPICAL） | ✅ §6.1 | 阶段 3 |
| S2 | 出生时间未知退化（无上升 → 太阳盘，落宫规则降级） | ✅ 需补实现 | 阶段 3 |
| S3 | 合盘对象本命盘也固定落库（related_person 走 ChartProvider） | ✅ §6.3 | 阶段 3 |
| S4 | 逆行是固定数据（cp.speed 已算，转述层要读到） | ✅ §4 | 阶段 1 |
| S5 | 角宫 angularity 强弱（确认 planet_strength 消费 houses.yaml angularity） | ✅ §4 | 阶段 1 |
| S6 | 太阳弧 v3 未实现 | ✅ 标注，不做 | — |
| S7 | 缓存 schema 版本号（算法升级按版本重算） | ✅ 需补实现 | 阶段 3 |
| S8 | 懒迁移（老用户无缓存 → 首次咨询自动算+写回） | ✅ §6.3 | 阶段 3 |
| S9 | 可解释性（每条 finding 带 rule_id，防瞎编可验证） | ✅ 需补实现 | 阶段 1/2 |
| S10 | 一致性（同一人同一盘本命解读无论何时都一样，仅动态部分随日期变） | ✅ 由静态落库保证 | 阶段 3 |

---

## 12. 测试计划

- **阶段 1**：`assess_planet` 唯一性——同一星走唯一函数，验证燃烧/逆行/角续果/劫夺/世代/昼夜全字段产出；验证旧 4 套调用点迁移后行为一致。
- **阶段 2**：定位层——婚姻/事业/财运/健康/学业各话题，承载者解析正确（7R/宫内星/征象星），写死 governors 不再出现。
- **阶段 3**：落库——注册即缓存；二次请求零 `compute(person)`；老用户懒迁移。（法达为纯函数，不落库、不做二分定位）
- **阶段 4**：帮手星——7R 受克场景，接纳链找到正确帮手星；scenario_maps 的 has_ally 触发。
- **阶段 5**：时机链——删年主星后无残留引用；法达大限+子限窗口正确；夏天盘实盘回归。
- **阶段 6**：全量 pytest 全绿 + 前端 vue-tsc/H5 build 全绿。

---

## 13. 执行原则

1. **先盘后改**：阶段 0 出资产盘点清单，用户过目确认一条不丢，才进阶段 1。
2. **资产不删**：§9 的 7 条判断逻辑原样抽离，只收敛矛盾系数，系数每个都查清"当时为什么这么定"再动。
3. **范式进 prompt**：§3 的看盘范式是唯一权威，YAML 不再写死任何"领域看哪些星"。
4. **可扩展**：新增领域 = 定位层加一条 + 征象星表加一条，范式/引擎/输出零改动。
5. **硬线**：结论全由 Domain 出，LLM 只转述。

---

## 14. 占星技法层审计（F1-F7 缺陷 + 证据链全清单 + 遗漏清单 + 证据层职责分工）

> 本节是「占星学正确性」层，与 §1 架构层 R1-R12 互补。来源：2026-08-13 占星师审稿。

### 14.1 占星技法层缺陷（F1-F7 + 当前状态 + 后续边界）

> **阅读口径**：F1-F7 是 2026-08-13 审稿时的历史缺陷编号；表内保留“为什么改”的诊断价值，同时标出当前实现。不要把历史位置/旧公式当作 active code。

| # | 历史缺陷 | 当前状态 | 后续边界 |
|---|---|---|---|
| **F1**（最重） | Timing 与问题无关：旧 `_month_score` 写死 `targets={year_lord, SUN}` | ✅ 已迁移为法达 major/sub + ConsultCallPlan enrichment + focus houses/lords + helper targets；payload 分开 direct/helper/scoring targets | 月度 scoring 的传统细化可后续增强，但不得回退到固定太阳/年主星 |
| **F2** | 年主星被当征象星 | ✅ active Timing 已删 year-lord/profection 权威，年度小限不参与结论 | 若历史数据导入出现旧字段，另做兼容迁移，不恢复活跃技法 |
| **F3** | 燃烧/日核/日光下缺失 | ✅ `assess_planet` accidental 轴已接线：日核/燃烧/日光下分轨 | 保持证据文本正负分轨 |
| **F4a** | 吉凶星写死，不按昼夜调制 | ✅ `assess_planet` 已按 sect 调制吉凶星 | 场景层不得重写第二套吉凶星系数 |
| **F4b** | 得时/失时作为独立 sect dignity 量纲待统一 | ⚠️ 当前保留在唯一 `assess_planet` 口径下审慎处理，避免压过本质尊贵 | 若新增/调整权重，必须只在 `assess_planet` 一处改，并补混合尊贵回归 |
| **F5** | 宫位制哲学冲突 | ✅ 产品默认 ALCABITIUS，支持 Placidus / Whole Sign；cache key 含 house_system/zodiac | 前端切换与旧缓存迁移按产品迭代做 |
| **F6** | quincunx、外行星尊贵、水星 sect 等数据口径不一 | ⚠️ active 接纳/状态评分已排除 minor dynamic；三王星只关联影响的原则已定 | `reception.yaml` 非经典标注、速度/世代修正等继续作为后续技法 audit |
| **F7** | 吉凶两论半途被净值化 | ✅ 合成器与 signification 已按 positive/negative axes 分轨；`_strength` 取 polarity-specific carrier 轴，不再用整宫净值平摊 | 内部排序标量/legacy `net_score` 可保留；用户可见结论不得展示“净吉凶/净分” |

### 14.2 证据链全清单（当前实现 + 后续项）

> 本表按 2026-08-16 当前工作树重标状态。历史审稿里的“planet_strength 没消费”仅说明旧 facade 的缺口；active 行星状态以 `assess_planet` 为准。

| 维度 | 状态 | 当前边界 |
|---|---|---|
| 掌宫（lordship，含劫夺 ruler 事实） | ✅ | `house_lord` / `house_rulers`；劫夺作为 ruler 事实可读 |
| 飞宫（disposition） | ✅ | `effective_house` / `dispositor` |
| 落座（sign） | ✅ | `cp.sign` |
| 尊贵（庙旺陷三分界面） | ✅ | `DignityEngine` → `assess_planet.essential` |
| 相位（吉凶 + 入相/出相） | ✅ | `aspects` + `application`；active 评分排除 minor dynamic |
| 互溶接纳 | ✅ | `ReceptionEngine` + `ConnectionClassifier.is_received` |
| 克向谁 × 有无接纳 两轴 | ✅ | `affliction_quality` + 接纳/acceptance 口径 |
| 飞宫得吉/受克意涵 | ✅ | `dispositor_rules` + `house_lord`，作为场景解释/兑现路径 |
| 行星×落宫意涵 | ✅ | `planet_in_house.yaml` |
| 行星×落座（120 条） | ✅ | `planet_sign_style.yaml` |
| **角续果（angularity）** | ✅ | `houses.yaml` angularity 已进 `assess_planet.accidental` |
| **逆行（retrograde）** | ✅ | `cp.speed` 已进 `assess_planet.accidental` |
| **燃烧 / 日核 / 日光下** | ✅ | 已进 `assess_planet.accidental`，正负证据分轨 |
| **吉凶星按 sect 调制 / 日月 sect light** | ✅ | 已进 `assess_planet.accidental` |
| **次要相位排除** | ✅ | `assess_planet` / `dispositor` / `planet_profile` active 口径一致排除 minor dynamic |
| **世代修正（三王星不硬碰）** | ⚠️ | 原则已定，部分场景层已消费；后续继续统一外行星/虚点压力在所有场景中的映射 |
| **劫夺（interception）评分** | ⚠️ | ruler 事实已有；暂不作为行星状态评分因子 |
| **福点 / 月相** | ⚠️ | 计算数据存在，分析层尚未系统消费 |
| **速度快慢** | ⚠️ | `speed_deg_per_day` 有数据；快慢/迟滞暂未进入核心评分 |
| **得时/失时细分** | ⚠️ | 吉凶星 sect 与日月 sect light 已接线；更细行星得时/失时权重后续统一 |

**结论**：阶段 1 已把燃烧/日核、sect 调制、角续果、逆行、日月 sect light、minor aspect 排除接入唯一 `assess_planet`。仍待后续的是速度、劫夺评分、福点/月相消费、外行星/虚点压力进一步统一，以及得时/失时细分权重。

### 14.3 遗漏清单（分四类，已剔除阶段1完成项）

**A. 技法完全缺失（❌，新写）**：**相位主星（aspect dispositor）**——刑你的星自己尊贵不尊贵，决定是「贵人的刑」还是「落水狗补一刀」；**太阳弧**（已标注未实现，v3 后置）。

**B. 数据已有没系统消费（⚠️）**：速度快慢、劫夺评分、福点/月相、**命主星特殊权重**（命主星=全局「盘主」，传统要加权读其状态，现只当普通 1 宫主）、**行星容许度 orb 死数据**（`planets.yaml` 每星 orb 未消费，`_pair_aspects` 用相位类型固定容许度+日月+2，传统应取 `(orb_A+orb_B)/2`）。

**C. 已收敛但需防回潮（✅/⚠️）**：minor dynamic 排除、吉凶两论不净值化、Timing 征象星化、法达 authority、R9 core_planets 三处重复、R10 静态 governors 退场均已完成；后续只保留文档/测试护栏。

**D. 架构缺口（补结构）**：**组合层统一入口**（金月火散在 planet_pair/theme_map/natal_composition/compositor 四处，缺 CombinationEngine）、**性别征象星**（女盘太阳=夫/男盘月亮=妻，`PartnerTraits` 没读）、婚姻征象星土星已补进 §3.1，后续要看输出链是否系统消费。

### 14.4 证据层职责分工（本命 / 法达 / 行运 / 日月返 / 年主星）

**不是并列，是分工 + 主次**：本命=地基，法达=当前章，行运=触发点，日月返=快照，年主星删除。

| 技法 | 回答什么 | 时间粒度 | 何时调用 | 结论权重 |
|---|---|---|---|---|
| **本命盘** natal | 「你是谁 / 你的模式」 | 终身不变 | **永远**（所有问题地基） | 主（底色） |
| **法达** firdaria | 「现在是哪一章」 | 大限≈10y / 子限≈1y | 问「现在/最近/这几年」 | 主（中观基调） |
| **行运** transit | 「现在具体发生什么 / 何时触发」 | 天~月 | 问「现在/这个月/什么时候」 | 触发点（不独立成论） |
| **日返/月返** | 「今年/这个月主题快照」 | 年/月 | 问「今年/这个月怎么样」 | 辅（可选增强） |
| ~~年主星~~ profection | ~~「今年哪个宫亮」~~ | — | **删除** | — |

**调用决策（写死成门控，别让 LLM 选）**：问「我是什么样/婚姻模式」→ 只本命；问「现在/最近/今年」→ 本命+法达+行运（+日返可选）；问「什么时候结婚」→ 本命（征象星）+法达（章节窗口）+行运（触发点）。**用时间粒度判断，不用话题判断。**

### 14.5 后续维护优先级

1. **已完成项设护栏**：F1 Timing 征象星化、F2 年主星退场、F3 燃烧/日核、F4 sect 调制、minor dynamic 排除、R9/R10 动态承载者，后续只保留测试与文档防回潮。
2. **继续统一但不抢主轴**：外行星/虚点压力、世代修正、得时/失时细分，只能在 `assess_planet` 或明确 scenario map 中推进，不新增第二套行星状态评分。
3. **数据已有但后置消费**：速度快慢、劫夺评分、福点/月相、命主星特殊权重、行星 orb，逐项补规则与回归，不在本轮假定完成。
4. **结构增强**：组合引擎（CombinationEngine）与性别征象星输出链，作为后续架构补缺，不影响当前唯一证据引擎收口。
5. **进阶技法后置**：相位主星、太阳弧等新技法另开阶段设计；不得混入本轮文档/契约收口。
