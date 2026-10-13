"""Offline unit tests: no browser, no network, no API keys."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from specterx import stealth
from specterx.fingerprint import Fingerprint
from specterx.launcher import find_chrome
from specterx.session import SessionStore
from specterx.solver import _classify


def test_fingerprint_mobile_consistent():
    fp = Fingerprint("example.com", base="mobile")
    d = fp.as_dict()
    assert "Android" in d["ua"] and "Mobile" in d["ua"]
    assert "arm" in d["platform"]
    assert d["max_touch_points"] > 0
    assert d["screen_width"] >= d["avail_width"]


def test_fingerprint_desktop_consistent():
    fp = Fingerprint("example.com", base="desktop")
    d = fp.as_dict()
    assert "Android" not in d["ua"]
    assert d["max_touch_points"] == 0


def test_fingerprint_deterministic():
    a = Fingerprint("example.com").as_dict()
    b = Fingerprint("example.com").as_dict()
    c = Fingerprint("other.org").as_dict()
    assert a["seed"] == b["seed"]
    assert a["seed"] != c["seed"]
    assert a["ua"] == b["ua"]
    assert a["canvas_seed"] == b["canvas_seed"]


def test_fingerprint_platform_no_typo():
    fp = Fingerprint("example.com", base="mobile")
    assert fp.as_dict()["platform"] == "Linux armv8l"


def test_stealth_build_sanity():
    fp = Fingerprint("example.com", base="mobile").as_dict()
    js = stealth.build(fp)
    assert "Linux armv8l" in js
    assert "Mali-G57 MC2" in js
    assert "console.log" not in js  # no beacon
    assert "addScriptToEvaluateOnNewDocument" not in js  # injection is CDP-side
    assert "__specterx_fp" in js


def test_stealth_build_desktop():
    fp = Fingerprint("example.com", base="desktop").as_dict()
    js = stealth.build(fp)
    assert "Win32" in js
    assert "Android" not in js


def test_classify():
    ti = "turnstile_interactive"
    assert _classify({"cfFrame": {"x": 1}, "widgetBox": None, "managed": False}) == ti
    assert _classify({"cfFrame": None, "widgetBox": {"w": 50}, "managed": False}) == ti
    assert _classify({"cfFrame": None, "widgetBox": None, "managed": True}) == "managed"
    assert _classify({"cfFrame": None, "widgetBox": None, "managed": False}) == "none"


def test_session_roundtrip(tmp_path):
    store = SessionStore(path=tmp_path / "t.db")
    store.save("example.com", "ua", {"a": "1"}, "CLR", "BM", ttl=3600)
    got = store.get("example.com")
    assert got["valid"] is True
    assert got["cf_clearance"] == "CLR"
    assert got["cookies"] == {"a": "1"}
    assert got["expires_in"] > 3500


def test_session_expired(tmp_path):
    store = SessionStore(path=tmp_path / "t.db")
    store.save("example.com", "ua", {}, None, None, ttl=-1)
    assert store.get("example.com")["valid"] is False


def test_session_missing(tmp_path):
    store = SessionStore(path=tmp_path / "t.db")
    assert store.get("nope.example") is None


def test_find_chrome_explicit_missing():
    with pytest.raises(FileNotFoundError):
        find_chrome(explicit="/nonexistent/chrome-binary")


def test_find_chrome_env(monkeypatch, tmp_path):
    fake = tmp_path / "chrome"
    fake.write_text("#!/bin/sh\n")
    monkeypatch.setenv("SPECTERX_CHROME", str(fake))
    assert find_chrome() == str(fake)
