"""每日推送触发脚本 —— 供外部 cron 调度。

调用后端 /push/trigger，让星灵在用户没打开 app 时也能把"今日来信"推出去。
只依赖 stdlib（urllib），无需额外依赖。

用法：
    python scripts/push_daily.py [--base-url http://127.0.0.1:8756]

cron 示例（每天早上 8 点）：
    0 8 * * * cd /path/to/garden-spirit && python scripts/push_daily.py >> logs/push.log 2>&1

安全：/push/trigger 会遍历全量用户并发推送，生产须限制该端点只能内网/
localhost 访问（防火墙或反向代理白名单），脚本从本机调用。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description="Trigger daily push notifications")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8756",
        help="Garden-Spirit API base URL (default: http://127.0.0.1:8756)",
    )
    args = parser.parse_args()

    url = f"{args.base_url.rstrip('/')}/push/trigger"
    try:
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        print(f"ERROR: 无法连接 {url}: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - 脚本出口明确报错
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("推送触发结果:")
    print(f"  总用户:     {result.get('total_persons', 0)}")
    print(f"  跳过(quiet):{result.get('skipped_quiet', 0)}")
    print(f"  跳过(无订阅):{result.get('skipped_no_sub', 0)}")
    print(f"  已推送:     {result.get('pushed', 0)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
