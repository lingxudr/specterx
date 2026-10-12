"""Consistent device fingerprints. Single source of truth: every spoofed
value (UA, platform, WebGL, screen, touch, timezone) derives from one
profile, so nothing contradicts itself under inspection."""
from __future__ import annotations

import hashlib
import random


MOBILE = {
    "name": "android_chrome_mid",
    "ua": ("Mozilla/5.0 (Linux; Android 13; 2201117PG) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/{cv} Mobile Safari/537.36"),
    "chrome_version": "130.0.6723.91",
    "platform": "Linux armv8l",
    "hardware_concurrency": 8,
    "device_memory": 4,
    "max_touch_points": 5,
    "screen_width": 1080,
    "screen_height": 2400,
    "avail_width": 1080,
    "avail_height": 2400,
    "color_depth": 24,
    "pixel_depth": 24,
    "device_pixel_ratio": 2.75,
    "webgl_vendor": "ARM",
    "webgl_renderer": "Mali-G57 MC2",
    "mobile": True,
    "touch": True,
    "languages": ["en-US", "en"],
}

DESKTOP = {
    "name": "win_chrome_desktop",
    "ua": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/{cv} Safari/537.36"),
    "chrome_version": "130.0.6723.91",
    "platform": "Win32",
    "hardware_concurrency": 12,
    "device_memory": 8,
    "max_touch_points": 0,
    "screen_width": 1920,
    "screen_height": 1080,
    "avail_width": 1920,
    "avail_height": 1040,
    "color_depth": 24,
    "pixel_depth": 24,
    "device_pixel_ratio": 1.0,
    "webgl_vendor": "Google Inc. (NVIDIA)",
    "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0, D3D11)",
    "mobile": False,
    "touch": False,
    "languages": ["en-US", "en"],
}

_TIMEZONES = [
    ("America/Los_Angeles", 480), ("America/New_York", 300),
    ("Europe/London", 0), ("Europe/Berlin", -60),
    ("Asia/Jakarta", -420), ("Asia/Singapore", -480),
]


class Fingerprint:
    """Deterministic per-host fingerprint derived from a base profile."""

    def __init__(self, host: str, base: str = "mobile", seed: int | None = None):
        self.host = host
        tpl = MOBILE if base == "mobile" else DESKTOP
        if seed is None:
            seed = int.from_bytes(hashlib.sha256(host.encode()).digest()[:4], "big")
        rng = random.Random(seed)
        d = dict(tpl)
        d["seed"] = seed
        d["ua"] = tpl["ua"].format(cv=tpl["chrome_version"])
        d["languages"] = list(tpl["languages"])
        if rng.random() < 0.35:
            d["languages"] = ["en-US", "en", "id-ID", "id"]
        tz, off = rng.choice(_TIMEZONES)
        d["timezone"] = tz
        d["tz_offset_min"] = off
        d["canvas_seed"] = seed
        self.data = d
        self._validate()

    def _validate(self):
        d = self.data
        if d["mobile"]:
            assert "Android" in d["ua"] and "Mobile" in d["ua"], "UA/mobile mismatch"
            assert "arm" in d["platform"], "platform/mobile mismatch"
            assert d["max_touch_points"] > 0, "touch/mobile mismatch"
        else:
            assert "Android" not in d["ua"], "UA/desktop mismatch"
            assert d["max_touch_points"] == 0, "touch/desktop mismatch"
        assert d["screen_width"] >= d["avail_width"], "screen/avail mismatch"

    def user_agent(self) -> str:
        return self.data["ua"]

    def as_dict(self) -> dict:
        return dict(self.data)
