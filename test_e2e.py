import json
import urllib.request

BASE = "http://127.0.0.1:8001"
QUESTION = "请解释一下什么是 RAG，它和 Agent 有什么区别？"


def main():
    # 1) 首页
    try:
        with urllib.request.urlopen(BASE + "/", timeout=8) as r:
            html = r.read().decode("utf-8", "ignore")
        print(f"[1] 首页 GET / -> HTTP {r.status}, HTML 长度 {len(html)} 字节")
    except Exception as e:
        print(f"[1] 首页获取失败: {e}")
        return

    # 2) 端到端问答（SSE 流式）
    payload = json.dumps({"question": QUESTION}).encode("utf-8")
    req = urllib.request.Request(
        BASE + "/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    print(f"\n[2] 发送问题：{QUESTION}\n" + "=" * 60)
    sources = []
    answer = []
    got_error = False
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            buf = ""
            for raw in resp:
                line = raw.decode("utf-8", "ignore")
                if not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if not data_str:
                    continue
                try:
                    obj = json.loads(data_str)
                except Exception:
                    continue
                t = obj.get("type")
                if t == "sources":
                    sources = obj.get("sources", [])
                elif t == "delta":
                    answer.append(obj.get("content", ""))
                elif t == "error":
                    got_error = True
                    print("【错误】", obj.get("content", ""))
                elif t == "done":
                    break
    except Exception as e:
        print(f"请求异常: {e}")
        return

    print("\n" + "=" * 60)
    print("【检索到的来源笔记】")
    if sources:
        for i, s in enumerate(sources, 1):
            score = s.get("score", 0)
            title = s.get("note_title", "?")
            head = s.get("heading", "")
            rel = s.get("rel_path", "")
            print(f"  {i}. [{score:.3f}] {title} {('· ' + head) if head else ''}  ({rel})")
    else:
        print("  （无来源）")

    full = "".join(answer)
    print("\n【DeepSeek 生成答案】")
    print(full if full else "（空答案）")
    print("\n" + "=" * 60)
    if got_error:
        print("结果：❌ 出现错误（见上方）")
    elif not full.strip():
        print("结果：⚠️ 未返回答案内容")
    elif not sources:
        print("结果：⚠️ 答案返回了，但无检索来源")
    else:
        print(f"结果：✅ 端到端成功（{len(sources)} 个来源，答案 {len(full)} 字）")


if __name__ == "__main__":
    main()
