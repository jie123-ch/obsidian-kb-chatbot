"""知识库助手 · PC 客户端（pywebview）"""
import json
import os
import sys
import traceback
from datetime import datetime

import webview

APP_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "KBChat")
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
LOG_PATH = os.path.join(APP_DIR, "client.log")


def _log(msg: str):
    """Append a line to the log file. Best-effort, never raises."""
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}\n")
    except Exception:
        pass


def _find_webview2_runtime() -> str | None:
    """Locate a WebView2 runtime binary on this machine.

    pywebview's default detection only checks the EdgeUpdate registry keys,
    which can be missing on machines where Edge is installed but WebView2
    Runtime was never registered separately. Edge itself ships a full
    WebView2 binary under Microsoft\\EdgeCore\\<version> — we can point
    pywebview directly at it via WEBVIEW2_RUNTIME_PATH.
    """
    candidates = []
    bases = [
        r"C:\Program Files (x86)\Microsoft\EdgeCore",
        r"C:\Program Files\Microsoft\EdgeCore",
        r"C:\Program Files (x86)\Microsoft\EdgeWebView\Application",
        r"C:\Program Files\Microsoft\EdgeWebView\Application",
    ]
    for base in bases:
        if not os.path.isdir(base):
            continue
        try:
            entries = os.listdir(base)
        except OSError:
            continue
        versions = []
        for name in entries:
            full = os.path.join(base, name)
            if not os.path.isdir(full):
                continue
            if not os.path.exists(os.path.join(full, "msedgewebview2.exe")):
                continue
            # version key is "X.Y.Z.W" — sort numerically
            parts = []
            for seg in name.split("."):
                try:
                    parts.append(int(seg))
                except ValueError:
                    parts.append(0)
            versions.append((tuple(parts), full))
        versions.sort(key=lambda x: x[0], reverse=True)
        candidates.extend(p for _, p in versions)

    return candidates[0] if candidates else None


def _bootstrap_webview2():
    """Make sure pywebview uses a real WebView2 backend (not IE MSHTML).

    Returns True if a WebView2 runtime was located.
    """
    runtime = _find_webview2_runtime()
    if runtime:
        webview.settings["WEBVIEW2_RUNTIME_PATH"] = runtime
        _log(f"WebView2 runtime pinned to: {runtime}")
        return True
    _log("ERROR: no WebView2 runtime found in standard locations")
    return False


SETTINGS_HTML = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>设置</title>
<style>
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html, body { height: 100%; margin: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Microsoft YaHei", sans-serif;
    background: linear-gradient(180deg, #fafafc 0%, #f2f2f7 40%, #ececf1 100%);
    color: #1c1c1e; display: flex; flex-direction: column;
    padding: 22px 20px; gap: 14px;
    -webkit-font-smoothing: antialiased;
  }
  .logo { font-size: 34px; text-align: center; margin: 8px 0 2px; }
  h1 { font-size: 19px; font-weight: 700; text-align: center; margin: 0 0 6px; }
  .tip { font-size: 12.5px; color: #8e8e93; text-align: center; line-height: 1.5; margin-bottom: 6px; }
  label { font-size: 13px; color: #3c3c43; font-weight: 600; margin: 4px 2px 0; display: block; }
  input {
    width: 100%; margin-top: 6px; padding: 11px 13px; font-size: 15px;
    border: 0.5px solid #c7c7cc; border-radius: 11px; background: #fff; outline: none;
    font-family: inherit;
  }
  input:focus { border-color: #007aff; box-shadow: 0 0 0 3px rgba(0,122,255,0.15); }
  .save {
    margin-top: 16px; width: 100%; padding: 13px; border: none; border-radius: 13px;
    background: #007aff; color: #fff; font-size: 16px; font-weight: 600; cursor: pointer;
    box-shadow: 0 4px 12px rgba(0,122,255,0.35);
  }
  .save:active { transform: scale(0.98); background: #0062cc; }
  .save:disabled { background: #8e8e93; box-shadow: none; cursor: default; }
  .err { color: #ff3b30; font-size: 12.5px; min-height: 16px; margin-top: 8px; text-align: center; }
</style>
</head>
<body>
  <div class="logo">📚</div>
  <h1>知识库助手</h1>
  <div class="tip">填写你的服务器地址与访问令牌<br>配置仅保存在本机，不会上传</div>
  <label>服务器地址</label>
  <input id="url" placeholder="https://kb.your-domain.com" />
  <label>访问令牌（可选，服务器开启鉴权时必填）</label>
  <input id="token" placeholder="与服务器 SERVER_TOKEN 一致" type="password" />
  <button class="save" id="saveBtn" type="button">保存并连接</button>
  <div class="err" id="err"></div>

<script>
  (function() {
    var cfg = __CFG__;
    if (cfg) {
      document.getElementById('url').value = cfg.server_url || '';
      document.getElementById('token').value = cfg.token || '';
    }

    var btn = document.getElementById('saveBtn');
    var errEl = document.getElementById('err');

    function ready() {
      return typeof window.pywebview !== 'undefined'
          && window.pywebview
          && window.pywebview.api
          && typeof window.pywebview.api.save_config === 'function';
    }

    function save() {
      var url = document.getElementById('url').value.trim();
      var token = document.getElementById('token').value.trim();
      errEl.textContent = '';
      if (!url) { errEl.textContent = '请填写服务器地址'; return; }
      if (!ready()) {
        errEl.textContent = '客户端尚未就绪，请稍候再试';
        return;
      }
      btn.disabled = true;
      btn.textContent = '连接中...';
      try {
        window.pywebview.api.save_config(url, token);
      } catch (e) {
        errEl.textContent = '保存失败：' + e;
        btn.disabled = false;
        btn.textContent = '保存并连接';
      }
    }

    btn.addEventListener('click', save);

    // Diagnostic: after a short delay, if pywebview is still not ready, surface it
    setTimeout(function() {
      if (!ready()) {
        errEl.textContent = '提示：客户端初始化较慢，请稍后再点保存';
      }
    }, 1500);
  })();
</script>
</body>
</html>
"""


class Api:
    def __init__(self):
        self.window = None

    def load_config(self):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"server_url": "", "token": ""}

    def save_config(self, url, token):
        url = (url or "").strip().rstrip("/")
        token = (token or "").strip()
        if not url:
            return
        try:
            os.makedirs(APP_DIR, exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump({"server_url": url, "token": token}, f, ensure_ascii=False)
            _log(f"config saved: {url} (token len={len(token)})")
        except Exception as e:
            _log(f"ERROR saving config: {e!r}")
            raise
        self._open_main(url, token)

    def open_settings(self):
        if self.window:
            cfg = self.load_config()
            html = SETTINGS_HTML.replace("__CFG__", json.dumps(cfg, ensure_ascii=False))
            self.window.load_html(html)

    def _open_main(self, url, token):
        if not url:
            self.open_settings()
            return
        full = url + ("?token=" + token if token else "")
        _log(f"opening main: {full}")
        if self.window:
            self.window.load_url(full)


def main():
    _log("=== KBChat client starting ===")
    # Pin WebView2 runtime BEFORE pywebview picks a backend. Without this,
    # pywebview falls back to MSHTML (IE) and the JS bridge is broken.
    if not _bootstrap_webview2():
        # Show a fallback dialog explaining what's missing
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "知识库助手",
            "本机未检测到 WebView2 运行时。\n\n"
            "请安装 Microsoft Edge 浏览器或在\n"
            "https://developer.microsoft.com/microsoft-edge/webview2/ 下载运行时。",
        )
        return

    api = Api()
    cfg = api.load_config()
    start_url = None
    if cfg.get("server_url"):
        start_url = cfg["server_url"] + (
            "?token=" + cfg["token"] if cfg.get("token") else ""
        )

    if start_url:
        window = webview.create_window(
            "知识库助手", url=start_url, js_api=api, width=440, height=780
        )
    else:
        html = SETTINGS_HTML.replace("__CFG__", json.dumps(cfg, ensure_ascii=False))
        window = webview.create_window(
            "知识库助手", html=html, js_api=api, width=440, height=780
        )
    api.window = window
    try:
        webview.start(menu=[{"label": "设置", "action": api.open_settings}])
    except Exception as e:
        _log(f"FATAL: webview.start failed: {e!r}\n{traceback.format_exc()}")
        raise


if __name__ == "__main__":
    main()
