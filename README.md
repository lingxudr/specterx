# specterx

Portable, hardened Cloudflare Turnstile / challenge solver. Built as a
clean-room improvement over `lingxudr/specter` after auditing it.

## What changed vs the original

| Area | Original | specterx |
|---|---|---|
| Launcher | Hardcoded Termux/proot paths, `proot-distro` | Auto-detects Chrome binary (`SPECTERX_CHROME` or PATH), temp profiles, any Linux/macOS |
| Stealth injection | Manual per-page `evaluate` | `Page.addScriptToEvaluateOnNewDocument` — runs before page scripts, survives navigation, covers iframes |
| Fingerprint | `"Linux armv81"` typo, no consistency checks | Typo fixed (`armv8l`), profile validated at build (UA/platform/touch/screen must agree) |
| `navigator.webdriver` | Set to `undefined` (detectable) | Property deleted / throws on access — no clean boolean leak |
| Patched functions | Raw overrides (`toString` leaks) | `toString` masked to look native |
| UA metadata | Flag-only UA (brands missing) | `Network.setUserAgentOverride` with full UA-CH brands |
| Mouse | Bezier + jitter | Bezier + jitter + ease-out timing + dwell + hold time |
| Solver | Fixed 90s loop, single profile | State machine (interactive/managed/none), fresh profile per retry, cached valid sessions reused |
| Tests | Mock serves cookies freely; `cookies_n >= 0` tautology | Stealth assertions against a real browser + honest mock-flow check |

## Install

```bash
pip install websockets          # only hard dependency
export SPECTERX_CHROME=/path/to/chrome   # or put chrome on PATH
```

## Use

```bash
python3 -m specterx "https://staging.example.com" --profile mobile
python3 -m specterx "https://staging.example.com" --json --timeout 60
```

Sessions persist to `~/.specterx/sessions.db` (override with `SPECTERX_DATA`).

## Verify locally

```bash
python3 tests/test_local.py
```

Spins up the mock server, launches a real browser, asserts every spoofed
fingerprint property, and checks the cookie-harvest flow.

## Scope

For authorized testing (your own staging / targets you may test). The tool
automates a real browser — it does not exploit Cloudflare.
