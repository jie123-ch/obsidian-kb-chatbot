# 知识库助手 · 部署与分发指南

把单人本机版改造成 **「服务器 + 轻量客户端」** 架构：
- **服务器**：跑在你的云主机（或常开电脑）上，持有知识库索引 + 你的 DeepSeek 密钥
- **PC 客户端（EXE）** / **安卓客户端（APK）**：只负责连服务器、显示聊天界面，**本地不跑模型、不需要密钥**

好友拿到 EXE/APK，填入你给的「服务器地址 + 访问令牌」即可直接使用，知识库与额度都在你这边。

---

## 一、交付物清单

| 文件 | 说明 |
|---|---|
| `dist-installer/KBChat-Setup.exe` | Windows 安装包（双击安装，含桌面快捷方式） |
| `android-client/app/build/outputs/apk/debug/app-debug.apk` | 安卓安装包（直接发给安卓手机安装） |
| `app.py` / `config.py` / `retrieve.py` / `embed.py` / `build_index.py` | 服务器源码 |
| `kb.db` | 已预构建的向量索引（你的知识库），随服务器一起部署 |
| `requirements.txt` / `Dockerfile` / `.dockerignore` | 服务端依赖与容器化 |
| `templates/index.html` | iOS 风格聊天界面（服务器渲染，客户端直接加载） |
| `.env.example` | 服务端配置模板 |

---

## 二、部署服务器

### 方式 A：Docker（推荐，最省心）

```bash
# 1) 进入本项目目录，构建镜像
docker build -t kb-chatbot .

# 2) 运行（务必填好两个环境变量）
docker run -d --restart=unless-stopped \
  -p 8000:8000 \
  -e DEEPSEEK_API_KEY=sk-你的密钥 \
  -e SERVER_TOKEN=一段强随机字符串 \
  --name kb-chatbot \
  kb-chatbot
```

> `kb.db` 已打包进镜像，无需在容器内重建索引。
> 生成强随机令牌：`python -c "import secrets;print(secrets.token_urlsafe(24))"`

### 方式 B：直接跑 Python（云主机或常开电脑）

```bash
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env：填 DEEPSEEK_API_KEY 与 SERVER_TOKEN
uvicorn app:app --host 0.0.0.0 --port 8000
```

### 三、HTTPS 与域名（给好友公网访问时必做）

客户端 WebView 在 `https` 页面下才能稳定工作；纯 `http` 仅限局域网/内网。
建议用 **Caddy** 反代（自动申请免费证书）：

```Caddyfile
kb.你的域名.com {
    reverse_proxy 127.0.0.1:8000
}
```

然后在云防火墙/安全组放行 80/443。好友使用的「服务器地址」就是 `https://kb.你的域名.com`。

> 若只在公司内网/局域网使用，可暂时用 `http://服务器内网IP:8000`，手机与电脑在同一网络即可。

---

## 四、给好友分发与使用

1. 把 `KBChat-Setup.exe` 发给用 Windows 的朋友；把 `app-debug.apk` 发给用安卓的朋友。
2. 告诉他们**服务器地址**和**访问令牌**（和你 `SERVER_TOKEN` 一致）。
3. 好友操作：
   - **Windows**：双击安装 → 打开「知识库助手」→ 首次弹出设置，填服务器地址 + 令牌 → 保存即连。
   - **安卓**：安装 APK（允许「未知来源」）→ 右上角齿轮 → 填服务器地址 + 令牌 → 保存并连接。
4. 之后每次打开即用，配置存在本机，无需重复填写。

---

## 五、更新知识库（可选）

当你的 Obsidian 笔记有变动时，在服务器上重建索引：

```bash
# 把最新 vault 放到服务器某目录，例如 /data/vault
export VAULT_PATH=/data/vault
python build_index.py      # 重新生成 kb.db
# 重启服务
```

> 仅重建 kb.db 即可，DeepSeek 密钥与令牌不变。

---

## 六、安全与成本提示

- **务必设置 `SERVER_TOKEN`**：否则任何人拿到地址都能白嫖你的 DeepSeek 额度。
- 服务器已有按 IP 的限流（默认 30 次/分钟），适合 10 人以内小团队。
- 成本：云主机约 ¥60–100/月（或用现有常开电脑零成本）+ DeepSeek 按量（小额）。
- 知识库文件只在服务器本地做向量化，不会上传到第三方（仅提问时把「问题+命中片段」发给 DeepSeek 生成答案，符合本地向量 + 云端 LLM 的隐私设计）。
