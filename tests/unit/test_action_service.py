"""行动层测试（B2 L6）：待验证清单 + 偏好控制。

验证：
- is_unverified：用户没反馈 且 没被事件验过 → 待验证
- findings_status：每条判断带 status/domain/event_verified 的结构
- pending_count：只数未验证的
- preferences：默认补全 / 校验 / 部分更新合并
"""

import pytest

from shared.models import ChartProfile, VerifiedFinding

from application.action.service import ActionService

SVC = ActionService()


def _profile(findings: list[VerifiedFinding] | None = None) -> ChartProfile:
    p = ChartProfile(person_id="p1")
    p.verified_findings = list(findings or [])
    return p


def _finding(statement: str, fid: str = "f1", *, feedback: str = "", notes: list[str] | None = None,
             domain: str = "career", confidence: float = 0.6) -> VerifiedFinding:
    return VerifiedFinding(
        id=fid, statement=statement, confidence=confidence,
        user_feedback=feedback, verification_notes=list(notes or []),
        domain=domain,
    )


# --- 待验证判断 ---


def test_is_unverified():
    assert SVC.is_unverified(_finding("土星落九宫")) is True
    # 用户反馈过 → 已验证
    assert SVC.is_unverified(_finding("土星落九宫", feedback="confirmed")) is False
    assert SVC.is_unverified(_finding("土星落九宫", feedback="refuted")) is False
    # 被事件验过 → 已验证
    assert SVC.is_unverified(_finding("土星落九宫", notes=["2026-08-06 事件「留学」验证通过"])) is False
    # 两者都有 → 已验证
    assert SVC.is_unverified(_finding("土星落九宫", feedback="confirmed", notes=["…"])) is False


def test_findings_status_enriches():
    items = SVC.findings_status(_profile([
        _finding("月亮落7宫", fid="a"),
        _finding("土星落9宫", fid="b", feedback="confirmed"),
        _finding("金星落10宫", fid="c", notes=["事件验证"]),
    ]))
    assert [i["status"] for i in items] == ["unverified", "verified", "verified"]
    assert items[0]["domain"] == "career"
    assert items[0]["event_verified"] is False
    assert items[1]["feedback"] == "confirmed"
    assert items[2]["event_verified"] is True


def test_findings_status_none_profile():
    assert SVC.findings_status(None) == []


def test_pending_count():
    assert SVC.pending_count(_profile([
        _finding("a", fid="1"),                              # 待验证
        _finding("b", fid="2", feedback="confirmed"),        # 已验证
        _finding("c", fid="3", notes=["事件"]),              # 已验证
    ])) == 1
    assert SVC.pending_count(None) == 0


# --- 偏好 ---


def test_preferences_default_fills_missing():
    got = SVC.preferences(_profile())
    assert got["push_frequency"] == "daily"
    assert got["sensitive_topics"] == []
    assert got["preferred_persona"] == ""


def test_preferences_stored_overrides_default():
    p = _profile()
    p.preferences = {"push_frequency": "quiet"}
    got = SVC.preferences(p)
    assert got["push_frequency"] == "quiet"
    assert got["sensitive_topics"] == []  # 未设置仍补默认


def test_validate_preferences_valid():
    cleaned = SVC.validate_preferences({
        "push_frequency": "off",
        "sensitive_topics": ["health", "家庭"],
        "preferred_persona": "moon",  # 10 星灵回归：行星人格值（sun/moon/…）
    })
    assert cleaned["push_frequency"] == "off"
    assert cleaned["sensitive_topics"] == ["health", "家庭"]
    assert cleaned["preferred_persona"] == "moon"


def test_validate_preferences_invalid():
    with pytest.raises(ValueError):
        SVC.validate_preferences({"push_frequency": "every_hour"})
    with pytest.raises(ValueError):
        SVC.validate_preferences({"preferred_persona": "not_a_persona"})
    with pytest.raises(ValueError):
        SVC.validate_preferences({"sensitive_topics": ["ok", 123]})
    with pytest.raises(ValueError):
        SVC.validate_preferences({"sensitive_topics": [" ", "  "]})  # 空白不算


def test_validate_preferences_ignores_unknown_keys():
    cleaned = SVC.validate_preferences({"push_frequency": "quiet", "hack": "x"})
    assert "hack" not in cleaned
    assert cleaned["push_frequency"] == "quiet"
