# specterx

[![CI](https://github.com/lingxudr/specterx/actions/workflows/ci.yml/badge.svg)](https://github.com/lingxudr/specterx/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

Portable, hardened Cloudflare Turnstile / challenge solver. Automates a real
Chrome through CDP: injects a consistent device fingerprint before any page
script runs, clicks interactive Turnstile widgets with human-like mouse
motion, waits out managed challenges, and harvests the resulting session
(`cf_clearance`, `__cf_bm`, cookies) into a persistent cache.

Built as a clean-room improvement over `lingxudr/specter` after auditing it.
It does not exploit Cloudflare — it drives a real browser the way the
challenge expects to be driven.

> **Authorized testing only.** Use specterx on systems you own or are
> explicitly authorized to test. See [SECURITY.md](SECURITY.md).

## Features

- **Portable launcher** — auto-detects the Chrome binary (`SPECTERX_CHROME`
  or PATH), uses throwaway profiles in a temp dir. No Termux/proot hardcode;
  works on any Linux/macOS with Chrome.
- **Hardened stealth** — injected via `Page.addScriptToEvaluateOnNewDocument`,
  so it runs before page scripts, survives navigation, and covers iframes
  (including the Turnstile iframe itself). Patches are masked to look native
  (`toString` preserved); `navigator.webdriver` is deleted rather than set to
  `undefined`.
- **Consistent fingerprints** — seeded per host; UA, platform, touch, screen,
  WebGL vendor/renderer and timezone are validated to agree at build time
  (no more `Linux armv81` typos).
- **Human-like input** — cubic-bezier mouse paths with jitter, ease-out
  timing, dwell before press, and realistic hold time.
- **Solver state machine** — classifies the challenge as
  `turnstile_interactive` / `managed` / `none` and acts accordingly; retries
  with a fresh profile; reuses valid cached sessions without relaunching.
- **Session cache** — SQLite store (`~/.specterx/sessions.db`, override with
  `SPECTERX_DATA`); solved sessions are reused until expiry.

## Install

Requires Python 3.10+ and a Chrome/Chromium binary.

```bash
pip install specterx            # from PyPI (once published)
# or from source:
git clone https://github.com/lingxudr/specterx
cd specterx && pip install .
```

Only hard dependency: `websockets`.

```bash
export SPECTERX_CHROME=/path/to/chrome   # or put chrome on PATH
```

## Quickstart

```bash
specterx "https://staging.example.com" --profile mobile
specterx "https://staging.example.com" --json --timeout 60 --attempts 3
```

As a library:

```python
from specterx import solve

r = solve("https://staging.example.com", profile="mobile")
if r.solved:
    print(r.cf_clearance)   # cookie value, or None
    print(r.cookies)        # harvested cookie dict
```

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `SPECTERX_CHROME` | Path to the Chrome binary | auto-detect |
| `SPECTERX_DATA` | Directory for `sessions.db` | `~/.specterx` |

CLI flags: `--profile {mobile,desktop}`, `--timeout` (seconds per attempt),
`--attempts` (fresh-profile retries), `--no-persist` (skip session cache),
`--json` (machine-readable output). Exit code 0 on solve, 1 otherwise.

## How it works

```
launcher  ->  Chrome --headless=new --remote-debugging-port=...
stealth   ->  addScriptToEvaluateOnNewDocument(fp JS)   [before any page JS]
fingerprint -> seeded per-host device profile, consistency-checked
solver    ->  detect challenge type
              ├─ turnstile_interactive: find widget, human-click it
              ├─ managed: wait for auto-clearance
              └─ none: harvest cookies immediately
session   ->  cache cf_clearance/__cf_bm per host, reuse while valid
```

A valid cached session short-circuits the whole flow — the browser is never
launched.

## Testing

```bash
pip install ".[dev]"
pytest -q                 # offline unit tests (no browser, no network)
python3 tests/test_local.py   # integration: mock server + real browser
```

`tests/test_local.py` spins up a mock Cloudflare page, launches a real
browser, and asserts every spoofed fingerprint property plus the
cookie-harvest flow. CI runs lint + unit tests on Python 3.10–3.12.

## Limitations

- Challenge triggering is decided server-side by Cloudflare's risk engine
  (IP reputation, fingerprint, behavior, cookies). specterx lowers the risk
  score; it cannot force a pass, and datacenter IPs will still be challenged
  more often than residential ones.
- Managed challenges and interactive widgets are handled; image-based
  third-party captchas (hCaptcha image grids, Aliyun slide) are out of scope.
- Cloudflare changes detection signals over time — expect maintenance.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

See [SECURITY.md](SECURITY.md) for the vulnerability-reporting policy.

## License

MIT — see [LICENSE](LICENSE).
