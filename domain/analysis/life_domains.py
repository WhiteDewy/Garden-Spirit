"""剩余四个生活领域模块（theme_map 驱动）。

Health / Emotion / Family / Learning 本质相同：各跑一个 theme_map 配方。
配方在 knowledge/rules/theme_map.yaml 里，新增领域只需加配方。
"""

from __future__ import annotations

from domain.analysis.theme_module import ThemeModule


class Health(ThemeModule):
    name = "Health"
    theme_id = "health"


class Emotion(ThemeModule):
    name = "Emotion"
    theme_id = "emotion"


class Family(ThemeModule):
    name = "Family"
    theme_id = "family"


class Learning(ThemeModule):
    name = "Learning"
    theme_id = "learning"
