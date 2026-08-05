# Garden-Spirit 架构文档

> 本架构已冻结。修改任何层次边界需先更新本文件并通过团队评审。

## 1. 四层架构

```
Application（应用层：交互 / Agent / 对话）
        │   ← 原则一：不懂占星
        ▼
Reasoning（推理层：Intent → Strategy → Plan → Evidence → Conclusion）
        │   ← 原则二：不依赖 LLM
        ▼
Astrology（占星层：计算 / 知识 / 指标 / 证据）
        │
        ▼
Foundation（基础层：天文 / LLM / DB / 缓存）
```

**层次归属：**
- `shared/` 是横切层，非第五层。被四层共享，本身不依赖任何一层。
- `domain/` 是业务层容器，装 Reasoning（推理层）+ Astrology/Analysis/Timeline（占星层）。

## 2. 三条原则（不可变更）

### 原则一：Application 不懂占星
只负责：收消息、调 Agent、管对话、输出回答。
**绝不**计算宫位、相位、行星。

### 原则二：Domain 不依赖 LLM
只负责：推理、计算、Evidence、Conclusion。
**哪怕没有 GPT**，也能给出完整结论。

### 原则三：LLM 永不推理
LLM 只负责：理解自然语言（Intent 辅助）、提问、解释、共情、组织语言。
**不能决定**：权重、吉凶、是否适合、哪个宫位重要。全部来自 Domain。

**LLM 边界只有两个入口：**
1. `application/agent/intent_parser.py` —— 自然语言 → 原始 slots
2. `application/conversation/response.py` —— Conclusion → 人格化文本

LLM 永不接触原始 Chart 数据，永不做出解释性判断。

## 3. 核心链路

```
User → Master Agent → Intent Parser → Intent → Strategy
     → Execution Plan → Analysis Modules → Astrology Kernel
     → Facts → Evidence → Reasoner → Conclusion → (Persona + LLM) → Answer
```

## 4. 关键边界（防火墙）

### Chart 是唯一跨层模型
所有计算器产出 `Chart`。所有分析模块只消费 `FactSet`（由 Chart 派生）。
Application 层永远看不到 `Chart`。

### Fact ↔ Evidence 边界
- **Fact**（`shared/models/facts.py`）：机械事实，从 Chart 原始数值直接提取。
  无解释、无权重、无极性。回答"是什么"。
- **Evidence**（`shared/models/evidence.py`）：加权解释。回答"对这个具体问题意味着什么"。
  权重与极性**只**由 Domain 规则产生。

**越界检查规则**：`domain/astrology/calculation/` 下任何调用 `Evidence()`、使用
`EvidencePolarity` 或赋值 `Weight` 的文件 = 边界违规，代码评审必须拦截。

### Strategy YAML 是插件系统
新增一个占星技法（如 v2 的 Zodiacal Releasing）只需：
1. 加计算模块
2. 加 Fact 提取器
3. 加 Indicator 模块
4. 加 YAML strategy 把它们串起来

**不需要改任何现有代码。**

## 5. 核心数据流说明

| 数据 | 产生者 | 消费者 | 内容 |
|------|--------|--------|------|
| Person | 用户输入 | 计算器 | 出生时间/地点/时区 |
| Chart | foundation/astronomy | Fact 提取器 | 完整星盘（行星/宫位/相位/互容） |
| FactSet | Fact 提取器 | Evidence Builder | 机械事实集合 |
| EvidenceSet | Evidence Builder | Reasoner | 加权解释 + 冲突消解 |
| Intent | Intent Router | Strategy 引擎 | 领域验证后的意图 |
| Strategy | YAML 加载 | Planner | 分析步骤 DAG |
| ExecutionPlan | Planner | Executor | 可执行计划 |
| Conclusion | Reasoner | Conversation | 领域生成的结论 |

## 6. 关键决策（v1）

| 决策 | 选择 | 影响 |
|------|------|------|
| 技术栈 | Python + pyswisseph | foundation/astronomy |
| 合盘 | 基础合盘（相位+落宫+互溶） | Synastry 模块，无 Composite/Davison |
| 事件问题 | 本命+行运时间窗口 | 不做卜卦 |
| 星历参数 | 回归黄道 + 象限制（Placidus） | 全局 config 默认值 |
| 知识库 | YAML 数据驱动 | 权重可调，不硬编码 |

## 7. 目录结构

```
application/    应用层（Agent 主循环 / 对话 / Persona / API）
domain/
  reasoning/    推理层（Intent / Strategy / Planner / Executor / Reasoner）
  analysis/     可复用分析模块
  astrology/    占星内核（calculation / knowledge / indicators / evidence）
  timeline/     人生 K 线
foundation/     基础设施（astronomy / llm / database / cache / config）
shared/         横切共享模型
docs/           设计文档
tests/          测试
app/            应用入口
```
