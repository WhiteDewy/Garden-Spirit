---
name: restart
description: 彻底重启 Garden-Spirit 前后端开发服务：先杀掉所有旧进程（按端口持有者 + 全部 python/node 进程树双路清理，循环验证直至端口释放），再启动 FastAPI 与 uni-app H5 并验证健康检查/端口。
---

# Garden-Spirit Restart Skill

用于用户要求重启 / 重新拉起 / 刷新 Garden-Spirit 前后端开发服务时。

## 项目信息

- 根目录：`C:\Users\PC\Desktop\red\Garden-Spirit`
- 后端：FastAPI，入口 `application.api.main:app`（文件底部 `app = create_app()`）
- 后端地址：`http://127.0.0.1:8756`，健康检查 `GET /health`（返回 `{"status": "ok", ...}`）
- 后端启动：`python -m uvicorn application.api.main:app --host 127.0.0.1 --port 8756 --reload`（须在项目根目录，`application` 包才可导入）
- 前端：uni-app H5，位于 `frontend/`
- 前端地址：`http://localhost:5173`（注意用 localhost，不是 127.0.0.1）
- 前端启动：`cd frontend && npm run dev:h5`（即 `uni`，dev 端口 5173）
- 前端环境：`frontend/.env.development` → `VITE_API_BASE=http://127.0.0.1:8756`
- Python：直接用 `python`（本机解析到带 uvicorn 的真实解释器）；若 `python -c "import uvicorn"` 失败，改用 `py -3 -m uvicorn` 或先确认环境
- 日志：后端 `data/backend.log`，前端 `data/frontend.log`

## 原则

每次重启**必须**：
1. 先彻底杀掉所有旧进程（含 `--reload` 的 reloader 父进程 + worker 子进程、被杀后仍短暂占端口的僵尸 socket）；
2. **确认 8756/5173/5174 三个端口全部释放后再启动**；
3. 启动后必须验证：后端 `/health` 返回 `status: ok`，前端 5173 端口监听、`http://localhost:5173` 可访问。

## 执行步骤

### 1. 杀掉所有旧进程（循环彻底清理）

`uvicorn --reload` 会派生 reloader 父进程 + worker 子进程：只杀子进程父进程会再拉起；且进程被杀后端口可能短暂残留。因此按「端口持有者 → 全部 python/node 进程树 → 循环重试」三层清理，**最多 8 轮，直到端口确认释放**：

```bash
powershell.exe -NoProfile -Command '
$ports=@(8756,5173,5174)

function Kill-PortOwners {
    Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $ports -contains $_.LocalPort } |
        ForEach-Object {
            $procId=$_.OwningProcess
            if ($procId -gt 0) {
                taskkill /PID $procId /T /F 2>$null | Out-Null
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }
        }
}

function Kill-DevTrees {
    Get-Process python*,pythonw*,node* -ErrorAction SilentlyContinue |
        ForEach-Object { taskkill /PID $_.Id /T /F 2>$null | Out-Null }
}

for ($i=1; $i -le 8; $i++) {
    Kill-PortOwners
    $left=@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $ports -contains $_.LocalPort })
    if ($left.Count -eq 0) { Write-Host "[$i] All target ports free"; exit 0 }
    Write-Host "[$i] Ports still bound, force-killing all python/node trees ($($left.Count) listener(s) left)..."
    Kill-DevTrees
    Start-Sleep -Seconds 2
}

$left=@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $ports -contains $_.LocalPort })
if ($left.Count -gt 0) {
    $left | ForEach-Object { Write-Host "STILL BOUND: port $($_.LocalPort) pid $($_.OwningProcess)" }
    Write-Host "ERROR: 端口未能释放，中止启动。请手动检查占用进程后重试。"
    exit 1
}
Write-Host "All target ports free"
exit 0
'
```

若上面命令退出码非 0 或输出含 `STILL BOUND`，**不要继续启动**，向用户报告哪个端口仍被占用、请其手动处理。

### 2. 启动后端（后台运行）

用后台任务启动（`run_in_background: true`），日志落盘便于排查：

```bash
cd "C:\Users\PC\Desktop\red\Garden-Spirit" && python -m uvicorn application.api.main:app --host 127.0.0.1 --port 8756 --reload > data/backend.log 2>&1
```

等 2~3 秒后验证端口监听 + 健康检查：

```bash
netstat -ano | grep -E ":8756[[:space:]]" | grep -i listen
curl -s http://127.0.0.1:8756/health
```

健康检查须返回 `"status": "ok"`。若失败或超时，读 `data/backend.log` 尾部排查（可用 `tail -50 data/backend.log`）。

### 3. 启动前端（后台运行）

```bash
cd "C:\Users\PC\Desktop\red\Garden-Spirit/frontend" && npm run dev:h5 > ../data/frontend.log 2>&1
```

用后台任务启动（`run_in_background: true`）。等 3~5 秒后验证 5173 端口监听：

```bash
netstat -ano | grep -E ":5173[[:space:]]" | grep -i listen
```

### 4. 冒烟验证

```bash
echo "== backend =="
curl -s http://127.0.0.1:8756/health
echo
echo "== frontend =="
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:5173
echo "== ports =="
netstat -ano | grep -E ":(8756|5173)[[:space:]]" | grep -i listen
```

全部就绪后向用户报告：
- 后端 `http://127.0.0.1:8756`（/health 返回 `status: ok`）
- 前端 `http://localhost:5173`（HTTP 200，5173 监听中）
