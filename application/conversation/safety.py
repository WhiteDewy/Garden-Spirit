"""Safety 模块 —— 免责声明 + 情绪危机检测。

PRD §9：
- 免责声明：占星不构成医疗/法律/财务建议
- 情绪危机检测：识别自伤/抑郁信号 → 停止占星式回答，给出专业求助引导
- 未成年人保护：涉及感情的深度内容需适龄门槛

原则三：本模块**纯确定性**（关键词检测），不依赖 LLM。
Application 层模块：不涉及占星计算，只做输入安全判定。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from foundation.logger import get_logger

logger = get_logger("application.conversation.safety")


# ---------------------------------------------------------------------------
# 免责声明
# ---------------------------------------------------------------------------

_DISCLAIMER = (
    "\n\n---\n"
    "* 占星仅供自我探索参考，不构成医疗、法律或财务建议。"
    "重要决策请结合现实情况，必要时咨询专业人士。"
)


def disclaimer_text() -> str:
    """标准免责声明，追加到每条回答末尾。"""
    return _DISCLAIMER


# ---------------------------------------------------------------------------
# 危机检测（纯关键词，无 LLM）
# ---------------------------------------------------------------------------

#: BLOCKED 级——自伤/自杀信号，命中即阻断占星回答
_CRISIS_PATTERNS = (
    "自杀",
    "自残",
    "割腕",
    "跳楼",
    "安眠药",
    "上吊",
    "烧炭",
    "不想活",
    "想死",
    "活不下去",
    "结束生命",
    "结束自己",
    "活着没意思",
    "活着有什么意义",
    "一了百了",
    "了结自己",
    "死了算了",
    "撑不住",
    "撑不下去",
    "扛不住",
    "抗不下去",
)

#: CAUTION 级——情绪低落信号。单个命中暂不阻断，仅记日志（v1 预留扩展）。
_CAUTION_PATTERNS = (
    "抑郁",
    "绝望",
    "没希望",
    "崩溃",
    "走不出来",
    "没有希望",
)


@dataclass(frozen=True)
class SafetyResult:
    """安全检测结果。"""

    level: str        # "safe" | "caution" | "blocked"
    message: str = ""  # blocked/caution 时返回的响应文本


_CRISIS_RESPONSE = (
    "我听到你的痛苦了。但这不是占星能回答的问题。"
    "如果你现在很不好，请立即拨打——"
    "全国心理援助热线：400-161-9995（24 小时免费），"
    "或拨打当地急救电话。你不需要一个人扛。"
)


def check_safety(message: str) -> SafetyResult:
    """纯关键词检测用户消息。

    - 命中自伤/自杀信号 → blocked（返回危机求助话术，阻断占星）
    - 命中情绪低落信号 → caution（记日志，v1 不阻断）
    - 否则 → safe
    """
    if not message:
        return SafetyResult(level="safe")

    for keyword in _CRISIS_PATTERNS:
        if keyword in message:
            logger.warning("safety: 检测到自伤信号「%s」", keyword)
            return SafetyResult(level="blocked", message=_CRISIS_RESPONSE + _DISCLAIMER)

    for keyword in _CAUTION_PATTERNS:
        if keyword in message:
            logger.info("safety: 检测到情绪低落信号「%s」（caution，不阻断）", keyword)
            return SafetyResult(level="caution")

    return SafetyResult(level="safe")


# ---------------------------------------------------------------------------
# 兼容 PRD 命名的 alias（v1 只做关键词检测，未成年人保护等 API 层再补）
# ---------------------------------------------------------------------------
__all__ = [
    "SafetyResult",
    "check_safety",
    "disclaimer_text",
    "_DISCLAIMER",
]
