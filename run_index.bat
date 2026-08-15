@echo off
chcp 65001 >nul
set HF_ENDPOINT=https://hf-mirror.com
set HF_HUB_DISABLE_XET=1
cd /d "%~dp0"
echo 正在重建知识库索引（扫描 VAULT_PATH 下的 Markdown）…
python build_index.py
echo 完成。
pause
