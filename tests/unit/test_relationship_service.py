"""A2 关系层单元测试：信任度量 + 自我介绍 + 邀请式引导。

验证：
- 等级阈值（分数 → 陌生/认识/信任/深交）
- 深度优先：一次深聊 > 十次闲聊
- record_consult / record_journal / record_finding_feedback 的权重与信号计数
- opening_message：首次见面自我介绍 / 老用户欢迎回来 / 等级前缀
- invitation：信任达标才返回，未达标为 None
"""

from datetime import datetime, timedelta, timezone

from shared.enums import ConsultMode, TrustLevel
from shared.models import ChartProfile

from application.relationship.service import RelationshipService


def _profile(score: float = 0.0, signals: dict | None = None) -> ChartProfile:
    p = ChartProfile(person_id="p1")
    p.trust_score = score
    p.trust_signals = dict(signals or {})
    return p


# --- 等级阈值 ---


def test_level_thresholds():
    assert RelationshipService.level_for_score(0) is TrustLevel.STRANGER
    assert RelationshipService.level_for_score(2.9) is TrustLevel.STRANGER
    assert RelationshipService.level_for_score(3) is TrustLevel.ACQUAINTANCE
    assert RelationshipService.level_for_score(9.9) is TrustLevel.ACQUAINTANCE
    assert RelationshipService.level_for_score(10) is TrustLevel.TRUSTED
    assert RelationshipService.level_for_score(19.9) is TrustLevel.TRUSTED
    assert RelationshipService.level_for_score(20) is TrustLevel.INTIMATE
    assert RelationshipService.level_for_score(99) is TrustLevel.INTIMATE


def test_level_none_profile_is_stranger():
    assert RelationshipService().level(None) is TrustLevel.STRANGER


def test_trust_label_zh():
    svc = RelationshipService()
    assert svc.trust_label(_profile(score=0)) == "陌生"
    assert svc.trust_label(_profile(score=5)) == "认识"
    assert svc.trust_label(_profile(score=15)) == "信任"
    assert svc.trust_label(_profile(score=25)) == "深交"


# --- 信任信号权重 ---


def test_depth_first_one_deep_beats_ten_casual():
    """深度优先核心：一次深聊（+6）> 十次闲聊（10×0.5=5）。"""
    svc = RelationshipService()
    deep = _profile()
    svc.record_consult(deep, mode=ConsultMode.DEEP)

    casual = _profile()
    for _ in range(10):
        svc.record_consult(casual, casual=True)

    assert deep.trust_score > casual.trust_score


def test_record_consult_modes():
    svc = RelationshipService()

    deep = _profile()
    svc.record_consult(deep, mode=ConsultMode.DEEP)
    assert deep.trust_score == 6.0
    assert deep.trust_signals == {"deep_consult": 1}

    quick = _profile()
    svc.record_consult(quick, mode=ConsultMode.QUICK)
    assert quick.trust_score == 2.0
    assert quick.trust_signals == {"quick_consult": 1}

    casual = _profile()
    svc.record_consult(casual, casual=True)
    assert casual.trust_score == 0.5
    assert casual.trust_signals == {"casual_chat": 1}


def test_record_consult_accepts_bare_string_mode():
    """mode 传裸字符串 "quick"（前端语义）也能正确区分。"""
    svc = RelationshipService()
    p = _profile()
    svc.record_consult(p, mode="quick")
    assert p.trust_score == 2.0
    assert p.trust_signals == {"quick_consult": 1}


def test_record_consult_default_mode_is_deep():
    p = _profile()
    RelationshipService().record_consult(p, mode=None)
    assert p.trust_score == 6.0
    assert p.trust_signals == {"deep_consult": 1}


def test_record_journal():
    p = _profile()
    RelationshipService().record_journal(p)
    assert p.trust_score == 3.0
    assert p.trust_signals == {"journal": 1}


def test_record_finding_feedback():
    svc = RelationshipService()

    confirmed = _profile()
    svc.record_finding_feedback(confirmed, "confirmed")
    assert confirmed.trust_score == 4.0
    assert confirmed.trust_signals == {"finding_confirmed": 1}

    refuted = _profile()
    svc.record_finding_feedback(refuted, "refuted")
    assert refuted.trust_score == 1.0  # 反驳也是认真互动
    assert refuted.trust_signals == {"finding_refuted": 1}


def test_signals_accumulate_without_float_drift():
    p = _profile()
    svc = RelationshipService()
    for _ in range(3):
        svc.record_consult(p, casual=True)
    assert p.trust_score == 1.5
    assert p.trust_signals == {"casual_chat": 3}


# --- 自我介绍 / 欢迎回来 ---


def test_opening_first_meeting_intro():
    """无画像或尚无任何信号 → 自我介绍（"我是谁/能做什么/怎么用"）。"""
    svc = RelationshipService()
    intro = svc.opening_message(None, person_name="小明")
    assert "星灵" in intro
    assert "星盘" in intro

    intro2 = svc.opening_message(_profile(), person_name="小明")
    assert "星灵" in intro2


def test_opening_welcome_back():
    svc = RelationshipService()
    p = _profile(score=6.0, signals={"deep_consult": 1})
    opening = svc.opening_message(
        p, person_name="小明", continue_from={"summary": "关于离职的抉择"}
    )
    assert "欢迎回来" in opening
    assert "小明" in opening
    assert "离职" in opening  # 上次聊到…


def test_opening_intimate_prefix():
    p = _profile(score=20.0, signals={"deep_consult": 4})
    opening = RelationshipService().opening_message(p, person_name="小明")
    assert "老朋友" in opening


def test_opening_trusted_prefix():
    p = _profile(score=12.0, signals={"deep_consult": 2})
    opening = RelationshipService().opening_message(p, person_name="小明")
    assert "我们聊过几回了" in opening


def test_opening_returning_user_with_day_gap():
    """老用户 + 上次对话 9 天前 → 天数缺口钩子（"已经 9 天没来找我"）。"""
    p = _profile(score=6.0, signals={"deep_consult": 1})
    opened_at = datetime.now(timezone.utc) - timedelta(days=9)
    opening = RelationshipService().opening_message(
        p,
        person_name="小明",
        continue_from={"started_at": opened_at.isoformat(), "summary": "关于离职的抉择"},
    )
    assert "9 天没来找我" in opening
    assert "小明" in opening
    assert "离职" in opening  # 上次聊到…仍保留


def test_opening_returning_user_same_day():
    """老用户同天再聊 → "我们又见面了"（不刻意提天数）。"""
    p = _profile(score=6.0, signals={"deep_consult": 1})
    opening = RelationshipService().opening_message(
        p,
        person_name="小明",
        continue_from={"started_at": datetime.now(timezone.utc).isoformat()},
    )
    assert "我们又见面了" in opening
    assert "小明" in opening


def test_opening_returning_user_without_timestamp():
    """老用户但拿不到上次时间 → 兜底"欢迎回来"。"""
    p = _profile(score=6.0, signals={"deep_consult": 1})
    opening = RelationshipService().opening_message(
        p, person_name="小明", continue_from={"summary": "关于离职的抉择"}
    )
    assert "欢迎回来" in opening


def test_opening_naturalizes_legacy_transcript_summary():
    """旧数据摘要可能是「用户:/星灵:」转写——开场只该露出用户话题，不 dump 整段对话。

    回归：用户反馈"上次我们聊到「用户: 最近在看九门 星灵: 你现在的状态…」"很丑。
    """
    p = _profile(score=6.0, signals={"deep_consult": 1})
    legacy = (
        "用户: 最近在看九门\n"
        "星灵: 你现在的状态听起来很平静，像在慢慢翻着一本旧书。九门这个词，让我想到那"
    )
    opening = RelationshipService().opening_message(
        p, person_name="夏天", continue_from={"summary": legacy}
    )
    assert "最近在看九门" in opening          # 用户话题保留
    assert "用户:" not in opening           # 标签不再漏出
    assert "星灵:" not in opening           # 回复正文不再漏出
    assert "上次我们聊到「最近在看九门」" in opening


def test_naturalize_recall_keeps_last_user_topic():
    """多轮转写 → 取最后一条用户话题；外层引号剥掉；结尾标点收敛。"""
    from application.relationship.service import naturalize_recall

    transcript = "用户: 你好\n星灵: 你好呀\n用户: 我该不该离职\n星灵: 土星落九宫…"
    assert naturalize_recall(transcript) == "我该不该离职"

    assert naturalize_recall("「关于离职的抉择」。") == "关于离职的抉择"
    assert naturalize_recall("《九门》那部剧，你说看的时候很平静。") == "《九门》那部剧，你说看的时候很平静"
    assert naturalize_recall("") == ""
    assert naturalize_recall(None) == ""


# --- 邀请式引导 ---


def test_invitation_at_trusted_or_above():
    svc = RelationshipService()
    assert svc.invitation(_profile(score=10.0)) is not None
    assert svc.invitation(_profile(score=20.0)) is not None
    assert "细看" in svc.invitation(_profile(score=15.0))


def test_invitation_none_below_trusted():
    svc = RelationshipService()
    assert svc.invitation(_profile(score=0)) is None
    assert svc.invitation(_profile(score=2.9)) is None
    assert svc.invitation(_profile(score=9.9)) is None
    assert svc.invitation(None) is None
