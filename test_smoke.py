import urllib.request, json

BASE = "http://127.0.0.1:8000"

def get_root():
    try:
        r = urllib.request.urlopen(BASE + "/", timeout=10)
        body = r.read()
        print("GET /  -> status", r.status, "bytes", len(body))
        return True
    except Exception as e:
        print("GET /  FAILED:", e)
        return False

def chat(q):
    try:
        req = urllib.request.Request(
            BASE + "/api/chat",
            data=json.dumps({"question": q}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            print("POST /api/chat -> status", resp.status)
            print(resp.read().decode("utf-8")[:2500])
    except Exception as e:
        print("POST /api/chat FAILED:", e)

if __name__ == "__main__":
    if get_root():
        chat("什么是 RAG？它和 Agent 有什么区别？")
