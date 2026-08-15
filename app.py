import json
import os
import re
import time
from collections import defaultdict, deque

import requests
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse, Response
from pathlib import Path

import config
import retrieve

app = FastAPI(title="知识库聊天机器人（可部署版）")

# 允许跨域（方便未来把前端单独托管 / 调试）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMPLATE = Path(__file__).resolve().parent / "templates" / "index.html"


# ============================================================
# 鉴权：共享令牌 SERVER_TOKEN（部署到云后必填）
# 客户端可通过：1) URL ?token=xxx  2) Authorization: Bearer xxx
#               3) 首次带 token 访问后服务器种下 kb_token Cookie
# ============================================================
def _extract_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    if "token" in request.query_params:
        return request.query_params["token"]
    return request.cookies.get("kb_token", "")


def _authorized(request: Request) -> bool:
    if not config.SERVER_TOKEN:
        return True  # 未配置令牌 = 开放（仅限本机开发）
    return _extract_token(request) == config.SERVER_TOKEN


# ============================================================
# 简单限流：按客户端 IP，/api/chat 每分钟上限（默认 30）
# 防止好友刷爆你的 DeepSeek 额度；10 人以下足够
# ============================================================
_RATE_LIMIT = int(getattr(config, "RATE_LIMIT_PER_MIN", 30))
_hits: dict[str, deque] = defaultdict(deque)


def _rate_ok(ip: str) -> bool:
    now = time.time()
    dq = _hits[ip]
    while dq and dq[0] < now - 60:
        dq.popleft()
    if len(dq) >= _RATE_LIMIT:
        return False
    dq.append(now)
    return True


# ============================================================
# 提示词（强调只要有资料就综合作答，不逐字命中也行）
# ============================================================
SYSTEM_PROMPT = (
    "你是一个基于用户个人 Obsidian 知识库的问答助手。\n"
    "回答规则：\n"
    "1) 只能依据下方【参考资料】作答，不要编造资料外的信息；\n"
    "2) 只要参考资料中存在与问题相关的内容（即使没有逐字命中用户的原话），就应当综合这些内容给出有依据的回答；\n"
    "3) 仅当系统明确告诉你【参考资料为空】时，才回答“资料中未找到相关内容”；\n"
    "4) 用简体中文回答；关键事实后用 [1]、[2]、[3] 的方式标注引用；\n"
    "5) 回答最后另起一行，以“来源：”开头列出所引用的笔记名称（如有多个则用逗号分隔）。"
)

_QUERY_EXPAND_PROMPT = (
    "你是一个查询改写助手。请将用户问题改写成更适合中文检索的关键词序列（不超过 30 字）。\n"
    "要求：\n"
    "- 保留原意；补齐同义词、口语-书面词、专有名词全称/简称；\n"
    "- 不要加解释、不要加标点；直接输出改写后的关键词字符串。\n"
    "示例：\n"
    "输入：徐州地铁一期投资\n"
    "输出：徐州地铁一期总投资 徐州地铁一期建设规划 徐州地铁一期工程投资\n"
    "输入：AI 大模型 怎么搞\n"
    "输出：AI 大模型 训练 部署 落地 应用 大语言模型 LLM"
)


def _expand_query(question: str) -> str:
    if not config.DEEPSEEK_API_KEY:
        return question
    try:
        r = requests.post(
            config.DEEPSEEK_CHAT_URL,
            headers={
                "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": config.DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": _QUERY_EXPAND_PROMPT},
                    {"role": "user", "content": question},
                ],
                "temperature": 0.0,
                "max_tokens": 80,
                "stream": False,
            },
            timeout=15,
        )
        r.raise_for_status()
        out = r.json()["choices"][0]["message"]["content"].strip()
        out = re.sub(r"^[\"']|[\"']$", "", out).strip()
        if 1 <= len(out) <= 80:
            return out
    except Exception:
        pass
    return question


def build_messages(query, contexts):
    if not contexts:
        user = "【参考资料为空】\n\n用户问题：" f"{query}"
    else:
        parts = []
        for i, c in enumerate(contexts, 1):
            head = f"（{c['heading']}）" if c.get("heading") else ""
            parts.append(
                f"[资料 {i}] 来源：{c['note_title']}{head}（{c['rel_path']}）\n{c['text']}"
            )
        ctx = "\n\n".join(parts)
        user = f"以下是相关资料：\n\n{ctx}\n\n用户问题：{query}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def sse(payload):
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# ============================================================
# 路由
# ============================================================
@app.get("/api/health")
async def health():
    return {"status": "ok", "auth": bool(config.SERVER_TOKEN), "model": config.EMBEDDING_MODEL}


# ============================================================
# 索引管理接口（知识库更新后，本地重建 kb.db 上传即可热更新）
# 需要 SERVER_TOKEN 鉴权；retrieve 已按 mtime 自动重载，替换文件即可
# ============================================================
@app.post("/api/admin/db")
async def admin_upload_db(request: Request):
    """接收新 kb.db 原始字节，原子替换后强制重载索引。"""
    if not _authorized(request):
        return PlainTextResponse(
            json.dumps({"error": "unauthorized"}, ensure_ascii=False),
            status_code=401,
            media_type="application/json",
        )
    body = await request.body()
    if not body:
        return {"error": "empty body"}
    db = config.INDEX_DB
    try:
        db.parent.mkdir(parents=True, exist_ok=True)
        tmp = db.with_name(db.name + ".tmp")
        tmp.write_bytes(body)
        os.replace(tmp, db)  # 原子替换，避免检索读到半个文件
    except Exception as e:
        return PlainTextResponse(
            json.dumps({"error": f"write failed: {e}"}, ensure_ascii=False),
            status_code=500,
            media_type="application/json",
        )
    data = retrieve.reload()
    n = len(data["texts"]) if data else 0
    return {"status": "ok", "bytes": len(body), "chunks": n}


@app.get("/api/admin/stats")
async def admin_stats(request: Request):
    """返回当前云端索引规模与更新时间，便于确认同步是否生效。"""
    if not _authorized(request):
        return PlainTextResponse(
            json.dumps({"error": "unauthorized"}, ensure_ascii=False),
            status_code=401,
            media_type="application/json",
        )
    db = config.INDEX_DB
    data = retrieve.reload()
    if data is None:
        return {"status": "empty", "chunks": 0, "mtime": int(db.stat().st_mtime) if db.exists() else 0}
    return {
        "status": "ok",
        "chunks": len(data["texts"]),
        "mtime": int(db.stat().st_mtime),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(db.stat().st_mtime)),
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    html = TEMPLATE.read_text(encoding="utf-8")
    auth_required = bool(config.SERVER_TOKEN)
    token = _extract_token(request) if auth_required else ""
    valid = (token == config.SERVER_TOKEN) if auth_required else True
    # 注入到前端：同源下 fetch 也会自动带 kb_token Cookie
    html = html.replace('"__KB_TOKEN__"', json.dumps(token if valid else ""))
    html = html.replace("KB_AUTH_BOOL", "true" if auth_required else "false")
    resp = HTMLResponse(content=html)
    if auth_required and valid and token:
        resp.set_cookie("kb_token", token, max_age=31536000, path="/", samesite="lax")
    return resp


@app.post("/api/chat")
async def chat(request: Request):
    if not _authorized(request):
        return PlainTextResponse(
            json.dumps({"error": "unauthorized", "type": "error"}, ensure_ascii=False),
            status_code=401,
            media_type="application/json",
        )
    ip = request.client.host if request.client else "unknown"
    if not _rate_ok(ip):
        return PlainTextResponse(
            json.dumps({"error": "rate limited", "type": "error"}, ensure_ascii=False),
            status_code=429,
            media_type="application/json",
        )

    data = await request.json()
    question = (data.get("question") or "").strip()
    if not question:
        return {"error": "empty question"}

    expanded = _expand_query(question)
    contexts = retrieve.search(expanded, k=config.TOP_K)

    def generate():
        yield sse({"type": "sources", "sources": contexts, "expanded_query": expanded})
        if not config.DEEPSEEK_API_KEY:
            yield sse(
                {
                    "type": "error",
                    "content": "未配置 DEEPSEEK_API_KEY，请在项目 .env 文件中填写后重启服务。",
                }
            )
            return
        try:
            resp = requests.post(
                config.DEEPSEEK_CHAT_URL,
                headers={
                    "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.DEEPSEEK_MODEL,
                    "messages": build_messages(question, contexts),
                    "temperature": 0.1,
                    "stream": True,
                },
                stream=True,
                timeout=120,
            )
            for raw in resp.iter_lines():
                if not raw:
                    continue
                line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                if not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if data_str == "[DONE]":
                    break
                try:
                    obj = json.loads(data_str)
                except Exception:
                    continue
                delta = obj.get("choices", [{}])[0].get("delta", {}).get("content")
                if delta:
                    yield sse({"type": "delta", "content": delta})
        except Exception as e:
            yield sse({"type": "error", "content": f"调用 DeepSeek 失败：{e}"})
        yield sse({"type": "done"})

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/note")
async def note(request: Request, path: str):
    if not _authorized(request):
        return PlainTextResponse("unauthorized", status_code=401)
    vault = config.VAULT_PATH.resolve()
    full = None
    try:
        full = (vault / path).resolve()
        full.relative_to(vault)  # 防止越权访问 vault 之外
    except Exception:
        return PlainTextResponse("forbidden", status_code=403)
    if full.exists():
        return PlainTextResponse(full.read_text(encoding="utf-8", errors="ignore"))
    # 云端未挂载 vault 文件时，从索引库拼接该笔记片段作为回退
    fallback = retrieve.get_note_text(path)
    if fallback:
        return PlainTextResponse(fallback)
    return PlainTextResponse("not found", status_code=404)
