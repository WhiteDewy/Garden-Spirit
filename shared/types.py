"""类型别名，保证跨层签名一致性。

只定义别名，不含逻辑。"""

from datetime import datetime
from typing import Any

# 儒略日数（pyswisseph 内部时间格式）
JulianDay = float

# 黄道经度 0.0 - 360.0
Degree = float

# 地理坐标
Latitude = float
Longitude = float
Altitude = float  # 米

# UTC 时间戳
UtcTimestamp = datetime

# 置信度 0.0 - 1.0
Confidence = float

# 权重（证据权值，可为负）
Weight = float

# 唯一标识
EntityId = str

# JSON 可序列化字典（LLM 边界用）
JsonDict = dict[str, Any]
