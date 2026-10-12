"""SQLite session/cookie persistence with TTL validation."""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path


def _db_path() -> Path:
    base = os.environ.get("SPECTERX_DATA") or os.path.expanduser("~/.specterx")
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    return p / "sessions.db"


class SessionStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else _db_path()
        self._init()

    def _init(self):
        with sqlite3.connect(self.path) as c:
            c.execute("""CREATE TABLE IF NOT EXISTS sessions (
                host TEXT PRIMARY KEY,
                user_agent TEXT,
                cookies TEXT,
                cf_clearance TEXT,
                cf_bm TEXT,
                saved_at REAL,
                ttl REAL,
                success_count INTEGER DEFAULT 0
            )""")

    def save(self, host: str, user_agent: str, cookies: dict,
             cf_clearance: str | None, cf_bm: str | None, ttl: float):
        import json
        with sqlite3.connect(self.path) as c:
            c.execute("""INSERT INTO sessions
                (host, user_agent, cookies, cf_clearance, cf_bm, saved_at, ttl, success_count)
                VALUES (?,?,?,?,?,?,?,1)
                ON CONFLICT(host) DO UPDATE SET
                    user_agent=excluded.user_agent, cookies=excluded.cookies,
                    cf_clearance=excluded.cf_clearance, cf_bm=excluded.cf_bm,
                    saved_at=excluded.saved_at, ttl=excluded.ttl,
                    success_count=success_count+1""",
                (host, user_agent, json.dumps(cookies), cf_clearance, cf_bm,
                 time.time(), ttl))

    def get(self, host: str) -> dict | None:
        import json
        with sqlite3.connect(self.path) as c:
            c.row_factory = sqlite3.Row
            row = c.execute("SELECT * FROM sessions WHERE host=?",
                            (host,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["cookies"] = json.loads(d["cookies"] or "{}")
        d["valid"] = (time.time() - d["saved_at"]) < d["ttl"]
        d["expires_in"] = max(0, d["ttl"] - (time.time() - d["saved_at"]))
        return d

    def clear(self, host: str):
        with sqlite3.connect(self.path) as c:
            c.execute("DELETE FROM sessions WHERE host=?", (host,))
