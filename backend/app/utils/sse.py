"""SSE 事件格式化。"""
import json


def sse_event(event: str, data: dict | str) -> str:
    if isinstance(data, str):
        payload = data
    else:
        payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def sse_ping() -> str:
    return ": ping\n\n"
