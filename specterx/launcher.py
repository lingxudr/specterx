"""Portable Chrome launcher. No Termux/proot hardcode.

Binary resolution order:
  1. $SPECTERX_CHROME env var
  2. shutil.which() for common binary names
  3. well-known install paths (Linux/macOS)

Profile dir defaults to a fresh temp dir per run (override with $SPECTERX_PROFILE
or the profile_dir argument for persistence).
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request

_CANDIDATES = [
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
    "chrome", "chrome-headless-shell",
]

_KNOWN_PATHS = [
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/opt/google/chrome/chrome",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/tmp/chrome-headless-shell-linux64/chrome-headless-shell",
    os.path.expanduser("~/chrome-headless-shell-linux64/chrome-headless-shell"),
]


def find_chrome(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("SPECTERX_CHROME")
    if env and os.path.exists(env):
        return env
    for name in _CANDIDATES:
        p = shutil.which(name)
        if p:
            return p
    for p in _KNOWN_PATHS:
        if p and os.path.exists(p):
            return p
    raise FileNotFoundError(
        "No Chrome/Chromium binary found. Set SPECTERX_CHROME=/path/to/chrome")


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class LaunchedChrome:
    def __init__(self, binary: str, port: int, profile_dir: str, proc: subprocess.Popen):
        self.binary = binary
        self.port = port
        self.profile_dir = profile_dir
        self.proc = proc
        self.debug_url = f"http://127.0.0.1:{port}"

    def version(self) -> dict:
        with urllib.request.urlopen(f"{self.debug_url}/json/version",
                                    timeout=5) as r:
            return json.loads(r.read().decode())

    def kill(self):
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass


def launch(user_agent: str, window_size: str = "1080,2400",
           profile_dir: str | None = None, binary: str | None = None,
           extra_flags: list[str] | None = None,
           timeout: int = 30) -> LaunchedChrome:
    chrome = find_chrome(binary)
    port = _free_port()
    if profile_dir is None:
        profile_dir = os.environ.get("SPECTERX_PROFILE") or tempfile.mkdtemp(
            prefix="specterx-profile-")
    os.makedirs(profile_dir, exist_ok=True)

    flags = [
        chrome,
        "--headless=new" if "headless-shell" not in chrome else "--headless",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-background-networking",
        "--disable-component-update",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=" + window_size,
        f"--user-data-dir={profile_dir}",
        f"--user-agent={user_agent}",
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        "about:blank",
    ]
    # NOTE: user_agent passed via flag AND via CDP Network.setUserAgentOverride
    # (the CDP override also sets UA metadata / brands, which the flag alone
    # does not).
    if extra_flags:
        flags.extend(extra_flags)

    log_path = os.path.join(tempfile.gettempdir(), f"specterx-chrome-{port}.log")
    with open(log_path, "w") as log:
        proc = subprocess.Popen(flags, stdout=log, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True)

    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version",
                                        timeout=2) as r:
                json.loads(r.read().decode())
                return LaunchedChrome(chrome, port, profile_dir, proc)
        except Exception as e:
            last_err = e
            if proc.poll() is not None:
                break
            time.sleep(0.5)
    try:
        proc.kill()
    except Exception:
        pass
    raise RuntimeError(f"Chrome failed to start in {timeout}s: {last_err} "
                       f"(log: {log_path})")
