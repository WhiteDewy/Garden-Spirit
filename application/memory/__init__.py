"""application/memory —— 第四层记忆：跨会话沉淀。

核心是"咨询后写回"管线（产品循环的后半段）：
  咨询 → 摘要 → 更新长期画像 → 生成成长事件 → 持久化

- summarizer.py：对话 → 摘要 + 结构化更新（LLM，可降级）
- service.py：写回编排（MemoryService）
"""
