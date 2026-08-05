"""证据卡（Evidence Card）—— 确定性，无 LLM。

证据卡是 LLM 转述层（P0）的前置数据结构：每条飞星读数生成一张"三板斧"卡片——
① 术语层（skeleton）：专业占星表述
② 共鸣层（resonance）：白话转译
③ 落地层（action）：怎么办/借力段

本次实现飞星（Dispositor）→ 证据卡联动。后续可扩展 signification / affliction 源。
所有文案来自 YAML（原则三），代码只做拼接不发明。
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.enums import Planet
from shared.models import Chart

from domain.astrology.interpretation.dispositor import dispositor_interpretations
from domain.astrology.knowledge.loader import KnowledgeBase


@dataclass(frozen=True)
class EvidenceCard:
    """一张证据卡：三层转述 + 怎么办借力段。

    skeleton  → LLM 不改动的"原文引用"（术语锚点）
    resonance → LLM 可换语气的"白话转译"（共鸣锚点）
    action    → LLM 可扩展的"怎么办"（行动锚点）
    """

    card_id: str
    source_type: str             # "dispositor"（后续可扩展）
    skeleton: str                # 术语层 —— "{N}宫主{X星}飞入{M}宫，得吉/受克——{标题}"
    resonance: str               # 共鸣层 —— YAML jin/ke 原文（白话表述）
    action: str                  # 落地层 —— 怎么办/借力段
    evidence: tuple[str, ...]    # 证据链
    polarity: str                # jin / ke
    from_house: int
    to_house: int
    lord: Planet

    def to_dict(self) -> dict:
        """出口：JSON 友好（供星灵 app + LLM 转述层消费）。"""
        return {
            "card_id": self.card_id,
            "source_type": self.source_type,
            "skeleton": self.skeleton,
            "resonance": self.resonance,
            "action": self.action,
            "evidence": list(self.evidence),
            "polarity": self.polarity,
            "from_house": self.from_house,
            "to_house": self.to_house,
            "lord": self.lord.value,
        }


def dispositor_cards(
    chart: Chart,
    kb: KnowledgeBase,
) -> list[EvidenceCard]:
    """飞星 → 证据卡联动：每条 DispositorReading 生成一张带借力段的证据卡。

    读取 dispositor_interpretations 的全量飞星（当前 4-12宫），
    对每条合成三层文案 + 借力建议。1-3 宫数据待补——补 YAML 后无需改代码。
    """
    readings = dispositor_interpretations(chart, kb)
    domains = (kb.time_lord_character or {}).get("house_domains", {})

    cards: list[EvidenceCard] = []
    for r in readings:
        lord_zh = kb.planet(r.lord).name_zh
        from_label = _house_label(domains, r.from_house)
        to_label = _house_label(domains, r.to_house)
        quality_zh = "得吉" if r.quality == "jin" else "受克"

        # ① 术语层：专业占星表述（LLM 不改动，直接引用）
        # title 是占星师速记标签（如"4之8，登神梯亦是心魔关"），
        # 不输出给客户——保留在 evidence 里做审计。
        skeleton = f"{r.from_house}宫主{lord_zh}飞入{r.to_house}宫，{quality_zh}"

        # ② 共鸣层：YAML jin/ke 原文（白话表述，LLM 可换语气不换内容）
        resonance = r.text

        # ③ 落地层：怎么办 / 借力段
        action = _build_action(r.quality, from_label, to_label, r.text)

        # 证据链
        evidence_parts = [
            f"{r.from_house}宫主{lord_zh}飞入{r.to_house}宫",
            f"飞星状态：{quality_zh}",
        ]
        if r.title:
            evidence_parts.append(f"主题：{r.title}")

        cards.append(EvidenceCard(
            card_id=f"dispositor:{r.from_house}→{r.to_house}:{r.lord.value}",
            source_type="dispositor",
            skeleton=skeleton,
            resonance=resonance,
            action=action,
            evidence=tuple(evidence_parts),
            polarity=r.quality,
            from_house=r.from_house,
            to_house=r.to_house,
            lord=r.lord,
        ))

    return cards


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------

def _house_label(domains: dict, house: int) -> str:
    """从 time_lord_character.yaml 的 house_domains 取宫位领域标签。

    YAML 未加引号的数字键解析为 int，加引号的为 str——两边都试。
    兜底返回 "{N}宫"。
    """
    label = domains.get(house) or domains.get(str(house))
    return str(label) if label else f"{house}宫"


def _build_action(
    quality: str,
    from_label: str,
    to_label: str,
    text: str,
) -> str:
    """合成怎么办/借力段（模板 + YAML 第一句，不做自由作文）。"""
    first = _first_sentence(text)

    if quality == "jin":
        # 得吉：借原宫之力托举飞入宫
        return (
            f"借力方向：{from_label} → {to_label}。"
            f"{first}——把{from_label}的本钱当成{to_label}的抓手。"
        )
    else:
        # 受克：飞入宫承接原宫压力，先稳住原宫
        return (
            f"注意：{to_label}会承接{from_label}的压力——"
            f"{first}。先稳住{from_label}再谈{to_label}。"
        )


def _first_sentence(text: str) -> str:
    """截取第一句（中文按 ；。！分割），不超过 40 字。

    用于 action 段引用 YAML 原文的关键句。
    """
    if not text:
        return ""
    for sep in ("；", "。", "！", "，", "?"):
        idx = text.find(sep)
        if idx > 0:
            snippet = text[:idx]
            if len(snippet) <= 40:
                return snippet
            return snippet[:40] + "…"
    return text if len(text) <= 40 else text[:40] + "…"
