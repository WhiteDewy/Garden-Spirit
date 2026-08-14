"""知识库加载器。

所有占星解释性规则（尊贵/互容/相位性质/宫位含义）都从 YAML 加载，
而不是硬编码在代码里。占星师调整一个权重只需改 YAML，不动代码。

知识库是单例，进程内缓存。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from foundation.logger import get_logger
from shared.enums import (
    AspectType,
    DignityState,
    Element,
    Modality,
    Planet,
    Sect,
    Sign,
)

logger = get_logger("astrology.knowledge")

_KNOWLEDGE_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlanetInfo:
    name_zh: str
    name_en: str
    gender: str | None
    sect: Sect | None
    nature: str | None
    domicile: list[Sign]
    traditional_domicile: list[Sign] | None
    exaltation: tuple[Sign, float] | None
    detriment: list[Sign]
    fall: tuple[Sign, float] | None
    orb: float
    speed_max: float
    speed_avg: float
    significations_zh: list[str]
    keywords: list[str]


@dataclass(frozen=True)
class SignInfo:
    name_zh: str
    name_en: str
    element: Element
    modality: Modality
    ruler: Planet
    traditional_ruler: Planet
    natural_house: int
    polarity: str
    keywords_zh: list[str]


@dataclass(frozen=True)
class HouseInfo:
    name_zh: str
    name_en: str
    angularity: str
    natural_sign: Sign
    natural_planet: Planet
    keywords_zh: list[str]


@dataclass(frozen=True)
class AspectInfo:
    angle: float
    orb: float
    nature: str            # HARMONIOUS / DYNAMIC / NEUTRAL
    weight_multiplier: float
    keywords_zh: list[str]
    description_zh: str


@dataclass(frozen=True)
class TermTable:
    ranges: list[float]    # 各段上界（30 度内）
    lords: list[Planet]    # 每段主星


@dataclass(frozen=True)
class FaceTable:
    ranges: list[float]
    lords: list[Planet]


@dataclass(frozen=True)
class DignityTable:
    scheme: str                              # traditional | modern
    scores: dict[DignityState, int]
    triplicity_lords: dict[Element, dict[str, Planet]]
    terms: dict[Sign, TermTable]
    faces: dict[Sign, FaceTable]


@dataclass(frozen=True)
class ReceptionTable:
    scores: dict[DignityState, int]
    one_way_multiplier: float
    allow_cross_scheme: bool
    # 互溶严格度（lenient/standard/strict）与接纳激活配置
    strictness: str = "standard"
    require_aspect: bool = True
    active_aspects: list[AspectType] = field(default_factory=list)
    # 三分主取法（all=三主都算 / sect=按昼夜取一主）
    triplicity_mode: str = "all"
    # 不参与互溶/接纳的星体（三王星世代性 + 虚点非行星）
    excluded_planets: list[Planet] = field(default_factory=list)


@dataclass
class KnowledgeBase:
    """加载后的完整知识库。"""

    planets: dict[Planet, PlanetInfo] = field(default_factory=dict)
    signs: dict[Sign, SignInfo] = field(default_factory=dict)
    houses: dict[int, HouseInfo] = field(default_factory=dict)
    aspects: dict[AspectType, AspectInfo] = field(default_factory=dict)
    dignity: DignityTable | None = None
    reception: ReceptionTable | None = None

    # 解读文法（rules/）
    planet_pairs: dict = field(default_factory=dict)          # "mars_moon" → {base, harmonious, dynamic}
    planet_in_house_rules: dict = field(default_factory=dict)  # "venus_5" → {base}
    house_lord_rules: dict = field(default_factory=dict)      # "7_1" → {base}
    theme_map: dict = field(default_factory=dict)             # theme_id → 配方
    house_significations: dict = field(default_factory=dict)  # house → 语义场条目
    time_lord_character: dict = field(default_factory=dict)   # 时间领主经验库（法达）
    affliction_quality: dict = field(default_factory=dict)    # 刑克性质经验库
    dispositor_rules: dict = field(default_factory=dict)      # 飞星论断（宫主星飞入各宫）
    planet_sign_style: dict = field(default_factory=dict)     # 行星×落座风格（单点档案）
    synastry_priority_pairs: list = field(default_factory=list)  # 合盘行星对
    synastry_partner_houses: list = field(default_factory=list)  # 合盘宫位焦点

    # 咨询模板规则（consult resolver 三层体系）
    house_derived: dict = field(default_factory=dict)            # 转宫关系表（X宫主落Y宫 → X之derived）
    planet_nature: dict = field(default_factory=dict)            # 星性规则（话题角色 + 特殊规则）
    natal_composition: dict = field(default_factory=dict)       # 本命组合规则（交叉判断 + 场景映射）
    timing_rules: dict = field(default_factory=dict)            # 推运规则（法达 × 本命 + 行运 + 窗口合成）

    # -- 便捷访问 ---------------------------------------------------------

    def planet(self, p: Planet) -> PlanetInfo:
        return self.planets[p]

    def sign(self, s: Sign) -> SignInfo:
        return self.signs[s]

    def house(self, h: int) -> HouseInfo:
        return self.houses[h]

    def aspect(self, a: AspectType) -> AspectInfo:
        return self.aspects[a]


def domain_planet_roles(planet_nature: dict | None, domain: str | None) -> tuple[list[str], list[str]]:
    """从 planet_nature.domain_signals 派生领域核心星与辅助星。

    R9 硬线：领域行星角色只以 planet_nature.domain_signals 为唯一来源；
    intent_profiles/theme_map 中的 core_planets 不能再作为独立真相源。
    """
    if not domain:
        return [], []
    planets_data = (planet_nature or {}).get("planets", {})
    core: list[str] = []
    supporting: list[str] = []
    for planet_key, planet_info in planets_data.items():
        if not isinstance(planet_info, dict):
            continue
        signals = planet_info.get("domain_signals", {}) or {}
        role = signals.get(domain, "neutral")
        if role == "core":
            core.append(str(planet_key))
        elif role == "supporting":
            supporting.append(str(planet_key))
    return core, supporting


# ---------------------------------------------------------------------------
# 加载
# ---------------------------------------------------------------------------

_SECT_ALIASES = {"diurnal": "day", "nocturnal": "night"}


def _parse_sect(raw: str | None) -> Sect | None:
    """解析 sect，兼容 diurnal/nocturnal 别名。"""
    if not raw:
        return None
    value = _SECT_ALIASES.get(raw.lower(), raw.lower())
    return Sect(value)


def _parse_planet(raw: dict) -> PlanetInfo:
    domicile = [Sign(s.lower()) for s in raw.get("domicile") or []]
    trad = [Sign(s.lower()) for s in raw.get("traditional_domicile") or []]
    ex = raw.get("exaltation") or {}
    fall = raw.get("fall") or {}
    exalt = (Sign(ex["sign"].lower()), float(ex["degree"])) if ex else None
    fall_t = (Sign(fall["sign"].lower()), float(fall["degree"])) if fall else None
    sect_raw = raw.get("sect")
    return PlanetInfo(
        name_zh=raw["name"]["zh"],
        name_en=raw["name"]["en"],
        gender=raw.get("gender"),
        sect=_parse_sect(sect_raw),
        nature=raw.get("nature"),
        domicile=domicile,
        traditional_domicile=trad if trad else None,
        exaltation=exalt,
        detriment=[Sign(s.lower()) for s in raw.get("detriment") or []],
        fall=fall_t,
        orb=float(raw.get("orb", 8.0)),
        speed_max=float(raw.get("speed_max", 1.0)),
        speed_avg=float(raw.get("speed_avg", 1.0)),
        significations_zh=list(raw.get("significations_zh") or []),
        keywords=list(raw.get("keywords") or []),
    )


def _parse_sign(raw: dict) -> SignInfo:
    return SignInfo(
        name_zh=raw["name"]["zh"],
        name_en=raw["name"]["en"],
        element=Element(raw["element"].lower()),
        modality=Modality(raw["modality"].lower()),
        ruler=Planet(raw["ruler"].lower()),
        traditional_ruler=Planet(raw["traditional_ruler"].lower()),
        natural_house=int(raw["natural_house"]),
        polarity=raw.get("polarity", "yang"),
        keywords_zh=list(raw.get("keywords_zh") or []),
    )


def _parse_house(raw: dict) -> HouseInfo:
    return HouseInfo(
        name_zh=raw["name"]["zh"],
        name_en=raw["name"]["en"],
        angularity=raw["angularity"],
        natural_sign=Sign(raw["natural_sign"].lower()),
        natural_planet=Planet(raw["natural_planet"].lower()),
        keywords_zh=list(raw.get("keywords_zh") or []),
    )


def _parse_aspect(raw: dict) -> AspectInfo:
    return AspectInfo(
        angle=float(raw["angle"]),
        orb=float(raw["orb"]),
        nature=raw["nature"],
        weight_multiplier=float(raw.get("weight_multiplier", 1.0)),
        keywords_zh=list(raw.get("keywords_zh") or []),
        description_zh=raw.get("description_zh", ""),
    )


def _parse_dignity(raw: dict) -> DignityTable:
    scores = {DignityState(k.lower()): int(v) for k, v in raw["scores"].items()}
    triplicity = {
        Element(k.lower()): {lk: Planet(lv.lower()) for lk, lv in v.items()}
        for k, v in raw["triplicity_lords"].items()
    }
    terms = {
        Sign(k.lower()): TermTable(ranges=[float(x) for x in v["ranges"]], lords=[Planet(l.lower()) for l in v["lords"]])
        for k, v in raw["terms"].items()
    }
    faces = {
        Sign(k.lower()): FaceTable(ranges=[float(x) for x in v["ranges"]], lords=[Planet(l.lower()) for l in v["lords"]])
        for k, v in raw["faces"].items()
    }
    return DignityTable(
        scheme=raw["scheme"],
        scores=scores,
        triplicity_lords=triplicity,
        terms=terms,
        faces=faces,
    )


def _parse_reception(raw: dict) -> ReceptionTable:
    mutual = raw.get("mutual_reception") or {}
    acceptance = raw.get("acceptance") or {}
    triplicity = raw.get("triplicity") or {}
    active = acceptance.get("active_aspects") or []
    return ReceptionTable(
        scores={DignityState(k.lower()): int(v) for k, v in raw["scores"].items()},
        one_way_multiplier=float(raw.get("one_way_multiplier", 0.5)),
        allow_cross_scheme=bool(raw.get("allow_cross_scheme", True)),
        strictness=str(mutual.get("strictness", "standard")),
        require_aspect=bool(acceptance.get("require_aspect", True)),
        active_aspects=[AspectType(a.lower()) for a in active],
        triplicity_mode=str(triplicity.get("mode", "all")),
        excluded_planets=[Planet(x.lower()) for x in raw.get("excluded_planets") or []],
    )


def _load_yaml(filename: str) -> dict:
    path = _KNOWLEDGE_DIR / filename
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"知识库文件格式错误: {filename}")
    return data


@lru_cache(maxsize=1)
def load_knowledge(knowledge_dir: str | None = None) -> KnowledgeBase:
    """加载完整知识库（进程内缓存，幂等）。

    Args:
        knowledge_dir: 覆盖知识库目录（主要用于测试注入）。
    """
    kb = KnowledgeBase()

    planets_raw = _load_yaml("planets.yaml")
    kb.planets = {Planet(k.lower()): _parse_planet(v) for k, v in planets_raw.items()}

    signs_raw = _load_yaml("signs.yaml")
    kb.signs = {Sign(k.lower()): _parse_sign(v) for k, v in signs_raw.items()}

    houses_raw = _load_yaml("houses.yaml")
    kb.houses = {int(k): _parse_house(v) for k, v in houses_raw.items()}

    aspects_raw = _load_yaml("aspects.yaml")
    kb.aspects = {AspectType(k.lower()): _parse_aspect(v) for k, v in aspects_raw.items()}

    kb.dignity = _parse_dignity(_load_yaml("dignity.yaml"))
    kb.reception = _parse_reception(_load_yaml("reception.yaml"))

    # 解读文法
    kb.planet_pairs = _load_yaml("rules/planet_pair.yaml")
    kb.planet_in_house_rules = _load_yaml("rules/planet_in_house.yaml")
    kb.house_lord_rules = _load_yaml("rules/house_lord.yaml")
    kb.theme_map = _load_yaml("rules/theme_map.yaml")
    kb.house_significations = _load_yaml("house_significations.yaml").get(
        "house_significations", {}
    )
    kb.time_lord_character = _load_yaml("time_lord_character.yaml")
    kb.affliction_quality = _load_yaml("affliction_quality.yaml")
    kb.dispositor_rules = _load_yaml("dispositor_rules.yaml")
    kb.planet_sign_style = _load_yaml("planet_sign_style.yaml")

    # 合盘规则
    synastry_raw = _load_yaml("rules/synastry_rules.yaml")
    kb.synastry_priority_pairs = synastry_raw.get("priority_pairs", [])
    kb.synastry_partner_houses = synastry_raw.get("partner_house_focus", [])

    # 咨询模板规则（三层体系）
    kb.house_derived = _load_yaml("house_derived.yaml").get("derived_houses", {})
    kb.planet_nature = _load_yaml("planet_nature.yaml")
    kb.natal_composition = _load_yaml("rules/natal_composition.yaml")
    kb.timing_rules = _load_yaml("rules/timing_rules.yaml")

    logger.info(
        "知识库加载完成: %d 行星, %d 星座, %d 宫位, %d 相位, %d 行星对, %d 落宫, %d 宫主规则, %d 主题, "
        "咨询模板: 转宫=%d 星性=%d 组合规则=%d 推运规则=%d",
        len(kb.planets), len(kb.signs), len(kb.houses), len(kb.aspects),
        len(kb.planet_pairs), len(kb.planet_in_house_rules),
        len(kb.house_lord_rules), len(kb.theme_map),
        len(kb.house_derived),
        len(kb.planet_nature.get("planets", {})),
        len(kb.natal_composition),
        len(kb.timing_rules),
    )
    return kb


def load_from_dir(knowledge_dir: str) -> KnowledgeBase:
    """从指定目录加载（测试用）。绕开 lru_cache。"""
    global _KNOWLEDGE_DIR
    _KNOWLEDGE_DIR = Path(knowledge_dir)
    load_knowledge.cache_clear()
    return load_knowledge()
