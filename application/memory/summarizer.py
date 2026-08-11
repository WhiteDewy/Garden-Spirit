"""MemorySummarizer —— 把一段对话压缩成"记忆 + 画像更新"。

LLM 路径：读对话转写，输出结构化 JSON（summary + 领域理解 + 关键日期
+ 星象观察 + 沉淀判断）。这些 JSON 结构直接对应 ChartProfile 的字段。

降级路径（无 LLM / 调用失败）：取最后一条用户消息作"上次聊到的话题"
摘要，不 dump 转写流水账（否则会以「用户:/星灵:」的丑样子进回访开场）。
不产出结构化更新——画像是纯增量，宁可少记不可瞎记（原则三：LLM 不可用时服务不断）。

LLM 永远只做"摘要 + 归类"，不产星象权重——画像里的置信度来自
Conclusion（Domain），不来自 LLM。
"""

from __future__ import annotations

from foundation.llm.client import LLMClient
from foundation.logger import get_logger
from shared.models import Conversation

logger = get_logger("application.memory.summarizer")

#: 转写窗口：最多喂给 LLM 的轮数（截头保尾，保留最近上下文）
_MAX_TURNS = 12

#: LLM 返回结构模板（对应 ChartProfile 字段）
_SYSTEM_PROMPT = """你是星灵花园的记忆管家。读一段用户与占星师的对话，输出结构化 JSON。

只输出 JSON，不要任何解释。结构如下：
{
  "summary": "一句朋友式的回访回忆（站在星灵立场转述用户上次在聊什么、什么感受，如'《九门》那部剧，你说看的时候很平静'；不要以'上次/你上次'开头，不要出现'用户：''星灵：'标签，不要写成流水账，2 句以内）",
  "domain_summary": "关于该领域的一句话长期理解（人话，不堆术语）",
  "key_dates": [{"label": "用户提到的重要日期/事件", "date": "YYYY-MM-DD"}],
  "lord_states": {"moon_in_7": "对该星象的一句观察"},
  "verified_findings": ["一句可复用的占星判断"]
}

要求：
- summary 客观转述，不编造对话里没有的内容。
- lord_states 的 key 用 snake_case，如 saturn_in_9、moon_in_7。
- 没有的内容就给空数组/空对象，不要虚构。
"""


class MemorySummarizer:
    """对话 → (摘要, 结构化更新 dict)。"""

    def __init__(self, llm_client: LLMClient | None = None):
        self._llm = llm_client

    def summarize(self, conversation: Conversation, domain: str = "") -> tuple[str, dict]:
        """返回 (summary, structured_updates)。

        structured_updates 为空 dict 表示"无结构化更新"（降级路径）。
        调用方只做增量合并，因此空 dict 是安全的默认值。
        """
        turns = conversation.turns
        if not turns:
            return "", {}

        if self._llm is not None and self._llm.available:
            try:
                return self._llm_summarize(turns, domain)
            except Exception as exc:  # noqa: BLE001 - 降级不阻断
                logger.warning("LLM 摘要失败，降级为规则摘要: %s", exc)

        return self._fallback_summarize(turns)

    # ------------------------------------------------------------------

    def _llm_summarize(self, turns, domain: str) -> tuple[str, dict]:
        transcript = self._build_transcript(turns)
        prompt = f"对话领域：{domain or '未指定'}\n\n对话转写：\n{transcript}"
        raw = self._llm.complete(prompt=prompt, system=_SYSTEM_PROMPT, temperature=0.2)
        data = LLMClient._parse_slots_json(raw)
        if not data:
            return self._fallback_summarize(turns)
        summary = str(data.get("summary", "")) or self._fallback_summarize(turns)[0]
        return summary, data

    def _fallback_summarize(self, turns) -> tuple[str, dict]:
        """降级摘要：一句"上次聊到的话题"，不 dump 转写流水账。

        旧实现把最近几轮拼成「用户:/星灵:」转写——会原样进"继续昨天"
        开场（用户看到的是一整段对话）。这里只取最后一条用户消息作话题，
        宁短而自然，不虚构。
        """
        for t in reversed(turns[-_MAX_TURNS:]):
            user_msg = (t.user_message or "").strip().replace("\n", " ")
            if user_msg:
                return user_msg[:120], {}
        return "", {}

    @staticmethod
    def _build_transcript(turns) -> str:
        lines: list[str] = []
        for t in turns[-_MAX_TURNS:]:
            lines.append(f"用户: {t.user_message}")
            lines.append(f"星灵: {t.assistant_response}")
        return "\n".join(lines)


__all__ = ["MemorySummarizer"]
