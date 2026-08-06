"""测试全局配置：禁用外部依赖，保证确定性。

测试必须离线：
- GS_LLM_DISABLE=1     → LLMClient 不可用（chat 走规则 + 降级模板，不真调 LLM）
- GS_GEOCODE_OFFLINE=1 → geocoding 走静态表（不依赖网络与 GS_AMAP_KEY）

真实 LLM 集成路径通过注入 fake 单独覆盖（见 test_llm_materials.py），
上线验证走脚本（scripts/）或手动冒烟。
"""

import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def _offline_external_deps():
    os.environ["GS_LLM_DISABLE"] = "1"
    os.environ["GS_GEOCODE_OFFLINE"] = "1"
