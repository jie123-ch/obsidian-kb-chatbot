"""vault_watch.py — 自动检测 Obsidian vault 变化并同步索引到云端

在 Obsidian 里编辑笔记（电脑必然开机）时，本进程每几秒扫描一次 vault，
发现 .md 文件有变化（新增/修改/删除）且稳定 15 秒后，自动：
    1. 重建本地 kb.db（build_index）
    2. 上传到云端 /api/admin/db（原子替换 + 热重载）
完成后电脑端 / 手机端问答立即命中新内容，全程无需手动操作。

用法：
    python vault_watch.py            # 前台启动监控
    python vault_watch.py --install  # 注册开机自启（HKCU Run，免管理员）
    python vault_watch.py --uninstall# 取消开机自启
"""
import argparse
import os
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import config
import build_index

SCAN_INTERVAL = 3          # 轮询间隔（秒）
DEBOUNCE_SECONDS = 15      # 文件停止变化后再等这么久才重建（防 Obsidian 连续保存频繁触发）

BASE_DIR = Path(__file__).resolve().parent
LOG_PATH = BASE_DIR / "vault_watch.log"
LOCK_PATH = BASE_DIR / "vault_watch.lock"
INDEX_DB = BASE_DIR / "kb.db"

SERVER_URL = os.getenv("KB_SERVER_URL", "https://kb.your-domain.com").rstrip("/")
SERVER_TOKEN = os.getenv("KB_SERVER_TOKEN", "")
AUTOSTART_KEY = "KBChatVaultWatch"


def log(msg: str):
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def snapshot(vault):
    """返回 {rel_path: (mtime_ns, size)}；只统计会被索引的 .md（复用排除规则）。"""
    out = {}
    for p, rel in build_index.iter_markdown_files():
        try:
            st = p.stat()
        except OSError:
            continue
        out[str(rel)] = (st.st_mtime_ns, st.st_size)
    return out


def sync() -> tuple[bool, str]:
    """重建本地索引并上传云端。返回 (是否成功, 说明)。"""
    try:
        log("重建本地索引…")
        build_index.build()
        if not INDEX_DB.exists():
            return False, "kb.db 不存在，索引重建可能无内容"
        data = INDEX_DB.read_bytes()
        req = urllib.request.Request(
            f"{SERVER_URL}/api/admin/db",
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {SERVER_TOKEN}",
                "Content-Type": "application/octet-stream",
            },
        )
        with urllib.request.urlopen(req, timeout=90) as r:
            body = r.read().decode("utf-8", errors="ignore")
        return True, f"云端已更新: {body}"
    except Exception as e:
        return False, f"同步失败: {e!r}"


def acquire_lock() -> bool:
    try:
        if LOCK_PATH.exists():
            try:
                pid = int(LOCK_PATH.read_text().strip())
            except Exception:
                pid = -1
            if pid > 0:
                try:
                    os.kill(pid, 0)  # 进程存在则返回，不存在抛异常
                    return False
                except OSError:
                    pass
        LOCK_PATH.write_text(str(os.getpid()))
        return True
    except Exception:
        return True  # 锁写失败不阻塞，最多双跑


def release_lock():
    try:
        if LOCK_PATH.exists():
            LOCK_PATH.unlink()
    except Exception:
        pass


def watch():
    vault = config.VAULT_PATH
    log(f"知识库自动同步启动：监控 {vault}")
    log(f"服务器：{SERVER_URL} ｜ 轮询 {SCAN_INTERVAL}s ｜ 稳定等待 {DEBOUNCE_SECONDS}s")
    if not vault.is_dir():
        log(f"错误：vault 路径不存在：{vault}")
        return

    snap = snapshot(vault)
    changed_since = None
    while True:
        time.sleep(SCAN_INTERVAL)
        try:
            cur = snapshot(vault)
        except Exception as e:
            log(f"扫描异常：{e!r}")
            continue

        if cur != snap:
            if changed_since is None:
                changed_since = time.time()
                log("检测到 vault 变化，等待内容稳定…")
            elif time.time() - changed_since >= DEBOUNCE_SECONDS:
                log("内容已稳定，开始同步到云端…")
                ok, msg = sync()
                if ok:
                    snap = cur
                    changed_since = None
                    log("✔ 同步完成，问答已可用新内容。")
                else:
                    # 失败则保留 changed_since 重置，下轮继续重试
                    changed_since = None
                    log(f"✘ {msg}（稍后自动重试）")
        else:
            if changed_since is not None:
                changed_since = None  # 变化被还原，忽略


def install_autostart():
    try:
        import winreg
        exe = f'"{sys.executable}" "{__file__}" --watch'
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, AUTOSTART_KEY, 0, winreg.REG_SZ, exe)
        print(f"已注册开机自启：{exe}")
        log(f"开机自启已注册：{exe}")
    except Exception as e:
        print(f"注册开机自启失败：{e!r}")


def uninstall_autostart():
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.DeleteValue(key, AUTOSTART_KEY)
        print("已取消开机自启。")
        log("开机自启已取消")
    except FileNotFoundError:
        print("未找到自启项（可能未安装）。")
    except Exception as e:
        print(f"取消开机自启失败：{e!r}")


def main():
    ap = argparse.ArgumentParser(description="Obsidian 知识库自动同步监控")
    ap.add_argument("--install", action="store_true", help="注册开机自启后退出")
    ap.add_argument("--uninstall", action="store_true", help="取消开机自启后退出")
    ap.add_argument("--watch", action="store_true", help="启动监控（默认行为，可省略）")
    args = ap.parse_args()

    if args.install:
        install_autostart()
        return
    if args.uninstall:
        uninstall_autostart()
        return

    if not acquire_lock():
        print("已有知识库自动同步进程在运行（vault_watch.lock）。")
        sys.exit(0)
    try:
        watch()
    finally:
        release_lock()


if __name__ == "__main__":
    main()
