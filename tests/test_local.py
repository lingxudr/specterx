"""Local verification: real browser, stealth assertions, mock-server flow.

Run:  python3 tests/test_local.py
Requires: chrome binary visible to launcher (SPECTERX_CHROME or PATH),
          websockets installed, mock server from the specter repo.
"""
import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
SPECTER = os.path.expanduser("~/workspace/specter-review")
sys.path.insert(0, SPECTER)

from specterx import stealth
from specterx.cdp import CDPClient, pick_target
from specterx.fingerprint import Fingerprint
from specterx.launcher import launch

MOCK_PORT = 18801
mock_proc = None


def start_mock():
    global mock_proc
    mock_proc = subprocess.Popen(
        [sys.executable, "-m", "specter", "--serve-mock", "--port", str(MOCK_PORT)],
        cwd=SPECTER, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{MOCK_PORT}/healthz",
                                        timeout=2) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("mock server did not start")


CHECKS_JS = """JSON.stringify({
  webdriver: ("webdriver" in navigator) ? String(navigator.webdriver) : "absent",
  platform: navigator.platform,
  hwc: navigator.hardwareConcurrency,
  touch: navigator.maxTouchPoints,
  lang: navigator.language,
  langs: navigator.languages.join(","),
  tzOff: new Date().getTimezoneOffset(),
  dpr: window.devicePixelRatio,
  scr: screen.width + "x" + screen.height,
  plugins: navigator.plugins.length,
  glVendor: (() => { const c = document.createElement("canvas");
    const g = c.getContext("webgl"); return g ? g.getParameter(37445) : "n/a"; })(),
  glRenderer: (() => { const c = document.createElement("canvas");
    const g = c.getContext("webgl"); return g ? g.getParameter(37446) : "n/a"; })(),
  fpFlag: !!window.__specterx_fp
})"""


async def main():
    fp = Fingerprint("127.0.0.1", base="mobile")
    chrome = launch(fp.user_agent())
    cdp = CDPClient()
    fails = []
    try:
        target = pick_target(chrome.debug_url)
        await cdp.connect(target["webSocketDebuggerUrl"])
        await cdp.cmd("Page.addScriptToEvaluateOnNewDocument",
                      {"source": stealth.build(fp.as_dict())}, timeout=10)
        await cdp.cmd("Page.enable", {}, timeout=10)
        await cdp.cmd("Page.navigate", {"url": "about:blank"}, timeout=10)
        await asyncio.sleep(1.5)
        raw = await cdp.js(CHECKS_JS, timeout=10)
        got = json.loads(raw)
        d = fp.data
        expect = {
            "platform": d["platform"],
            "hwc": d["hardware_concurrency"],
            "touch": d["max_touch_points"],
            "lang": d["languages"][0],
            "tzOff": d["tz_offset_min"],
            "dpr": d["device_pixel_ratio"],
            "scr": f"{d['screen_width']}x{d['screen_height']}",
            "plugins": 0,
            "glVendor": d["webgl_vendor"],
            "glRenderer": d["webgl_renderer"],
            "fpFlag": True,
        }
        print("== stealth assertions ==")
        for k, v in expect.items():
            ok = got.get(k) == v
            print(f"  [{'PASS' if ok else 'FAIL'}] {k}: got={got.get(k)!r} want={v!r}")
            if not ok:
                fails.append(k)
        # webdriver must read as "false", exactly like a real user-driven browser
        # (automated Chrome reports "true"; throwing would also be suspicious)
        wd = got.get("webdriver")
        wd_ok = wd == "false"
        print(f"  [{'PASS' if wd_ok else 'FAIL'}] webdriver: got={wd!r} (real browsers report false)")
        if not wd_ok:
            fails.append("webdriver")

        # mock challenge flow: navigate, confirm no crash, cookies visible
        await cdp.cmd("Page.navigate",
                      {"url": f"http://127.0.0.1:{MOCK_PORT}/cloudflare"}, timeout=10)
        await asyncio.sleep(2)
        r = await cdp.cmd("Network.getAllCookies", {}, timeout=8)
        names = sorted(ck["name"] for ck in r.get("cookies", []))
        ok = "cf_clearance" in names
        print(f"  [{'PASS' if ok else 'FAIL'}] mock cookie harvest: {names}")
        if not ok:
            fails.append("cookies")
    finally:
        await cdp.close()
        chrome.kill()
    print("RESULT:", "ALL PASS" if not fails else f"FAILURES: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    start_mock()
    try:
        rc = asyncio.run(main())
    finally:
        if mock_proc:
            mock_proc.terminate()
    sys.exit(rc)
