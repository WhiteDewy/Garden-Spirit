"""Fernet 加密密钥轮换脚本 —— 换密钥但数据不丢。

流程（标准轮换）：
1. 生成新密钥：`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
2. 把**新**密钥写进 `GS_ENCRYPTION_KEY`，**旧**密钥写进 `GS_OLD_ENCRYPTION_KEYS`（逗号分隔）。
   此刻服务照常可读写：新数据用新密钥，旧密文用旧密钥解（keyring 逐个尝试）。
3. 跑本脚本把库里所有旧密文重加密为新密钥：
       python scripts/rotate_key.py ./data/garden_spirit.db --dry-run   # 先预览
       python scripts/rotate_key.py ./data/garden_spirit.db             # 正式执行
   正式执行前自动备份 `{db}.bak.{时间戳}`。
4. 撤下旧密钥：清空 `GS_OLD_ENCRYPTION_KEYS`，重启服务。

安全：操作不可逆（备份可回滚）。dry-run 只打印计数，不写库。
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
import time

# 可独立运行：`python scripts/rotate_key.py ...`（把项目根目录加进 sys.path）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from foundation.database.encryption import (  # noqa: E402
    ENV_KEY_NAME,
    OLD_KEYS_ENV_NAME,
    Encryptor,
    _parse_old_keys,
)


def _collect_encrypted_columns(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """所有 (表, 加密列)：列名以 _enc / _encrypted 结尾（persons 表用 _encrypted）。"""
    tables = [
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    out: list[tuple[str, str]] = []
    for table in tables:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        for col in cols:
            if col.endswith("_enc") or col.endswith("_encrypted"):
                out.append((table, col))
    return out


def _normalize_key_args(argv: list[str]) -> list[str]:
    """允许 Fernet key 以 '-' 开头时仍可作为 option 参数被 argparse 解析。"""
    key_options = {"--current-key", "--old-keys"}
    known_options = key_options | {"--dry-run", "-h", "--help"}
    normalized: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in key_options and i + 1 < len(argv) and argv[i + 1] not in known_options:
            normalized.append(f"{arg}={argv[i + 1]}")
            i += 2
            continue
        normalized.append(arg)
        i += 1
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-encrypt all Fernet columns with the new key", allow_abbrev=False)
    parser.add_argument("database_path", help="SQLite database file path")
    parser.add_argument("--dry-run", action="store_true", help="只打印计数，不写库")
    parser.add_argument("--current-key", default="", help="新密钥（默认取 GS_ENCRYPTION_KEY）")
    parser.add_argument("--old-keys", default="", help="旧密钥逗号分隔（默认取 GS_OLD_ENCRYPTION_KEYS）")
    args = parser.parse_args(_normalize_key_args(sys.argv[1:]))

    new_key = args.current_key or os.getenv(ENV_KEY_NAME, "")
    old_keys = _parse_old_keys(args.old_keys or os.getenv(OLD_KEYS_ENV_NAME, ""))
    if not new_key:
        print(f"ERROR: 未提供新密钥（--current-key 或 {ENV_KEY_NAME}）", file=sys.stderr)
        return 2
    if not old_keys:
        print(f"ERROR: 未提供旧密钥（--old-keys 或 {OLD_KEYS_ENV_NAME}）", file=sys.stderr)
        return 2

    decryptor = Encryptor(key=new_key, old_keys=old_keys)  # [新, *旧] 可解全部
    writer = Encryptor(key=new_key)                         # 只用新密钥加密
    print(f"新密钥: {new_key[:16]}…")
    print(f"旧密钥数: {len(old_keys)}")

    conn = sqlite3.connect(args.database_path)
    conn.row_factory = sqlite3.Row
    # 生产并发：重加密可能跑在线上库，锁时等待而不是立刻报错
    conn.execute("PRAGMA journal_mode=WAL").fetchone()
    conn.execute("PRAGMA busy_timeout=5000")
    columns = _collect_encrypted_columns(conn)
    if not columns:
        print("未发现加密列，退出。")
        conn.close()
        return 0

    per_table: dict[str, int] = {}
    failed: list[tuple[str, int, str, str]] = []
    for table, col in columns:
        rows = conn.execute(f'SELECT rowid, "{col}" AS c FROM "{table}"').fetchall()
        for row in rows:
            raw = row["c"]
            if not raw:
                continue  # 从未写入的默认空串，跳过
            try:
                plaintext = decryptor.decrypt(raw)
                reenc = writer.encrypt(plaintext)
            except ValueError as exc:
                failed.append((table, row["rowid"], col, str(exc)))
                continue
            per_table[table] = per_table.get(table, 0) + 1
            if not args.dry_run:
                conn.execute(f'UPDATE "{table}" SET "{col}" = ? WHERE rowid = ?', (reenc, row["rowid"]))

    if not args.dry_run:
        backup = f"{args.database_path}.bak.{time.strftime('%Y%m%d%H%M%S')}"
        shutil.copy2(args.database_path, backup)
        conn.commit()
        print(f"已备份到: {backup}")

    print("\n重加密统计:")
    for table, count in sorted(per_table.items()):
        print(f"  {table:<20} {count:>6} 行")
    total = sum(per_table.values())
    print(f"  {'合计':<20} {total:>6} 行")
    print(f"  {'失败':<20} {len(failed):>6} 行")
    for table, rowid, col, err in failed[:10]:
        print(f"  ✗ {table}#{rowid} ({col}): {err}", file=sys.stderr)

    conn.close()
    if args.dry_run:
        print("\n[dry-run] 未写库。确认无误后去掉 --dry-run 正式执行。")
    else:
        print("\n完成。请清空 GS_OLD_ENCRYPTION_KEYS 后重启服务（旧密钥撤下）。")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
