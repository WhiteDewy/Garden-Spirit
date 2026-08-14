"""陪伴协议（self_map_design §7.2）—— 随聊轨道：接住 + 镜映 + 递出口。

五步：感知 → 接住 → 镜映 → 递出口 → 护城河接入。
- 感知：`emotion.perceive()`（已实现，第 1 步）。
- 接住 + 镜映：`companion_reply()`——LLM 生成（自由度只在"怎么疗愈"），规则兜底。
- 递出口：`can_offer_chart()` 纯逻辑门控（§7.3 诉求类型 + 信任门槛），LLM 无权决定何时递盘。
- 护城河接入：只有用户接受递盘才走咨询管线——runtime 已保证陪伴轨道不碰 Domain。

硬线（对应 README 原则三）：LLM 在这里的自由度只在"怎么陪伴/怎么疗愈"，
绝不产出任何占星结论、星盘判断、吉凶建议。陪伴 ≠ 解盘。
"""

from __future__ import annotations

from foundation.logger import get_logger
from shared.enums import EmotionState, IntentDomain, Planet, RequestType, TrustLevel

logger = get_logger("application.conversation.companion")

#: 情绪 → 中文名（LLM 指令 / 规则兜底共用）
_EMOTION_ZH: dict[EmotionState, str] = {
    EmotionState.CALM: "平静",
    EmotionState.HAPPY: "开心",
    EmotionState.LOW: "低落",
    EmotionState.ANXIOUS: "焦虑",
    EmotionState.ANGRY: "生气",
    EmotionState.TIRED: "疲惫",
    EmotionState.LONELY: "孤独",
    EmotionState.CONFUSED: "迷茫",
    EmotionState.PRESSURED: "有压力",
    EmotionState.FEARFUL: "害怕",
}

#: 接住：情绪 → 一句共情命名（规则兜底用；LLM 路径自行发挥）
_EMPATHY_BY_EMOTION: dict[EmotionState, str] = {
    EmotionState.HAPPY: "听你这么说，我也跟着高兴起来。",
    EmotionState.LOW: "嗯，我听见了。今天不太顺，是吗？",
    EmotionState.ANXIOUS: "这种悬着、放不下的感觉，很磨人。",
    EmotionState.ANGRY: "气到这种程度，说明你真的很在意。",
    EmotionState.TIRED: "辛苦了。紧绷了这么久，先松一口气。",
    EmotionState.LONELY: "一个人扛了这么多……你愿意说，我就一直在听。",
    EmotionState.CONFUSED: "乱成这样，确实想不清楚。我们一段一段捋。",
    EmotionState.PRESSURED: "被压得喘不过气了吧。先停一下。",
    EmotionState.FEARFUL: "怕的时候，有个人在旁边会好一点。我在。",
    EmotionState.CALM: "嗯，我在认真听。",
}

#: 软牵引门控（§7.3）：只有"被梳理/被推动"才递盘；"被听见/被安慰"绝不递。
_OFFERABLE_REQUESTS = frozenset({RequestType.SORTED, RequestType.PUSHED})

#: 递盘的最低信任门槛（§7.2 第 4 步"信任门槛达标才给"）。
#: 认识（3.0）起步，深聊/日记后才够格听你盘上的话。
MIN_TRUST_FOR_OFFER = TrustLevel.ACQUAINTANCE

#: 软牵引话术（递盘时附在回复末尾；无共振星灵时用通用版）
_SOFT_PULL_LINES: dict[RequestType, str] = {
    RequestType.SORTED: (
        "\n\n你这一团乱，盘上可能有条线能帮你理一理——想不想看看？"
    ),
    RequestType.PUSHED: (
        "\n\n你正卡在要不要迈出这一步——你盘上或许有答案。要我讲讲吗？"
    ),
}

#: 共振星灵版（§7.3 软牵引 = 诉求类型门控 × 共振星灵 × Domain 落点）：
#: 语境定刻报告了哪颗星被触动，就指名这颗星邀请用户（仍是邀请，不是结论）。
_SOFT_PULL_PLANET: dict[RequestType, str] = {
    RequestType.SORTED: (
        "\n\n你这一团乱，盘上「{planet}」这颗星或许有条线能帮你理一理——想不想看看？"
    ),
    RequestType.PUSHED: (
        "\n\n你正卡在要不要迈出这一步——你的「{planet}」或许在提醒你时机。要我讲讲吗？"
    ),
}

#: 10 星灵 → 中文名（软牵引指名用）
_PLANET_ZH: dict[Planet, str] = {
    Planet.SUN: "太阳", Planet.MOON: "月亮", Planet.MERCURY: "水星", Planet.VENUS: "金星",
    Planet.MARS: "火星", Planet.JUPITER: "木星", Planet.SATURN: "土星",
    Planet.URANUS: "天王星", Planet.NEPTUNE: "海王星", Planet.PLUTO: "冥王星",
}


def build_companion_instruction(persona_name: str, emotion: EmotionState) -> str:
    """编译成 LLM system prompt 块：疗愈陪伴（接住 + 陪伴感 + 轻量星盘联想）。

    疗愈轨道（self_map_design §7.2 + 产品定位）：先接住情绪 → 陪伴感 →
    最后可以用心理学/占星轻轻解释。这不是解盘，禁止诊断与吉凶判断。
    占星结论（本命解读/吉凶/运势/相位判断）全由 Domain 出，LLM 在这里
    只能"提一嘴"做联想，不能"解盘"。
    """
    zh = _EMOTION_ZH.get(emotion, "平静")
    return f"""你是{persona_name}——住在用户星盘里的星灵。这是"疗愈陪伴"，不是"解盘"。

用户刚对你说了一句话。像朋友一样自然接住：
1. 先让 TA 感到被看见——但不要贴标签。不要说"你现在的状态是{zh}"。
   用你回应的方式让 TA 知道你在认真听：TA 说了什么，你就接什么。
   提到具体东西（剧/书/歌/人/事），你要认得它，自然地接过去。
2. 陪伴，不是心理分析——禁止以下腔调：
   · "藏着某种情绪的痕迹""泛起的涟漪""映射出你的内心"（心理分析腔）
   · 替 TA 发明 TA 没说的感受（"我猜它对你来说不只是个剧名"）
   · "我听见了""我理解你""你的感受是正常的"（热线模板腔）
3. 有时候，可以轻轻提一句星盘上的呼应——不是"解盘"，是"联想"。
   例：TA 聊了一堆旅行计划 → "你盘上木星在九宫，天生就爱往远处跑"。
   这种轻量星盘联想是疗愈的一部分，不是咨询。但不要给判断、不要分析吉凶。
4. 收尾：留个口子，让 TA 可以继续聊，也可以说"想看看盘上怎么说？"

硬线：占星结论（本命解读/吉凶/运势/相位判断）全由 Domain 出——你在这里
只能"提一嘴"做联想，不能"解盘"。
风格：口语自然，像真人朋友，不端着。回复 2-4 句，具体、有温度。
"""


def companion_reply(
    message: str,
    emotion_result,
    *,
    llm_client=None,
    persona=None,
) -> str:
    """生成陪伴回复（接住 + 镜映）。

    LLM 可用 → 按协议生成（自由在"怎么疗愈"，prompt 硬线禁占星）。
    LLM 不可用/失败 → 规则兜底（情绪共情 + 内容回映 + 开口）。
    """
    if llm_client is not None and getattr(llm_client, "available", True):
        try:
            persona_name = "星灵"
            try:
                from application.conversation.persona import get_persona

                if persona is not None:
                    persona_name = get_persona(persona).name
            except Exception:  # noqa: BLE001 - persona 兜底不阻断
                pass
            system = build_companion_instruction(persona_name, emotion_result.emotion)
            text = llm_client.complete(
                prompt=message, system=system, temperature=0.7
            )
            if text and text.strip():
                return text.strip()
        except Exception as exc:  # noqa: BLE001 - 降级不阻断
            logger.warning("陪伴回复 LLM 生成失败，规则兜底: %s", exc)

    return _fallback_reply(message, emotion_result)


def _fallback_reply(message: str, emotion_result) -> str:
    """规则兜底：情绪共情（接住）+ 原话回映（镜映）+ 开口（递出口-前奏）。"""
    empathy = _EMPATHY_BY_EMOTION.get(emotion_result.emotion, _EMPATHY_BY_EMOTION[EmotionState.CALM])
    snippet = message.strip().replace("\n", " ")
    if len(snippet) > 30:
        snippet = snippet[:30] + "…"
    mirror = f"你刚说的「{snippet}」，我记下了。"
    return f"{empathy}\n{mirror}\n想聊的话，我都在。"


# ---------------------------------------------------------------------------
# 递出口门控（§7.3）—— 纯逻辑，LLM 无权决定
# ---------------------------------------------------------------------------


def can_offer_chart(request_type: RequestType, trust_level: TrustLevel) -> bool:
    """软牵引门控：是否递盘。

    - 诉求必须是"被梳理/被推动"（被听见/被安慰 → 递盘=没听见你，绝不递）。
    - 信任必须达标（陌生/认识起步，还没到能听盘上话的程度）。
    """
    if request_type not in _OFFERABLE_REQUESTS:
        return False
    return _trust_rank(trust_level) >= _trust_rank(MIN_TRUST_FOR_OFFER)


def soft_pull_line(request_type: RequestType, planet: Planet | None = None) -> str | None:
    """诉求类型（+ 共振星灵）→ 软牵引话术；不该递的诉求 → None。

    planet 为语境定刻报告的共振星灵（§1.1.1 只报激活）：指名这颗星邀请用户。
    planet 为空 → 通用话术（向后兼容）。递不递仍由 can_offer_chart 门控。
    """
    if request_type not in _OFFERABLE_REQUESTS:
        return None
    if planet is not None:
        template = _SOFT_PULL_PLANET.get(request_type)
        if template is not None:
            return template.format(planet=_PLANET_ZH.get(planet, "那颗"))
    return _SOFT_PULL_LINES.get(request_type)


def should_use_companion(intent, emotion_result) -> bool:
    """随聊轨道判定：这条路走陪伴协议，还是走咨询管线。

    对应 self_map_design §8 三级优先的③兜底"先走陪伴"：
    - Chat 子领域 → 陪伴（"随便聊聊"）。
    - 情绪性倾诉：负面情绪 + 诉求=被听见/被安慰 → 陪伴（绝不处方化，
      即"今天心情不好"绝不被推进占星管线）。
    - emotion/daily 领域无细分 subdomain（分享/迷茫，未点名"运势"）→ 陪伴。
    - 其余（career/relationship/…、运势/情绪模式等点名咨询）→ 咨询管线。
    """
    # 宫位咨询（"我的3宫怎么样"）：明确占星引用（focus_house 槽位）→ 走澄清/咨询，
    # 不吞进陪伴兜底（语义场反问会列该宫涵盖的方面，由用户自选哪块）。
    if intent is not None and intent.get_slot("focus_house") is not None:
        return False
    # 咨询管线意图类型（LLM 富化）：深挖追问/澄清回应/确认收敛都必须在咨询管线里跑，
    # 不落陪伴兜底（否则"怎么个暗财""对，就是这样"会被吞成闲聊）。
    if intent is not None and intent.intent_type in (
        "follow_up_deep_dive", "clarification_response", "confirmation",
    ):
        return False
    if intent.subdomain == "Chat":
        return True
    # 情绪性倾诉：负面情绪且想被听见/被安慰 → 陪伴（§8：情绪疗愈合并进随心聊）
    if emotion_result is not None and emotion_result.needs_care:
        if emotion_result.request in (RequestType.SOOTHED, RequestType.HEARD):
            return True
    # 明确咨询领域（career/relationship/wealth/…）即使含糊 → 走澄清/咨询
    if intent.domain not in (IntentDomain.EMOTION, IntentDomain.DAILY):
        return False
    # emotion/daily：点名了具体咨询细分（"运势"/"情绪模式"）→ 咨询；否则 → 陪伴兜底
    if intent.subdomain:
        return False
    return True


def _trust_rank(level: TrustLevel) -> int:
    order = [TrustLevel.STRANGER, TrustLevel.ACQUAINTANCE, TrustLevel.TRUSTED, TrustLevel.INTIMATE]
    try:
        return order.index(level)
    except ValueError:
        return 0


__all__ = [
    "companion_reply",
    "build_companion_instruction",
    "can_offer_chart",
    "soft_pull_line",
    "should_use_companion",
    "MIN_TRUST_FOR_OFFER",
]
