"""LLM 客户端 —— 统一抽象，只透传不做占星逻辑。

支持 openai 兼容协议（OpenAI / 兼容网关 / Anthropic 的 openai 兼容端点 / Gemini 的 openai 兼容端点）。
LLM 永远只做两件事：意图槽抽取 + 结论转述（原则三防火墙）。

- 无占星逻辑：只把 messages 发给 provider，把返回文本取回。
- 无状态：每次调用独立。
- provider 差异只体现在 base_url / model 命名上，协议统一为 /chat/completions。
"""

from __future__ import annotations

import json
from typing import Any

from foundation.config import LLMConfig
from foundation.logger import get_logger

logger = get_logger("foundation.llm")

try:
    import requests  # 可选依赖：未安装时 LLM 不可用，但系统其余部分照常工作

    _HAS_REQUESTS = True
except ImportError:  # pragma: no cover
    requests = None  # type: ignore
    _HAS_REQUESTS = False

#: provider → openai 兼容 base_url（可被 LLMConfig.base_url 覆盖）
_PROVIDER_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
}


class LLMError(RuntimeError):
    """LLM 调用失败。"""


class LLMClient:
    """OpenAI 兼容的 LLM 客户端（同步为主，异步留接口）。"""

    def __init__(self, config: LLMConfig | None = None):
        self._config = config or LLMConfig()
        self._base_url = (
            self._config.base_url
            if getattr(self._config, "base_url", "")
            else _PROVIDER_BASE_URLS.get(
                self._config.provider, _PROVIDER_BASE_URLS["openai"]
            )
        )

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def chat(self, messages: list[dict], **kwargs: Any) -> str:
        """同步对话：messages 为 [{role, content}, ...]，返回助手文本。"""
        if not _HAS_REQUESTS:
            raise LLMError("未安装 requests——无法调用 LLM")
        if not self._config.api_key:
            raise LLMError("未配置 LLM api_key（LLMConfig.api_key）")

        url = f"{self._base_url.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            "temperature": kwargs.pop("temperature", self._config.temperature),
            "max_tokens": kwargs.pop("max_tokens", self._config.max_tokens),
        }
        payload.update(kwargs)

        try:
            resp = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {self._config.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._config.request_timeout,
            )
        except Exception as exc:  # pragma: no cover - 网络层
            logger.error("LLM 请求失败: %s", exc)
            raise LLMError(f"LLM 请求失败: {exc}") from exc

        if resp.status_code != 200:
            logger.error("LLM 返回 %s: %s", resp.status_code, resp.text[:300])
            raise LLMError(f"LLM 返回 {resp.status_code}: {resp.text[:300]}")

        try:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, json.JSONDecodeError) as exc:  # pragma: no cover
            raise LLMError(f"LLM 响应解析失败: {resp.text[:300]}") from exc

    # ------------------------------------------------------------------
    # 便捷
    # ------------------------------------------------------------------

    def complete(self, prompt: str, system: str | None = None, **kwargs: Any) -> str:
        """单轮补全：system（可选）+ 一条 user prompt。"""
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, **kwargs)

    # ------------------------------------------------------------------
    # 意图槽抽取（原则三：LLM 只抽槽，不判领域）
    # ------------------------------------------------------------------

    def extract_slots(self, system_prompt: str, message: str) -> dict:
        """调用 LLM 从自然语言中抽取结构化槽位。

        system_prompt: 抽取指令（如"返回 JSON：{person, timeframe, ...}"）。
        message: 用户原始文本。
        返回 dict（槽名 → 值）；失败返回 {}，让规则兜底。
        """
        try:
            raw = self.complete(prompt=message, system=system_prompt, temperature=0.0)
            return self._parse_slots_json(raw)
        except Exception:
            logger.warning("LLM 槽位抽取失败，退化为空槽", exc_info=True)
            return {}

    @staticmethod
    def _parse_slots_json(raw: str) -> dict:
        """从 LLM 返回文本中提取 JSON 槽位。

        容忍 markdown 代码块包裹、前后空白、以及顶层 key 缺失。
        """
        import re

        raw = raw.strip()
        # 去掉 markdown 代码块 ```json ... ```
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if m:
            raw = m.group(1)
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return {k: v for k, v in data.items() if v is not None}
            return {}
        except json.JSONDecodeError:
            # 试图从文本中抓第一个 {...}
            m2 = re.search(r"\{.*?\}", raw, re.DOTALL)
            if m2:
                try:
                    data = json.loads(m2.group(0))
                    if isinstance(data, dict):
                        return {k: v for k, v in data.items() if v is not None}
                except json.JSONDecodeError:
                    pass
            return {}

    @property
    def available(self) -> bool:
        """LLM 是否可用（装了 requests 且有 key）。"""
        return _HAS_REQUESTS and bool(self._config.api_key)
