"""34 子类点亮系统（self_map_design §2）—— 随聊记录层。

一张"自我星盘轮"，三区 34 子类，记录用户聊过什么，聊过就点亮：
- 行星动力区（10）：心理动能 / 内在驱力
- 宫位舞台区（12）：生活领域 / 故事场景
- 星座风格区（12）：行为风格 / 应对方式

点亮机制（§2.4）：多维多亮——一条消息可同时点亮多个子类（多标签，不做最强透镜去重）。
深度分（§4.2）：提及 +1 / 倾诉 +3 / 完整咨询反向点亮 +10（调用方传入）。

硬线（§12，不可违反）：
- 34 子类只记录"你聊过什么"，不声称"你是谁"（星座区 = 话题的原型风格，不贴用户标签）。
- 本模块不产生任何占星结论，不参与 Domain 推理。
- LLM 分类受控枚举：只能从 34 个 id 里选，不能发明。
- LLM 不可用/失败 → 规则兜底（离线可测、服务不断）。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from foundation.logger import get_logger
from foundation.utils import utc_now_aware
from shared.models import FragmentLight

logger = get_logger("application.conversation.fragments")

#: 每条消息最多点亮的子类数（防 LLM 全亮，点亮才有分量）
MAX_FRAGMENTS = 6


class FragmentZone(str, Enum):
    """三区。"""

    PLANET = "planet"   # 行星动力区（10）
    HOUSE = "house"     # 宫位舞台区（12）
    SIGN = "sign"       # 星座风格区（12）


@dataclass(frozen=True)
class Fragment:
    """一个子类。id 是稳定主键（落库/前端用）。"""

    id: str
    zone: FragmentZone
    name: str                  # "太阳·核心意志"
    triggers: str              # 触发说明（LLM prompt / 规则表注释共用）
    keywords: tuple[str, ...]  # 规则兜底关键词


# ---------------------------------------------------------------------------
# 34 子类目录（§2.1 / §2.2 / §2.3）
# ---------------------------------------------------------------------------

_CATALOG: list[Fragment] = [
    # ── 行星动力区（10）───────────────────────────────────────────────
    Fragment("sun_core", FragmentZone.PLANET, "太阳·核心意志", "成就感、人生目标、想成为的人",
             ("成就感", "人生目标", "想成为", "抱负", "使命", "梦想是", "自我价值", "我是谁")),
    Fragment("moon_tide", FragmentZone.PLANET, "月亮·情绪潮汐", "心情起伏、安全感、原生家庭",
             ("心情", "情绪", "安全感", "原生家庭", "难过", "委屈", "想哭", "情绪化")),
    Fragment("mercury_maze", FragmentZone.PLANET, "水星·思维迷宫", "学习、沟通、逻辑分析、写日记",
             ("学习", "沟通", "逻辑", "分析", "写作", "日记", "思考", "想不通")),
    Fragment("venus_love", FragmentZone.PLANET, "金星·爱与审美", "恋爱、美食、购物、艺术享受",
             ("恋爱", "爱情", "美食", "购物", "艺术", "审美", "浪漫", "喜欢的人")),
    Fragment("mars_action", FragmentZone.PLANET, "火星·行动引擎", "运动、愤怒、竞争、解压",
             ("运动", "健身", "生气", "愤怒", "竞争", "解压", "冲动", "行动力")),
    Fragment("jupiter_faith", FragmentZone.PLANET, "木星·信念高塔", "旅行、哲学、乐观主义、人生意义",
             ("旅行", "远方", "哲学", "人生意义", "乐观", "信念", "希望")),
    Fragment("saturn_order", FragmentZone.PLANET, "土星·秩序边界", "工作压力、责任、自律、恐惧",
             ("压力", "责任", "自律", "纪律", "规则", "边界", "背负", "恐惧")),
    Fragment("uranus_awake", FragmentZone.PLANET, "天王星·觉醒闪电", "打破常规、特立独行、突发奇想",
             ("打破常规", "特立独行", "突发奇想", "叛逆", "不一样", "革新", "变化")),
    Fragment("neptune_dream", FragmentZone.PLANET, "海王星·梦境迷雾", "做梦、发呆、艺术灵感、迷茫",
             ("做梦", "梦到", "发呆", "灵感", "创作", "迷茫", "梦幻", "模糊")),
    Fragment("pluto_depth", FragmentZone.PLANET, "冥王星·深渊重生", "秘密、创伤、至暗时刻、深刻转变",
             ("秘密", "创伤", "至暗", "重生", "疗愈", "控制", "深藏", "阴影")),
    # ── 宫位舞台区（12）───────────────────────────────────────────────
    Fragment("house1_mask", FragmentZone.HOUSE, "1宫·自我面具", "外貌、穿搭、第一印象、自我保护",
             ("外貌", "穿搭", "长相", "第一印象", "形象", "面具", "保护自己")),
    Fragment("house2_value", FragmentZone.HOUSE, "2宫·价值金库", "赚钱、花钱、理财、自我价值感",
             ("赚钱", "花钱", "理财", "存钱", "工资", "收入", "金钱", "自我价值感")),
    Fragment("house3_bridge", FragmentZone.HOUSE, "3宫·沟通之桥", "兄弟姐妹、短途出行、信息交换、考试",
             ("兄弟姐妹", "短途", "信息", "聊天", "交流", "考试", "邻居", "学新")),
    Fragment("house4_home", FragmentZone.HOUSE, "4宫·心灵小屋", "家庭、房产、童年记忆、内心安全感",
             ("家庭", "房产", "房子", "童年", "家人", "父母", "爸妈", "老家")),
    Fragment("house5_joy", FragmentZone.HOUSE, "5宫·快乐剧场", "恋爱、娱乐、创造力、孩子、投机",
             ("恋爱", "娱乐", "快乐", "创造力", "孩子", "小孩", "浪漫", "玩")),
    Fragment("house6_daily", FragmentZone.HOUSE, "6宫·日常秩序", "工作日常、健康管理、宠物、生活习惯",
             ("工作日常", "健康", "宠物", "习惯", "作息", "日常", "养生")),
    Fragment("house7_mirror", FragmentZone.HOUSE, "7宫·关系镜像", "伴侣、合伙人、公开的敌人、一对一关系",
             ("伴侣", "老公", "老婆", "合伙人", "搭档", "合作", "关系", "一对一")),
    Fragment("house8_crisis", FragmentZone.HOUSE, "8宫·危机洞穴", "共同财产、性、危机、生死、他人资源",
             ("共同财产", "性", "危机", "生死", "死亡", "遗产", "保险", "负债")),
    Fragment("house9_far", FragmentZone.HOUSE, "9宫·远方灯塔", "高等教育、长途旅行、法律、信仰",
             ("大学", "硕士", "博士", "留学", "高等教育", "长途", "法律", "信仰")),
    Fragment("house10_career", FragmentZone.HOUSE, "10宫·事业高塔", "职业成就、社会地位、公众形象、领导",
             ("职业", "事业", "工作", "成就", "地位", "领导", "老板", "晋升")),
    Fragment("house11_net", FragmentZone.HOUSE, "11宫·社群星网", "朋友圈、社团、互联网、未来愿景",
             ("朋友", "朋友圈", "社团", "社群", "互联网", "网友", "人脉", "愿景")),
    Fragment("house12_secret", FragmentZone.HOUSE, "12宫·隐秘花园", "潜意识、秘密、灵性、独处、梦境",
             ("潜意识", "灵性", "独处", "冥想", "隐秘", "一个人待", "神秘")),
    # ── 星座风格区（12）───────────────────────────────────────────────
    Fragment("aries_fire", FragmentZone.SIGN, "白羊·勇气之火", "冲动、直接、竞争、想抢先",
             ("冲动", "直接", "抢先", "竞争", "勇敢", "冲劲", "直来直去")),
    Fragment("taurus_earth", FragmentZone.SIGN, "金牛·感官大地", "享受美食、追求稳定、固执、物质安全感",
             ("美食", "稳定", "固执", "物质", "享受", "踏实", "慢慢来")),
    Fragment("gemini_wind", FragmentZone.SIGN, "双子·信息之风", "好奇心、多变、八卦、学习新东西",
             ("好奇", "多变", "八卦", "聊个不停", "新鲜", "兴趣广", "学新")),
    Fragment("cancer_shell", FragmentZone.SIGN, "巨蟹·柔软之壳", "怀旧、保护欲、情绪敏感、照顾他人",
             ("怀旧", "保护欲", "敏感", "照顾", "念旧", "柔软", "顾家")),
    Fragment("leo_glory", FragmentZone.SIGN, "狮子·荣耀之光", "想被关注、骄傲、创造力、大方",
             ("被关注", "骄傲", "出众", "大方", "光环", "表现欲", "面子")),
    Fragment("virgo_mirror", FragmentZone.SIGN, "处女·细节之镜", "追求完美、挑剔、服务精神、秩序感",
             ("完美主义", "完美", "挑剔", "细节", "秩序", "严谨", "洁癖")),
    Fragment("libra_balance", FragmentZone.SIGN, "天秤·平衡之秤", "犹豫不决、追求和谐、社交、审美",
             ("犹豫", "纠结", "和谐", "社交", "公平", "平衡", "选择困难")),
    Fragment("scorpio_eye", FragmentZone.SIGN, "天蝎·深渊之眼", "洞察人性、掌控欲、极致情感、秘密",
             ("洞察", "掌控", "极致", "深情", "猜疑", "占有", "深刻")),
    Fragment("sagittarius_arrow", FragmentZone.SIGN, "射手·自由之箭", "冒险、乐观、讨厌束缚、追求真理",
             ("冒险", "乐观", "讨厌束缚", "真理", "随性", "直率", "不想被管")),
    Fragment("capricorn_peak", FragmentZone.SIGN, "摩羯·责任之峰", "野心、自律、悲观、长期主义",
             ("野心", "自律", "悲观", "长期主义", "现实", "目标感", "沉稳")),
    Fragment("aquarius_star", FragmentZone.SIGN, "水瓶·革新之星", "叛逆、独立、人道主义、特立独行",
             ("叛逆", "独立", "人道主义", "特立独行", "反主流", "理性", "革新")),
    Fragment("pisces_sea", FragmentZone.SIGN, "双鱼·梦幻之海", "共情、逃避、想象力、灵性、牺牲",
             ("共情", "逃避", "想象力", "牺牲", "梦幻", "柔软", "感同身受")),
]

#: id → Fragment
_FRAGMENT_BY_ID: dict[str, Fragment] = {f.id: f for f in _CATALOG}

#: 三区分组（GET /fragments 的"自我星盘轮"用）
ZONES: dict[FragmentZone, list[Fragment]] = {
    zone: [f for f in _CATALOG if f.zone == zone] for zone in FragmentZone
}

#: LLM 分类 system prompt（受控枚举：只能从目录里选）
_FRAGMENT_CLASSIFY_SYSTEM = """你是星灵花园的"话题归属器"。读用户的一句话，判断 TA 聊到了哪些话题子类。
这只是话题收集（记录"聊过什么"），不是性格判断、不是星座贴标签。

可选子类（只从这些 id 里选，不要发明新 id）：
{option_lines}

规则：
- 多维多亮：一条消息可同时点亮多个子类（最多 6 个）。
- 只看这句里真实聊到的话题，不要脑补。
- 完全无话题/太含糊 → fragments 返回空数组。

只输出 JSON（不要任何解释）：
{{"fragments": ["moon_tide", "house10_career"]}}
"""


# ---------------------------------------------------------------------------
# 分类器
# ---------------------------------------------------------------------------


class FragmentClassifier:
    """消息 → 命中的子类 id 列表（LLM 优先，规则兜底）。"""

    def __init__(self, llm_client=None):
        self._llm = llm_client

    def classify(self, message: str) -> list[str]:
        """分类一条消息 → 命中的子类 id（去重、限 6 个、只含目录内 id）。"""
        if not message or not message.strip():
            return []

        if self._llm is not None and getattr(self._llm, "available", True):
            result = self._llm_classify(message)
            if result is not None:
                return result

        return self._rule_fallback(message)

    # ------------------------------------------------------------------

    def _llm_classify(self, message: str) -> list[str] | None:
        """LLM 分类。失败/返回无效 → None（规则兜底）。返回 [] 也算合法。"""
        try:
            if not hasattr(self._llm, "complete"):
                return None
            from foundation.llm.client import LLMClient

            raw = self._llm.complete(
                prompt=message,
                system=_FRAGMENT_CLASSIFY_SYSTEM.format(
                    option_lines=self._option_lines()
                ),
                temperature=0.0,
            )
            data = LLMClient._parse_slots_json(raw)
            if not isinstance(data, dict):
                return None
            raw_ids = data.get("fragments")
            if not isinstance(raw_ids, list):
                return None
            ids: list[str] = []
            for raw_id in raw_ids:
                fid = str(raw_id).strip().lower()
                if fid in _FRAGMENT_BY_ID and fid not in ids:
                    ids.append(fid)
            return ids[:MAX_FRAGMENTS]
        except Exception:  # noqa: BLE001 - 降级不阻断
            logger.warning("34 子类 LLM 分类失败，规则兜底")
            return None

    def _rule_fallback(self, message: str) -> list[str]:
        """关键词兜底：命中关键词数 > 0 的子类，按命中数降序，限 6 个。"""
        scored: list[tuple[int, str]] = []
        for frag in _CATALOG:
            hits = sum(1 for kw in frag.keywords if kw in message)
            if hits > 0:
                scored.append((hits, frag.id))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [fid for _, fid in scored[:MAX_FRAGMENTS]]

    @staticmethod
    def _option_lines() -> str:
        return "\n".join(
            f"- {f.id} = {f.name}（{f.triggers}）" for f in _CATALOG
        )


# ---------------------------------------------------------------------------
# 点亮服务（纯逻辑：只操作传入的 profile，不碰 store）
# ---------------------------------------------------------------------------

#: 深度分（§4.2）：提及 / 倾诉 / 咨询反向点亮 / 被照见 / 触发行动
DEPTH_MENTION = 1
DEPTH_OUTPOURING = 3
DEPTH_CONSULT = 10
DEPTH_SEEN = 5       # 被照见（用户说"对，就是这样"）—— Phase 2 接入
DEPTH_ACTION = 20    # 触发行动（聊完去做了一件事）—— Phase 2 接入


class FragmentLightKind(str, Enum):
    """账本点亮方式（§4.2 深度分来源）。"""

    MENTION = "mention"       # 提及 +1
    OUTPOURING = "outpouring" # 倾诉 +3 / keepsake 次需求灵魂碎片
    CONSULT = "consult"       # 完整咨询反向点亮 +10
    SEEN = "seen"             # 被照见 +5
    ACTION = "action"         # 触发行动 +20


def _kind_for_depth(depth: int) -> str:
    """深度分 → 账本 kind（未显式指定时按此推导）。"""
    if depth == DEPTH_OUTPOURING:
        return FragmentLightKind.OUTPOURING.value
    if depth == DEPTH_CONSULT:
        return FragmentLightKind.CONSULT.value
    if depth == DEPTH_SEEN:
        return FragmentLightKind.SEEN.value
    if depth == DEPTH_ACTION:
        return FragmentLightKind.ACTION.value
    return FragmentLightKind.MENTION.value

#: 咨询反向点亮映射（§5）：解析后的 Domain 结论 → 命中子类。
#: 确定性、无 LLM——方向由 Domain 出（硬线）。一次完整咨询 = 一次深度照见（+10）。
#: 语义取自 §2.1-2.3 各子类的触发说明。
_CONSULT_DOMAIN_FRAGMENTS: dict[str, list[str]] = {
    "career":       ["house10_career", "sun_core", "saturn_order"],
    "relationship": ["venus_love", "house7_mirror", "moon_tide"],
    "wealth":       ["house2_value", "saturn_order", "jupiter_faith"],
    "health":       ["house6_daily", "pluto_depth", "moon_tide"],
    "emotion":      ["moon_tide", "neptune_dream", "pluto_depth"],
    "family":       ["house4_home", "moon_tide", "cancer_shell"],
    "learning":     ["mercury_maze", "house3_bridge", "house9_far"],
    "growth":       ["house9_far", "jupiter_faith", "sagittarius_arrow"],
    "network":      ["house11_net", "libra_balance", "gemini_wind"],
    "self":         ["house1_mask", "sun_core", "house12_secret"],
    "daily":        ["sun_core", "moon_tide"],
}


def _level_for_depth(depth: int, action_count: int = 0) -> int:
    """深度分 + 行动次数 → 五层成长级（§4.2 1-5 级；未点亮 = 0）。

    后端统一出级（前端只渲染，不再各自推），保证全端一致。

    级数 = 分数 + 行动双重门槛（§4.2，2026-08-10 定稿）：
    深度分定"数值档位"，行动次数定"上限"——聊得再多，没真做过事也到不了 4 级：
    - action_count < 1 → 最高 3 级（"聊了 N 次却没真的做"）
    - action_count < 2 → 最高 4 级
    - action_count >= 2 → 可到 5 级
    这让"真去做一次"比"随口聊 20 次"更珍贵：20 次随聊 = 20 分也只停 3 级，
    一次真行动（+20 分但 kind=action 记 1 次）立刻打开 4 级。
    """
    if depth <= 0:
        return 0
    if depth >= 100:
        base = 5
    elif depth >= 30:
        base = 4
    elif depth >= 10:
        base = 3
    elif depth >= 3:
        base = 2
    else:
        base = 1
    if action_count < 1:
        max_by_action = 3
    elif action_count < 2:
        max_by_action = 4
    else:
        max_by_action = 5
    return min(base, max_by_action)


class FragmentService:
    """把命中的子类点亮到 profile.fragments（深度分累加）。"""

    @staticmethod
    def light(
        profile,
        fragment_ids: list[str],
        depth: int = DEPTH_MENTION,
        kind: str | None = None,
        source: str = "",
        ledger: list | None = None,
    ) -> list[str]:
        """累加点亮深度分。返回实际点亮的子类 id（目录内才认）。

        - kind：账本点亮方式（FragmentLightKind 值），默认按 depth 推导。
        - source：来源摘录（用户消息片段等），写进账本供追溯。
        - ledger：传入后，每次真实点亮追加一条 FragmentLight（成长复利账本地基）。

        本方法仍是纯逻辑（只操作传入的 profile/ledger，不碰 store）；
        由调用方把 ledger 交给 GardenStore.append_fragment_lights 持久化。
        """
        lit: list[str] = []
        effective_kind = kind or _kind_for_depth(depth)
        now = utc_now_aware()
        for fid in fragment_ids:
            if fid not in _FRAGMENT_BY_ID:
                continue
            profile.fragments[fid] = int(profile.fragments.get(fid, 0)) + depth
            if ledger is not None:
                ledger.append(FragmentLight(
                    subtype_id=fid,
                    delta=depth,
                    kind=effective_kind,
                    source=source,
                    lit_at=now,
                ))
            lit.append(fid)
        if lit:
            profile.updated_at = now
        return lit

    @staticmethod
    def fragments_for_domain(domain: str) -> list[str]:
        """咨询反向点亮（§5）：Domain 结论 → 命中的子类 id。未知领域 → []。

        只从解析后的 Domain 领域取映射（Domain 事实），不调 LLM——
        一次完整咨询照见哪几个子类，由领域本身决定。
        """
        return list(_CONSULT_DOMAIN_FRAGMENTS.get(domain, []))

    @staticmethod
    def grid(profile, action_counts: dict[str, int] | None = None) -> list[dict]:
        """"自我星盘轮"：全部 34 子类 + 当前深度分 + 成长级（未点亮 = 0，供"盲区"叙事）。

        action_counts：store.count_fragment_actions() 的账本聚合（kind=action 次数），
        用于级数行动门槛（§4.2：level 4 起需真做过事）。缺省按 0 处理（保持旧行为）。
        """
        depths = profile.fragments if profile is not None else {}
        action_counts = action_counts or {}
        return [
            {
                "id": f.id,
                "zone": f.zone.value,
                "name": f.name,
                "triggers": f.triggers,
                "depth": int(depths.get(f.id, 0)),
                "level": _level_for_depth(
                    int(depths.get(f.id, 0)),
                    int(action_counts.get(f.id, 0)),
                ),
                "action_count": int(action_counts.get(f.id, 0)),
            }
            for f in _CATALOG
        ]

    @staticmethod
    def top_soul_fragments(lights, limit: int = 3) -> list[dict]:
        """今日灵魂碎片（§2.5 每日结算）：账本按日聚合 → top N。

        输入：store.list_fragment_lights(person_id, since=今日 00:00 本地)。
        返回：按当天累计 delta 降序，附 name/zone（只含当天真点亮的子类）。
        """
        agg: dict[str, int] = {}
        for light in lights:
            agg[light.subtype_id] = agg.get(light.subtype_id, 0) + int(light.delta)
        ranked = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)
        out: list[dict] = []
        for fid, delta in ranked[:limit]:
            frag = _FRAGMENT_BY_ID.get(fid)
            if frag is None:
                continue
            out.append({
                "id": fid,
                "name": frag.name,
                "zone": frag.zone.value,
                "delta": delta,
            })
        return out

    @staticmethod
    def name_for(subtype_id: str) -> str:
        """子类 id → 中文名（记忆召回/文案用）。未知 id → 原样返回，不炸。"""
        frag = _FRAGMENT_BY_ID.get(subtype_id)
        return frag.name if frag is not None else subtype_id


__all__ = [
    "Fragment",
    "FragmentZone",
    "FragmentClassifier",
    "FragmentService",
    "FragmentLightKind",
    "DEPTH_MENTION",
    "DEPTH_OUTPOURING",
    "DEPTH_CONSULT",
    "DEPTH_SEEN",
    "DEPTH_ACTION",
    "MAX_FRAGMENTS",
    "ZONES",
]
