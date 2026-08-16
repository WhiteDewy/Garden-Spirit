"""疗愈协议（A3）—— 叙事 5 步 + 输出护栏。

把"疗愈"从人的直觉变成可审计、可测试的结构。这是产品哲学链的落点：
占星→疗愈→陪伴。协议保证：给用户看的每一份解读，都走同一条情绪弧线，
都绝不会留下"命好坏/一定离婚/必有灾"式的致命判决。

三层落地（同一协议，单源）：
1. **LLM 提示词**：build_healing_instruction() 编译进 system prompt，
   约束转述的情绪节奏（软护栏）。
2. **降级模板**：无 LLM 时，runtime 的 fallback 也按 5 步组织、保证给出路。
3. **输出后置检测**：healing_guardrail_check() 扫最终输出文本，命中致命判决词
   就补一段"给出路"收尾——这是**硬护栏**，不依赖 LLM 判断、纯确定性，
   无论 LLM 还是 Domain 翻车都能兜住。

护栏规则与占星结论无关，纯文本判定。Application 层模块。
"""

from __future__ import annotations

from foundation.logger import get_logger

logger = get_logger("application.conversation.healing")

#: 叙事 5 步弧线（顺序即情绪弧线：从接住情绪开始，落到可执行的功课结束）
HEALING_STEPS: tuple[tuple[str, str, str], ...] = (
    ("empathy", "共情", "先接住情绪、命名伤口——让用户感到被看见，而不是被分析"),
    ("natal", "本命基调", "讲这个领域的长期结构：哪颗星管它、自己强不强、谁帮谁压"),
    ("cross", "交叉判断", "打通关键结构：宫主星连接、蓄力还是发力、感情系统如何走向婚姻"),
    ("timing", "时机", "讲当前走到哪一章（法达/行运），具体到'现在''这一章''明年的节点'"),
    ("way_out", "给出路", "落在一句可执行的功课上：入庙能扛、过程差不等于结局差、抽象凶变具体注意点"),
)

#: 致命判决词——命中即判定输出越界（"星盘是判决书"式语言）。
#: 这是硬护栏：不删改内容，只追加"给出路"收尾。
GUARDRAIL_PATTERNS: tuple[str, ...] = (
    "注定",
    "命里",
    "命不好",
    "一定离婚",
    "必离婚",
    "注定单身",
    "嫁不出去",
    "娶不到",
    "没救了",
    "完蛋",
    "永远不可能",
    "这辈子不可能",
    "不可能有结果",
)

#: 出路收尾的标记串——已含则视为"已给出路"，不重复追加（幂等）。
_WAY_OUT_MARKER = "不过，这都不是判决"

WAY_OUT_CODA = (
    f"\n\n{_WAY_OUT_MARKER}。星盘上的压力是压力，不是绝路——"
    "总有能扛的星，总有能发力的章节。地图是死的，走路的是你。"
)

#: 降级模板在没有建议时兜底的通用出路
GENERIC_WAY_OUT = (
    "\n不管怎样，这条路都不是死路——先找盘上能发力、能借力的点，走一步看一步。"
)


def build_healing_instruction() -> str:
    """编译成 LLM system prompt 块：5 步弧线 + 输出护栏（软护栏）。"""
    lines = [
        "## 疗愈叙事协议（5 步节奏——不是章节标题，是你叙事的情绪弧线）",
        "从接住情绪开始，落到可执行的功课结束，按此弧线组织你的解读：",
    ]
    for i, (_sid, title, focus) in enumerate(HEALING_STEPS, 1):
        lines.append(f"{i}. {title}：{focus}")
    lines.append("")
    lines.append("## 输出护栏（绝对遵守）")
    lines.append("- 绝不给'命好坏/一定离婚/必有灾'式的判决——星盘是地图，不是判决书。")
    lines.append("- 压力不等于垮台：凶相位给压力，但入庙能扛、过程差不等于结局差。")
    lines.append("- 永远落在一句可执行的功课上（具体动词），不说'学会平衡'式正确废话。")
    lines.append("- 看到问题必须给出路，不给绝路、不添堵。")
    from application.conversation.safety import medical_boundary_instruction

    lines.append(f"- {medical_boundary_instruction()}")
    return "\n".join(lines)


def healing_guardrail_check(text: str) -> str | None:
    """扫最终输出：命中致命判决词 → 返回需要追加的"给出路"收尾；否则 None。

    幂等：文本已含 WAY_OUT_MARKER（已给过出路）→ 直接返回 None，不重复追加。
    """
    if not text:
        return None
    if _WAY_OUT_MARKER in text:
        return None
    for kw in GUARDRAIL_PATTERNS:
        if kw in text:
            logger.warning("healing: 输出含致命判决词「%s」，追加给出路收尾", kw)
            return WAY_OUT_CODA
    return None


__all__ = [
    "HEALING_STEPS",
    "GUARDRAIL_PATTERNS",
    "WAY_OUT_CODA",
    "GENERIC_WAY_OUT",
    "build_healing_instruction",
    "healing_guardrail_check",
]
