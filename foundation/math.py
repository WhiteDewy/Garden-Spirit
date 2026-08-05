"""天文/占星数学工具。纯函数，无状态。"""

import math

FULL_CIRCLE = 360.0
HALF_CIRCLE = 180.0


def normalize_degree(deg: float) -> float:
    """归一到 0-360。"""
    return deg % FULL_CIRCLE


def normalize_180(deg: float) -> float:
    """归一到 -180..+180。"""
    deg = deg % FULL_CIRCLE
    if deg > HALF_CIRCLE:
        deg -= FULL_CIRCLE
    return deg


def signed_angle_diff(a: float, b: float) -> float:
    """a 到 b 的最短有向角度差（-180..+180）。"""
    return normalize_180(b - a)


def angular_distance(a: float, b: float) -> float:
    """两黄经的最短角距（0..180）。"""
    return abs(signed_angle_diff(a, b))


def degrees_to_dms(deg: float) -> tuple[int, int, float]:
    """十进制度数 → (度, 分, 秒)。"""
    d = int(deg)
    m_float = (deg - d) * 60.0
    m = int(m_float)
    s = (m_float - m) * 60.0
    return d, m, s


def dms_to_degrees(d: int, m: int, s: float) -> float:
    """(度, 分, 秒) → 十进制度数。"""
    return d + m / 60.0 + s / 3600.0


def sign_index(absolute_degree: float) -> int:
    """黄经 → 星座序号 0-11（0=白羊）。"""
    return int(absolute_degree // 30.0) % 12


def degree_in_sign(absolute_degree: float) -> float:
    """黄经 → 星座内度数 0-30。"""
    return absolute_degree % 30.0


def is_orb_applicable(current: float, exact: float, orb: float) -> bool:
    """判断是否在容许度内（用于相位检测）。"""
    return angular_distance(current, exact) <= orb


def interpolate(x0: float, y0: float, x1: float, y1: float, x: float) -> float:
    """线性插值。"""
    if x1 == x0:
        return y0
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def clamp(value: float, lo: float, hi: float) -> float:
    """限幅。"""
    return max(lo, min(hi, value))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """两点地表距离（km），用于城市匹配。"""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
