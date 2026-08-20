"""DailyReminder —— 每日行运生活提醒。

把「今日行运」翻译成生活里能用的一句话：
行运触发 → 本命承载点/宫位 → 生活场景 → 大白话建议。

边界：
- 只做提醒，不做事件预言；不说“今天一定会发生”。
- 生活场景来自 12 宫语义场 + 受控映射，LLM 不参与生成占星结论。
- 月亮是短暂计时器；火星/水星/土星等触发具体场景时权重更高。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from foundation.logger import get_logger
from shared.constants import ASPECT_ZH
from shared.enums import AspectApplication, AspectType, Planet
from shared.models import Aspect, Chart, Person

from domain.astrology.calculation import TransitCalculator
from domain.astrology.common import house_rulers
from domain.astrology.knowledge import load_knowledge

logger = get_logger("analysis.daily_reminder")

# 日推主看“今天能被体感到”的触发星。外行星长背景后续由 Timing/年度层补权重，
# 这里先避免把多年背景写成每天都在响的提醒。
_REMINDER_TRANSIT_BODIES = [
    Planet.MOON,
    Planet.SUN,
    Planet.MERCURY,
    Planet.VENUS,
    Planet.MARS,
    Planet.JUPITER,
    Planet.SATURN,
]

# 慢行星/社会行星只作为「同一承载点的背景」，不单独每天推送。
_BACKGROUND_TRANSIT_BODIES = [
    Planet.JUPITER,
    Planet.SATURN,
    Planet.URANUS,
    Planet.NEPTUNE,
    Planet.PLUTO,
]

_SOFT_BACKGROUND_ASPECTS = {
    AspectType.CONJUNCTION,
    AspectType.OPPOSITION,
    AspectType.SQUARE,
    AspectType.TRINE,
    AspectType.SEXTILE,
    AspectType.QUINCUNX,
}

_DAY_SCAN_HOURS = tuple(range(24))

_TARGETS = {
    Planet.SUN,
    Planet.MOON,
    Planet.MERCURY,
    Planet.VENUS,
    Planet.MARS,
    Planet.JUPITER,
    Planet.SATURN,
    Planet.URANUS,
    Planet.NEPTUNE,
    Planet.PLUTO,
}

_DAILY_MAIN_ASPECTS = {
    AspectType.CONJUNCTION,
    AspectType.OPPOSITION,
    AspectType.SQUARE,
    AspectType.TRINE,
    AspectType.SEXTILE,
}

_DYNAMIC_ASPECTS = _DAILY_MAIN_ASPECTS

_PLANET_WEIGHT = {
    Planet.MOON: 0.55,     # 快速点火，只作轻提醒
    Planet.SUN: 0.9,
    Planet.MERCURY: 1.0,
    Planet.VENUS: 0.85,
    Planet.MARS: 1.45,     # 急性、碰撞、劳损、冲动
    Planet.JUPITER: 0.95,
    Planet.SATURN: 1.2,    # 责任、规则、卡点
}

_PLANET_ZH = {
    Planet.SUN: "太阳",
    Planet.MOON: "月亮",
    Planet.MERCURY: "水星",
    Planet.VENUS: "金星",
    Planet.MARS: "火星",
    Planet.JUPITER: "木星",
    Planet.SATURN: "土星",
    Planet.URANUS: "天王星",
    Planet.NEPTUNE: "海王星",
    Planet.PLUTO: "冥王星",
}

# 受控生活场景层：底层意义仍以 house_significations.yaml 为准，这里只把它翻译
# 成日推可执行的生活提示。文案要像朋友提醒，不像“分析报告”。
_HOUSE_SCENES: dict[int, dict[str, object]] = {
    1: {
        "scene": "身体状态/出门安全",
        "keywords": ("身体", "状态", "出门"),
        "advice": "今天别太急着证明自己。出门、运动、临时赶路时慢半拍，身体哪里不舒服就先照顾它。",
    },
    2: {
        "scene": "付款/消费/贵重物",
        "keywords": ("钱", "付款", "消费"),
        "advice": "今天花钱前多看一眼。付款金额、订阅扣费、转账对象、贵重物品都顺手确认一下。",
    },
    3: {
        "scene": "通勤/交通/消息文书",
        "keywords": ("开车", "通勤", "消息", "文书"),
        "advice": "今天路上别抢那一下，车距、路口、导航多看一眼；消息、表格、合同小字也顺手再过一遍。",
    },
    4: {
        "scene": "家里/房子/家人",
        "keywords": ("家", "房子", "家人"),
        "advice": "今天家里的小事别拖。门窗、水电、钥匙、快递和家人消息，能顺手确认就确认一下。",
    },
    5: {
        "scene": "恋爱/玩乐/孩子/投机",
        "keywords": ("恋爱", "孩子", "娱乐"),
        "advice": "今天容易一时兴起。约会、玩乐、抽奖投机都可以开心，但别上头到忘了分寸。",
    },
    6: {
        "scene": "身体劳损/日常工作",
        "keywords": ("身体", "劳损", "作息", "工作"),
        "advice": "搬重物、久坐起身、运动拉伸、腰背用力都别太急；工作上也别为了赶时间硬扛。",
    },
    7: {
        "scene": "合作/伴侣/客户/合同",
        "keywords": ("合作", "伴侣", "客户", "合同"),
        "advice": "今天和人对接别只靠默认理解。约定、边界、时间、合同条款，说清楚比事后补救省心。",
    },
    8: {
        "scene": "保险/赔付/债务/共同钱",
        "keywords": ("保险", "赔付", "债务", "共同钱"),
        "advice": "今天涉及保险、报销、借还、共同账户的事，证据和记录留好，别口头说完就算。",
    },
    9: {
        "scene": "远行/考试/法律/证件",
        "keywords": ("远行", "考试", "法律", "证件"),
        "advice": "今天远行、考试、证件、法律材料这类事，提前查规则，别临到门口才发现少一步。",
    },
    10: {
        "scene": "工作责任/老板/公开表现",
        "keywords": ("事业", "老板", "责任"),
        "advice": "今天工作上容易被看见，也容易被追问。重要回复、汇报和交付物，发出去前再看一遍。",
    },
    11: {
        "scene": "朋友/团队/社群平台",
        "keywords": ("朋友", "团队", "平台"),
        "advice": "今天群聊、团队、平台上的话别太快发。先想清楚对象和场合，少一点误会。",
    },
    12: {
        "scene": "睡眠/隐藏压力/幕后事项",
        "keywords": ("睡眠", "压力", "幕后"),
        "advice": "今天别把所有压力都憋着。睡眠、情绪、幕后杂事要留一点余地，别硬撑到最后一刻。",
    },
}


@dataclass(frozen=True)
class DailyReminder:
    """一条可推送/可入信的日常提醒。"""

    level: int
    score: float
    house: int
    scene: str
    sender: str
    title: str
    reason: str
    advice: str
    trigger_planet: Planet
    natal_planet: Planet
    aspect_type: AspectType
    orb: float
    role: str
    confidence: float
    reason_chain: list[str] = field(default_factory=list)
    time_label: str = "全天背景"
    start_at: str | None = None
    end_at: str | None = None

    @property
    def body(self) -> str:
        return f"{self.reason}{self.advice}"

    def as_metadata(self) -> dict[str, object]:
        return {
            "level": self.level,
            "score": round(self.score, 3),
            "house": self.house,
            "scene": self.scene,
            "sender": self.sender,
            "reason": self.reason,
            "advice": self.advice,
            "trigger_planet": self.trigger_planet.value,
            "natal_planet": self.natal_planet.value,
            "aspect": self.aspect_type.value,
            "orb": round(self.orb, 3),
            "role": self.role,
            "confidence": round(self.confidence, 3),
            "reason_chain": list(self.reason_chain),
            "time_label": self.time_label,
            "start_at": self.start_at,
            "end_at": self.end_at,
        }


@dataclass(frozen=True)
class DailyReminderDigest:
    """当日日推：本地 0:00-24:00 的提醒集合。"""

    letter_date: str
    timezone_name: str
    summary: str
    items: list[DailyReminder]
    disclaimer: str = "不是说一定会发生什么，只是这些生活场景今天更容易被点亮。"

    def as_metadata(self) -> dict[str, object]:
        return {
            "letter_date": self.letter_date,
            "timezone_name": self.timezone_name,
            "summary": self.summary,
            "items": [item.as_metadata() for item in self.items],
            "disclaimer": self.disclaimer,
        }


@dataclass(frozen=True)
class _TimedReminder:
    reminder: DailyReminder
    local_dt: datetime


@dataclass(frozen=True)
class _HouseCandidate:
    house: int
    role: str  # placement | house_lord
    score_multiplier: float


class DailyReminderEngine:
    """把今日行运相位排序成生活提醒。"""

    def __init__(self, kb=None):
        self._kb = kb or load_knowledge()
        self._transit = TransitCalculator(self._kb)

    def top_reminder(
        self,
        chart: Chart,
        person: Person,
        params: dict | None = None,
        *,
        target: datetime | None = None,
    ) -> DailyReminder | None:
        reminders = self.reminders(chart, person, params, target=target)
        return reminders[0] if reminders else None

    def daily_digest(
        self,
        chart: Chart,
        person: Person,
        params: dict | None = None,
        *,
        target_date: date | None = None,
    ) -> DailyReminderDigest:
        """生成当日日推：按盘主本地日扫描 0:00-24:00，聚合全部有效提醒。"""
        tz_name, tz = self._person_timezone(person)
        local_day = target_date or datetime.now(tz).date()
        timed: list[_TimedReminder] = []
        for hour in _DAY_SCAN_HOURS:
            local_dt = datetime.combine(local_day, time(hour=hour), tzinfo=tz)
            when = local_dt.astimezone(timezone.utc)
            backgrounds = self._background_aspects(chart, when)
            for reminder in self.reminders(
                chart,
                person,
                params,
                target=when,
                limit=None,
                backgrounds=backgrounds,
            ):
                timed.append(_TimedReminder(reminder=reminder, local_dt=local_dt))

        items = self._collapse_daily_items(timed)
        summary = self._digest_summary(items)
        return DailyReminderDigest(
            letter_date=local_day.isoformat(),
            timezone_name=tz_name,
            summary=summary,
            items=items,
        )

    @staticmethod
    def _digest_summary(items: list[DailyReminder]) -> str:
        if not items:
            return "今天没有特别强的日推提醒"
        first = items[0]
        if first.house == 3 and any(token in "\n".join(first.reason_chain) for token in ("7宫", "8宫", "合同", "赔付")):
            return "今天路上慢半拍，沟通和赔付留证据"
        if first.house == 3:
            return "今天路上和消息都慢半拍"
        if first.house == 6:
            return "今天身体和工作节奏别硬扛"
        if first.house in (7, 8):
            return "今天对接、合同和钱的边界说清楚"
        return f"今天{first.scene}这块先慢一点"

    def reminders(
        self,
        chart: Chart,
        person: Person,
        params: dict | None = None,
        *,
        target: datetime | None = None,
        limit: int | None = 5,
        backgrounds: dict[Planet, list[Aspect]] | None = None,
    ) -> list[DailyReminder]:
        when = target or datetime.now(timezone.utc)
        aspects = self._transit.transit_aspects(chart, when, _REMINDER_TRANSIT_BODIES)
        bg = backgrounds if backgrounds is not None else self._background_aspects(chart, when)
        result: list[DailyReminder] = []
        for aspect in aspects:
            if aspect.aspect_type not in _DAILY_MAIN_ASPECTS:
                continue
            result.extend(self._reminders_for_aspect(chart, aspect, backgrounds=bg))
        result = [r for r in result if r.level > 0]
        result.sort(key=lambda r: (r.level, r.score, r.confidence), reverse=True)
        logger.info("DailyReminder: 今日 %d 条生活提醒", len(result))
        return result[:limit] if limit is not None else result

    # ------------------------------------------------------------------

    def _reminders_for_aspect(
        self,
        chart: Chart,
        aspect: Aspect,
        *,
        backgrounds: dict[Planet, list[Aspect]] | None = None,
    ) -> list[DailyReminder]:
        if aspect.body1 not in _REMINDER_TRANSIT_BODIES:
            return []
        if aspect.body2 not in _TARGETS or aspect.body2 not in chart.planets:
            return []
        info = self._kb.aspects.get(aspect.aspect_type)
        if info is None:
            return []

        base = info.weight_multiplier * _PLANET_WEIGHT.get(aspect.body1, 0.8)
        base *= self._orb_multiplier(aspect.orb)
        base *= self._application_multiplier(aspect.application)
        bg_aspects = (backgrounds or {}).get(aspect.body2, [])
        if bg_aspects and aspect.body1 in (Planet.MOON, Planet.MERCURY, Planet.MARS):
            # 快行星是计时器；同一本命承载点若同时被天王/海王/土星等托起，日推应更容易浮上来。
            base *= min(1.45, 1.0 + 0.16 * len(bg_aspects))

        reminders: list[DailyReminder] = []
        for candidate in self._house_candidates(chart, aspect.body2):
            score = base * candidate.score_multiplier * self._scene_fit(
                aspect.body1, candidate.house, candidate.role
            )
            level = self._level_for(score, aspect, candidate.house)
            if level <= 0:
                continue
            reminders.append(
                self._build_reminder(
                    chart=chart,
                    aspect=aspect,
                    candidate=candidate,
                    score=score,
                    level=level,
                    background_aspects=bg_aspects,
                )
            )
        return reminders

    def _house_candidates(self, chart: Chart, natal_planet: Planet) -> list[_HouseCandidate]:
        candidates: list[_HouseCandidate] = []
        placement = chart.planets[natal_planet].house.house
        if 1 <= placement <= 12:
            candidates.append(_HouseCandidate(placement, "placement", 1.35))

        for house in range(1, 13):
            try:
                rulers = house_rulers(chart, self._kb, house)
            except Exception:  # noqa: BLE001 - 盘数据不完整时跳过宫主增强
                rulers = []
            if natal_planet in rulers:
                # 宫主是“事务承载者”，日推里应略高于单纯落宫；
                # 火星/水星等会通过 _scene_fit 把更贴近生活的宫位顶上来。
                candidates.append(_HouseCandidate(house, "house_lord", 1.3))

        deduped: dict[tuple[int, str], _HouseCandidate] = {}
        for c in candidates:
            deduped[(c.house, c.role)] = c
        return list(deduped.values())

    @staticmethod
    def _orb_multiplier(orb: float) -> float:
        return max(0.4, 1.4 - min(abs(orb), 4.0) * 0.25)

    @staticmethod
    def _application_multiplier(application: AspectApplication) -> float:
        if application == AspectApplication.EXACT:
            return 1.25
        if application == AspectApplication.APPLYING:
            return 1.15
        if application == AspectApplication.SEPARATING:
            return 0.85
        return 1.0

    @staticmethod
    def _scene_fit(trigger: Planet, house: int, role: str = "placement") -> float:
        if trigger == Planet.MARS and house == 6 and role == "house_lord":
            return 1.75
        if trigger == Planet.MARS and house in (1, 3, 6, 8):
            return 1.25
        if trigger == Planet.MOON and house == 3:
            return 1.22
        if trigger == Planet.MOON and house in (1, 6, 8):
            return 1.1
        if trigger == Planet.MERCURY and house in (2, 3, 7, 9, 10):
            return 1.18
        if trigger == Planet.SATURN and house in (6, 7, 8, 10):
            return 1.15
        if trigger == Planet.VENUS and house in (2, 5, 7):
            return 1.12
        if trigger == Planet.SUN and house in (1, 10):
            return 1.1
        if trigger == Planet.JUPITER and house in (2, 9, 11):
            return 1.08
        return 1.0

    @staticmethod
    def _person_timezone(person: Person) -> tuple[str, ZoneInfo]:
        tz_name = person.birth.location.timezone_name or "Asia/Shanghai"
        try:
            return tz_name, ZoneInfo(tz_name)
        except Exception:  # noqa: BLE001 - 非法时区兜底东八区
            return "Asia/Shanghai", ZoneInfo("Asia/Shanghai")

    def _background_aspects(self, chart: Chart, when: datetime) -> dict[Planet, list[Aspect]]:
        """同一本命点的慢行星背景；只补解释链/权重，不单独生成日推。"""
        result: dict[Planet, list[Aspect]] = {}
        try:
            aspects = self._transit.transit_aspects(chart, when, _BACKGROUND_TRANSIT_BODIES)
        except Exception as exc:  # noqa: BLE001 - 星历背景失败不阻断日推
            logger.warning("DailyReminder: 背景行运计算失败: %s", exc)
            return result
        for aspect in aspects:
            if aspect.body1 not in _BACKGROUND_TRANSIT_BODIES:
                continue
            if aspect.body2 not in _TARGETS:
                continue
            if aspect.aspect_type not in _SOFT_BACKGROUND_ASPECTS:
                continue
            if aspect.body1 in (Planet.JUPITER, Planet.SATURN) and aspect.orb > 2.5:
                continue
            if aspect.body1 in (Planet.URANUS, Planet.NEPTUNE, Planet.PLUTO) and aspect.orb > 3.0:
                continue
            result.setdefault(aspect.body2, []).append(aspect)
        for natal_planet, items in result.items():
            items.sort(key=lambda a: (a.orb, -_PLANET_WEIGHT.get(a.body1, 0.8)))
            result[natal_planet] = items[:3]
        return result

    def _collapse_daily_items(self, timed: list[_TimedReminder]) -> list[DailyReminder]:
        if not timed:
            return []
        groups: dict[tuple[Planet, Planet, AspectType], list[_TimedReminder]] = {}
        for item in timed:
            r = item.reminder
            # 日推展示按“同一行运触发同一本命承载点”聚合，而不是按 house/role 拆散。
            # 例如月亮触发本命木星时，木星可能同时承载 3宫交通、7宫对接、8宫赔付；
            # 用户需要一条可行动提醒，而不是连续读三条相似提醒。
            key = (r.trigger_planet, r.natal_planet, r.aspect_type)
            groups.setdefault(key, []).append(item)

        collapsed: list[DailyReminder] = []
        for items in groups.values():
            collapsed.append(self._merge_timed_group(items))

        collapsed.sort(key=self._daily_item_sort_key)
        return collapsed[:8]

    def _daily_item_sort_key(self, reminder: DailyReminder) -> tuple[int, int, int, float]:
        return (
            self._time_order(reminder.time_label),
            self._daily_item_priority(reminder),
            -reminder.level,
            -reminder.score,
        )

    @staticmethod
    def _daily_item_priority(reminder: DailyReminder) -> int:
        chain_text = "\n".join(reminder.reason_chain)
        has_traffic = reminder.house == 3 or "3宫" in chain_text
        has_people_money = any(token in chain_text for token in ("7宫", "8宫", "合同", "赔付"))
        if has_traffic and has_people_money:
            return 0
        if has_traffic:
            return 1
        if reminder.house in (6, 8):
            return 2
        return 3

    def _merge_timed_group(self, items: list[_TimedReminder]) -> DailyReminder:
        best = max(items, key=lambda x: self._merge_primary_key(x.reminder))
        layers = self._unique_layer_reminders([i.reminder for i in items])
        reminder = best.reminder
        if len(layers) > 1:
            reminder = self._merge_layered_reminders(reminder, layers)

        hours = sorted({i.local_dt.hour for i in items})
        start_hour = hours[0]
        end_hour = min(24, hours[-1] + 1)
        time_label = self._time_label(start_hour, end_hour, reminder.trigger_planet)
        return self._with_time_window(
            reminder,
            time_label=time_label,
            start_at=best.local_dt.replace(hour=start_hour, minute=0, second=0, microsecond=0).isoformat(),
            end_at=self._window_end_iso(best.local_dt, end_hour),
        )

    @staticmethod
    def _merge_primary_key(reminder: DailyReminder) -> tuple[bool, bool, int, float, float]:
        mars_body_work = reminder.trigger_planet == Planet.MARS and reminder.house == 6 and reminder.level >= 2
        traffic_layer = reminder.trigger_planet in (Planet.MOON, Planet.MERCURY) and reminder.house == 3
        return (mars_body_work, traffic_layer, reminder.level, reminder.score, reminder.confidence)

    def _unique_layer_reminders(self, reminders: list[DailyReminder]) -> list[DailyReminder]:
        layers: dict[tuple[int, str], DailyReminder] = {}
        for reminder in reminders:
            key = (reminder.house, reminder.role)
            existing = layers.get(key)
            if existing is None or self._merge_primary_key(reminder) > self._merge_primary_key(existing):
                layers[key] = reminder
        return sorted(layers.values(), key=self._layer_sort_key)

    @staticmethod
    def _layer_sort_key(reminder: DailyReminder) -> tuple[int, int, int, float]:
        if reminder.house == 3:
            priority = 0
        elif reminder.house == 6 and reminder.trigger_planet == Planet.MARS:
            priority = 1
        elif reminder.house in (7, 8):
            priority = 2
        else:
            priority = 3
        return (priority, reminder.house, -reminder.level, -reminder.score)

    def _merge_layered_reminders(self, primary: DailyReminder, layers: list[DailyReminder]) -> DailyReminder:
        ordered = [primary]
        ordered.extend(layer for layer in layers if (layer.house, layer.role) != (primary.house, primary.role))
        scenes = self._dedupe_text([layer.scene for layer in ordered])
        scene = self._merged_scene(scenes)
        advice = self._merged_advice(primary, ordered)
        reason = self._merged_reason(primary, ordered)
        reason_chain = self._merged_reason_chain(primary, ordered, advice)
        return DailyReminder(
            level=max(layer.level for layer in ordered),
            score=max(layer.score for layer in ordered),
            house=primary.house,
            scene=scene,
            sender=primary.sender,
            title=primary.title,
            reason=reason,
            advice=advice,
            trigger_planet=primary.trigger_planet,
            natal_planet=primary.natal_planet,
            aspect_type=primary.aspect_type,
            orb=min(layer.orb for layer in ordered),
            role="multi_layer",
            confidence=max(layer.confidence for layer in ordered),
            reason_chain=reason_chain,
            time_label=primary.time_label,
            start_at=primary.start_at,
            end_at=primary.end_at,
        )

    @staticmethod
    def _dedupe_text(values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    @staticmethod
    def _merged_scene(scenes: list[str]) -> str:
        if len(scenes) <= 1:
            return scenes[0] if scenes else "日常节奏"
        return f"{scenes[0]}；也牵到{'、'.join(scenes[1:3])}"

    @staticmethod
    def _merged_advice(primary: DailyReminder, layers: list[DailyReminder]) -> str:
        houses = {layer.house for layer in layers}
        if 3 in houses and houses & {7, 8}:
            return "今天路上慢半拍，车距、路口、导航多看一眼；如果牵到沟通、合同、保险或赔付，证据和记录留好。"
        if 3 in houses:
            return str(_HOUSE_SCENES[3]["advice"])
        if houses & {7, 8} == {7, 8}:
            return "今天和人对接、合同、保险赔付或共同钱别只靠口头，边界、金额和证据留清楚。"
        return primary.advice

    @staticmethod
    def _merged_reason(primary: DailyReminder, layers: list[DailyReminder]) -> str:
        if len(layers) <= 1:
            return primary.reason
        t_zh = _PLANET_ZH.get(primary.trigger_planet, primary.trigger_planet.value)
        n_zh = _PLANET_ZH.get(primary.natal_planet, primary.natal_planet.value)
        if primary.trigger_planet == Planet.MOON:
            lead = f"今天月亮短暂碰到你的本命{n_zh}，{primary.scene}这块先慢一点。"
        else:
            precision = "精准" if primary.orb <= 0.2 else "正在" if primary.orb <= 1.0 else ""
            lead = f"今天{t_zh}{precision}引动你的本命{n_zh}，{primary.scene}这块先慢一点。"
        other_scenes = DailyReminderEngine._dedupe_text(
            [layer.scene for layer in layers if layer.scene != primary.scene]
        )
        if not other_scenes:
            return lead
        return f"{lead}同一颗{n_zh}也牵到{'、'.join(other_scenes[:3])}，放在同一条里一起看。"

    def _merged_reason_chain(
        self,
        primary: DailyReminder,
        layers: list[DailyReminder],
        advice: str,
    ) -> list[str]:
        chain: list[str] = []
        transit_line = next((line for line in primary.reason_chain if line.startswith("行运")), "")
        if transit_line:
            chain.append(transit_line)
        n_zh = _PLANET_ZH.get(primary.natal_planet, primary.natal_planet.value)
        layer_lines: list[str] = []
        for layer in sorted(layers, key=self._layer_sort_key):
            role_text = self._role_text(layer.house, layer.natal_planet, layer.role)
            layer_lines.append(f"{n_zh}作为{role_text}承载{layer.scene}")
        chain.extend(self._dedupe_text(layer_lines))
        if len(layers) > 1:
            houses = "、".join(f"{layer.house}宫" for layer in sorted(layers, key=self._layer_sort_key))
            chain.append(f"合并提醒：同一颗本命{n_zh}同时连到{houses}，不用拆成多条读")
        chain.append(f"建议：{advice}")

        extras: list[str] = []
        for layer in layers:
            extras.extend(
                line for line in layer.reason_chain
                if line.startswith("同一本命点背景") or line.startswith("本命网络带")
            )
        chain.extend(self._dedupe_text(extras))
        return chain

    @staticmethod
    def _window_end_iso(local_dt: datetime, end_hour: int) -> str:
        start = local_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return (start + timedelta(hours=end_hour)).isoformat()

    @staticmethod
    def _with_time_window(
        reminder: DailyReminder,
        *,
        time_label: str,
        start_at: str,
        end_at: str,
    ) -> DailyReminder:
        return DailyReminder(
            level=reminder.level,
            score=reminder.score,
            house=reminder.house,
            scene=reminder.scene,
            sender=reminder.sender,
            title=reminder.title,
            reason=reminder.reason,
            advice=reminder.advice,
            trigger_planet=reminder.trigger_planet,
            natal_planet=reminder.natal_planet,
            aspect_type=reminder.aspect_type,
            orb=reminder.orb,
            role=reminder.role,
            confidence=reminder.confidence,
            reason_chain=list(reminder.reason_chain),
            time_label=time_label,
            start_at=start_at,
            end_at=end_at,
        )

    @staticmethod
    def _time_label(start_hour: int, end_hour: int, trigger: Planet) -> str:
        if trigger in (Planet.SUN, Planet.JUPITER, Planet.SATURN):
            return "全天背景"
        if end_hour - start_hour >= 12:
            return "白天" if 5 <= start_hour and end_hour <= 20 else "全天背景"
        if start_hour < 6:
            return "清晨"
        if start_hour < 11:
            return "上午"
        if start_hour < 14:
            return "中午"
        if start_hour < 18:
            return "下午"
        if start_hour < 21:
            return "傍晚"
        return "夜间"

    @staticmethod
    def _time_order(label: str) -> int:
        order = {
            "清晨": 0,
            "上午": 1,
            "中午": 2,
            "下午": 3,
            "傍晚": 4,
            "夜间": 5,
            "白天": 6,
            "全天背景": 7,
        }
        return order.get(label, 9)

    @staticmethod
    def _level_for(score: float, aspect: Aspect, house: int) -> int:
        level = 0
        if score >= 2.25:
            level = 3
        elif score >= 1.3:
            level = 2
        elif score >= 0.65:
            level = 1

        # 火星精准触发 6宫/6宫主：身体劳损是明确提醒，但文案仍不做恐吓预言。
        if (
            aspect.body1 == Planet.MARS
            and house == 6
            and aspect.aspect_type in _DYNAMIC_ASPECTS
            and aspect.orb <= 0.5
        ):
            level = max(level, 2)
        return level

    def _build_reminder(
        self,
        *,
        chart: Chart,
        aspect: Aspect,
        candidate: _HouseCandidate,
        score: float,
        level: int,
        background_aspects: list[Aspect] | None = None,
    ) -> DailyReminder:
        scene_info = _HOUSE_SCENES[candidate.house]
        t_zh = _PLANET_ZH.get(aspect.body1, aspect.body1.value)
        n_zh = _PLANET_ZH.get(aspect.body2, aspect.body2.value)
        aspect_zh = ASPECT_ZH.get(aspect.aspect_type.value, aspect.aspect_type.value)
        scene = str(scene_info["scene"])
        advice = str(scene_info["advice"])
        role_text = self._role_text(candidate.house, aspect.body2, candidate.role)
        precision = self._precision_word(aspect)

        reason = f"今天{t_zh}{precision}引动你的{role_text}，{scene}这块更容易被点到。"
        if aspect.body1 == Planet.MOON:
            reason = f"今天月亮短暂碰到你的{role_text}，{scene}这块会比较容易冒出来。"
        elif aspect.body1 == Planet.MARS and candidate.house == 6 and candidate.role == "house_lord":
            reason = f"今天火星{precision}引动你的6宫主，身体和日常劳损这块更容易被点到。"

        reason_chain = [
            f"行运{t_zh}{aspect_zh}本命{n_zh}（orb {aspect.orb:.2f}°）",
            f"{n_zh}作为{role_text}承载{scene}",
            f"建议：{advice}",
        ]
        reason_chain.extend(self._background_notes(background_aspects or []))
        reason_chain.extend(self._network_notes(chart, aspect.body2))

        confidence = max(0.45, min(0.9, 0.86 - aspect.orb * 0.06 + (0.04 if candidate.role == "house_lord" else 0.0)))
        title = f"{t_zh}提醒"
        return DailyReminder(
            level=level,
            score=score,
            house=candidate.house,
            scene=scene,
            sender=aspect.body1.value,
            title=title,
            reason=reason,
            advice=advice,
            trigger_planet=aspect.body1,
            natal_planet=aspect.body2,
            aspect_type=aspect.aspect_type,
            orb=aspect.orb,
            role=candidate.role,
            confidence=confidence,
            reason_chain=reason_chain,
        )

    @staticmethod
    def _precision_word(aspect: Aspect) -> str:
        if aspect.application == AspectApplication.EXACT or aspect.orb <= 0.2:
            return "精准"
        if aspect.application == AspectApplication.APPLYING:
            return "正在"
        return ""

    @staticmethod
    def _role_text(house: int, planet: Planet, role: str) -> str:
        p_zh = _PLANET_ZH.get(planet, planet.value)
        if role == "house_lord":
            return f"{house}宫主"
        return f"{house}宫里的{p_zh}"

    @staticmethod
    def _background_notes(aspects: list[Aspect]) -> list[str]:
        notes: list[str] = []
        for aspect in aspects[:3]:
            t_zh = _PLANET_ZH.get(aspect.body1, aspect.body1.value)
            n_zh = _PLANET_ZH.get(aspect.body2, aspect.body2.value)
            aspect_zh = ASPECT_ZH.get(aspect.aspect_type.value, aspect.aspect_type.value)
            if aspect.body1 == Planet.URANUS:
                suffix = "临时变化、突然中断感会更明显"
            elif aspect.body1 == Planet.NEPTUNE:
                suffix = "边界、距离、判断模糊感要多留意"
            elif aspect.body1 == Planet.SATURN:
                suffix = "规则、责任、手续和延迟感更需要耐心"
            elif aspect.body1 == Planet.PLUTO:
                suffix = "压力、控制感或深层牵动会更明显"
            else:
                suffix = "这条承载点今天也有背景能量"
            notes.append(f"同一本命点背景：行运{t_zh}{aspect_zh}本命{n_zh}（orb {aspect.orb:.2f}°），{suffix}")
        return notes

    @staticmethod
    def _network_notes(chart: Chart, natal_planet: Planet) -> list[str]:
        """本命网络只作解释链补充，不单独抬高到预言。"""
        notes: list[str] = []
        seen: set[Planet] = set()
        for natal_aspect in chart.aspects:
            if natal_planet not in (natal_aspect.body1, natal_aspect.body2):
                continue
            other = natal_aspect.body2 if natal_aspect.body1 == natal_planet else natal_aspect.body1
            if other in seen:
                continue
            seen.add(other)
            if other == Planet.URANUS:
                notes.append("本命网络带天王星：事情容易有临时变化/突然中断的体感")
            elif other == Planet.NEPTUNE:
                notes.append("本命网络带海王星：边界、距离、判断容易有点模糊")
            elif other == Planet.MARS:
                notes.append("本命网络带火星：动作、急躁、摩擦感会更明显")
            elif other == Planet.SATURN:
                notes.append("本命网络带土星：规则、责任、手续会更需要耐心")
        return notes[:2]


__all__ = ["DailyReminder", "DailyReminderDigest", "DailyReminderEngine"]
