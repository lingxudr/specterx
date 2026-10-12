"""specterx CLI: solve a Cloudflare challenge and print the session."""
from __future__ import annotations

import argparse
import json
import sys

from .solver import solve


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="specterx",
                                description="Solve Cloudflare challenge, harvest session")
    p.add_argument("url", help="target URL (staging you own / are authorized to test)")
    p.add_argument("--profile", default="mobile", choices=["mobile", "desktop"],
                   help="device profile (default: mobile)")
    p.add_argument("--timeout", type=float, default=75,
                   help="seconds per attempt (default: 75)")
    p.add_argument("--attempts", type=int, default=2,
                   help="max attempts with fresh profiles (default: 2)")
    p.add_argument("--no-persist", action="store_true",
                   help="don't read/write the session cache")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args(argv)

    r = solve(args.url, profile=args.profile, timeout=args.timeout,
              max_attempts=args.attempts, persist=not args.no_persist)
    if args.json:
        print(json.dumps({
            "host": r.host, "solved": r.solved,
            "challenge_type": r.challenge_type, "attempts": r.attempts,
            "elapsed": round(r.elapsed, 1), "note": r.note,
            "cf_clearance": bool(r.cf_clearance), "cf_bm": bool(r.cf_bm),
            "cookie_names": sorted(r.cookies.keys()),
        }, indent=2))
    else:
        print(f"host:           {r.host}")
        print(f"solved:         {r.solved}")
        print(f"challenge:      {r.challenge_type}")
        print(f"attempts:       {r.attempts}")
        print(f"elapsed:        {r.elapsed:.1f}s")
        print(f"note:           {r.note}")
        print(f"cf_clearance:   {'yes' if r.cf_clearance else 'no'}")
        print(f"cf_bm:          {'yes' if r.cf_bm else 'no'}")
        print(f"cookies:        {sorted(r.cookies.keys())}")
    return 0 if r.solved else 1


if __name__ == "__main__":
    sys.exit(main())
