"""Challenge solver: detect -> act -> verify -> persist.

Strategy per challenge type:
  turnstile_interactive  human-like mouse (bezier + jitter + realistic timing)
                         click on the widget, then wait for clearance cookie
  turnstile_managed/js   real browser usually clears these on its own;
                         wait + poll cookies with deadline
  none                   nothing to do

Success = cf_clearance or __cf_bm cookie present and session persisted.
Retries with a fresh profile when the fingerprint looks burned.
"""
from __future__ import annotations

import asyncio
import math
import random
import time
import urllib.parse
from dataclasses import dataclass, field

from . import stealth
from .cdp import CDPClient, pick_target
from .fingerprint import Fingerprint
from .launcher import launch
from .session import SessionStore

SOLVED_COOKIES = ("cf_clearance", "__cf_bm", "cf_bm")

_DETECT_JS = r"""
(() => {
  const q = (s) => document.querySelector(s);
  const qa = (s) => Array.from(document.querySelectorAll(s));
  const iframes = qa("iframe").map(f => {
    const r = f.getBoundingClientRect();
    return { src: f.src || "", x: r.x, y: r.y, w: r.width, h: r.height,
             cf: (f.src || "").includes("challenges.cloudflare.com") };
  });
  const cfFrame = iframes.find(f => f.cf) || null;
  const widget = q(".cf-turnstile, [data-sitekey]");
  let box = null;
  const el = widget || (cfFrame ? null : null);
  if (widget) {
    const r = widget.getBoundingClientRect();
    if (r.width >= 10 && r.height >= 10) box = { x: r.x, y: r.y, w: r.width, h: r.height };
  }
  const title = (document.title || "").toLowerCase();
  const body = ((document.body && document.body.innerText) || "").toLowerCase().slice(0, 600);
  const managed = !!q("#challenge-form, .cf-challenge, #cf-challenge-running") ||
    title.includes("just a moment") || body.includes("verifying you are human") ||
    body.includes("checking your browser");
  return JSON.stringify({
    title: document.title, url: location.href,
    cfFrame, widgetBox: box,
    iframeCount: iframes.length,
    managed, bodyLen: body.length,
  });
})()
"""


@dataclass
class SolverResult:
    host: str
    solved: bool
    challenge_type: str
    cookies: dict = field(default_factory=dict)
    cf_clearance: str | None = None
    cf_bm: str | None = None
    attempts: int = 0
    elapsed: float = 0.0
    note: str = ""


def _bezier(p0, p1, p2, p3, n):
    pts = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t ** 2 * p2[0] + t ** 3 * p3[0]
        y = (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t ** 2 * p2[1] + t ** 3 * p3[1]
        pts.append((x, y))
    return pts


async def _human_move(cdp: CDPClient, start, end):
    dist = math.hypot(end[0] - start[0], end[1] - start[1])
    steps = max(10, min(48, int(dist / 10)))
    cp1 = (start[0] + (end[0] - start[0]) * 0.3 + random.uniform(-50, 50),
           start[1] + (end[1] - start[1]) * 0.3 + random.uniform(-50, 50))
    cp2 = (start[0] + (end[0] - start[0]) * 0.7 + random.uniform(-35, 35),
           start[1] + (end[1] - start[1]) * 0.7 + random.uniform(-35, 35))
    for i, (x, y) in enumerate(_bezier(start, cp1, cp2, end, steps)):
        # overshoot-and-correct on the final approach, like a real hand
        jx, jy = x + random.uniform(-1.5, 1.5), y + random.uniform(-1.5, 1.5)
        try:
            await cdp.cmd("Input.dispatchMouseEvent",
                          {"type": "mouseMoved", "x": jx, "y": jy}, timeout=3)
        except Exception:
            return
        # ease-out timing: fast mid-flight, slow near target
        frac = i / steps
        base = 0.006 + 0.03 * (frac ** 2)
        await asyncio.sleep(base + random.uniform(0, 0.012))


async def _human_click(cdp: CDPClient, x: float, y: float):
    sx, sy = random.uniform(80, 900), random.uniform(80, 500)
    await _human_move(cdp, (sx, sy), (x + random.uniform(-2, 2), y + random.uniform(-2, 2)))
    await asyncio.sleep(random.uniform(0.09, 0.22))  # dwell before press
    press = {"type": "mousePressed", "x": x, "y": y,
             "button": "left", "buttons": 1, "clickCount": 1}
    release = {"type": "mouseReleased", "x": x, "y": y,
               "button": "left", "buttons": 0, "clickCount": 1}
    await cdp.cmd("Input.dispatchMouseEvent", press, timeout=5)
    await asyncio.sleep(random.uniform(0.07, 0.16))  # hold time
    await cdp.cmd("Input.dispatchMouseEvent", release, timeout=5)
    await asyncio.sleep(random.uniform(0.15, 0.4))


async def _cookies(cdp: CDPClient) -> dict:
    r = await cdp.cmd("Network.getAllCookies", {}, timeout=8)
    out = {}
    for ck in (r or {}).get("cookies", []):
        out[ck["name"]] = ck["value"]
    return out


def _classify(info: dict) -> str:
    if info.get("cfFrame") or info.get("widgetBox"):
        return "turnstile_interactive"
    if info.get("managed"):
        return "managed"
    return "none"


async def _solve_once(url: str, profile: str, timeout: float,
                      headless_shell_ok: bool) -> SolverResult:
    host = urllib.parse.urlparse(url).hostname or url
    fp = Fingerprint(host, base=profile)
    t0 = time.time()
    chrome = launch(fp.user_agent(),
                    window_size=f"{fp.data['screen_width']},{fp.data['screen_height']}")
    cdp = CDPClient()
    result = SolverResult(host=host, solved=False, challenge_type="none")
    try:
        target = pick_target(chrome.debug_url)
        if not target:
            result.note = "no page target"
            return result
        await cdp.connect(target["webSocketDebuggerUrl"])
        # stealth before any navigation; applies to iframes too
        await cdp.cmd("Page.addScriptToEvaluateOnNewDocument",
                      {"source": stealth.build(fp.as_dict())}, timeout=10)
        # UA metadata override (brands) — the --user-agent flag alone skips this
        await cdp.cmd("Network.setUserAgentOverride", {
            "userAgent": fp.user_agent(),
            "userAgentMetadata": {
                "brands": [{"brand": "Chromium", "version": "130"},
                           {"brand": "Google Chrome", "version": "130"},
                           {"brand": "Not?A_Brand", "version": "99"}],
                "fullVersion": "130.0.6723.91",
                "platform": "Android" if fp.data["mobile"] else "Windows",
                "platformVersion": "13.0.0" if fp.data["mobile"] else "15.0.0",
                "architecture": "arm" if fp.data["mobile"] else "x86",
                "model": "2201117PG" if fp.data["mobile"] else "",
                "mobile": fp.data["mobile"],
            }}, timeout=10)
        await cdp.cmd("Page.enable", {}, timeout=10)
        await cdp.cmd("Page.navigate", {"url": url}, timeout=15)

        deadline = time.time() + timeout
        clicked_at = 0.0
        stable_rounds = 0
        while time.time() < deadline:
            await asyncio.sleep(2.5)
            try:
                raw = await cdp.js(_DETECT_JS, timeout=10)
                info = __import__("json").loads(raw) if isinstance(raw, str) else {}
            except Exception:
                continue
            ctype = _classify(info)
            result.challenge_type = ctype
            jar = await _cookies(cdp)
            if any(k in jar for k in SOLVED_COOKIES):
                result.solved = True
                result.cookies = jar
                result.cf_clearance = jar.get("cf_clearance")
                result.cf_bm = jar.get("__cf_bm") or jar.get("cf_bm")
                result.note = "clearance cookie present"
                return result
            if ctype == "none":
                stable_rounds += 1
                if stable_rounds >= 2:
                    result.note = "no challenge detected"
                    return result
                continue
            stable_rounds = 0
            if ctype == "turnstile_interactive":
                box = info.get("widgetBox") or info.get("cfFrame")
                if box and box.get("w", 0) >= 10 and time.time() - clicked_at > 9:
                    clicked_at = time.time()
                    cx, cy = box["x"] + box["w"] / 2, box["y"] + box["h"] / 2
                    await _human_click(cdp, cx, cy)
            # managed/js: just wait — a real browser clears these itself
        result.note = "timeout waiting for clearance"
        return result
    finally:
        result.elapsed = time.time() - t0
        try:
            await cdp.close()
        except Exception:
            pass
        chrome.kill()


async def _solve_async(url: str, profile: str = "mobile", timeout: float = 75,
                       max_attempts: int = 2, persist: bool = True) -> SolverResult:
    host = urllib.parse.urlparse(url).hostname or url
    store = SessionStore()
    if persist:
        cached = store.get(host)
        if cached and cached["valid"] and cached.get("cf_clearance"):
            return SolverResult(host=host, solved=True, challenge_type="cached",
                                cookies=cached["cookies"],
                                cf_clearance=cached["cf_clearance"],
                                cf_bm=cached.get("cf_bm"), attempts=0,
                                note="valid cached session")
    last: SolverResult | None = None
    for attempt in range(1, max_attempts + 1):
        # fresh profile each attempt (burned fingerprints don't recover)
        last = await _solve_once(url, profile, timeout,
                                 headless_shell_ok=True)
        last.attempts = attempt
        if last.solved:
            if persist:
                ttl = 3600 if last.cf_clearance else 1500
                store.save(host, "", last.cookies, last.cf_clearance,
                           last.cf_bm, ttl)
            return last
        if last.challenge_type == "none":
            return last  # nothing to solve; don't burn another profile
    return last


def solve(url: str, profile: str = "mobile", timeout: float = 75,
          max_attempts: int = 2, persist: bool = True) -> SolverResult:
    """Solve Cloudflare challenge at url. Returns SolverResult."""
    return asyncio.run(_solve_async(url, profile, timeout, max_attempts, persist))
