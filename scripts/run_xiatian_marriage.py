"""Dogfooding：夏天真实盘跑「啥时候能结婚」。

验证：时机问题（结婚）路由是否正确 + 是否产出时机结论（time_periods）。
不修改项目代码，只做调用。
"""

from datetime import datetime
import zoneinfo

from shared.enums import HouseSystem, PersonaType
from shared.models import BirthData, GeoLocation, Person
from application.agent import GardenSpiritAgent


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


def main() -> None:
    person = build_person()
    agent = GardenSpiritAgent()

    q = "好的 夏天的盘 啥时候能结婚啊"
    answer = agent.handle_message("s_xiatian_marriage", q, person, PersonaType.MOON)
    print(answer)

    ctx = agent.context_builder._sessions["s_xiatian_marriage"]
    intent = ctx.latest_intent
    concl = ctx.latest_conclusion
    print("\n" + "=" * 60)
    if intent is not None:
        print(f"【意图】domain={intent.domain.value} subdomain={intent.subdomain!r} "
              f"type={intent.intent_type} house={getattr(intent, 'focus_house', None)}")
    if concl is not None:
        md = concl.metadata or {}
        print(f"【结论】verdict={md.get('verdict')} confidence={concl.overall_confidence:.0%} "
              f"findings={len(concl.findings)} time_periods={len(concl.time_periods)}")
        for tp in concl.time_periods[:6]:
            print("  时机:", tp)


if __name__ == "__main__":
    main()
