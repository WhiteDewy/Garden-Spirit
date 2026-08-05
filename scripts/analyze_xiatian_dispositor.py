"""分析夏天（1991-03-21 山西陵川）的飞星证据卡。
不做"推理"，只打印计算层产出。
"""
from datetime import datetime
import json
import zoneinfo

from domain.astrology.calculation import NatalChartCalculator
from domain.astrology.interpretation import dispositor_cards, dispositor_interpretations
from domain.astrology.knowledge import load_knowledge
from shared.enums import HouseSystem
from shared.models import BirthData, GeoLocation, Person

kb = load_knowledge()

p = Person(
    id="xiatian",
    name="夏天",
    gender="女",
    birth=BirthData(
        datetime(1991, 3, 21, 9, 25, tzinfo=zoneinfo.ZoneInfo("Asia/Shanghai")),
        GeoLocation(35.7, 113.35, timezone_name="Asia/Shanghai", place_name="山西省陵川县"),
    ),
    house_system=HouseSystem.ALCABITIUS,
)
chart = NatalChartCalculator().compute(p)

# -- 本命基本面 --
asc = chart.house_cusps[1]
print("=== 夏天 . 本命基本面 ===")
print(f"上升: {kb.sign(asc.sign).name_zh} {asc.degree:.1f}度")
for pl, cp in chart.planets.items():
    info = kb.planet(pl)
    sign_name = kb.sign(cp.sign.sign).name_zh
    print(f"{info.name_zh:4s} {sign_name:3s} {cp.sign.degree_in_sign:5.1f}度  落{cp.house.house:2d}宫")

print()

# -- 飞星读数 --
readings = dispositor_interpretations(chart, kb)
jin_r = [r for r in readings if r.quality == "jin"]
ke_r = [r for r in readings if r.quality == "ke"]
print(f"=== 飞星读数: {len(readings)} 条（得吉 {len(jin_r)} / 受克 {len(ke_r)}）===")

# -- 证据卡 --
cards = dispositor_cards(chart, kb)
jin_cards = [c for c in cards if c.polarity == "jin"]
ke_cards = [c for c in cards if c.polarity == "ke"]

domains = (kb.time_lord_character or {}).get("house_domains", {})

def h_domain(h: int) -> str:
    label = domains.get(h) or domains.get(str(h))
    return str(label) if label else f"{h}宫"

print(f"\n--- 得吉卡 ({len(jin_cards)} 张) ---")
for c in jin_cards:
    fdom = h_domain(c.from_house)
    tdom = h_domain(c.to_house)
    print(f"  {c.card_id}")
    print(f"    术语: {c.skeleton}")
    print(f"    借力: {fdom} --> {tdom}")

print(f"\n--- 受克卡 ({len(ke_cards)} 张) ---")
for c in ke_cards:
    fdom = h_domain(c.from_house)
    tdom = h_domain(c.to_house)
    print(f"  {c.card_id}")
    print(f"    术语: {c.skeleton}")
    print(f"    警告: {tdom} 承接 {fdom} 的压力")

# -- JSON 出口样本 --
print(f"\n=== to_dict 出口样本（前3张）===")
sample = [c.to_dict() for c in cards[:3]]
print(json.dumps(sample, ensure_ascii=False, indent=2))
