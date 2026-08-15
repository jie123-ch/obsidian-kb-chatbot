"""无显示环境下验证 PC 客户端的核心逻辑（不真正创建窗口）。
monkeypatch pywebview 的 create_window/start，检查：
1) 无配置时展示设置页（html 含输入框）
2) 有配置时直接连到 server_url?token=...
3) save_config 把配置写进文件且正确拼装 URL
"""
import os
import sys
import json
import types

# 用一个临时目录当配置目录
TMP = "/tmp/kbchat_test"
os.makedirs(TMP, exist_ok=True)
CFG = os.path.join(TMP, "config.json")
# 用写入空配置来重置状态（沙箱禁止 os.remove）
with open(CFG, "w", encoding="utf-8") as f:
    f.write("{}")

import client_pc
client_pc.APP_DIR = TMP
client_pc.CONFIG_PATH = CFG

captured = {}

def fake_create_window(title, url=None, html=None, js_api=None, width=0, height=0):
    captured["title"] = title
    captured["url"] = url
    captured["html"] = html
    captured["api"] = js_api
    # 把 api.window 指回一个能记录 load_url 的假对象
    fake_win = types.SimpleNamespace(load_url=lambda u: captured.setdefault("loaded", u),
                                     load_html=lambda h: captured.setdefault("loaded_html", h))
    js_api.window = fake_win
    return fake_win

def fake_start(menu=None):
    captured["menu"] = menu

client_pc.webview.create_window = fake_create_window
client_pc.webview.start = fake_start

# ===== 场景1：无配置 -> 显示设置页 =====
client_pc.main()
assert captured.get("url") is None, "无配置时不应直接连 URL"
assert captured.get("html") and "服务器地址" in captured["html"], "应展示设置页"
assert captured.get("menu") is not None, "应注册设置菜单"
print("[场景1] 无配置 -> 显示设置页 ✅")

# ===== 场景2：save_config 写文件并连 URL（含令牌）=====
api = captured["api"]
api.save_config("https://kb.example.com", "sec123")
assert os.path.exists(CFG), "配置应已写入"
with open(CFG, encoding="utf-8") as f:
    cfg = json.load(f)
assert cfg["server_url"] == "https://kb.example.com" and cfg["token"] == "sec123"
assert captured.get("loaded") == "https://kb.example.com?token=sec123", captured.get("loaded")
print("[场景2] 保存配置 -> 连 https://kb.example.com?token=sec123 ✅")

# ===== 场景3：重启后直接连（读取已有配置）=====
captured.clear()
client_pc.main()
assert captured.get("url") == "https://kb.example.com?token=sec123", captured.get("url")
print("[场景3] 已有配置 -> 直接连 https://kb.example.com?token=sec123 ✅")

# ===== 场景4：无令牌时 URL 不带 token =====
api.save_config("http://192.168.1.10:8000", "")
assert captured.get("loaded") == "http://192.168.1.10:8000", captured.get("loaded")
print("[场景4] 无令牌 -> http://192.168.1.10:8000 ✅")

print("\n全部客户端逻辑测试通过 ✅")
