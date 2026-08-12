"""SQLite 一致性备份脚本 —— VACUUM INTO 生成单文件快照。

直接 cp 在 WAL 模式下可能拿到不一致快照（已提交数据还在 .db-wal 里，.db 是
旧 checkpoint）。`VACUUM INTO` 由 SQLite 引擎在内部事务里做 checkpoint + 复制，
结果天然一致：单文件、可直接换库恢复。

用法：
    python scripts/backup_db.py
        # 备份 ./data/garden_spirit.db → ./data/backups/garden_spirit.<时间戳>.db
    python scripts/backup_db.py <db> [--out <dest>]   # 指定源库与输出路径

建议放进 cron 每日一次（如 03:17 错峰）：
    python scripts/backup_db.py
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time

# 可独立运行：`python scripts/backup_db.py`（把项目根目录加进 sys.path）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_DB = "./data/garden_spirit.db"


def main() -> int:
    parser = argparse.ArgumentParser(description="SQLite 一致性备份（VACUUM INTO）")
    parser.add_argument("database_path", nargs="?", default=DEFAULT_DB, help="源库路径")
    parser.add_argument("--out", default="", help="备份目标路径（默认 data/backups/ 下带时间戳）")
    args = parser.parse_args()

    db = args.database_path
    if not os.path.exists(db):
        print(f"ERROR: 源库不存在: {db}", file=sys.stderr)
        return 2

    out = args.out
    if not out:
        ts = time.strftime("%Y%m%d_%H%M%S")
        base = os.path.basename(db)
        out = os.path.join(
            os.path.dirname(os.path.abspath(db)) or ".", "backups", f"{base}.{ts}.db"
        )
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    if os.path.exists(out):
        print(f"ERROR: 目标已存在，拒绝覆盖: {out}（换 --out）", file=sys.stderr)
        return 2

    try:
        src = sqlite3.connect(db)
        try:
            src.execute("PRAGMA busy_timeout=5000")  # 备份时源库被写 → 等待而非立刻失败
            src.execute(f"VACUUM INTO '{out}'")
        finally:
            src.close()
    except sqlite3.Error as exc:
        print(f"ERROR: 备份失败: {exc}", file=sys.stderr)
        return 1

    size_kb = os.path.getsize(out) / 1024
    print(f"已备份: {out}（{size_kb:.1f} KB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
