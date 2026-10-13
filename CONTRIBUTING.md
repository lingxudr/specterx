# Contributing

## Ground rules

- Only work on targets you own or are authorized to test. PRs that add
  features aimed at unauthorized use will be rejected.
- Keep the dependency footprint minimal. `websockets` is the only runtime
  dependency; proposals adding new ones need a strong justification.
- No vendored binaries, no bundled Chrome.

## Development setup

```bash
git clone https://github.com/lingxudr/specterx
cd specterx
pip install -e ".[dev]"
```

## Checks before opening a PR

```bash
ruff check specterx/ tests/test_unit.py
pytest -q
python3 tests/test_local.py   # needs a real Chrome binary
```

CI runs ruff + the offline unit tests on Python 3.10–3.12. The integration
test (`test_local.py`) is run manually since it needs a browser.

## Code style

- `ruff` with the repo's `pyproject.toml` config is the linter of record.
- Broad `except Exception` around best-effort CDP calls is an intentional
  resilience pattern here (documented in `pyproject.toml`) — don't "fix" it
  into narrow handlers that let a flaky browser kill a solve.
- Keep the stealth JS in `stealth.py` free of `console.log` and any beacon;
  every patch should preserve native `toString`.

## Pull requests

- Small, focused PRs. One behavior change per PR.
- Add or update tests for behavior changes. Offline unit tests go in
  `tests/test_unit.py`; browser-dependent flows go in `tests/test_local.py`.
- Update the README if you change CLI flags, env vars, or the module layout.
- Describe what you tested and on which Chrome version.
