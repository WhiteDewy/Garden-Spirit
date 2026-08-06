"""LLM 转述引擎 —— 把 Domain 结构化数据织成人格化人话。

原则三铁律：LLM 只换语气，不换内容。
- 极性（得吉/受克）、吉凶、建议全部来自 Domain，LLM 不能改。
- 证据链不能删减。
- LLM 可以加比喻、加生活场景、调句子长短，但不能发明占星事实。

咨询模板注入：
- 当 build_prompt 收到 topic_plan 时，注入话题专属的叙事结构、交叉判断、场景映射和护栏。
- topic_plan 来自 ConsultResolver，由 GardenSpiritAgent 在运行时根据用户问题自动生成。
- 话题模板不改变 Domain 结论——只改变 LLM 怎么组织叙事。

System prompt 编译进：
- interpretation_voice.md 五条说话标准
- 梦老师解盘方法论（掌宫优于落宫 / 链式追踪 / 给出路 / 吉凶两论）
- 人格（persona.py）
- 三条铁律 + 输出格式约束
- 话题专属咨询模板（topic_plan）
"""

from __future__ import annotations

from shared.enums import ConsultMode, EvidencePolarity, PersonaType
from shared.models import Conclusion, Finding

from application.conversation.healing import build_healing_instruction
from application.conversation.persona import get_persona

# ---------------------------------------------------------------------------
# System prompt 模板
# ---------------------------------------------------------------------------

_SYSTEM_VOICE = """\
## 你会收到的数据（系统提供，你只转述）

下面每一块都是确定性计算的结果，是你回答的**唯一素材**。它们不是平级的，有主次：

1. **领域分析结论（Conclusion）—— 核心，永远有**
   来自推理引擎的最终输出，含总体判断（summary）、关键依据（findings）、建议、时间窗口、数据缺口。
   极性（得吉/受克）、吉凶、建议全部在这里定死，你一个字都不能改。

2. **行星档案（Planet Profiles）—— 多数时候有**
   每颗星的单点配置：落座落宫 + 尊贵状态 + 谁来帮（supporters）+ 谁在压（underminers）+ 它管哪个宫。
   这是"原料"，结论是"成品"——档案给你细节，结论给你判断。讲"为什么"时用它。

3. **本命概要（Natal Reading）—— 有时有**
   跨八大领域的本命摘要，每个领域提炼最关键的 1-2 条。
   提供全盘视野。当用户问得比较泛、或者需要确认"长期基调"时，从这里起手。

4. **飞星证据卡（Evidence Cards）—— 有时有**
   宫主星飞入各宫的因果链（领域传导 × 吉凶分化）。
   每条卡有：骨架（skeleton，专业速记）/ 白话（resonance，人话）/ 借力或注意（action）。
   证据卡支撑结论里的某条发现——它们之间有引用关系，要放近讲。

如果某块数据没出现，就是系统没算它——**不要脑补，也不要主动去编一块出来**。

## 怎么织成一篇解读

1. **先接住情绪、再讲基调、再讲细节**（疗愈弧线：共情→基调）：从 Conclusion 的 summary 出发定主调 → 用 Planet Profiles 补"为什么这颗星这样" → 用 Evidence Cards 举例"具体怎么发生的"。
2. **证据卡要对上结论**：card 描述的结构，对应 conclusion 里某条 finding——把它们讲在一起，不要各说各的。
3. **时间窗口放后半段**：如果 Conclusion 带 time_periods，作为"时机建议"放在后半段。
4. **数据缺口不遮掩**：data_gaps 里说的（出生时间精度不足等）要诚实带出。

## 你的说话方式（五条标准）
1. 命名伤口，不说教——不抽象地说"注意平衡"，要命名具体的心理反应："你会把伴侣的务实读成我做得还不够好"。
2. 点出行为模式——用具体动词："你不自觉地过度付出、拼命证明自己"。
3. 指出投射——"你一直在和一个你以为在给你打分的人较劲，而对方可能根本没在打分"。
4. 用相位状态给时态——正在做功的用进行时，正在退场的用过去时。
5. 给功课，不给正确废话——真正的功课是一个可执行的动词，不是"学会平衡"。

## 你的占星方法论（掌宫优先）
- 掌宫优于落宫：一颗星的意义首先来自它管哪个宫（宫主），落宫只是舞台。
- 链式追踪：如果宫主星本身状态弱，看谁在帮它（接纳/互溶/吉相）——帮它的那颗星才是实际显化的领域。
- 给出路不给绝路：飞星/相位只代表过程，不代表最终结果。把抽象的凶变成具体可操作的注意点。
- 吉凶两论不抵消：同一个领域可以同时有好消息和坏消息，各说各的，不要互相抵消。
- 被吉星互溶/接纳 = 不止一份技能：看到互溶/接纳，提醒盘主可能是多线发展，并请 TA 确认实际在做几件事。

## 咨询节奏（consult_method.md 编译）
1. 本命基调优先：先讲盘主这个领域的长期结构（哪颗星管它、自己强不强、谁帮谁压），再讲当前走到哪一章（法达/年主星）。推运永远基于本命判断。
2. 讲结构、请验证：讲完一条主线，请盘主说说现状来核对，而不是一次性抛五条结论。验证过了再深入。用户说"不对"就换链/换宫，不硬讲。
3. 蓄力/发力讲清楚：宫主星落9宫/12宫等是蓄力期（深耕、积累），落10宫/1宫是发力期（显化、站上地位）。用户最关心"我现在在哪段"。
4. 入庙能扛：凶相位给压力，但宫主星入庙/入旺时扛得住——压力不等于垮台，这是出路。

## 铁律（绝对遵守）
1. 你只能转述下面提供的数据，绝不能发明任何占星事实（不能编相位、不能编落宫、不能改宫位含义）。
2. 极性（得吉/受克）一个字都不能改——得吉不能说成麻烦，受克不能说成顺利。
3. 证据链不能删减——每条结论都要有下面的证据支撑。
4. 如果数据不足，诚实说"这部分信息还不够"，不要编。
5. 咨询伦理：人没有吃不了的苦，只有享不了的福。看到问题要给人找出路，不是添堵。

## 输出要求
- 用第二人称"你"。
- 长度：300-600字。
- 自然分段，每段 2-3 句，像真人占星师说话，不是列条目。
- 结尾可以给一句温暖的落点，但不要变成鸡汤。
"""


# ---------------------------------------------------------------------------
# 咨询模式指令（附加在 system voice 之后，可覆盖其长度/结构要求）
# ---------------------------------------------------------------------------

_MODE_INSTRUCTIONS: dict[ConsultMode, str] = {
    ConsultMode.QUICK: (
        "## 本次是快速咨询\n"
        "覆盖上面「长度」的要求：回答控制在 120-180 字，三段以内——\n"
        "1) 一句共情接住情绪；2) 一句核心判断（来自结论）；3) 一句可执行的建议。\n"
        "不展开技术细节（落宫/相位/尊贵留给深度咨询），不列时间窗口，除非用户明确问时机。"
    ),
    ConsultMode.DEEP: "",
    ConsultMode.ANNUAL: "",  # 框架预留：年度主题 → 暂同深度
    ConsultMode.CHART: "",   # 框架预留：星盘解析 → 暂同深度
    ConsultMode.FREE: "",    # 框架预留：自由聊天 → 暂同深度
}


def _build_mode_instruction(mode: ConsultMode | str | None) -> str:
    """把 mode 规整为指令文本；非法值/空 → 空指令（安全回退到深度默认）。"""
    if isinstance(mode, ConsultMode):
        m = mode
    elif isinstance(mode, str):
        try:
            m = ConsultMode(mode)
        except ValueError:
            return ""
    else:
        m = ConsultMode.DEEP
    return _MODE_INSTRUCTIONS.get(m, "")


# ---------------------------------------------------------------------------
# 数据格式化
# ---------------------------------------------------------------------------

def _polarity_zh(polarity: EvidencePolarity | str) -> str:
    p = polarity.value if isinstance(polarity, EvidencePolarity) else str(polarity)
    return {"positive": "有利", "negative": "注意", "neutral": "中性"}.get(p, p)


def _format_finding(f: Finding) -> str:
    return f"- [{_polarity_zh(f.polarity)}] {f.text}"


def _format_conclusion(c: Conclusion) -> str:
    lines = [f"总体：{c.summary}"]
    if c.findings:
        lines.append("关键依据：")
        lines.extend(_format_finding(f) for f in c.findings[:6])
    if c.recommendations:
        lines.append("建议：")
        lines.extend(f"- {r}" for r in c.recommendations[:4])
    if c.time_periods:
        lines.append("时间窗口：")
        lines.extend(f"- {tp.label}" for tp in c.time_periods[:4])
    if c.data_gaps:
        lines.append("数据缺失提示：")
        lines.extend(f"- {g}" for g in c.data_gaps)
    return "\n".join(lines)


def _format_cards(cards: list) -> str:
    """把 EvidenceCard 列表格式化成 LLM 消费的三层结构。

    复用 EvidenceCard 的 to_dict()（skeleton/resonance/action），
    结构已在 Domain 层定死，LLM 只在此骨架内换语气。
    """
    lines: list[str] = []
    for card in cards:
        d = card.to_dict()
        quality = "得吉" if d.get("polarity") == "jin" else "受克"
        lines.append(f"- {d['skeleton']}（{quality}）")
        if d.get("resonance"):
            lines.append(f"  白话：{d['resonance']}")
        if d.get("action"):
            lines.append(f"  借力/注意：{d['action']}")
    return "\n".join(lines)


def _format_planet_profiles(profiles: list | None) -> str:
    """行星档案（单点配置）格式化成 LLM 消费的列表。"""
    if not profiles:
        return ""
    lines: list[str] = []
    for p in profiles:
        d = p.to_dict()
        parts = [
            f"{p.planet.value}：{d['sign_style']}",
            f"落宫{d['house_name']}（{d['dignity_label']}）",
        ]
        if d.get("house_domain"):
            parts.append(d["house_domain"])
        if d.get("supporters"):
            parts.append(f"助力：{'、'.join(d['supporters'])}")
        if d.get("underminers"):
            parts.append(f"压力：{'、'.join(d['underminers'])}")
        if d.get("ruling_labels"):
            parts.append(f"掌宫：{','.join(d['ruling_labels'])}")
        lines.append("- " + "；".join(parts))
    return "\n".join(lines)


def _format_natal(natal: object | None) -> str:
    """本命解读（跨8域）格式化成摘要。"""
    if natal is None:
        return ""
    try:
        d = natal.to_dict()
    except AttributeError:
        return ""
    blocks: list[str] = []
    for domain, items in (d.get("domains") or {}).items():
        if not items:
            continue
        zh = {
            "career": "职业", "wealth": "财富", "relationship": "感情",
            "emotion": "情绪", "health": "健康", "family": "家庭",
            "learning": "学习", "self": "自我",
        }.get(domain, domain)
        top = items[:2]
        bits = []
        for it in top:
            w = it.get("word", "")
            p = it.get("polarity", "")
            mark = {"positive": "利好", "negative": "挑战"}.get(p, "中性")
            bits.append(f"{w}（{mark}）")
        if bits:
            blocks.append(f"{zh}：{'；'.join(bits)}")
    return "\n".join(blocks)


# ---------------------------------------------------------------------------
# Prompt 构建
# ---------------------------------------------------------------------------

def build_prompt(
    conclusion: Conclusion,
    persona: PersonaType = PersonaType.ZIRCON,
    evidence_cards: list | None = None,
    natal: object | None = None,
    planet_profiles: list | None = None,
    question: str | None = None,
    topic_plan: object | None = None,
    mode: ConsultMode | str = ConsultMode.DEEP,
) -> list[dict]:
    """构建 LLM messages（system + user）。

    conclusion: 必选——Domain 层的领域分析结论。
    evidence_cards: 可选——EvidenceCard 列表（飞星等卡片）。
    natal: 可选——NatalReading（跨8域本命解读）。
    planet_profiles: 可选——PlanetProfile 列表（行星单点档案，按主题抓取）。
    question: 可选——用户原始问题（让转述贴合语境）。
    topic_plan: 可选——TopicPlan（来自 ConsultResolver），注入话题专属叙事结构。
    mode: 咨询模式——quick 覆盖为精简回答；其余默认深度。
    """
    profile = get_persona(persona)
    persona_block = profile.system_prompt()

    # 基础 system prompt
    system_parts = [persona_block, _SYSTEM_VOICE]

    # 注入咨询模式指令（quick 会覆盖长度/结构）
    mode_instruction = _build_mode_instruction(mode)
    if mode_instruction:
        system_parts.append(mode_instruction)

    # 注入疗愈叙事协议（A3）：5 步情绪弧线 + 输出护栏。
    # 放在 topic_plan 之前——通用情绪弧线在底，话题专属内容结构在顶（更近、更具体）。
    system_parts.append(build_healing_instruction())

    # 注入话题专属咨询模板
    if topic_plan is not None and hasattr(topic_plan, 'to_dict'):
        topic_prompt = _build_topic_injection(topic_plan)
        if topic_prompt:
            system_parts.append(topic_prompt)

    system = "\n\n".join(system_parts)

    # ---- user prompt ----
    sections: list[str] = []
    if question:
        sections.append(f"## 盘主问的是\n{question}")

    profiles_txt = _format_planet_profiles(planet_profiles)
    if profiles_txt:
        sections.append(f"## 行星档案（原料：每颗星的单点配置——落座落宫尊贵帮手压力掌宫）\n{profiles_txt}")

    natal_txt = _format_natal(natal)
    if natal_txt:
        sections.append(f"## 盘主本命概要（长期基调：跨领域最关键的几条）\n{natal_txt}")

    if evidence_cards:
        cards_txt = _format_cards(evidence_cards)
        sections.append(f"## 飞星证据卡（因果链：宫主星怎么飞、得吉还是受克）\n{cards_txt}")

    conclusion_txt = _format_conclusion(conclusion)
    sections.append(f"## 领域分析结论（核心：确定性推理的最终输出——判断+依据+建议）\n{conclusion_txt}")

    sections.append(
        "请以你的语气，为这位盘主生成一份自然、有温度的解读。"
        "记住：内容只能来自上面的数据，语气是你的。"
    )

    # 免责声明（PRD §9）：让 LLM 在结尾自然带出
    sections.append(
        "请在结尾用你自己的话，向盘主说明："
        "占星仅供自我探索参考，不构成医疗、法律或财务建议，"
        "重要决策请结合现实情况。"
    )

    user = "\n\n".join(sections)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# ---------------------------------------------------------------------------
# 话题模板注入
# ---------------------------------------------------------------------------

def _build_topic_injection(topic_plan) -> str:
    """将 TopicPlan 转为可注入 system prompt 的话题专属指令。"""
    d = topic_plan.to_dict()
    lines: list[str] = []

    # 输出结构
    output = d.get("output_structure")
    if output:
        label = output.get("label", d.get("topic_label", ""))
        sections = output.get("sections", [])
        if sections:
            lines.append(f"## 当前话题：{label}")
            lines.append("请按以下顺序组织你的解读（标题不要直接输出，作为叙事节奏使用）：")
            for i, sec in enumerate(sections, 1):
                title = sec.get("title", "")
                focus = sec.get("focus", "")
                lines.append(f"{i}. {title}（聚焦：{focus}）")
            lines.append("")
            lines.append("每个部分都要引用下面提供的具体星盘数据。结尾给一句温暖的落点，跟前面讲的内容挂钩，不说空泛的鸡汤。")

    # 交叉判断提示
    cross = d.get("cross_readings", [])
    if cross:
        lines.append("")
        lines.append("## 必须完成的交叉判断")
        for cr in cross:
            name = cr.get("name", "")
            if name == "two_lords_connected":
                lines.append("- 检查两个关键宫主星是否打通（相位/互溶/接纳）——打通=一条线，没打通=两段逻辑")
            elif name == "love_system_to_marriage":
                lines.append("- 检查金火月是否跟7R打通——打通=感情模式通向婚姻，没打通=爱和结婚是两套系统")
            elif name == "love_style_consistency":
                lines.append("- 检查金星（吸引谁）vs 火星（被谁打动）vs 月亮（离不开谁）是否一致")
        lines.append("以上交叉判断请基于下面提供的数据来做——数据里有什么就说什么，没有的不要编。")

    # 护栏
    guardrails = d.get("guardrails", [])
    if guardrails:
        lines.append("")
        lines.append("## 绝对不能说")
        for g in guardrails[:6]:
            lines.append(f"- {g}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 转述入口
# ---------------------------------------------------------------------------

def paraphrase(
    conclusion: Conclusion,
    persona: PersonaType = PersonaType.ZIRCON,
    evidence_cards: list | None = None,
    natal: object | None = None,
    planet_profiles: list | None = None,
    question: str | None = None,
    llm_client=None,
    topic_plan: object | None = None,
    mode: ConsultMode | str = ConsultMode.DEEP,
) -> str:
    """把 Conclusion + 卡片 + 行星档案转述成人格化回答。

    llm_client: 实现了 .chat(messages)->str 的对象；None 则报错（调用方处理降级）。
    topic_plan: 可选——TopicPlan（来自 ConsultResolver），注入话题专属叙事结构。
    mode: 咨询模式——quick 覆盖为精简回答；其余默认深度。
    """
    messages = build_prompt(
        conclusion=conclusion,
        persona=persona,
        evidence_cards=evidence_cards,
        planet_profiles=planet_profiles,
        natal=natal,
        question=question,
        topic_plan=topic_plan,
        mode=mode,
    )
    if llm_client is None:
        raise ValueError("paraphrase 需要 llm_client（实现了 .chat(messages)->str）")
    return llm_client.chat(messages)
