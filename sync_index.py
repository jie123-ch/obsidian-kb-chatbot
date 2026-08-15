"""知识库索引一键同步到云端服务器。

用法：
    python sync_index.py                # 重建本地索引并上传
    python sync_index.py --skip-build   # 只上传当前 kb.db（已重建过时）
    python sync_index.py --url https://你的域名 --token 你的令牌

流程：
    1. 扫描 Obsidian vault（config.VAULT_PATH），重建 kb.db
    2. POST 上传到云端 /api/admin/db（原子替换 + 热重载，无需重启服务）
    3. 查询 /api/admin/stats 确认云端索引规模已更新

依赖：requests（本地 venv 已装）
"""
import argparse
import os
import sys
from pathlib import Path

import requests

import build_index

DEFAULT_URL = os.getenv("KB_SERVER_URL", "https://kb.your-domain.com")
DEFAULT_TOKEN = os.getenv("KB_SERVER_TOKEN", "")


def main():
    ap = argparse.ArgumentParser(description="同步 kb.db 索引到云端知识库服务器")
    ap.add_argument("--url", default=DEFAULT_URL, help="服务器地址（不带结尾斜杠）")
    ap.add_argument("--token", default=DEFAULT_TOKEN, help="SERVER_TOKEN")
    ap.add_argument("--skip-build", action="store_true", help="只上传现有 kb.db，不重建")
    args = ap.parse_args()
    base = args.url.rstrip("/")

    if not args.skip_build:
        print("== 1/3 重建本地索引（扫描 Obsidian vault）…")
        build_index.build()
    else:
        print("== 1/3 跳过重建，直接上传现有 kb.db")

    db = Path(__file__).resolve().parent / "kb.db"
    if not db.exists():
        print("kb.db 不存在，请先运行 python build_index.py")
        sys.exit(1)
    print(f"== 2/3 上传 {db}（{db.stat().st_size} 字节）→ {base}/api/admin/db …")
    try:
        r = requests.post(
            f"{base}/api/admin/db",
            data=db.read_bytes(),
            headers={
                "Authorization": f"Bearer {args.token}",
                "Content-Type": "application/octet-stream",
            },
            timeout=60,
        )
    except Exception as e:
        print(f"上传失败：{e}")
        sys.exit(1)
    print("HTTP", r.status_code, r.text[:300])
    if r.status_code != 200:
        print("上传未成功，请检查服务器地址 / 令牌。")
        sys.exit(1)

    print("== 3/3 查询云端索引状态 …")
    try:
        s = requests.get(
            f"{base}/api/admin/stats",
            headers={"Authorization": f"Bearer {args.token}"},
            timeout=30,
        )
        print("云端状态:", s.text[:300])
    except Exception as e:
        print(f"状态查询失败：{e}")

    print("\n同步完成！现在电脑端 / 手机端问答即可命中新文档。")


if __name__ == "__main__":
    main()
