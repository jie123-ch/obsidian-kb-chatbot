@echo off
chcp 65001 >nul
set HF_ENDPOINT=https://hf-mirror.com
set HF_HUB_DISABLE_XET=1
cd /d "%~dp0"

REM 启动前清理占用 8000 端口的旧 uvicorn 进程（避免 stale 实例读不到新 key）
echo 正在清理可能占用 8000 端口的旧进程…
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" 2>nul

echo 正在启动本地知识库聊天机器人，请稍候…
echo 启动后请在浏览器打开 http://127.0.0.1:8000
python -m uvicorn app:app --host 127.0.0.1 --port 8000
pause
