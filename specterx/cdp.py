"""Minimal async CDP client over websockets."""
from __future__ import annotations

import asyncio
import json
import urllib.request

import websockets


class CDPError(RuntimeError):
    pass


class CDPClient:
    def __init__(self):
        self._ws = None
        self._id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._reader_task = None

    async def connect(self, ws_url: str):
        self._ws = await websockets.connect(ws_url, max_size=16 * 1024 * 1024)
        self._reader_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self):
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                mid = msg.get("id")
                if mid is not None and mid in self._pending:
                    fut = self._pending.pop(mid)
                    if not fut.done():
                        if "error" in msg:
                            fut.set_exception(CDPError(msg["error"]))
                        else:
                            fut.set_result(msg.get("result"))
        except Exception:
            pass

    async def cmd(self, method: str, params: dict | None = None, timeout: float = 30):
        self._id += 1
        mid = self._id
        fut = asyncio.get_event_loop().create_future()
        self._pending[mid] = fut
        await self._ws.send(json.dumps({"id": mid, "method": method,
                                        "params": params or {}}))
        return await asyncio.wait_for(fut, timeout)

    async def js(self, expr: str, timeout: float = 15, await_promise: bool = False):
        r = await self.cmd("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": await_promise,
        }, timeout=timeout)
        res = (r or {}).get("result", {})
        if res.get("subtype") == "error":
            raise CDPError(res.get("description", "js error"))
        return res.get("value")

    async def close(self):
        try:
            if self._reader_task:
                self._reader_task.cancel()
            if self._ws:
                await self._ws.close()
        except Exception:
            pass


def http_json(url: str, timeout: float = 5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def pick_target(debug_url: str, url_substr: str = "about:blank") -> dict | None:
    """Return the first page target matching url_substr."""
    try:
        targets = http_json(f"{debug_url}/json/list")
    except Exception:
        return None
    for t in targets:
        if t.get("type") == "page" and url_substr in t.get("url", ""):
            return t
    for t in targets:
        if t.get("type") == "page":
            return t
    return None
