import json
import urllib.request

BASE = "http://127.0.0.1:8002"
Q = "南京的AI就业环境如何？"


def chat(question):
    req = urllib.request.Request(
        BASE + "/api/chat",
        data=json.dumps({"question": question}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    sources = []
    answer_parts = []
    got_error = False
    with urllib.request.urlopen(req, timeout=120) as resp:
        buf = ""
        for raw in resp:
            line = raw.decode("utf-8", "ignore")
            if not line.startswith("data:"):
                continue
            d = line[len("data:"):].strip()
            if not d:
                continue
            try:
                obj = json.loads(d)
            except Exception:
                continue
            t = obj.get("type")
            if t == "sources":
                sources = obj.get("sources", [])
            elif t == "delta":
                answer_parts.append(obj.get("content", ""))
            elif t == "error":
                got_error = True
                print("  【错误】", obj.get("content", ""))
            elif t == "done":
                break
    return sources, "".join(answer_parts), got_error


def main():
    print(f"\n=== 问题：{Q} ===\n" + "=" * 60)
    sources, answer, err = chat(Q)

    print("\n【召回来源】")
    if sources:
        for i, s in enumerate(sources, 1):
            print(f"  {i}. [{s['score']:.3f}] {s['note_title'][:30]}  |  {s['heading'] or '(无标题)'}")
    else:
        print("  （空）")

    print("\n【来源笔记名列表（用于查徐州地铁是否出现）】")
    titles = [s["note_title"] for s in sources]
    print("  →", titles)
    polluted = any("徐州" in t or "地铁" in t for t in titles)
    print(f"  含徐州地铁? {'❌ 是' if polluted else '✅ 否'}")

    print("\n【DeepSeek 答案】")
    print(answer if answer else "（空）")

    print("\n" + "=" * 60)
    if err:
        print("结果：❌ 接口报错")
    elif polluted:
        print("结果：❌ 仍有无关来源")
    elif len(sources) == 0:
        print("结果：⚠️ 无来源")
    else:
        print(f"结果：✅ {len(sources)} 个来源，全部相关")


if __name__ == "__main__":
    main()