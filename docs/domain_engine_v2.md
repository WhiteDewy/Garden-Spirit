# 领域引擎 v2 设计（Domain Engine v2）

> 状态：**已实现 v1（2026-08-12）**，四步迁移全落地，707→716 测试全绿。
> 实现记录：① 词汇合一（`shared/enums.py` IntentDomain 11 域 + 三套词汇对齐）；② 语义场（house_significations 全词条加 `governors`、signs.yaml 12 星座 `behavior_style`、planet_nature 天海冥只关联）；③ 领域定义数据化（intent_profiles 新增 growth/network/self 三域配方 + 反向点亮映射）；④ per-signification 调制（`signification.py::_strength` 改为"词级基础 × governor 对应正/负轴 × 宫结构加权贡献"）+ 三轨合成器（`interpretation/compositor.py::DomainCompositor`，轨A征象×轨B宫主×轨C互溶桥，§4.4 合读规则五档）。
> 覆盖：语义场单一真相源 + 领域=精心挑选的子集 + 三轨合成器 + per-signification 调制 + 领域集合（11 域）+ 迁移路径。
> 配套：`docs/self_map_design.md`（自我地图，本设计取代其中"9宫只挂学习 / 11宫被弱化"的旧表述）· `domain/astrology/knowledge/house_significations.yaml` · `domain/astrology/knowledge/planet_nature.yaml` · `domain/reasoning/intent/intent_profiles.yaml` · `domain/astrology/interpretation/compositor.py`

---

## 0. 为什么要有 v2：三套领域词汇在打架

当前系统里存在**三套互不一致的领域清单**，各自为政：

| 来源 | 词汇 | 例子 |
|---|---|---|
| `shared/enums.py` `IntentDomain` | career / relationship / wealth / health / emotion / family / learning / **daily** | 意图路由用这套 |
| `natal.py` `NATAL_DOMAINS` + `house_significations.yaml` domains | career / wealth / relationship / emotion / health / family / learning / **self** | 宫位语义场引擎用这套 |
| `planet_nature.yaml` domain_signals | career / **marriage / dating** / wealth / health / **study** / family / **villain** | 星性角色用这套 |

**后果**：
- `daily` 在宫位语义表里**一个条目都没有** → 若路由到引擎解读，出空。
- `self`（我是谁/内在成长/灵性）在意图层**没有正门** → 用户问"我是谁"接不住。对一个"自我探索陪伴"产品，最核心的域反而是孤儿。
- `marriage/dating/villain` 与 `relationship`、`study` 与 `learning` 同义异构 → 跨模块对不上。

**v2 目标**：一套领域词汇，一个真相源（语义场），领域从语义场派生，不再手工写死。

---

## 1. 核心原则（设计硬线）

1. **语义场是唯一真相源**：12 宫 × 10 星 × 12 星座的"语义单位"（含 `domains` 标签 + `governors` 主星）是事实。领域**不是**事实，是**视图**。
2. **领域 = 精心挑选的语义场子集（curated selection）**：你决定哪些语义单位属于"事业"，这份"属于"写成标签；引擎机械展开。定义是声明的、数据驱动的，不是每个领域一段手写 Python。
3. **三轨分离，宫性优先**：论一个领域，三轨并出、结构轨优先——征象轨（星性/色彩）× 宫主轨（宫性/结构）× 互溶桥（通道）。"宫性大于星性"= 领域的成败以宫主星（宫性的代言人）为准，先天征象星只做色彩调制。
4. **per-signification 调制**：每个语义含义带自己的 `governors`（主星），强弱 = 词级基础 × governor 对应正/负轴 × 宫结构贡献。**严禁**整个宫一份状态平摊给所有含义。
5. **三王星只做关联影响**：天王/海王/冥王不掌宫、不互溶接纳、无传统尊贵、刑冲算"外部压力"——只从星性 × 落座 × 落宫解读，做领域染色，不做结构判断。规则已实现（`reception.yaml:11-18` / `dignity.yaml:7` / `common.py:20-26` / `dispositor.py:86-90`）。
6. **硬线不变**：占星结论全由 Domain 出，LLM 自由度只在"怎么疗愈 / 怎么陪伴"。

---

## 2. 领域集合：11 域（12 宫全覆盖）

> 在原有 8 域基础上：**感情加宽**（收 12 宫暗面）、**新增 9 宫远方·信念**、**新增 11 宫人际·社群**、**新增 self 自我**。daily 保留为跨域行运视图。

| # | key | 中文名 | 宫位绑定 | 用户问题示例 |
|---|---|---|---|---|
| 1 | career | 事业 | 10, 6, 2, 1 | 该不该换工作 / 能升职吗 / 适合创业吗 / 职业方向 |
| 2 | relationship | 感情（宽） | 5, 7, 8, 12 | 暧昧 / 暗恋 / 相亲 / 恋爱 / 复合 / 婚姻 / 异地 / 背叛 / 三角 |
| 3 | wealth | 财富 | 2, 8, 11 | 财运 / 投资 / 理财 / 偏财 / 副业 |
| 4 | health | 健康 | 1, 6, 12 | 精力 / 失眠 / 疲劳 / 身心连接 |
| 5 | emotion | 情绪 | 4, 8, 12 | 低落 / 焦虑 / 迷茫 / 内心安全感 |
| 6 | family | 家庭 | 4, 5(亲子), 10 | 原生家庭 / 亲子 / 房产 / 父母 |
| 7 | learning | 学习 | 3, 6 | 考试 / 考研 / 考证 / 学习 |
| 8 | growth | 远方·信念 | 9, 12 | 留学 / 出国 / 深造 / 信仰 / 人生意义 / 旅行 |
| 9 | network | 人际·社群 | 11, 3, 7 | 朋友 / 人脉 / 圈子 / 团队 / 粉丝 / 社交 |
| 10 | self | 自我 | 1, 9, 12 | 我是谁 / 人格 / 内在成长 / 灵性 |
| 11 | daily | 每日 | 跨域行运 | 今日运势 |

**12 宫覆盖核对**（每宫至少 1 域，一个没丢）：

| 宫 | 归属域 | 宫 | 归属域 |
|---|---|---|---|
| 1 | career·health·self | 7 | relationship·network |
| 2 | career·wealth | 8 | relationship·wealth·emotion |
| 3 | learning·network | 9 | growth·self |
| 4 | emotion·family | 10 | career·family |
| 5 | relationship·family | 11 | wealth·network |
| 6 | career·health·learning | 12 | health·emotion·relationship·growth·self |

> **决策点（本稿推荐）**：`self` 单列成 11 域。理由：① "我是谁/我想成为什么样的人"是自我探索产品的**核心问题**；② 语义场已标好 `self`（`house_significations.yaml` 多处 `domains: [..., self]`），`NATAL_DOMAINS` 也含 self——不单列就重现"孤儿域"。**备选**：若想压回 10 域，把 self 并进 growth（灵性/信仰）与 emotion（内在安全感），删除 self 行。
> **决策点**：感情加宽为"恋爱/婚姻/亲密/暧昧/暗恋/相亲/异地/复合/背叛/三角"整条光谱（5/7/8/12），朋友/社群归 11 人际·社群，亲情归 4 家庭——三者不再互相挤占。

---

## 3. 语义场标签规范（数据层）

语义单位 = 固定集合（宫位语义 + 行星征象 + 星座行为），标签只是映射。**收敛约束**：每个语义单位最多打 **2-3 个主域**，防信号稀释成"标签丛林"。

### 3.1 宫位语义场（已有，需加 governors + 修 daily/self）

`house_significations.yaml` 现状：12 宫 × 多义词，每个词有 `domains`。改造：
- **词汇对齐**：`self` 保留；无 `daily` 词条（daily 是跨域行运视图，不在此表）。
- **加 `governors`**：每个含义声明"这顶帽子听谁的"。例（3 宫）：

```yaml
3:
  - word: "沟通/表达/写作"
    domains: [career, learning, self]
    governors: [mercury]          # 自己表达看水星 + 3宫主
    ...
  - word: "兄弟姐妹/邻里/熟人群"
    domains: [family]
    governors: [3rd_lord]         # 手足看3宫结构 + 3宫主，不看水星
    ...
```

- **governors 取值**：具体行星（`mercury`）/ 宫主引用（`3rd_lord`）/ 多主星（`[mercury, jupiter]`）。`3rd_lord` 在运行时展开为实际宫主星（传统守卫星，`common.py` 已实现）。

### 3.2 行星征象场（已有星性，缺领域标签）

`planets.yaml` 10 星有 `significations_zh`（先天征象词），`planet_nature.yaml` 有 `domain_signals`（但词汇是 marriage/dating/study/villain，需对齐）。改造：
- `planet_nature.yaml` `domain_signals` 词汇**对齐到 11 域**（marriage/dating → relationship；study → learning；villain 拆给 relationship·network）。
- 天海冥：`domain_signals` 保持"只做关联影响"定位——全部 `supporting` 或 `neutral`，**不设 `core`**，`core_formula` 保持 `变革 × {house_domain}`（不含 dignity_adverb）。

| 行星 | 先天征象 → 域（示意） |
|---|---|
| 太阳 | career(被看见/成就) · self(意志) · health(生命力) · family(父亲) |
| 月亮 | emotion(情绪) · family(母亲/安全感) · health(身心) · self(潜意识) |
| 水星 | learning(思维/表达) · network(沟通/信息) · career(技能/商业) |
| 金星 | relationship(爱情/吸引力) · wealth(价值/审美消费) · network(人际魅力) |
| 火星 | career(行动/竞争) · relationship(激情/性) · health(活力/炎症) |
| 木星 | career(扩张/贵人) · wealth(偏财/丰盛) · growth(远见/深造) · network(贵人/人脉) |
| 土星 | career(结构/权威/成就) · family(责任/父亲) · learning(纪律/毅力) · health(慢性/压力) |
| 天王 | career(变革/科技/独立) · network(社群/创新) —— 关联 |
| 海王 | growth(灵性/信仰/艺术) · relationship(理想化/幻灭) · health(不明原因) —— 关联 |
| 冥王 | relationship(深度/执念/权力) · wealth(大额投资/偏财) · self(转化/重生) —— 关联 |

### 3.3 星座行为场（已有 keywords，补行为风格 × 域）

- `signs.yaml` 有 `keywords_zh`（勇气/开创/直接…白羊）。改造：新增 `behavior_style`（应对方式，对齐 self_map_design 星座风格区），并标 `domains` 弱标签（1-2 域，作行为调制用，不做主选）。
- 行为场在解读中做**"怎么表现"的调制**，不参与"属于哪个域"的主选（星座区 = 行为原型，不贴人格标签，硬线）。

### 3.4 标签防稀释规则

- 每语义单位 **2-3 主域上限**；超过需裁剪。
- `governors` 至少 1 颗主星；`governors` 不能是虚点/三王星（它们不掌宫），只能做次级关联。

---

## 3.5 入口路由：从问题到领域（四层推导链）

> 本节回答「用户一句话，怎么落到领域/宫/星/星座」——这是 §4 三轨合成的前置：先有入口，才有合成。

```
用户意图 → 领域 (domain)
              ├─ 线A【宫·后天】: 领域 → 宫(WHERE) → 后天宫主星 XR + 宫内星
              └─ 线B【星·先天】: 领域 → 先天征象星(WHAT)   ← 静态词典，直接从领域命中
          ↓ 两条线汇合 = 承载者集合
   每个承载者 → 落座(HOW) → 证据链 → 结论 → LLM 转述
```

**命中 / 解析 三档**（规则优先，LLM 只兜底受控枚举——绝不 LLM 看盘）：

| 层 | 命中 or 解析 | 怎么得到 |
|---|---|---|
| 宫 WHERE | **命中** | 确定性规则优先（domain 词表 + `rules._HOUSE_RE` + house_significations `domains`）；规则 miss → LLM 受控枚举 |
| 先天征象星 WHAT | **命中（静态查表）** | 领域 → `domain_signals`（`planet_nature.yaml` core/supporting） |
| 后天宫主星 / 宫内星 | **解析** | 宫 → `house_lord` / `house_rulers`（含劫夺）+ 宫内星 |
| 星座 HOW | **解析** | 承载者 → `cp.sign.sign` |

**先天 vs 后天 征象星**（读一个主题，征象星双轨）：

| | 先天征象星（natural） | 后天征象星（accidental） |
|---|---|---|
| 来源 | 行星固有本性，人人相同 | 宫头星座，每人不同 |
| 回答 | 「你怎么爱 / 能力底色」 | 「你实际遇到谁 / 具体对象」 |

即便 7R 是火星，金星仍是婚姻的先天征象星，必须读——两者互补不替代。**先天星性（行星本性）× 后天职责（掌什么宫）相乘才是完整解读**：读「7R 火星」=「火星星性 × 掌 7 宫职责」=「伴侣是火星特质的人」。

**先天征象星对照表**（静态词典，唯一按领域填的部分）：

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

**性别征象星**（传统固定）：女盘看太阳=夫/男盘看月亮=妻（`PartnerTraits` 待补这一颗）。

**与体系一（`ConsultResolver` keyword 路由）的关系**：体系一是资产（规则命中宫），不是要删——升级为「语义场词典 + 正则 + LLM 兜底」，结果形态从写死 `TopicPlan` 升级为 `{domain, focus_house, focus_slice, 承载者}`。最终只留这一套入口。

---

## 4. 三轨合成器（核心引擎）

**输入**：领域 key。**输出**：该领域的解读条目（每条带证据链）。

```
领域 ──① 展开语义场 ──→ 该域所有语义单位（宫+星+星座）
          │
          ├─ 轨 A · 征象轨：先天征象行星的落宫/落座/尊贵 → "能力与色彩"
          ├─ 轨 B · 宫主轨：领域核心宫的宫主星尊贵/落宫/受克 → "结构与吉凶"（优先）
          └─ 轨 C · 互溶桥：A 与 B 是否互溶/接纳/飞宫 → "哪条通道兑现"
          │
          ├─ per-word 调制：每个含义按 governors 单独算强度（§5）
          └─→ 合读：结构轨定成败，色彩轨定表现，桥轨定路径
```

### 4.1 轨 A · 先天征象（色彩）

取该域 `domain_signals` 标定的征象星（如事业=太阳/土星/木星/火星），读它们的 `planet_profile`（落座风格/落宫领域/尊贵/支持者/破坏者）。回答："你在这个领域是什么底色、靠什么发光"。

### 4.2 轨 B · 宫主（结构，优先）

取该域 `core_houses` 的宫主星（`house_lord`，传统守卫星），读宫主尊贵、落宫、受克。回答："这个领域的结构是顺是逆、正轨能不能立住"。**宫主轨权威 > 征象轨**：不因太阳尊贵就说事业好。

### 4.3 轨 C · 互溶桥（通道）

用 `ConnectionClassifier`（已实现互溶4>接纳3>相位2.5>飞宫2>同宫1>潜在0.5）检测：征象星与宫主星是否互溶/接纳/飞宫。回答："哪条通道兑现"——有桥则才能就是实际路径（绕开落陷结构）；无桥则两轨各说各话（才华与结构不对口，需现实中把才华导向结构）。

### 4.4 合读规则（确定性、可追溯）

```
有桥 + 结构好 + 征象好 → 顺遂（才能走正轨，锦上添花）
有桥 + 结构弱 + 征象好 → 绕道成才（用才能绕开弱结构，走非主流路径）
无桥 + 结构好 + 征象弱 → 有平台缺锋芒（结构托底，能力需补）
无桥 + 结构弱 + 征象好 → 有能力不对口（才华与结构无连接，需主动搭建）
无桥 + 结构弱 + 征象弱 → 该领域先天吃力（多维度短板，提示需外部支持）
```

> 每一条结论必须能指到"哪个语义单位 + 哪条规则"。硬线内：LLM 不参与合成，只转述 + 疗愈叙事。

---

## 5. per-signification 调制（修复整宫状态平摊缺陷）

**已修复口径**：每个语义词按自己的 `governors` 与 polarity-specific axes 单独调制，避免把同一宫位的一份状态平摊给所有含义 → 引擎可以表达“3宫结构强，但自己表达弱、手足旺”的分化。

**改造**：每个含义按 `governors` 单独算强度。

```
含义强度(word) = 词级基础(intensity)
              × (1 + Σ governors 对应正/负轴调制)  # 词级主星状态
              × (1 + 宫结构贡献 × 权重)              # 宫结构只贡献一部分，不独占
```

**设计用例（验收标准）**——"3宫强，但沟通弱、手足旺"：
- 3宫结构强 + 3宫主好 → `兄弟姐妹/邻里` 帽子的 governors(`3rd_lord`) 强 → 手足旺 ✅
- `沟通/表达/写作` 帽子的 governors(`mercury`) 受克 → 自己表达弱 ✅
- 两顶帽子各论各的，互不污染。引擎必须能同时输出这两个结论。

> 这就是语义场必须 per-word 而非 per-house 的原因。这个案例写进测试当黄金夹具。

---

## 6. 工程架构与迁移路径

### 6.1 四层架构

```
L4 叙事层    LLM 转述 + 疗愈叙事（人格化）        ← 唯一允许 LLM 的地方
L3 领域层    领域定义 YAML（声明式）+ 合成器         ← 三轨合成 + per-word 调制
L2 语义场层  house/planet/sign 语义场 + 结构规则     ← 落宫/落座/掌宫/飞星/尊贵/相位/互溶接纳（确定性）
L1 数据层    YAML 知识库（单一真相源）
```

### 6.2 迁移四步（每步测试兜底，全量回归）

| 步 | 内容 | 产物 |
|---|---|---|
| **1 合一词汇** | `IntentDomain` 扩到 11 域；`natal.py`/`house_significations`/`planet_nature` 词汇对齐到 11 域；删 `daily`/`self` 分裂 | `shared/enums.py` + 词汇表 |
| **2 补语义场** | house_significations 加 `governors`；planet_nature domain_signals 对齐 + 天海冥确认"只关联"；signs.yaml 补 `behavior_style` | 三个 YAML |
| **3 领域定义数据化** | `intent_profiles.yaml` 保留 core_houses/house_lords 等结构配方；领域行星角色统一从 `planet_nature.domain_signals` 派生，`core_planets` 不再作为独立真相源；新增 growth/network/self 三域配方 | `intent_profiles.yaml` + `planet_nature.yaml` |
| **4 合成器 + 模块转型** | 新建三轨合成器 + per-word 调制；现有 CareerStrength/Wealth/Risk 等**保留为"领域放大器"**，通用语义场读数为底，逐域迁移 | 新引擎 + 测试 |

> **放大器原则**：专用模块不删除、不重写语义，只做"通用读数之上再深挖"（如职业时机/财务杠杆）。通用语义场给骨架，放大器给血肉，二者可并行存在。

### 6.3 风险与对策

| 风险 | 对策 |
|---|---|
| 三轨合成变黑箱 | 每条结论带证据链（哪个语义单位+哪条规则），LLM 不参与合成（硬线） |
| 标签丛林（一个单位打 10 个域） | 2-3 主域上限 + governors 至少 1 主星；超限裁剪 |
| 专用模块丢调优 | 保留为放大器，逐域迁移，每步 707 全量回归 |
| 天海冥误入结构判断 | `_participating()`/`house_lord`/`dignity` 已排除；合成器禁以天海冥为宫主 |
| 感情加宽后与 11/4 域重叠 | 明确边界：恋爱/婚姻/亲密→relationship，朋友/社群→network，亲情/亲子→family |

---

## 7. 验收标准

1. **手足案例**（§5）：3宫强 + 水星受克 → 引擎同时输出"手足旺"+"表达弱"，各带证据。
2. **太阳尊贵落3宫 vs 10宫落陷**（§4）：三轨并出——征象"有表达才能" + 宫主"事业结构弱" + 互溶桥判定"走非主流路径 or 不对口"，不因太阳尊贵误判"事业好"。
3. **词汇合一**：全代码 grep 领域字符串，只有 11 域一套；`daily`/`self` 分裂消除。
4. **天海冥规则回归**：三王星不掌宫、不互溶、无尊贵、刑冲=外部压力（现有测试保持绿）。
5. **全量回归**：现有 727 测试全绿 + 新增语义场/合成器/调制测试。

---

## 8. 宫位咨询意图流（2026-08-12 新增）

用户直接问"我的3宫怎么样"时，宫位是**精确占星词汇**（不走 LLM，纯确定性规则
`domain/reasoning/intent/rules.py` `_HOUSE_RE` 抽取），但裸宫位是**多义语义场**
——同一个 3 宫涵盖表达/学习/传播/手足四块，领域归属必须由用户点名。

三步闭环（全确定性，硬线：LLM 自由度只在"怎么疗愈/怎么陪伴"）：

1. **裸宫反问**：`route()` 命中宫位号但无切片词、无规则领域词 → 置
   `requires_clarification`，问题列出该宫语义场切片（`house_significations.yaml`
   唯一事实源），由用户自选："3宫涵盖的方面挺多的——沟通/表达/写作、学习/短途/走动…你想问的是哪一块？"
2. **切片锁定（跨轮）**：反问时 runtime 把 `focus_house` 暂存到
   `SessionContext.pending_focus_house`（经 `to_intent_context()["active_house"]` 透传）。
   本轮回答切片词（表达/出行/桃花…）→ `_resolve_house_followup` 匹配该宫切片 →
   锁 `focus_house` + `focus_domain`（歧义切片按 `_SLICE_DOMAIN_PREF = (self, learning)` 优先序）。
3. **宫位解读**：runtime 检测 `focus_house` 槽位 → 跳过领域策略管线，直接
   `HouseSignificationEngine.interpret(chart, domain, houses=[N])` 出宫位语义场解读
   → 组装 descriptive Conclusion（summary + findings 带证据）→ LLM 转述
   （`response.py` 注入 `house_focus` 聚焦指令，不发散到别的宫）。

配套规则：
- **领域词 + 宫位**（"12宫财运"）：规则锁域（wealth）+ 宫位作 focus，不反问。
- **口语别名**（`_SLICE_ALIASES`）：出行→短途、口才→说话、桃花→恋爱。
- **陪伴门控**：`should_use_companion` 检测 `focus_house` 槽位 → 宫位引用不进
  陪伴兜底（否则 domain=DAILY+subdomain="" 会被当闲聊吞掉）。
- **转话题消解**：反问后用户回答不匹配任何切片（"我感情怎么样"）→ 常规路由，暂存清理。
- **无信号降级**：该宫该域无切片（如"3宫感情"）→ 诚实说"这个面上没有明显结构信号"。

---

## 8.1 三层意图 Prompt（对话模式感知，2026-08-13 新增）

用户批评"意图识别做得很弱"——旧 `_INTENT_CLASSIFY_SYSTEM` 是裸领域枚举分类器，
LLM 看不到对话上下文、不懂宫位、没有"深挖/确认/切换"概念，LLM 被严重浪费。
升级为三层意图 prompt（`application/agent/intent_parser.py`），共享同一输出骨架，
但上下文注入量、意图粒度、追问姿态完全不同：

| 模式 | Prompt | 任务 | 上下文注入 |
|------|--------|------|-----------|
| DEEP（默认） | `_DEEP_INTENT_PROMPT` | intent_type（此刻在做什么）+ 领域 + 宫位 + 切片 + 深挖/确认 | 完整：最近 3 轮 + 活跃领域/宫位 |
| QUICK | `_QUICK_INTENT_PROMPT` | DEEP 骨架 + 收敛规则（不深挖/高澄清门槛/不宫位反问） | 同 DEEP |
| FREE | `_FREE_INTENT_PROMPT` | 只判断「是否在聊占星」 | 无（不看宫位表） |

**上下文注入（python 侧）**：`to_intent_context()` 增 `recent_turns`（最近 3 轮，
`assistant` 截断——**最后一条取尾部 160 字**，验证问句/反问都写在回复末尾，LLM 要
看到它才能识别"确认轮"）。`_build_context_block()` 拼 `## 对话历史` + `## 活跃上下文`。

**富输出**（Intent 模型扩 4 字段）：
- `intent_type`: new_question / follow_up_deep_dive / clarification_response /
  topic_switch / confirmation / chat / meta（只影响路由方向，不影响结论内容）
- `focus_slice`: 用户点名的切片词
- `deep_dive`: 对上一轮某切片的深挖追问
- `confirmed`: 确认轮的 确认/否认

**硬线不变的落地方式**：
- 领域仍是受控枚举，LLM 输出非法 → 规则兜底不信。
- 宫位是精确占星词汇 → `parse()` 里 `_house_from_text` 确定性检测**永远先于 LLM**。
- LLM 给 `focus_slice` 后，用规则的 `_match_slice`/`_domain_for_slice`（signification 表）
  **权威化领域**——LLM 猜 learning，3宫"表达"切片仍归 self（`_SLICE_DOMAIN_PREF`）。
- `rules.py` 保持纯安全网（LLM 不可用/非法 → 完整规则路由，离线可测）。

**FREE 模式**：`ConsultMode.FREE` 接线走通。LLM 判 `is_astrology_question=false` →
`Daily.Chat`（陪伴管线，不进占星）；true → 用 DEEP 模板二次分类（两次调用仅发生在
FREE 下转占星）。API `_parse_mode` 已支持 "free"。

## 8.2 证据链深挖（"怎么个暗财"，2026-08-13 新增）

用户"你说12宫暗财，那我要问你是怎么个暗财呢"——旧实现把同一份顶层读数重放一遍
（玄学+暗财 top-3 证据），没有钻进去。修复：`intent_type=follow_up_deep_dive` +
`focus_house` → runtime 走**深挖宫位路径**：

1. `_house_conclusion(deep=True)`：`max_items` 6→10、evidence **全链展开**（不截
   top-3——来源/通道/托底/风险逐环可见）、summary 改机制视角
   （"往下钻「暗财」的来路——机制是这样一环环扣起来的"）。
2. **验证问句**（`_verification_question`，确定性模板）：深挖回复末尾追加机制验证
   ——"你最近有没有靠不公开的渠道进账——副业、投资、资源置换这类？"。
   对应 consult_method §3「对话验证，不讲独白」：结论要用户自己认领。
3. **确认收敛**（`intent_type=confirmation`）：用户"对，就是有副业" → runtime 经
   `ctx.pending_house_verify`（(宫位, 域, 切片) 暂存）继承宫位 → `_house_conclusion(
   deep=True, confirmed=True)` → summary 收敛为"坐实"/"倾向"（确认/否认两分支），
   不复述证据链。`response.py` 注入 `confirmed` 收敛指令，LLM 先承接确认再收束。
4. **离线兜底**：规则层 `_detect_confirmation`（紧前置：`pending_house_verify` 非空
   + 短句 ≤20 字 + 确认词枚举）→ LLM 关闭时确认轮也走通证据链闭环。

---

## 9. 参考文件

- `shared/enums.py` —— IntentDomain（待扩 11 域）
- `domain/astrology/knowledge/house_significations.yaml` —— 宫位语义场（加 governors）
- `domain/astrology/knowledge/planet_nature.yaml` —— 星性/domain_signals（词汇对齐）
- `domain/astrology/knowledge/signs.yaml` + `planet_sign_style.yaml` —— 星座行为场
- `domain/astrology/knowledge/reception.yaml` + `reception.py` —— 互溶接纳（天海冥排除已实现）
- `domain/astrology/interpretation/signification.py` —— HouseSignificationEngine（per-word 调制改造点）
- `domain/astrology/interpretation/synapsis.py` —— ConnectionClassifier（互溶桥）
- `domain/reasoning/intent/intent_profiles.yaml` —— 领域配方（第三步改派生）
- `docs/self_map_design.md` —— 自我地图（本设计取代旧 8 域表述）
