# Obsidian 知识库问答助手（KB Chatbot）

把你的 **Obsidian 个人知识库**变成一个可对话的 AI 助手：本地向量化笔记 → 检索相关片段 → 交给 DeepSeek 生成带来源的回答。

支持 **浏览器 / Windows 桌面端（EXE）/ 安卓端（APK）** 三端使用，可部署到公网（Docker 或腾讯云 CloudBase），好友填入「服务器地址 + 访问令牌」即可使用你的知识库问答。

> 隐私友好：笔记向量化在本地完成，嵌入模型本地运行；只有提问时，问题与命中的片段才会发给 DeepSeek 生成答案。

---

## ✨ 功能特性

- 📚 读取 Obsidian vault 全部 Markdown，自动排除插件/工具目录
- 🧠 本地嵌入模型 `BAAI/bge-small-zh-v1.5`（fastembed + ONNX，CPU 即可，无 GPU 依赖）
- 🔍 查询改写（DeepSeek 补关键词）→ 余弦检索 Top-K → 相似度阈值过滤（默认 0.49）
- 💬 流式回答（SSE），回答标注来源，点击来源可查看原笔记
- 🔐 访问令牌鉴权（`?token=` / `Authorization` / Cookie）+ 按 IP 限流（防刷 DeepSeek 额度）
- 📱 三端：浏览器（服务端渲染 iOS 风格 UI）、Windows EXE（pywebview）、安卓 APK（WebView shell）
- 🔄 知识库更新热同步：上传新索引即可热重载，无需重启；可选本地 watcher 自动检测 vault 变化

---

## 🏗 架构

```
Obsidian 笔记 (本地 VAULT_PATH)
      │  本地遍历 + 中文分块 + 本地向量化
      ▼
kb.db (sqlite + numpy 向量)  ──┐
                               ▼
用户提问 ──► 嵌入问题 ──► 余弦检索 Top-K 片段 ──► [问题 + 片段] ──► DeepSeek API
                                                               │
                                                         流式回答 + 来源标注

部署形态（三选一）：
  A. 本机单机：浏览器访问 http://127.0.0.1:8000
  B. 服务器 + 瘦客户端：服务端持有 kb.db 跑在云上；PC/安卓客户端只负责连服务器
  C. 公网开放给好友：给好友「服务器地址 + SERVER_TOKEN」，他们填入客户端即可用
```

---

## 🚀 快速开始（本机单机版）

### 环境要求
- Python 3.9+（推荐 3.11+）
- 依赖：`pip install -r requirements.txt`

### 1. 配置

```bash
cp .env.example .env   # Windows: copy .env.example .env
```

编辑 `.env`：
- `DEEPSEEK_API_KEY`：必填（https://platform.deepseek.com 免费申请）
- `VAULT_PATH`：你的 Obsidian 仓库路径
- `SERVER_TOKEN`：部署到公网时必填（`python -c "import secrets;print(secrets.token_urlsafe(24))"` 生成）

### 2. 构建索引

```bash
set HF_ENDPOINT=https://hf-mirror.com   # 国内加速，Windows
set HF_HUB_DISABLE_XET=1
python build_index.py
```

首次运行会自动下载嵌入模型（约几十 MB）。成功提示：`索引完成：N 个片段，向量维度 512，已写入 kb.db`。

### 3. 启动

```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

浏览器打开 `http://127.0.0.1:8000` 提问。Windows 也可双击 `run.bat`。

---

## ☁️ 部署到公网（好友可访问）

### 方式 A：Docker（任意云主机 / 腾讯云云托管）

```bash
docker build -t kb-chatbot .
docker run -d --restart=unless-stopped \
  -p 8000:8000 \
  -e DEEPSEEK_API_KEY=sk-你的密钥 \
  -e SERVER_TOKEN=一段强随机字符串 \
  --name kb-chatbot kb-chatbot
```

> 容器必须监听平台注入的 `PORT` 环境变量（Dockerfile 已用 `${PORT:-8000}` 兜底），适配云托管弹性扩缩容。

### 方式 B：腾讯云 CloudBase 云托管（本项目实测路线）

1. 环境开通云托管 → 新建容器服务（`serverType=container`，`OpenAccessTypes=["PUBLIC"]`）
2. 环境变量注入：`DEEPSEEK_API_KEY`、`SERVER_TOKEN`
3. 从源码部署（云端自动构建镜像）：
   - **pip 镜像**：腾讯云构建机访问 `pypi.tuna` 会 403，Dockerfile 已改用腾讯云内网镜像 + 官方源兜底
   - **嵌入模型预下载**：Dockerfile 构建期预下载 `BAAI/bge-small-zh-v1.5` 到镜像内 `HF_HOME`，实例启动即用

### 知识库索引同步（核心机制）

服务端 `retrieve.py` 按 **mtime 缓存热重载**：只要替换 `kb.db` 文件，检索立即用新索引，**无需重启**。配套两个接口：

| 接口 | 说明 |
|---|---|
| `POST /api/admin/db` | 接收新 `kb.db` 原始字节，原子替换 + 强制重载（需 `SERVER_TOKEN`） |
| `GET /api/admin/stats` | 查询云端索引规模与更新时间 |

本地同步方式：
```bash
# 一键：重建索引 + 上传云端（Windows 双击 sync_index.bat）
python sync_index.py --url https://你的域名 --token 你的令牌

# 只上传不重建
python sync_index.py --skip-build --url ... --token ...
```

**自动同步（可选，推荐）**：`vault_watch.py` 常驻监控 vault 变化，检测到笔记新增/修改/删除且内容稳定 15 秒后，自动重建 + 上传，两端立即生效：

```bash
python vault_watch.py              # 前台监控
python vault_watch.py --install    # 注册 Windows 开机自启（HKCU Run）
python vault_watch.py --uninstall  # 取消自启
```

---

## 🖥 构建 Windows 客户端（EXE）

```bash
pip install pyinstaller
python -m PyInstaller --onedir --noconsole --name KBChat \
  --hidden-import webview --hidden-import webview.platforms.winforms \
  --hidden-import webview.platforms.edgechromium \
  --hidden-import pythonnet \
  --collect-submodules webview --collect-submodules pythonnet \
  client_pc.py
```

> ⚠️ **WebView2 坑**：pywebview 6.x 在 Windows 上默认只认 EdgeUpdate 注册表里的 WebView2 Runtime。很多机器 Edge 装了但 WebView2 未单独注册，pywebview 会静默降级到 IE(MSHTML)，JS 桥接全断（界面能打开、按钮无反应、本地文件不写）。`client_pc.py` 已内置 `_find_webview2_runtime()`：扫描 `EdgeCore/<版本>` 与 `EdgeWebView/Application` 目录，自动指定 `WEBVIEW2_RUNTIME_PATH`，无需用户手动装运行时。
>
> 安装包：`installer.iss`（Inno Setup 7，`PrivilegesRequired=lowest` 免管理员）。

---

## 🤖 构建安卓客户端（APK）

```bash
cd android-client
export JAVA_HOME=...; export ANDROID_HOME=...   # Android SDK + JDK 17
gradle assembleDebug
# 产物：app/build/outputs/apk/debug/app-debug.apk
```

安卓端是纯 WebView shell（`MainActivity.java`）：设置对话框持久化「服务器地址 + 令牌」到 SharedPreferences，加载 `服务器地址?token=...`。首次打开填服务器地址与令牌即可。

> ⚠️ **Gradle 中文路径坑**：项目路径含中文时（如 `工作`），Java 按 GBK 误解析路径，`.gradle` 缓存锁创建报"拒绝访问"。解法：把工程复制到**纯 ASCII 路径**构建。

---

## 📁 目录结构

```
kb-chatbot/
├─ app.py               # FastAPI：UI + /api/chat(SSE) + /api/note + /api/admin/*
├─ config.py            # 读取 .env，暴露常量
├─ embed.py             # 本地嵌入封装（fastembed + BGE）
├─ build_index.py       # 遍历 vault → 解析/分块 → 本地嵌入 → 写 kb.db
├─ retrieve.py          # 载入 kb.db（mtime 热重载），嵌入查询，余弦 top-k
├─ sync_index.py        # 重建 + 上传索引到云端
├─ vault_watch.py       # 自动监控 vault 变化并同步（可选）
├─ client_pc.py         # Windows 桌面客户端（pywebview）
├─ requirements.txt     # 服务端依赖
├─ Dockerfile           # 容器化（含模型预下载）
├─ installer.iss        # Inno Setup 安装包脚本
├─ templates/index.html # 聊天界面（服务端渲染）
└─ android-client/      # 安卓 WebView 客户端（Gradle 工程）
```

---

## ⚙️ 配置说明（.env）

| 变量 | 默认 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 空 | 必填，DeepSeek 平台申请 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 可换 `deepseek-reasoner` |
| `SERVER_TOKEN` | 空 | 公网部署必填；空 = 不鉴权（仅本机） |
| `VAULT_PATH` | `C:\Users\...\MyBrain` | Obsidian 仓库路径 |
| `EXCLUDE_DIRS` | `.obsidian,.copilot,.agents,.claude,.opencode,copilot` | 索引时排除的目录 |
| `EMBEDDING_MODEL` | `BAAI/bge-small-zh-v1.5` | 本地嵌入模型（可换 `BAAI/bge-m3`） |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `700` / `120` | 切块参数（按字符） |
| `TOP_K` | `3` | 检索片段数 |
| `MIN_SCORE` | `0.49` | 相似度阈值，低于视为噪声 |

---

## 🩺 故障排查

| 现象 | 原因 / 解决 |
|---|---|
| 构建索引卡在下载 / `401 CAS` | HuggingFace xet 被墙。设置 `HF_ENDPOINT=https://hf-mirror.com` + `HF_HUB_DISABLE_XET=1` |
| PC 客户端界面能打开，按钮无反应 | WebView2 未注册，pywebview 降级 IE。确认使用 `client_pc.py` 内置的运行时探测逻辑 |
| 手机装了 APK 显示"别的应用" | 大概率传错 APK 文件；本应用包名 `com.kbchat`、应用名"知识库助手"、蓝色气泡图标 |
| 云端镜像构建 `pip install` 403 | 腾讯云构建机换腾讯云内网 PyPI 镜像（见 Dockerfile） |
| 新笔记问不到 | 索引是快照。运行 `sync_index.py` 上传新索引，或启用 `vault_watch.py` 自动同步 |
| 回答"资料中未找到相关内容" | `TOP_K` 调高（6~8）重建索引；或 `MIN_SCORE` 调低 |
| 来源出现不相关笔记 | 通用词误判；`MIN_SCORE` 调高（0.55）更严格 |

---

## 🔒 安全说明

- 笔记向量化完全本地完成，嵌入模型本地运行，笔记原文不发往云端
- 提问时仅发送「问题 + 命中的片段文本」给 DeepSeek
- DeepSeek Key 只存服务端环境变量（`.env`），客户端不持有
- 公网部署务必设置强 `SERVER_TOKEN`，且建议配合平台限流

## 📄 License

MIT
