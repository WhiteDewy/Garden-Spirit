"""地名 → 经纬度 + 时区 解析测试。

验证：
- 静态表：中文名/拼音/模糊包含匹配
- 未匹配 → None（调用方负责 422，禁止静默降级）
- 时区推导：中国大陆/台湾/香港/海外
- manual_location 精确路径
- 高德路径无 key 时优雅回退（不打网络）
"""

import pytest

from foundation.astronomy.geocoding import (
    geocode,
    infer_timezone,
    manual_location,
)


@pytest.fixture(autouse=True)
def _offline_amap(monkeypatch):
    """显式离线：GS_GEOCODE_OFFLINE=1 跳过高德——测试不依赖网络与 key。

    高德会把垃圾地址也模糊解析出结果，导致"未知→None"断言失效。
    在线路径（source=amap）由集成验证覆盖，不在这里测网络。
    """
    monkeypatch.setenv("GS_GEOCODE_OFFLINE", "1")


def test_static_exact_chinese():
    r = geocode("上海")
    assert r is not None and r.latitude == 31.2304 and r.longitude == 121.4737
    assert r.timezone_name == "Asia/Shanghai"
    assert r.source == "static_table"


def test_static_exact_pinyin():
    r = geocode("beijing")
    assert r is not None
    assert r.latitude == 39.9042 and r.timezone_name == "Asia/Shanghai"


def test_static_fuzzy_contains():
    r = geocode("上海市浦东新区")
    assert r is not None
    assert r.place_name == "上海"


def test_unknown_place_returns_none():
    """未知城市 → None（不做任意猜测）。"""
    assert geocode("不存在的城市xyz") is None


def test_empty_place_returns_fallback():
    fallback = manual_location(1.0, 2.0, "UTC")
    assert geocode("", fallback=fallback) is fallback


def test_unknown_place_returns_fallback():
    fallback = manual_location(1.0, 2.0, "UTC")
    assert geocode("不存在的城市xyz", fallback=fallback) is fallback


# --- 时区推导 ---

def test_tz_mainland():
    assert infer_timezone(country="中国", province="浙江省") == "Asia/Shanghai"


def test_tz_taiwan_hk_macau():
    assert infer_timezone(country="中国", province="台湾") == "Asia/Taipei"
    assert infer_timezone(country="中国", province="香港") == "Asia/Hong_Kong"
    assert infer_timezone(country="中国", province="澳门") == "Asia/Macau"


def test_tz_overseas():
    assert infer_timezone(country="日本", province="东京都") == "Asia/Tokyo"
    assert infer_timezone(country="英国", province="伦敦") == "Europe/London"
    assert infer_timezone(country="未知国", province="") == "UTC"


def test_manual_location():
    r = manual_location(39.9, 116.4, "Asia/Shanghai")
    assert r.latitude == 39.9 and r.timezone_name == "Asia/Shanghai"
    assert r.source == "manual"
