"""SSE 问答链路测试：登录 → 建会话 → 流式提问 → 打印事件流。"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"


def req(method, path, token=None, body=None):
    r = urllib.request.Request(BASE + path, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    try:
        with urllib.request.urlopen(r, data=data) as resp:
            content = resp.read()
            return resp.status, json.loads(content) if content else None
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main():
    question = sys.argv[1] if len(sys.argv) > 1 else "蓝牙耳机 X1 的续航和价格是多少？"

    status, resp = req("POST", "/auth/login", body={"username": "admin", "password": "123456"})
    token = resp["access_token"]
    print(f"[1] login OK")

    status, resp = req("POST", "/sessions", token, {"title": "chat test"})
    session_id = resp["id"]
    print(f"[2] session created: {session_id}")

    # SSE 流式请求
    r = urllib.request.Request(f"{BASE}/chat/stream", method="POST")
    r.add_header("Content-Type", "application/json")
    r.add_header("Authorization", f"Bearer {token}")
    body = json.dumps({"session_id": session_id, "question": question}, ensure_ascii=False).encode("utf-8")
    print(f"[3] asking: {question}\n--- SSE events ---")
    full = []
    with urllib.request.urlopen(r, data=body, timeout=120) as resp:
        event = None
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                payload = line.split(":", 1)[1].strip()
                if event == "citations":
                    data = json.loads(payload)
                    print(f"  [citations] mode={data['mode']} count={len(data['citations'])}")
                    for c in data["citations"]:
                        loc = f"p{c['page']}" if c.get("page") else ("r%d-%d" % (c.get("row_start") or 0, c.get("row_end") or 0))
                        print(f"    - [{c['filename']} {loc}] {c['text'][:60]}")
                elif event == "token":
                    full.append(json.loads(payload)["content"])
                elif event == "done":
                    print(f"  [done] message_id={json.loads(payload)['message_id']}")
                elif event == "error":
                    print(f"  [error] {payload}")
    print("---")
    print("ANSWER:", "".join(full))
    print(f"\n[4] answer length: {len(''.join(full))} chars")


if __name__ == "__main__":
    main()
