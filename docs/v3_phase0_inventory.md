# v3 阶段0：证据资产盘点清单

> 状态：Draft。阶段0 只读盘点，不改实现。
> 目标：在进入/收敛唯一 `assess_planet` 之前，把现有证据判断逻辑逐条列清，确认资产不丢、口径不混、删除项有明确替代。
> 权威来源：`docs/refactor_plan.md`；本表按当前工作树核对，不采用隔离 worktree 的过期扫描结果。

---

## 1. 阶段0验收标准

阶段0完成时，需要给出并确认以下内容：

1. **状态评估逻辑**：公式、系数、阈值、门控、调用点、已有测试。
2. **时机链现状**：年主星/profections 残留、法达大限/子限现状、行运触发点现状、Timing 是否按领域征象星化。
3. **接纳/帮手星现状**：互溶、接纳、相位接纳、飞宫连接、帮手星链哪些已实现，哪些只是 YAML 声明。
4. **静态盘缓存现状**：本命 `Chart` 是否落库、互溶接纳是否进缓存、运行时还有哪些 `compute(person)` 调用点。
5. **可保留资产清单**：迁入 `assess_planet` / `ConnectionClassifier` / scenario map 的旧逻辑，不直接删除。
6. **口径冲突清单**：阶段1必须统一的系数/相位/世代修正/净值化问题。
7. **删除残留清单**：阶段5删除年主星时必须同步清理的代码、测试、文档。

---

## 2. 不变硬线

- Application 不懂占星。
- Domain 不依赖 LLM。
- LLM 永不看原始 Chart，永不决定吉凶、权重、重要宫位。
- 占星结论全部由 Domain 产生，LLM 只做自然语言映射、追问、疗愈转述。
- v3 重构目标不是换流派，而是把已选定的西占范式做成一套一致、可审计、可回归的证据引擎。

---

## 3. 当前总评

当前工作树已经不是“v3 从零开始”：核心轴、接纳链、时机链、静态缓存都已有大量提前落地。阶段1不应大拆重写，而应做**收敛、去重、定口径**。

| 模块 | 当前判断 | 阶段动作 |
|---|---|---|
| `assess_planet` 三轴 | 已落地；含本质/境遇/关系三轴、正负分开、证据可追踪、chart 内 memo | 阶段1把剩余局部评分迁入它，避免第二套评分 |
| `planet_strength` | 已降级为兼容薄包装；不再是权威评分源 | 保留短期兼容，阶段3后评估删除/改名 |
| 宫位语义场 | 已消费 `assess_planet`，并有 per-signification 调制 | 清理 stale docstring；固定词级调制测试 |
| 飞星/行星档案 | 已消费 `assess_planet`，但仍保留局部阈值/标签映射 | 保留为场景映射，不回流成评分源 |
| 合成器 `compositor.py` | 已迁入公共 `assess_planet`；局部 `_assess_planet_r9` / `_helpers_of_r9` 已删除 | 阶段1已完成首要迁移；后续只保留合成器场景阈值 |
| Timing | 代码已转向法达 major/sub + 问题征象星 + 帮手星；无 active `_year_lord`；`ANNUAL_PROFECTION` enum 与活跃 timing 文档已清 | 阶段5已收口；仅保留历史计划/盘点记录说明删除背景 |
| Chart cache | 已有 `NatalChartCache`，API/runtime/letter/learning 已注入 | 注册时预热可后置；先保留懒计算 |

---

## 4. 资产盘点表：状态评估逻辑

| # | 逻辑/函数 | 文件位置 | 输入 | 输出 | 公式/系数 | 门控/阈值 | 调用点 | 测试覆盖 | 迁移去向 | 风险 |
|---|---|---|---|---|---|---|---|---|---|---|
| A1 | `assess_planet` | `domain/astrology/common.py` | `Chart`, `KnowledgeBase`, `Planet`, 可选 `DignityEngine`, `ConnectionClassifier` | `PlanetAssessment`：essential/accidental/relational 三轴正负分与证据 | essential：尊贵正负 `×0.35`；accidental：燃烧/日核/日光下、sect 调制吉凶星、角续果、逆行、日月 sect light；relational：和谐相 `+0.3`、动态相未接纳 `+0.5`/有接纳 `+0.3`、互溶 `+0.5`、接纳 `+0.3` | 排除 minor aspects；chart.planet_assessments memo；自定义 dignity/classifier identity 隔离 | signification、dispositor、planet_profile、analysis 模块、兼容 wrapper | `tests/unit/test_combustion_sect.py` 覆盖双轴、混合尊贵、逆行、minor aspect 排除、接纳帮手、memo | 已是目标权威函数 | `compositor` 已消费公共评估；继续防止新增第二套状态评分 |
| A2 | `planet_strength` | `domain/astrology/common.py` | 同 `assess_planet` | `(pos, neg, evidence)` | 直接调用 `assess_planet`，合并三轴 pos/neg/evidence | 无新增门控 | 旧调用兼容；个别历史模块可能仍依赖 tuple 形态 | 间接受 `assess_planet` 测试保护 | 作为过渡 facade；不再扩展新逻辑 | 名称容易误导为权威评分；阶段3后建议全量替换调用点 |
| A3 | `_house_quality_dual` | `domain/astrology/interpretation/signification.py` | `Chart`, `house` | 宫结构 `(pos, neg, pos_ev, neg_ev)` | 宫主：`essential + accidental_pos*0.4 + relational_pos*0.3`；凶轨：`essential_neg + accidental_neg*0.8 + relational_neg*1.5`；宫内星贡献 `×0.5` | 吉凶分轨不净合；按 evidence marker 拆正负证据 | `HouseSignificationEngine.interpret`, `firdaria.time_lord_character` | `tests/unit/test_house_signification.py` + career modules 的 mixed dignity/house target 回归 | 保留为 house/scenario 层消费口径，不回写 `assess_planet` | `_strength` 已按 polarity-specific axes 消费 governor 与宫结构贡献，避免整宫状态平摊 |
| A4 | `_governor_quality` / `_strength` | `domain/astrology/interpretation/signification.py` | 语义词 governors、宫结构分 | `SignificationItem.strength` 或 gated None | positive 吃 `gpos/pos`；negative 吃 `gneg/neg`；neutral 吃 `max`；`base * gov_factor * (1 + house_contrib*0.25) + flight_boost` | `_MIN_STRENGTH=0.3`；event 需 `strong_count >= requires_corroboration` | 宫位咨询、Domain conclusions、法达领主读宫 | `tests/unit/test_house_signification.py`，宫位咨询相关测试间接覆盖 | per-signification 资产必须保留 | 需要新增“同宫不同词不同强弱”的显式回归，防止退回整宫平摊 |
| A5 | `dispositor._quality` | `domain/astrology/interpretation/dispositor.py` | `Chart`, `KnowledgeBase`, lord, classifier | `jin` / `ke` | 动态相：有接纳 `+0.4`、outer/虚点压力 `+0.5`、实星硬碰 `+0.8`；`essential_neg>0` 加 `+1.0` | minor dynamic 排除；`hard>=1.5` 判 `ke` | `dispositor_interpretations` | `tests/unit/test_dispositor.py` | 阶段1纳入关系轴/scenario map 的“飞星质量”映射 | 与 `assess_planet.relational_neg` 存在重复系数；要决定保留为场景阈值还是合并为统一关系轴 |
| A6 | `planet_profile` 相位/帮手判断 | `domain/astrology/interpretation/planet_profile.py` | `Chart`, `KnowledgeBase`, planet | `PlanetProfile`：尊贵标签、supporters、underminers、掌宫 | dignity score 从 `assessment.essential_pos/neg ÷0.35` 映射；supporters=和谐/有接纳；underminers=主动态相，接纳=磨合，outer=外部压力 | 排除 semisquare/sesquiquadrate/quincunx；混合本质尊贵优先暴露受限 | 全星档案、主题抓取、前端/LLM 转述素材 | `tests/unit/test_planet_profile.py` | 保留为解释素材层；不作为评分权威 | `dignity_score` 是旧字段兼容映射，不能重新扩散成 net score |
| A7 | `compositor._assess_planet` | `domain/astrology/interpretation/compositor.py` | `Chart`, planet | 公共 `PlanetAssessment` | 直接调用 `assess_planet(chart, kb, planet, dignity, classifier)`；轨A/B 只读 essential/accidental/relational 三轴 | 轨强弱仍由 compositor 场景阈值 `_verdict_axes` 判读 | compositor 合成解释 | `tests/unit/test_domain_compositor.py` + `tests/unit/test_combustion_sect.py` 已回归 | 已完成阶段1首要迁移；局部 R9 评分与 helpers 已删除 | 需要继续防止后续重新引入第二套状态评分 |
| A8 | analysis scalar adapters | `domain/analysis/career_strength.py`, `finance.py`, `opportunity.py`, `risk.py` | `Chart`, topic params, execution `_enrichment` | 领域事实/分数/标签；阶段2 首轮已合并 `ConsultCallPlan` 承载者（`focus_planets`/`focus_house_lords`/`focus_houses`） | 已消费 `assess_planet`；`finance.py` / `opportunity.py` 的 `_dignity_total` 重算 helper 已删除，展示用 `raw_score` 由本质轴反推；`focus_planets_from_enrichment` 只扩展本轮扫描目标，不改核心二/八宫或 MC 逻辑 | 领域内 threshold gates，如 strong/weak/negative polarity；无 enrichment 时保持旧默认目标 | Strategy/Planner 执行模块；runtime 已把 `ConsultCallPlan` carriers 注入每个 step params | `tests/unit/test_career_modules.py`, `tests/unit/test_runtime_call_plan.py` | 保留为领域 scenario map；定位层承载者只作为动态目标输入，不让 Application 计算占星 | 领域阈值仍可读 essential_pos/neg，但不得重新调用 `DignityEngine.compute` 生成第二套状态分；后续继续清 governors 前需确认 signification per-word 调制替代 |

---

## 5. 必须保留的旧资产

这些不是“旧代码垃圾”，阶段1只能抽离合并，不能直接丢：

| 资产 | 当前来源 | 迁移要求 | 验证方式 |
|---|---|---|---|
| 吉凶两论，正负分开累积、不直接抵消 | `PlanetAssessment` 三轴；`_house_quality_dual`; signification polarity tracks | 保留为 axes，不退回单一极性轴 | `test_assess_planet_two_axes_separate`, mixed dignity tests |
| 混合尊贵可见 | `assess_planet.essential_pos/neg`; `planet_profile._dignity_label_from_assessment` | 输出允许“有支撑但受限/吉凶并见”，不净值抹平 | `test_assess_planet_keeps_mixed_dignity_components_visible`, `test_planet_profile.py` |
| per-signification 调制 | `HouseSignificationEngine._governor_quality/_strength` | 每个语义词单独按 governors 算强弱，不按整宫平摊 | 新增/保留 3宫表达 vs 手足差异断言 |
| 飞宫增强 | `effective_house`, `_flight_boost`, `ConnectionClassifier.classify(... flight)` | 作为结构/兑现路径证据保留 | `strong_count` / house signification / dispositors 回归 |
| gated/event 门控 | `SignificationItem.gated`, `strong_count`, `requires_corroboration` | 强事件词仍需 strong connection 才出事件性判断 | gated 语义测试；宫位深挖不应倾倒事件词 |
| 接纳三档 | `ConnectionClassifier.is_received`, `dispositor._quality`, `planet_profile._aspect_partners`, `assess_planet` relational axis | 统一为“有接纳=磨合 / outer=外部压力 / 无接纳实星=硬碰” | aspect reception tests、dispositor/planet profile tests |
| 世代修正 | `kb.affliction_quality.outer`, reception engine 排除三王/虚点 | 天海冥/虚点不作为传统硬克同权处理 | outer pressure 回归；`test_reception_excludes_outer_planets` |
| 次要相位排除 | `assess_planet`, `dispositor._quality`, `planet_profile._aspect_partners` | 半刑/八分/梅花口径统一；状态评分只吃主相位 | `test_assess_planet_excludes_minor_aspects` |
| 接纳/互溶快照 | `Chart.receptions`, `Chart.acceptances`, `ConnectionClassifier._receptions/_acceptances` | 出生盘固化；旧图缺字段才现场补算 | `test_reception_snapshots_roundtrip`, `test_helpers_of_prefers_cached_reception_snapshots` |
| 帮手星链 | `ConnectionClassifier.helpers_of`, `ally_timeline`, `Timing._helper_targets` | 作为“有伤但有托住”的结构，不替代本质弱项 | `test_ally_timeline_public_method_is_auditable`, timing helper tests |

---

## 6. 阶段1口径冲突待确认

| 冲突点 | 现有分歧 | 建议口径 | 需要确认 |
|---|---|---|---|
| 尊贵权重 | `assess_planet` 用 `score*0.35`；旧字段通过 `/0.35` 还原；analysis 模块的 `_dignity_total` 重算 helper 已删除 | 唯一 dignity 轴保留原始正负分；领域模块只读 axis，不重算 dignity | 已完成 finance/opportunity 清理；后续禁止新增 `_dignity_total` |
| 吉凶星系数 | `assess_planet` sect 调制；合成器 R9 有本地 `_benefic_malefic_scale` | 只保留 `assess_planet` 的 sect 调制；场景层不得重写 | 合成器迁移前后快照对比 |
| 刑冲惩罚 | `assess_planet` relational、`dispositor._quality` hard、`planet_profile` underminers 各自映射 | 行星状态只在 relational 轴算；飞星/档案只做标签或 scenario threshold | 保留 `dispositor._quality` 的 `1.5` 作为场景阈值，还是改为读 relational_neg |
| 次要相位 | `assess_planet/dispositor/planet_profile` 已排除；ReceptionEngine active defaults/YAML 已移除 quincunx | 状态评分、飞星受克、档案破坏者、接纳激活均排除 minor dynamic；梅花/半刑/八分等只保留描述性/次要相位 | 阶段1已收敛：接纳只由 conjunction/opposition/trine/square/sextile 激活 |
| 世代星 | 三王星可作关联/外部压力，但不掌传统宫、不参与传统接纳 | 三王星不掌宫、不传统尊贵、不硬克同权；作为 associative influence | affliction_quality YAML 与所有调用点一致化 |
| 净值化 | `planet_strength` tuple 与部分旧字段仍可能诱导 `pos-neg` | 保留双轴/三轴，最后由 scenario map 判读 | 禁止新增 `net_score`；现有 `dignity_score` 标记为兼容展示字段 |
| 帮手星深度 | 当前 `helpers_of/ally_timeline` 是直接互溶/接纳；v3 目标提到最多2跳 | 阶段1先统一直接帮手；2跳等 scenario map 稳定后再加 | 是否真的需要2跳，避免解释过度扩散 |
| 证据文案拆轨 | `_polarity_evidence` 靠中文 marker 拆正负 | 短期保留；长期考虑 evidence typed tags | marker 漏判会导致证据错挂正/负轨 |

---

## 7. 时机链盘点表

| 项 | 当前实现 | 问题 | v3目标 | 迁移阶段 | 风险 |
|---|---|---|---|---|---|
| 年主星/profections | 当前 `domain/analysis/timing.py` 未见 active `_year_lord`; `Timing` 描述和 payload 均以 `firdaria` 为 authority；`shared.enums.ChartType.ANNUAL_PROFECTION` 已删除；活跃 timing/consult/lunar/product 文档已改为法达权威口径 | 仅历史盘点中保留删除背景，避免误认为活跃技法 | 保持删除，不参与结论 | ✅ 阶段5已收口 | 若历史数据曾序列化旧 enum，需在导入层另做兼容迁移 |
| 法达大限 | `compute_firdaria` 以出生 UTC + sect + reference + method 计算 major lord；`Timing.analyze` 以 major lord 作为 target | 夜生交点位置存在传统差异，必须显式 preset | 保留为章节主轴；产品默认夜生火星后接北交/南交，`nodes_at_end` 仅作兼容口径 | 已落地/阶段5收口 | `_FIRDARIA_YEARS` 与 `compute_firdaria` 注释均已核对为 75 年循环；“100 年”仅为展示边界，不是计算上限 |
| 法达子限 | `FirdariaPeriod.sub_lord`; 非节点大限按 7 段切子限；节点大限整段读作北交/南交主题 | 浮点边界已有兜底；节点大限不能虚构 7 段行星小运 | 保留为窗口副主轴；节点大限出口 `sub_lord == major_lord` 且覆盖整段 | 已落地/阶段5收口 | 子限顺序与节点处理差异需在 docs 明示采用口径 |
| 行运触发点 | `Timing._month_score` 扫描候选月份；`TimingStack` 输出 6个月窗口 | 行运不能独立成论 | 只作为候选窗口内触发点，打到 targets/scoring_targets | 已落地/阶段5收口 | 若 response 层措辞过强，会像“行运断事” |
| 领域征象星 targets | `_timing_targets(chart, major, sub, enrichment)` 合并 major/sub、`focus_planets`、`focus_house_lords`、`focus_houses` | 依赖上游 enrichment 准确输出承载者 | 按领域承载者 + 宫主星 + 帮手星 | 已落地/阶段4-5强化 | 缺 enrichment 时只能法达主轴，问题相关性下降 |
| 帮手星 targets | `_helper_targets` 通过 `ConnectionClassifier.ally_timeline` 找接纳/互溶帮手；helper 不混进 direct target | 帮手是触发观察对象，不应盖过本体 | scoring_targets = direct targets ∪ helpers，payload 分开展示 | 已落地 | 多帮手时解释要避免“帮手=必然解决” |
| TimingStack | `build_timing_stack` 合成 firdaria、solar/lunar return、secondary/tertiary moon、transits；已接收 enrichment，把问题征象星/宫主星并入 direct targets，把接纳/互溶帮手星并入 scoring targets | 栈层多，权威需明确 | `timing_authority=firdaria`; 返回盘/推运是背景层；行运只作触发窗口 | ✅ 阶段5已收口 | response 层仍需持续避免把返回盘/推运说成第二权威 |

---

## 8. 接纳链盘点表

| 能力 | 当前状态 | 数据来源 | 是否进入结论 | v3动作 |
|---|---|---|---|---|
| mutual reception | 已实现；双向正面尊严，无需相位；强度 `4.0` | `ReceptionEngine.detect`; `Chart.receptions`; `ConnectionClassifier._receptions` 优先读快照 | 是：`classify`、`helpers_of/ally_timeline`、`assess_planet` relational helper、Timing helper targets | 保留并统一 classify；确保缓存快照始终随 natal chart 落库 |
| reception by dignity | 已实现正面尊严集：domicile/exaltation/triplicity/term/face；triplicity 支持 `all/sect` | `knowledge/reception.py`, `dignity.yaml/reception.yaml` | 是：作为 mutual/acceptance 判断基础 | 保留；文档说明只使用正面尊严，不把 detriment/fall 当接纳 |
| aspect reception / acceptance | 已实现；单向尊严 + active major aspect 才是 acceptance；互溶不重复进入 acceptance；quincunx/minor aspect 不激活接纳 | `ReceptionEngine.detect_acceptance`; `Chart.acceptances` | 是：`is_received` 影响刑冲“磨合/硬碰”；`ally_timeline` 暴露 helper | 保留；阶段1已固定 active aspect 口径 |
| flight/dispositor bridge | 已实现 `effective_house`; `classify` 的 `flight` 强度 `2.0`; `dispositor_interpretations` 使用飞入宫文案 | house cusps + planet positions + `dispositor_rules.yaml` | 是：signification connection evidence、dispositor readings | 保留为承载者/兑现路径，不等同接纳帮手 |
| same-house/sign / cohabit | 已实现；强度 `1.0` | `ConnectionClassifier.classify` | 弱证据；不触发 strong event gate | 保留为辅助连接 |
| latent reception | 已实现；单向尊严无激活相位，强度 `0.5` | `ConnectionClassifier._latent` | 弱证据；不算 strong、不进 `helpers_of` | 保留为潜在解释，不进入核心 helper 链 |
| helper/ally chain | 已实现直接帮手链：mutual `4.0`、acceptance `3.0`；按强度排序，输出 `AllyFact` | `ConnectionClassifier.ally_timeline` | 是：`assess_planet`, `Timing._helper_targets`, 产品层“有伤但有托住” | 阶段1先统一直接链；最多2跳作为后续增强，不阻塞唯一评分 |
| cached snapshots | 已实现；chart codec roundtrip；旧 chart 缺字段时现场补算 | `Chart.receptions`, `Chart.acceptances`, repository encrypted chart cache | 是；多个模块优先读快照 | 保留；避免每次解释重算接纳导致漂移 |

---

## 9. 静态缓存盘点表

| 调用点 | 当前行为 | 是否重复 compute | v3目标 | 迁移风险 |
|---|---|---|---|---|
| 注册/建档 | `Person.chart_cache` 字段已存在；仓库可加密保存 chart_cache；但创建 Person 时不强制预热 natal cache | 首次咨询/接口仍会懒计算一次 | 可后续在建档/首次出生数据确认时预热；短期懒迁移可接受 | 注册链路增加排盘可能影响建档速度；出生数据修改需清缓存 |
| `NatalChartCache` | `application/chart_cache.py` 是唯一读写入口；key=`natal:v1:{house_system}:{zodiac}`；校验 person_id/house_system/zodiac；有效旧 `natal:{house_system}` 只懒迁移到新 key，损坏或黄道错配则重算覆盖当前 key | 同一 house_system+zodiac 命中后不重复 compute | 保持为 ChartProvider 权威入口 | 未来算法版本变化继续 bump schema version；出生数据修改需清缓存 |
| runtime consult | `GardenSpiritAgent` 有 `_chart_provider`; API 注入 `chart_cache.get_or_compute`; 宫位确认、宫位咨询、常规 plan 都走 provider | 生产路径不重复 compute；同一轮多分支可能各取一次 provider 但会命中缓存 | 保持 Application 注入，Domain 不知道缓存 | 测试直接实例化 agent 时默认仍是 calculator compute，需要明确是测试/standalone 行为 |
| planner/executor | `planner.create_plan(... chart=None)` 仍有 fallback `self._calculator.compute(person)`；runtime 已传入 chart | fallback 下会重复 compute | 保留 fallback 供测试/直接调用；生产必须传 chart | 阶段2可把 fallback 标注 deprecated 或改为显式 ChartProvider |
| API endpoints | `application/api/main.py` 创建 `chart_cache` 并挂 `app.state.chart_cache`; endpoint 有 `chart_cache.get_or_compute(person)` | 已按缓存入口读 | API 层统一走 provider | 需继续 grep 新 endpoint，防止直接 `NatalChartCalculator().compute` 回潮 |
| daily/letter/learning | `LetterService` / `LearningService` 构造时传 `chart_provider=chart_cache.get_or_compute` | 已走缓存 | 保持服务层注入 provider | 后续新增 service 要复制此接线模式 |
| repository storage | `chart_cache_encrypted` 落库；明文不含 `natal:v1:P:tropical`/`planets`/person id | 无重复 compute 问题 | 出生派生数据加密静态落库 | 密钥丢失即不可解；已有 `.env.example` 警告，继续保留备份/轮换流程 |

---

## 10. 删除/残留清单

| 残留 | 当前位置 | 处理建议 | 阶段 |
|---|---|---|---|
| 年主星/profection enum | `shared/enums.py` 原 `ChartType.ANNUAL_PROFECTION` | 已删除；保持 API/序列化不再声明年度小限为活跃图型 | ✅ 阶段5已完成 |
| 旧 timing docs | `docs/astrology_timing.md`, `docs/astrology_lunar_return.md`, `docs/consult_method.md`, `docs/product_report_uiux.md` | 已统一为“法达 major/sub 为权威，行运扫问题 targets + helpers”；历史计划文档仅保留删除背景 | ✅ 阶段5已完成 |
| `compute_firdaria` 注释 | `domain/timeline/firdaria.py` 注释已为“75 年循环/75 年后循环重来” | 无需改动；保持 75 年循环口径 | ✅ 已核对 |
| `compositor` 迁移记录 | 原 `_assess_planet_r9` / `_helpers_of_r9` 已删除，现通过公共 `_assess_planet` wrapper 消费 `assess_planet` | 保留迁移记录；禁止重新引入局部状态评分 | 阶段1已完成 |
| signification docstring | `_strength` 已描述为 polarity-specific axes / 吉凶两轨调制 | 保持该口径，避免后续回退为整宫状态平摊 | ✅ 阶段1小修 |
| `planet_strength` 命名 | 兼容 wrapper 名称像权威函数 | 全调用替换后删除或改名为 `legacy_planet_strength_tuple` | 阶段3 |
| analysis dignity helper | `finance.py`, `opportunity.py` 原 `_dignity_total` 已删除；`raw_score` 由 `assess_planet` 本质轴反推 | 保留领域阈值，禁止重算行星本质状态 | 阶段1已完成 |

---

## 11. 测试覆盖索引

| 能力 | 已有测试 |
|---|---|
| `assess_planet` 双轴/混合尊贵/逆行/minor aspect/接纳/memo | `tests/unit/test_combustion_sect.py` |
| ReceptionEngine mutual/acceptance/snapshot/weak dignity/outer 排除 | `tests/unit/test_reception_engine.py`, `tests/unit/test_combustion_sect.py` |
| helper/ally 可审计链 | `tests/unit/test_combustion_sect.py` 的 helpers/ally timeline 回归 |
| Timing 法达 authority、question targets、focus houses、helper targets | `tests/unit/test_career_modules.py` |
| Firdaria major/sub | `tests/unit/test_firdaria.py` |
| chart cache 加密、house system key、损坏恢复 | `tests/unit/test_storage.py` |
| house signification / dispositor / planet profile 消费 `assess_planet` | `tests/unit/test_house_signification.py`, `tests/unit/test_dispositor.py`, `tests/unit/test_planet_profile.py` |
| API/runtime chart provider | `tests/unit/test_runtime_call_plan.py`, `tests/unit/test_api.py` |

---

## 12. 阶段0结论

- **迁移完成**：合成器局部状态评分与局部 helper 链已迁入公共 `assess_planet` / `ConnectionClassifier` 消费链，合成器不再保留第二套状态评分。
- **统一口径**：刑冲接纳三档、minor aspect、outer pressure、dignity 权重、净值字段兼容映射，需要阶段1定成唯一规则。
- **已经落地**：`assess_planet`、接纳/互溶快照、`ally_timeline`、法达 major/sub、Timing targets/helpers、`NatalChartCache`。
- **暂不迁移**：TimingStack 中 solar/lunar return、progressed moon 可继续作为背景层；不要与法达 authority 抢主轴。
- **删除残留**：年主星/profection 的 active code 与活跃方法文档已退场；当前仅在历史计划/盘点说明与负向测试断言中保留删除背景。
- **阶段6回归**：2026-08-16 已跑全量 `python -m pytest -q`，841 passed；阶段5时机链改动未引入回归失败。
- **新增/保留测试建议**：合成器迁移快照、per-signification 差异词测试、禁止新增直接 `NatalChartCalculator().compute` 的接线测试。

---

## 13. 建议阶段1执行顺序

1. ✅ 已完成：迁移合成器局部状态评分到公共 `assess_planet`，删除局部 helper 链。
2. ✅ 已完成：修正 signification/compositor/firdaria stale 注释，不改变行为。
3. ✅ 已完成：扫描并分类 analysis 模块 `_dignity_total`；领域阈值保留，重复状态评分已删除。
4. ✅ 已完成：固化 quincunx/minor aspect 与 outer pressure 文档口径。
5. 跑 `pytest tests/unit/test_combustion_sect.py tests/unit/test_house_signification.py tests/unit/test_dispositor.py tests/unit/test_planet_profile.py tests/unit/test_career_modules.py tests/unit/test_storage.py` 做阶段1前基线。
