"""端到端冒烟测试脚本：认证 → 建库 → 上传 → 状态轮询 → 权限校验。"""
import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"


def req(method, path, token=None, body=None, raw=False):
    r = urllib.request.Request(BASE + path, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    try:
        with urllib.request.urlopen(r, data=data) as resp:
            content = resp.read()
            return resp.status, json.loads(content) if content and not raw else content
    except urllib.error.HTTPError as e:
        content = e.read()
        try:
            return e.code, json.loads(content)
        except Exception:
            return e.code, content.decode("utf-8", errors="replace")


def main():
    # 1. admin 登录
    status, resp = req("POST", "/auth/login", body={"username": "admin", "password": "123456"})
    assert status == 200, f"admin login failed: {resp}"
    admin_token = resp["access_token"]
    print("[1] admin login OK")

    # 2. 建知识库
    status, resp = req("POST", "/admin/kbs", admin_token, {"name": "商品知识库", "description": "电商商品信息"})
    assert status == 201, f"create kb failed: {resp}"
    kb_id = resp["id"]
    print(f"[2] kb created: {kb_id}")

    # 3. 普通用户注册
    status, resp = req("POST", "/auth/register", body={"username": "shopper1", "password": "test123456"})
    assert status == 201, f"register failed: {resp}"
    user_token = resp["access_token"]
    print("[3] user register OK")

    # 4. 普通用户访问 admin 接口 → 403
    status, resp = req("GET", "/admin/kbs", user_token)
    assert status == 403, f"expected 403, got {status}: {resp}"
    print("[4] non-admin blocked with 403 OK")

    # 5. 上传文档（multipart）
    boundary = "----testboundary"
    with open("scripts/testdata/products.md", "rb") as f:
        file_content = f.read()
    filename = "products.md"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: text/markdown\r\n\r\n"
    ).encode("utf-8") + file_content + f"\r\n--{boundary}--\r\n".encode("utf-8")

    r = urllib.request.Request(f"{BASE}/admin/documents?kb_id={kb_id}", data=body, method="POST")
    r.add_header("Authorization", f"Bearer {admin_token}")
    r.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        with urllib.request.urlopen(r) as resp:
            content = json.loads(resp.read())
            print(f"[5] upload OK: {content['filename']} status={content['parse_status']}")
            doc_id = content["id"]
    except urllib.error.HTTPError as e:
        print(f"[5] upload FAILED: {e.code} {e.read().decode('utf-8', errors='replace')[:200]}")
        sys.exit(1)

    # 6. 轮询解析状态（embedding 无 key 时会 failed，验证状态机流转）
    for _ in range(10):
        time.sleep(3)
        status, resp = req("GET", f"/admin/documents/{doc_id}", admin_token)
        assert status == 200
        ps = resp["parse_status"]
        print(f"[6] parse status: {ps} (progress={resp['parse_progress']}, error={resp['error_message']})")
        if ps in ("succeeded", "failed"):
            break
    else:
        print("[6] parse still pending after 30s")

    # 7. 分块预览
    if resp["parse_status"] == "succeeded":
        status, chunks = req("GET", f"/admin/documents/{doc_id}/chunks?page=1&page_size=5", admin_token)
        print(f"[7] chunks total={chunks['total']}, first: {chunks['items'][0]['content'][:50] if chunks['items'] else 'N/A'}")


if __name__ == "__main__":
    main()
