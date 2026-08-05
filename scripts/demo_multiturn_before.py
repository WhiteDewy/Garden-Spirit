"""多轮追问演示（修复前）：先问转行，再追问，观察当前状态机行为。"""

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
        house_system=HouseSystem.ALCABITIUS,
    )


def main() -> None:
    person = build_person()
    agent = GardenSpiritAgent()
    sid = "mt_xiatian"

    turns = [
        "我想换工作，换行业去做AI产品经理，今年合适吗？风险大吗？",
        "那明年呢？",
        "那具体哪几个月比较好？",
        "我最近压力好大，工作没意思",
    ]

    for i, msg in enumerate(turns):
        print("=" * 60)
        print(f"[第{i}轮] 用户：{msg}")
        answer = agent.handle_message(sid, msg, person, PersonaType.ZIRCON)
        print(f"助手：{answer}")
        ctx = agent.context_builder._sessions[sid]
        if ctx.latest_intent:
            it = ctx.latest_intent
            print(f"  (状态: domain={it.domain.value}/{it.subdomain} "
                  f"clarify={it.requires_clarification})")


if __name__ == "__main__":
    main()
