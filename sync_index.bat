@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ================================================
echo    知识库索引一键同步（重建 + 上传云端）
echo ================================================
echo.
echo 提示：首次使用请先设置环境变量 KB_SERVER_URL / KB_SERVER_TOKEN，
echo   或直接运行： python sync_index.py --url https://你的域名 --token 你的令牌
echo.
python sync_index.py
echo.
pause
