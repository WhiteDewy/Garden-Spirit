"""Dogfooding：用真实用户（夏天）的出生数据跑完整管线。

验证：算得真（星盘位置）+ 路由正确 + 结论确定性。
不修改任何项目代码，只做调用。
"""

from datetime import datetime
import zoneinfo

from shared.enums import HouseSystem, IntentDomain, PersonaType
from shared.models import BirthData, GeoLocation, Person
from domain.astrology.calculation import NatalChartCalculator
from domain.reasoning.intent import IntentRouter
from application.agent import GardenSpiritAgent

PLANET_ZH = {
    "sun": "太阳", "moon": "月亮", "mercury": "水星", "venus": "金星",
    "mars": "火星", "jupiter": "木星", "saturn": "土星", "uranus": "天王星",
    "neptune": "海王星", "pluto": "冥王星", "north_node": "北交点",
    "south_node": "南交点", "chiron": "凯龙", "lilith": "莉莉丝",
}
SIGN_ZH = {
    "aries": "白羊", "taurus": "金牛", "gemini": "双子", "cancer": "巨蟹",
    "leo": "狮子", "virgo": "处女", "libra": "天秤", "scorpio": "天蝎",
    "sagittarius": "射手", "capricorn": "摩羯", "aquarius": "水瓶", "pisces": "双鱼",
}


def build_person() -> Person:
    return Person(
        id="p_xiatian",
        name="夏天",
        gender="女",
        birth=BirthData(
            datetime(1991, 3, 21, 9, 25, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
            GeoLocation(35.7, 113.35, timezone_name="Asia/Shanghai",
                        place_name="山西省陵川县附城镇青杨庄村"),
        ),
        house_system=HouseSystem.ALCABITIUS,  # 用户指定：阿卡比特宫位制
    )


def print_chart(person: Person) -> None:
    calc = NatalChartCalculator()
    chart = calc.compute(person)
    print("=" * 60)
    print("【本命盘】", chart.epoch_utc.isoformat(), "·",
          chart.location, "·", chart.house_system.name)
    asc = chart.ascendant
    mc = chart.midheaven
    print(f"上升 {SIGN_ZH[asc.sign.value]} {asc.degree_in_sign:.1f}° · "
          f"天顶 {SIGN_ZH[mc.sign.value]} {mc.degree_in_sign:.1f}°")
    print("-" * 60)
    for p, cp in chart.planets.items():
        if p.value in ("south_node", "chiron", "lilith"):
            continue
        ret = " R" if cp.speed.value.startswith("retro") else ""
        print(f"{PLANET_ZH[p.value]:　<4}{SIGN_ZH[cp.sign.sign.value]}"
              f"{cp.sign.degree_in_sign:5.1f}°  落{cp.house.house}宫{ret}")
    return chart


def main() -> None:
    person = build_person()
    print_chart(person)

    router = IntentRouter()
    agent = GardenSpiritAgent()

    # --- 1. 她的自然语言路由测试 ---
    natural = "我想转行做AI产品经理，不确定我能不能转行成功，你从星盘能分析出这个职业路径吗？"
    intent = router.route(natural)
    print("\n" + "=" * 60)
    print("【意图路由】自然语言 →", intent.domain.value, "/", intent.subdomain,
          f"(置信度 {intent.domain_confidence:.2f})",
          "需澄清" if intent.requires_clarification else "")
    if intent.requires_clarification:
        print("   →", intent.clarification_question)

    # --- 2. 完整管线：她的真实问题 ---
    print("\n" + "=" * 60)
    print("【完整管线】她的真实问题")
    answer = agent.handle_message("s_xiatian", natural, person, PersonaType.MOON)
    print(answer)
    ctx = agent.context_builder._sessions["s_xiatian"]
    concl = ctx.latest_conclusion
    print("\n-- 结论结构 --")
    print(f"verdict={concl.metadata.get('verdict')} confidence={concl.overall_confidence:.0%} "
          f"findings={len(concl.findings)} time_periods={len(concl.time_periods)}")

    # --- 3. 换工作策略（ChangeJob）---
    print("\n" + "=" * 60)
    print("【完整管线】ChangeJob 策略（换工作/换行业）")
    q2 = "我想换工作，换行业去做AI产品经理，今年合适吗？风险大吗？"
    intent2 = router.route(q2)
    print("路由 →", intent2.domain.value, "/", intent2.subdomain)
    answer2 = agent.handle_message("s_xiatian2", q2, person, PersonaType.MOON)
    print(answer2)

    # --- 4. 确定性验证 ---
    print("\n" + "=" * 60)
    a1 = agent.handle_message("s_det1", "我适合转行做产品经理吗？", person, PersonaType.MOON)
    a2 = agent.handle_message("s_det2", "我适合转行做产品经理吗？", person, PersonaType.MOON)
    print("【确定性】同一问题两次回答完全一致:", a1 == a2)


if __name__ == "__main__":
    main()
