# Security Policy

## Scope

specterx is a browser-automation tool for **authorized testing** — systems
you own or are explicitly permitted to test. It is not intended for, and must
not be used for, unauthorized access to third-party systems.

## Reporting a vulnerability

If you find a security issue in specterx itself (e.g. the tool leaking
session data, executing untrusted input, or a supply-chain problem in its
dependencies):

- **Do not** open a public issue.
- Open a private security advisory on GitHub
  (`Security` tab → `Report a vulnerability`), or email the maintainer
  through the address listed on their GitHub profile.
- Include: what the issue is, how to reproduce it, and what you think the
  impact is.

We aim to acknowledge reports within 7 days and will coordinate a fix before
any public disclosure.

## What is in scope

- Vulnerabilities in specterx code: session store handling, Chrome launcher
  argument construction, CDP client, stealth injection.
- Dependency issues that are actually exploitable through specterx's usage.

## What is out of scope

- Reports that specterx can be used to bypass Cloudflare challenges — that
  is the tool's stated purpose on authorized targets, not a vulnerability
  in the tool.
- Vulnerabilities in Cloudflare itself — report those to Cloudflare.
- Automated scanner output without a demonstrated impact.

## Data handling

specterx stores solved sessions (`cf_clearance`, cookies) in a local SQLite
file under `~/.specterx/` (or `SPECTERX_DATA`). Treat that file like a
credential store: it grants the access the session had. Do not commit it,
do not share it, and delete it when the engagement ends.
