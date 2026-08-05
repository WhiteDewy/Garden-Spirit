# 🌿 Garden-Spirit

AI 占星 Agent —— 一个懂得占星、会说人话的数字星灵。

## 架构（已冻结）

```
Application（应用层：交互 / Agent / 对话）
        │   ← 不懂占星
        ▼
Reasoning（推理层：Intent → Strategy → Plan → Evidence → Conclusion）
        │   ← 不依赖 LLM
        ▼
Astrology（占星层：计算 / 知识 / 指标 / 证据）
        │
        ▼
Foundation（基础层：天文 / LLM / DB / 缓存）
```

`shared/` 是横切层（非第五层）；`domain/` 是业务层容器（装 Reasoning + Astrology）。

### 三条原则

1. **Application 不懂占星** —— 不收算宫位、相位、行星。
2. **Domain 不依赖 LLM** —— 没有 GPT 也能给出完整结论。
3. **LLM 永不推理** —— LLM 只理解自然语言、提问、解释、共情、组织语言；权重、吉凶、适合与否全部来自 Domain。

### 核心链路

```
User → Master Agent → Intent Parser → Intent → Strategy
     → Execution Plan → Analysis Modules → Astrology Kernel
     → Facts → Evidence → Reasoner → Conclusion → (Persona + LLM) → Answer
```

## 关键决策（v1）

| 决策 | 选择 |
|------|------|
| 技术栈 | Python + pyswisseph |
| 合盘 | 基础合盘（相位 + 落宫 + 互溶） |
| 事件问题 | 本命 + 行运时间窗口（不做卜卦） |
| 星历参数 | 回归黄道 + 象限制（Placidus） |

## 项目结构

```
application/     应用层（Agent 主循环 / 对话 / Persona / API）
domain/
  reasoning/     推理层（Intent / Strategy / Planner / Executor / Reasoner）
  analysis/      可复用分析模块（CareerStrength / Timing / Risk / ...）
  astrology/     占星内核（calculation / knowledge / indicators / evidence）
  timeline/      人生 K 线（WindowScanner / Curves）
foundation/      基础设施（astronomy / llm / database / cache / config）
shared/          横切共享模型（Chart / Facts / Intent / Evidence / ...）
docs/            设计文档
tests/           测试
app/             应用入口
```

## 快速开始

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -e ".[dev]"
pytest
```
