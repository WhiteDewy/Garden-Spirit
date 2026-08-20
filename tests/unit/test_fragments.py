"""34 子类点亮测试（self_map_design §2 随聊记录层）+ 闲聊记忆写回。

验证：
- 目录完整性：34 子类，三区 = 10 行星 / 12 宫位 / 12 星座
- LLM 分类：受控枚举（发明 id 丢弃）、限 6 个
- 规则兜底：关键词命中 → 对应子类（离线可测）
- 空消息 → 不点亮
- FragmentService.light：深度分累加、忽略非法 id
- FragmentService.grid：34 条目 + 深度分（未点亮 = 0）
- 接线：agent 随聊轨道点亮 → ctx.fragments
- 接线：API /chat 点亮并落库，GET /fragments 可见
- 接线：闲聊记忆写回（§6 双存）——"继续昨天"能拿到随聊摘要
"""

import json
from collections import Counter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from shared.models import BirthData, ChartProfile, FragmentLight, GeoLocation, Person

from application.agent import GardenSpiritAgent
from application.conversation.fragments import (
    DEPTH_ACTION,
    DEPTH_CONSULT,
    DEPTH_MENTION,
    DEPTH_OUTPOURING,
    DEPTH_SEEN,
    MAX_FRAGMENTS,
    FragmentClassifier,
    FragmentLightKind,
    FragmentService,
    FragmentZone,
    _level_for_depth,
)
from foundation.llm.client import LLMClient as _RealLLMClient


@pytest.fixture(scope="module")
def client():
    from foundation.config import AppConfig
    from application.api.main import create_app

    config = AppConfig()
    config.storage.db_path = ":memory:"
    app = create_app(config)
    with TestClient(app) as c:
        yield c


class FakeFragmentLLM:
    """有 complete() 的假 LLM——返回子类 id 列表 JSON。"""

    available = True

    def __init__(self, fragment_ids: list[str]):
        self._ids = fragment_ids

    def complete(self, prompt, system=None, **kwargs):
        return json.dumps({"fragments": self._ids})


def _make_person() -> Person:
    return Person(
        id="p_frag",
        name="碎片测试",
        birth=BirthData(
            datetime(1990, 6, 15, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
            GeoLocation(31.2304, 121.4737, timezone_name="Asia/Shanghai", place_name="上海"),
        ),
    )


# ---------------------------------------------------------------------------
# 目录完整性（§2：三区 34 子类）
# ---------------------------------------------------------------------------


def test_catalog_34_total():
    grid = FragmentService.grid(None)
    assert len(grid) == 34


def test_catalog_three_zones_counts():
    counts = Counter(f["zone"] for f in FragmentService.grid(None))
    assert counts[FragmentZone.PLANET.value] == 10
    assert counts[FragmentZone.HOUSE.value] == 12
    assert counts[FragmentZone.SIGN.value] == 12


def test_catalog_ids_unique_and_stable():
    grid = FragmentService.grid(None)
    ids = [f["id"] for f in grid]
    assert len(ids) == len(set(ids))
    assert "moon_tide" in ids and "house10_career" in ids and "sagittarius_arrow" in ids


# ---------------------------------------------------------------------------
# LLM 分类（受控枚举）
# ---------------------------------------------------------------------------


def test_llm_classify_valid_ids():
    c = FragmentClassifier(FakeFragmentLLM(["moon_tide", "house10_career"]))
    assert c.classify("今天好难过") == ["moon_tide", "house10_career"]


def test_llm_classify_drops_invented_ids():
    """LLM 发明子类 → 丢弃（只能从 34 个里选，不能发明）。"""
    c = FragmentClassifier(FakeFragmentLLM(["bogus_thing", "venus_love"]))
    assert c.classify("今天好难过") == ["venus_love"]


def test_llm_classify_caps_at_max():
    many = [f"moon_tide"] + [f"house{i}_x" for i in range(1, 15)] + ["venus_love"]
    c = FragmentClassifier(FakeFragmentLLM(many))
    result = c.classify("测试")
    # 只保留目录内的合法 id，且不超过上限
    assert len(result) <= MAX_FRAGMENTS
    assert all(fid != "house1_x" for fid in result)  # 目录内不存在的 house 变体全被丢


def test_llm_classify_empty_list_is_valid():
    """LLM 判断无话题 → 空数组（不点亮，不触发兜底）。"""
    c = FragmentClassifier(FakeFragmentLLM([]))
    assert c.classify("你好") == []


def test_llm_classify_failure_falls_back():
    """LLM 返回非法结构 → 规则兜底。"""

    class BrokenFragmentLLM:
        available = True

        def complete(self, prompt, system=None, **kwargs):
            return "not json at all"

    c = FragmentClassifier(BrokenFragmentLLM())
    result = c.classify("今天好难过，想哭")
    assert result == ["moon_tide"]


# ---------------------------------------------------------------------------
# 规则兜底（无 LLM）
# ---------------------------------------------------------------------------


def test_rule_fallback_sadness():
    c = FragmentClassifier()
    assert c.classify("今天好难过，想哭") == ["moon_tide"]


def test_rule_fallback_multi_light():
    """多维多亮（§2.4）：一条消息点亮多个子类。"""
    c = FragmentClassifier()
    result = c.classify("被老板骂了，好生气，想辞职去旅行")
    assert "mars_action" in result        # 生气 → 火星·行动引擎
    assert "house10_career" in result     # 老板 → 10宫·事业高塔
    assert "jupiter_faith" in result      # 旅行 → 木星·信念高塔


def test_rule_fallback_empty_message():
    c = FragmentClassifier()
    assert c.classify("") == []
    assert c.classify(None) == []


def test_rule_fallback_no_topic():
    c = FragmentClassifier()
    assert c.classify("嗯嗯，好的") == []


# ---------------------------------------------------------------------------
# FragmentService（深度分落库）
# ---------------------------------------------------------------------------


def test_light_increments_depth():
    profile = ChartProfile(person_id="p")
    lit = FragmentService.light(profile, ["moon_tide", "bogus"], depth=DEPTH_MENTION)
    assert lit == ["moon_tide"]           # 非法 id 被忽略
    assert profile.fragments["moon_tide"] == 1


def test_light_accumulates():
    profile = ChartProfile(person_id="p")
    FragmentService.light(profile, ["moon_tide"], depth=DEPTH_MENTION)
    FragmentService.light(profile, ["moon_tide"], depth=DEPTH_OUTPOURING)
    assert profile.fragments["moon_tide"] == 4   # 提及 +1，倾诉 +3


def test_grid_reflects_depths():
    profile = ChartProfile(person_id="p")
    FragmentService.light(profile, ["moon_tide", "venus_love"], depth=DEPTH_OUTPOURING)
    by_id = {f["id"]: f for f in FragmentService.grid(profile)}
    assert by_id["moon_tide"]["depth"] == 3
    assert by_id["venus_love"]["depth"] == 3
    assert by_id["pluto_depth"]["depth"] == 0   # 未点亮 = 0（盲区即课题）


# ---------------------------------------------------------------------------
# 成长复利账本（fragment_lights 的产出侧）：light(ledger=...) 写账本
# ---------------------------------------------------------------------------


def test_grid_includes_level():
    """深度分 → 五层成长级（§4.2）：后端统一出级，未点亮 = 0。"""
    profile = ChartProfile(person_id="p")
    FragmentService.light(profile, ["moon_tide"], depth=DEPTH_MENTION)        # 1
    FragmentService.light(profile, ["venus_love"], depth=DEPTH_OUTPOURING)    # 3
    FragmentService.light(profile, ["mars_action"], depth=DEPTH_SEEN)         # 5
    FragmentService.light(profile, ["sun_core"], depth=DEPTH_CONSULT)         # 10
    by_id = {f["id"]: f for f in FragmentService.grid(profile)}
    assert by_id["pluto_depth"]["level"] == 0    # 未点亮 = 0
    assert by_id["moon_tide"]["level"] == 1      # 1-2 → Ⅰ
    assert by_id["venus_love"]["level"] == 2     # 3-9 → Ⅱ
    assert by_id["mars_action"]["level"] == 2    # 5 → Ⅱ
    assert by_id["sun_core"]["level"] == 3       # 10-29 → Ⅲ


def test_light_ledger_records_valid_ids_only():
    """传 ledger：每次真实点亮追加一条 FragmentLight，非法 id 不记。"""
    profile = ChartProfile(person_id="p")
    ledger: list = []
    lit = FragmentService.light(
        profile, ["moon_tide", "bogus"], depth=DEPTH_MENTION,
        source="我最近总是心情不好", ledger=ledger,
    )
    assert lit == ["moon_tide"]
    assert len(ledger) == 1
    rec = ledger[0]
    assert rec.subtype_id == "moon_tide"
    assert rec.delta == DEPTH_MENTION
    assert rec.kind == FragmentLightKind.MENTION.value
    assert rec.source == "我最近总是心情不好"
    assert rec.lit_at is not None


def test_light_ledger_kind_by_depth():
    """kind 未显式指定时按深度分推导（§4.2 深度分 → 点亮方式）。"""
    profile = ChartProfile(person_id="p")
    ledger: list = []
    FragmentService.light(profile, ["moon_tide"], depth=DEPTH_OUTPOURING, ledger=ledger)
    FragmentService.light(profile, ["venus_love"], depth=DEPTH_CONSULT, ledger=ledger)
    FragmentService.light(profile, ["sun_core"], depth=DEPTH_SEEN, ledger=ledger)
    kinds = {r.subtype_id: r.kind for r in ledger}
    assert kinds == {
        "moon_tide": FragmentLightKind.OUTPOURING.value,
        "venus_love": FragmentLightKind.CONSULT.value,
        "sun_core": FragmentLightKind.SEEN.value,
    }


def test_light_ledger_does_not_change_cumulative():
    """账本是追加式日志：累计深度仍以 profile.fragments 为单一事实源。"""
    profile = ChartProfile(person_id="p")
    ledger: list = []
    FragmentService.light(profile, ["moon_tide"], depth=DEPTH_MENTION, ledger=ledger)
    FragmentService.light(profile, ["moon_tide"], depth=DEPTH_OUTPOURING, ledger=ledger)
    assert profile.fragments["moon_tide"] == 4          # 累计不变
    assert [r.delta for r in ledger] == [1, 3]          # 账本两条事件


# ---------------------------------------------------------------------------
# 咨询反向点亮映射（§5：Domain 结论 → 子类，确定性、无 LLM）
# ---------------------------------------------------------------------------


def test_fragments_for_domain_all_domains_mapped():
    """11 个咨询领域都有映射，且只含目录内合法 id（v2：+growth/network/self）。"""
    from shared.enums import IntentDomain

    consult_domains = {d.value for d in IntentDomain if d.value in {
        "career", "relationship", "wealth", "health", "emotion", "family", "learning",
        "growth", "network", "self", "daily"}}
    all_ids = {f["id"] for f in FragmentService.grid(None)}
    for domain in sorted(consult_domains):
        ids = FragmentService.fragments_for_domain(domain)
        assert ids, f"{domain} 没有反向点亮映射"
        assert len(ids) <= MAX_FRAGMENTS
        assert set(ids) <= all_ids, f"{domain} 映射出目录外 id: {ids}"


def test_fragments_for_domain_unknown_empty():
    assert FragmentService.fragments_for_domain("bogus") == []
    assert FragmentService.fragments_for_domain("") == []


def test_fragments_for_domain_career_semantics():
    """事业咨询 = 10宫·事业高塔 + 太阳·核心意志 + 土星·秩序边界。"""
    ids = FragmentService.fragments_for_domain("career")
    assert ids == ["house10_career", "sun_core", "saturn_order"]


def test_fragments_for_domain_does_not_mutate():
    """返回副本，调用方改动不影响目录（防误改静态映射）。"""
    ids = FragmentService.fragments_for_domain("career")
    ids.append("moon_tide")
    assert FragmentService.fragments_for_domain("career") == [
        "house10_career", "sun_core", "saturn_order"]


# ---------------------------------------------------------------------------
# 接线：agent 随聊轨道点亮
# ---------------------------------------------------------------------------


def test_agent_lights_fragments_on_companion():
    agent = GardenSpiritAgent()
    person = _make_person()
    agent.handle_message("sess_f1", "今天好难过，想哭", person)
    ctx = agent.get_session_context("sess_f1")
    assert ctx.last_was_companion is True
    assert "moon_tide" in ctx.fragments


def test_agent_no_fragments_on_consult():
    """咨询轨道不跑随聊话题分类（§2 只记随聊；咨询反向点亮在 API 层按领域映射）。"""
    agent = GardenSpiritAgent()
    person = _make_person()
    agent.handle_message("sess_f2", "我该不该换工作", person)
    ctx = agent.get_session_context("sess_f2")
    assert ctx.fragments == []


# ---------------------------------------------------------------------------
# 接线：API /chat 点亮 + 落库 + GET /fragments
# ---------------------------------------------------------------------------


def _create_person(client) -> str:
    pid = client.post("/person", json={
        "name": "碎片API",
        "birth": {
            "datetime_local": "1995-06-15T09:30:00",
            "location": {"place_name": "上海"},
            "time_known": True,
        },
        "gender": "F",
    }).json()["id"]
    return pid


def test_chat_lights_and_persists_fragments(client):
    pid = _create_person(client)

    chat = client.post("/chat", json={"person_id": pid, "message": "今天好难过，想哭"})
    assert chat.status_code == 200
    data = chat.json()
    assert "moon_tide" in data["lit_fragments"]

    # 落库后 GET 可见，倾诉（负面情绪）→ 深度 +3
    grid = client.get(f"/person/{pid}/fragments").json()["fragments"]
    by_id = {f["id"]: f for f in grid}
    assert by_id["moon_tide"]["depth"] == DEPTH_OUTPOURING
    assert len(grid) == 34


def test_chat_lights_multiple_fragments(client):
    pid = _create_person(client)
    chat = client.post("/chat", json={
        "person_id": pid,
        "message": "被老板骂了，好生气，想辞职去旅行",
    })
    assert chat.status_code == 200
    lit = chat.json()["lit_fragments"]
    assert "mars_action" in lit and "house10_career" in lit and "jupiter_faith" in lit


def test_consult_reverse_lights(client):
    """§5 咨询反向点亮：一次完整咨询 = 一次深度照见（+10），按领域确定性映射。

    事业咨询 → house10_career / sun_core / saturn_order 深度 +10。
    这是林间给不了的差异化：专业咨询比十次闲聊点得更深。
    """
    pid = _create_person(client)
    r = client.post("/chat", json={"person_id": pid, "message": "我该不该换工作"})
    assert r.status_code == 200
    data = r.json()
    assert data["written_back"] is True        # 出了 Domain 结论
    assert "house10_career" in data["lit_fragments"]

    grid = client.get(f"/person/{pid}/fragments").json()["fragments"]
    by_id = {f["id"]: f for f in grid}
    assert by_id["house10_career"]["depth"] == DEPTH_CONSULT
    assert by_id["sun_core"]["depth"] == DEPTH_CONSULT
    assert by_id["saturn_order"]["depth"] == DEPTH_CONSULT
    assert by_id["moon_tide"]["depth"] == 0     # 领域无关的不误点亮


def test_consult_reverse_lights_accumulates_with_chat(client):
    """反向点亮与随聊点亮深度分累加：先随聊提及 +1，再咨询 +10 → 11。"""
    pid = _create_person(client)
    client.post("/chat", json={"person_id": pid, "message": "最近工作压力好大"})
    client.post("/chat", json={"person_id": pid, "message": "我该不该换工作"})

    grid = client.get(f"/person/{pid}/fragments").json()["fragments"]
    by_id = {f["id"]: f for f in grid}
    # 随聊"压力"（负面情绪=倾诉）→ saturn_order +3；咨询事业 → saturn_order +10 → 累加 13
    assert by_id["saturn_order"]["depth"] == DEPTH_OUTPOURING + DEPTH_CONSULT


def test_chat_seen_confirmation_adds_depth(client):
    """§4.2 被照见 +5：上一轮倾诉点亮 moon_tide，本轮确认"对，就是这样" → 补 +5。

    确认走规则兜底（离线）；账本记 kind=seen（成长复利地基）。
    """
    pid = _create_person(client)
    sid = "sess_seen1"

    r1 = client.post("/chat", json={
        "person_id": pid, "message": "今天好难过，想哭", "session_id": sid,
    })
    assert r1.status_code == 200
    assert "moon_tide" in r1.json()["lit_fragments"]
    assert r1.json()["seen_fragments"] == []      # 第一轮无照见候选

    r2 = client.post("/chat", json={
        "person_id": pid, "message": "对，就是这样，你懂我", "session_id": sid,
    })
    assert r2.status_code == 200
    assert "moon_tide" in r2.json()["seen_fragments"]

    grid = client.get(f"/person/{pid}/fragments").json()["fragments"]
    by_id = {f["id"]: f for f in grid}
    assert by_id["moon_tide"]["depth"] == DEPTH_OUTPOURING + DEPTH_SEEN

    # 账本：kind=seen 一条，delta=+5
    store = client.app.state.store
    seen = [l for l in store.list_fragment_lights(pid) if l.kind == "seen"]
    assert len(seen) == 1
    assert seen[0].subtype_id == "moon_tide"
    assert seen[0].delta == DEPTH_SEEN


def test_chat_non_confirmation_no_seen(client):
    """弱认同不算照见：上一轮倾诉后回"嗯嗯" → 不补 +5（宁缺毋滥）。"""
    pid = _create_person(client)
    sid = "sess_seen2"
    client.post("/chat", json={
        "person_id": pid, "message": "今天好难过，想哭", "session_id": sid,
    })
    r2 = client.post("/chat", json={
        "person_id": pid, "message": "嗯嗯", "session_id": sid,
    })
    assert r2.status_code == 200
    assert r2.json()["seen_fragments"] == []

    grid = client.get(f"/person/{pid}/fragments").json()["fragments"]
    by_id = {f["id"]: f for f in grid}
    assert by_id["moon_tide"]["depth"] == DEPTH_OUTPOURING    # 没有被照见 +5


# ---------------------------------------------------------------------------
# 今日灵魂碎片（§2.5 每日结算）：账本按日聚合 → top3
# ---------------------------------------------------------------------------


def test_top_soul_fragments_aggregates_and_ranks():
    """按当天累计 delta 降序，目录外 id 忽略，limit 生效。"""
    lights = [
        FragmentLight(subtype_id="moon_tide", delta=3, kind="outpouring"),
        FragmentLight(subtype_id="moon_tide", delta=5, kind="seen"),
        FragmentLight(subtype_id="venus_love", delta=1, kind="mention"),
        FragmentLight(subtype_id="bogus", delta=99, kind="mention"),
    ]
    top = FragmentService.top_soul_fragments(lights, limit=3)
    assert [f["id"] for f in top] == ["moon_tide", "venus_love"]   # bogus 忽略
    assert top[0]["delta"] == 8
    assert top[0]["name"] == "月亮·情绪潮汐"
    assert top[0]["zone"] == "planet"


def test_top_soul_fragments_limit_and_empty():
    assert FragmentService.top_soul_fragments([]) == []
    lights = [FragmentLight(subtype_id=f"sun_core", delta=1, kind="mention") for _ in range(5)]
    assert len(FragmentService.top_soul_fragments(lights, limit=3)) == 1   # 只有 1 个子类
    many = [FragmentLight(subtype_id=f"house{i}_career", delta=1, kind="mention") for i in range(1, 7)]
    assert len(FragmentService.top_soul_fragments(many, limit=3)) <= 3


def test_soul_fragments_today_endpoint(client):
    """今日碎片端点：今天点亮 + 被照见 → top1 = moon_tide（累计 8），带名称/星区。"""
    pid = _create_person(client)
    sid = "sess_soul1"
    client.post("/chat", json={
        "person_id": pid, "message": "今天好难过，想哭", "session_id": sid,
    })                                     # moon_tide 倾诉 +3
    client.post("/chat", json={
        "person_id": pid, "message": "对，就是这样，你懂我", "session_id": sid,
    })                                     # moon_tide 被照见 +5

    res = client.get(f"/person/{pid}/soul-fragments/today")
    assert res.status_code == 200
    data = res.json()
    assert data["date"]
    assert data["person_id"] == pid
    assert data["fragments"] and data["fragments"][0]["id"] == "moon_tide"
    assert data["fragments"][0]["delta"] == DEPTH_OUTPOURING + DEPTH_SEEN
    assert data["fragments"][0]["name"] == "月亮·情绪潮汐"
    assert data["fragments"][0]["zone"] == "planet"


def test_soul_fragments_today_empty_for_fresh_person(client):
    """新用户今天没点亮 → 空碎片（前端给希望态，不报错）。"""
    pid = _create_person(client)
    res = client.get(f"/person/{pid}/soul-fragments/today")
    assert res.status_code == 200
    assert res.json()["fragments"] == []


def test_garden_carries_today_soul_fragments(client):
    """站内"回家看看"（推送后置兜底）：/garden 聚合今日碎片 top3，与今日端点同口径。"""
    pid = _create_person(client)
    sid = "sess_garden1"
    client.post("/chat", json={
        "person_id": pid, "message": "今天好难过，想哭", "session_id": sid,
    })                                     # moon_tide 倾诉 +3
    client.post("/chat", json={
        "person_id": pid, "message": "对，就是这样，你懂我", "session_id": sid,
    })                                     # moon_tide 被照见 +5

    g = client.get(f"/garden?person_id={pid}")
    assert g.status_code == 200
    data = g.json()
    assert "soul_fragments" in data                      # 新字段：回家看看数据卡
    assert data["soul_fragments"] and data["soul_fragments"][0]["id"] == "moon_tide"
    assert data["soul_fragments"][0]["delta"] == DEPTH_OUTPOURING + DEPTH_SEEN

    # 同口径：garden.soul_fragments ≡ soul-fragments/today.fragments
    today = client.get(f"/person/{pid}/soul-fragments/today").json()["fragments"]
    assert data["soul_fragments"] == today


# ---------------------------------------------------------------------------
# 接线：来信式日记（§6.1/§6.2 keepsake）——倾诉时刻 → 来信 + 推导链 + 汇入轮盘
# ---------------------------------------------------------------------------


def test_chat_outpouring_generates_keepsake_letter(client):
    """倾诉时刻（需要被接住）→ keepsake 来信，落款推导链显式出参。

    "值得记住的时刻" = 陪伴轨道 + 负面情绪（needs_care）。正文 = 星灵那段
    完整回复原样（来信式日记，不是摘要）；metadata 留 explain 推导链。
    """
    pid = _create_person(client)
    r = client.post("/chat", json={"person_id": pid, "message": "今天好难过，想哭"})
    assert r.status_code == 200
    data = r.json()
    assert data["keepsake_created"] is True
    assert "moon_tide" in data["lit_fragments"]

    letters = client.get(f"/person/{pid}/letters").json()["items"]
    keepsakes = [l for l in letters if l["kind"] == "keepsake"]
    assert len(keepsakes) == 1
    k = keepsakes[0]
    assert k["sender"] == "moon"
    assert k["primary_need"] == "soothed"
    assert k["healing_name"] == "想被抱抱的我"
    assert "想被抱抱" in k["explain"]
    assert "moon_tide" in k["lit_fragments"]
    assert k["body"].strip()  # 正文 = 那段完整回复，非空


def test_keepsake_soul_fragments_light_wheel(client):
    """灵魂碎片汇入轮盘：keepsake 次需求点亮的 34 子类也 light() 进深度。

    委屈（主：想被抱抱）+ 旅行（次：想飞）→ 灵魂碎片 = jupiter_faith /
    sagittarius_arrow。话题已点亮 jupiter_faith（旅行）+3，需求链再点亮 +3 → 6；
    sagittarius_arrow 只来自需求链（话题没聊到）→ +3。
    """
    pid = _create_person(client)
    r = client.post("/chat", json={
        "person_id": pid,
        "message": "被老板骂了好委屈，想辞职去旅行",
    })
    assert r.status_code == 200
    assert r.json()["keepsake_created"] is True

    grid = client.get(f"/person/{pid}/fragments").json()["fragments"]
    by_id = {f["id"]: f for f in grid}
    assert by_id["jupiter_faith"]["depth"] == DEPTH_OUTPOURING * 2   # 话题 + 需求链
    assert by_id["sagittarius_arrow"]["depth"] == DEPTH_OUTPOURING  # 纯需求链点亮
    assert by_id["moon_tide"]["depth"] == DEPTH_OUTPOURING           # 纯话题点亮


def test_consult_does_not_create_keepsake(client):
    """咨询轨道不出来信式日记：keepsake 只属于随聊倾诉时刻。"""
    pid = _create_person(client)
    r = client.post("/chat", json={"person_id": pid, "message": "我该不该换工作"})
    assert r.status_code == 200
    assert r.json()["keepsake_created"] is False
    letters = client.get(f"/person/{pid}/letters").json()["items"]
    assert all(l["kind"] != "keepsake" for l in letters)


# ---------------------------------------------------------------------------
# 接线：词条式来信（§6.1 日常/正面分享时刻，memorable）
# ---------------------------------------------------------------------------


class FakeMemorableLLM(_RealLLMClient):
    """真实 LLMClient 的子类——继承 _parse_slots_json，只覆盖 complete。

    以类名替换 foundation.llm.client.LLMClient 后，各分类器内部的
    `LLMClient._parse_slots_json` 仍指向继承来的静态方法（不会断）。
    按 system prompt 分发：情绪感知 → memorable；需求识别 → JSON；
    词条蒸馏 → 诗化一句；其余（陪伴/子类分类）→ 自然回应（触发各自规则兜底）。
    memorable 用类属性，测试前改 `FakeMemorableLLM.memorable` 切换。"""

    available = True
    memorable = True

    def complete(self, prompt, system=None, **kwargs):
        s = system or ""
        distressed = ("难过" in prompt) or ("想哭" in prompt)
        if "情绪感知器" in s:
            if distressed:
                return json.dumps({
                    "emotion": "low", "request": "soothed", "confidence": 0.9,
                    "memorable": True,
                })
            return json.dumps({
                "emotion": "calm", "request": "heard", "confidence": 0.9,
                "memorable": type(self).memorable,
            })
        if "情绪需求识别器" in s:
            return json.dumps(
                {"primary": "soothed", "secondary": []} if distressed
                else {"primary": "dream", "secondary": []}
            )
        if "记忆词条" in s:
            return "在九门的世界里，你找到了暂时栖息的梦境。"
        return "嗯，我在听。你继续说。"


def _memorable_app(monkeypatch, *, memorable: bool):
    FakeMemorableLLM.memorable = memorable
    monkeypatch.setattr("foundation.llm.client.LLMClient", FakeMemorableLLM)
    from foundation.config import AppConfig  # noqa: PLC0415
    from application.api.main import create_app  # noqa: PLC0415

    config = AppConfig()
    config.storage.db_path = ":memory:"
    return TestClient(create_app(config))


def test_chat_memorable_creates_entry_keepsake(monkeypatch):
    """日常/正面分享（calm + memorable）→ 词条式 keepsake，落款推导链完整。"""
    client = _memorable_app(monkeypatch, memorable=True)
    pid = _create_person(client)
    with client:
        r = client.post("/chat", json={"person_id": pid, "message": "最近在看九门"})
        assert r.status_code == 200
        data = r.json()
        assert data["keepsake_created"] is True
        assert data["emotion"] == "calm"
        assert data["request_type"] == "heard"

        letters = client.get(f"/person/{pid}/letters").json()["items"]
        keepsakes = [l for l in letters if l["kind"] == "keepsake"]
        assert len(keepsakes) == 1
        k = keepsakes[0]
        assert k["entry"] is True                 # 词条标记（前端区分样式）
        assert k["primary_need"] == "dream"
        assert "在九门的世界里" in k["body"]        # 诗化词条成信（不是整段回复）
        assert "想做梦" in k["explain"]           # 推导链显式可解释（§6.2）


def test_chat_non_memorable_no_keepsake(monkeypatch):
    """功能性短句（memorable=false）→ 不生成词条来信。"""
    client = _memorable_app(monkeypatch, memorable=False)
    pid = _create_person(client)
    with client:
        r = client.post("/chat", json={"person_id": pid, "message": "好的"})
        assert r.status_code == 200
        assert r.json()["keepsake_created"] is False
        letters = client.get(f"/person/{pid}/letters").json()["items"]
        assert all(l["kind"] != "keepsake" for l in letters)


def test_chat_distress_still_keepsake_not_entry(monkeypatch):
    """负面倾诉仍走 needs_care 来信（保留整段回复），不因 memorable 重复出词条。"""
    client = _memorable_app(monkeypatch, memorable=True)  # 倾诉也 memorable → 应只出一封
    pid = _create_person(client)
    with client:
        r = client.post("/chat", json={"person_id": pid, "message": "今天好难过，想哭"})
        assert r.status_code == 200
        assert r.json()["keepsake_created"] is True

        letters = client.get(f"/person/{pid}/letters").json()["items"]
        keepsakes = [l for l in letters if l["kind"] == "keepsake"]
        assert len(keepsakes) == 1          # 不重复：needs_care 优先，不并出词条
        k = keepsakes[0]
        assert k["entry"] is False           # 倾诉来信不是词条
        assert k["primary_need"] == "soothed"


# ---------------------------------------------------------------------------
# 接线：闲聊记忆写回（§6 双存——"继续昨天"能拿到随聊摘要）
# ---------------------------------------------------------------------------


def test_chat_writeback_saves_summary(client):
    """随聊也写回会话摘要（不再只认咨询结论），供首页"继续昨天"。"""
    pid = _create_person(client)
    r = client.post("/chat", json={"person_id": pid, "message": "今天好难过，想哭"})
    assert r.status_code == 200
    assert r.json()["written_back"] is False  # 无占星结论 → 不算咨询写回

    garden = client.get(f"/garden?person_id={pid}").json()
    continue_from = garden.get("continue_from")
    assert continue_from is not None
    assert continue_from.get("summary")  # 随聊摘要在"继续昨天"里可见
    assert "好难过" in continue_from["summary"]


# ---------------------------------------------------------------------------
# 触发行动（§4.2 +20）：级数行动门槛 + 行动回报接线
# ---------------------------------------------------------------------------


def test_level_gate_action_threshold():
    """级数 = 分数 + 行动双重门槛（2026-08-10 定稿）：
    深度分定"数值档位"，行动次数定"上限"——没真做过事，聊再多也到不了 4 级。
    """
    lvl = _level_for_depth
    # 数值档位（0 次行动时上限 3 级）
    assert lvl(0, 0) == 0
    assert lvl(2, 0) == 1       # 1-2 → Ⅰ
    assert lvl(9, 0) == 2       # 3-9 → Ⅱ
    assert lvl(29, 0) == 3      # 10-29 → Ⅲ
    assert lvl(30, 0) == 3      # 30 分但 0 行动 → 卡在 Ⅲ（聊了 N 次却没真的做）
    assert lvl(100, 0) == 3     # 100 分但 0 行动 → 仍卡 Ⅲ
    # 1 次行动 → 上限 4 级
    assert lvl(30, 1) == 4      # 30 分 + 1 次行动 → Ⅳ
    assert lvl(99, 1) == 4
    assert lvl(100, 1) == 4     # 100 分但只 1 次行动 → 卡 Ⅳ
    # 2 次行动 → 上限 5 级
    assert lvl(100, 2) == 5     # 100 分 + 2 次行动 → Ⅴ
    assert lvl(30, 2) == 4      # 分数不够，行动再多也按分数档（min）
    assert lvl(29, 5) == 3      # 分数挡在 Ⅲ，行动次数不越级
    assert lvl(0, 99) == 0      # 未点亮永远是 0（行动不能点亮未聊过的子类）


def test_grid_includes_action_count_and_gate():
    """grid 出 action_count；级数行动门槛随 action_counts 生效（缺省=旧行为）。"""
    profile = ChartProfile(person_id="p")
    FragmentService.light(profile, ["moon_tide"], depth=DEPTH_CONSULT)          # 10 → 档 3
    FragmentService.light(profile, ["sun_core"], depth=DEPTH_CONSULT * 3)       # 30 → 档 4
    by_id = {
        f["id"]: f
        for f in FragmentService.grid(
            profile, action_counts={"sun_core": 1},
        )
    }
    assert by_id["moon_tide"]["action_count"] == 0
    assert by_id["moon_tide"]["level"] == 3
    assert by_id["sun_core"]["action_count"] == 1
    assert by_id["sun_core"]["level"] == 4     # 30 分 + 1 次行动 → Ⅳ
    # 同一 profile 不传 action_counts（旧调用方）→ action_counts 视为空 → 升顶门槛生效：
    # 30 分但 0 行动 → 卡 Ⅲ（这正是"聊了 N 次却没真的做"的叙事，非旧行为）
    old = {f["id"]: f for f in FragmentService.grid(profile)}
    assert old["sun_core"]["action_count"] == 0
    assert old["sun_core"]["level"] == 3


def test_chat_action_report_lights_previous_session(client):
    """触发行动（§4.2 +20）：上一段会话聊过 → 新会话回报"我做到了" → 补 +20。

    目标 = 上一段会话点亮的子类（账本 session_id 精确回溯，不靠时间边界）。
    上一段用完整咨询（+10）铺底 → 行动 +20 后正好 30 分 + 1 次行动 → 打开 Ⅳ 级
    （"真去做一次"比"随口聊 20 次"更珍贵：20 分只停 Ⅲ）。
    """
    pid = _create_person(client)
    # 上一段会话（不同 session）：完整事业咨询反向点亮 house10_career / sun_core / saturn_order（+10）
    r1 = client.post("/chat", json={
        "person_id": pid, "message": "我该不该换工作", "session_id": "sess_act_prev",
    })
    assert r1.status_code == 200
    prev_lit = set(r1.json()["lit_fragments"])
    assert "house10_career" in prev_lit

    # 新会话回报行动完成
    r2 = client.post("/chat", json={
        "person_id": pid, "message": "我做到了，我真的去做了", "session_id": "sess_act_now",
    })
    assert r2.status_code == 200
    data = r2.json()
    assert data["actioned_fragments"], "行动回报应点亮上一段会话的子类"
    assert prev_lit.issubset(set(data["actioned_fragments"]))

    # 深度：上一段子类 +20（账本 kind=action 一条）；10+20=30 分 + 1 行动 → 打开 Ⅳ 级
    grid = client.get(f"/person/{pid}/fragments").json()["fragments"]
    by_id = {f["id"]: f for f in grid}
    for fid in prev_lit:
        assert by_id[fid]["depth"] == DEPTH_CONSULT + DEPTH_ACTION, fid
        assert by_id[fid]["action_count"] == 1, fid
        assert by_id[fid]["level"] == 4, fid

    store = client.app.state.store
    actions = [l for l in store.list_fragment_lights(pid) if l.kind == "action"]
    assert len(actions) == len(prev_lit)
    assert all(l.delta == DEPTH_ACTION for l in actions)
    assert all(l.session_id for l in actions), "行动账本必须盖章所属会话"


def test_chat_action_same_session_prior_turns(client):
    """同一段会话里：先聊 → 再行动回报，目标含本会话更早轮次点亮的子类。"""
    pid = _create_person(client)
    sid = "sess_act_same"
    r1 = client.post("/chat", json={
        "person_id": pid, "message": "工作压力好大，想辞职", "session_id": sid,
    })
    assert r1.status_code == 200
    lit1 = set(r1.json()["lit_fragments"])
    assert lit1

    r2 = client.post("/chat", json={
        "person_id": pid, "message": "我辞职了", "session_id": sid,
    })
    assert r2.status_code == 200
    data = r2.json()
    assert data["actioned_fragments"]
    assert lit1.issubset(set(data["actioned_fragments"]))

    grid = client.get(f"/person/{pid}/fragments").json()["fragments"]
    by_id = {f["id"]: f for f in grid}
    for fid in lit1:
        assert by_id[fid]["depth"] >= DEPTH_OUTPOURING + DEPTH_ACTION, fid


def test_chat_action_no_prior_light_no_action(client):
    """从没聊过 → 首条"我做到了"不点亮（不能对没聊过的子类行动）。"""
    pid = _create_person(client)
    r = client.post("/chat", json={"person_id": pid, "message": "我做到了！"})
    assert r.status_code == 200
    assert r.json()["actioned_fragments"] == []

    grid = client.get(f"/person/{pid}/fragments").json()["fragments"]
    assert all(f["action_count"] == 0 for f in grid)
    store = client.app.state.store
    assert not [l for l in store.list_fragment_lights(pid) if l.kind == "action"]


def test_chat_not_action_no_light(client):
    """"还没做到/犹豫"不是行动回报：宁缺毋滥，不补 +20、账本无 action。"""
    pid = _create_person(client)
    client.post("/chat", json={
        "person_id": pid, "message": "最近总是很难过", "session_id": "sess_na_prev",
    })
    r = client.post("/chat", json={
        "person_id": pid, "message": "我还没做到，还在犹豫", "session_id": "sess_na_now",
    })
    assert r.status_code == 200
    assert r.json()["actioned_fragments"] == []

    grid = client.get(f"/person/{pid}/fragments").json()["fragments"]
    assert all(f["action_count"] == 0 for f in grid)
    store = client.app.state.store
    assert not [l for l in store.list_fragment_lights(pid) if l.kind == "action"]


def test_fragments_endpoint_includes_action_count(client):
    """GET /fragments 出 action_count 字段（升顶门槛的前端原料）。"""
    pid = _create_person(client)
    client.post("/chat", json={"person_id": pid, "message": "最近总是很难过"})
    grid = client.get(f"/person/{pid}/fragments").json()["fragments"]
    assert all("action_count" in f for f in grid)
    assert all(f["action_count"] == 0 for f in grid)   # 无行动 → 全 0
