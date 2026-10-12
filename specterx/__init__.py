"""specterx — portable, hardened Cloudflare Turnstile / challenge solver.

Modules:
    launcher    portable Chrome launcher (no Termux hardcode)
    stealth     hardened fingerprint-spoofing JS
    fingerprint consistent device profiles
    cdp         minimal async CDP client
    solver      challenge detection + solve state machine
    session     SQLite cookie/session persistence
"""
from .solver import solve, SolverResult

__all__ = ["solve", "SolverResult"]
__version__ = "0.1.0"
