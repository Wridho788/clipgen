"""Minimal in-process ASGI client (httpx is not a runtime dependency)."""
from __future__ import annotations

import asyncio
import json as jsonlib

from app.main import app


async def call(method: str, path: str, *, json=None, headers: dict[str, str] | None = None):
    body = jsonlib.dumps(json).encode() if json is not None else b""
    messages = []
    received = False
    complete = asyncio.Event()

    async def receive():
        nonlocal received
        if not received:
            received = True
            return {"type": "http.request", "body": body, "more_body": False}
        await complete.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)
        if message["type"] == "http.response.body" and not message.get("more_body", False):
            complete.set()

    raw_headers = [(b"origin", b"http://localhost:3000")]
    if json is not None:
        raw_headers.append((b"content-type", b"application/json"))
    for key, value in (headers or {}).items():
        raw_headers.append((key.lower().encode(), value.encode()))
    path, _, query = path.partition("?")
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": query.encode(), "root_path": "", "headers": raw_headers,
        "client": ("127.0.0.1", 1234), "server": ("test", 80),
    }
    await app(scope, receive, send)
    start = next(m for m in messages if m["type"] == "http.response.start")
    payload = b"".join(m.get("body", b"") for m in messages)
    response_headers = {key.decode(): value.decode() for key, value in start["headers"]}
    content_type = response_headers.get("content-type", "")
    data = jsonlib.loads(payload) if content_type.startswith("application/json") and payload else payload
    return start["status"], response_headers, data
