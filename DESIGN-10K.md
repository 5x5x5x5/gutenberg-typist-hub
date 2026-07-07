# DESIGN-10K: the greenfield hub for 10,000 users

What this system looks like designed from scratch for 10,000 users — no
incrementalism constraint. Companion to `SCALING.md` (the incremental
playbook); the ingress-service trigger there and this document describe the
same destination.

## Requirements

~4,300 submissions/day (10+/min peaks) · 30–100k page views/day · strangers,
so anti-cheat and moderation are first-class · mobile-first reading · history
as the engagement feature · solo maintainer · < $20/month.

Two things survive unchanged from today, because they were designed for this:
**bundle format v1 as the wire format** (identity-free, mergeable, versioned)
and the Vim-buffer aesthetic.

## Architecture

```
Vim plugin ──:GT publish──▶ POST /api/v1/upload (Bearer token)
                                   │  FastAPI on one VPS
                                   ▼
                            SQLite (WAL) ──Litestream──▶ R2 (continuous backup)
                                   │
                      board JSON materialized every ~30 s
                                   │
Browser ◀── Cloudflare free tier (edge cache) ◀── Caddy (auto-TLS)
```

**Stack: FastAPI + SQLite + Caddy on a ~$6 VPS, Cloudflare free in front.**
Why: the maintainer's tooling (uv/ruff/mypy/pytest); `build.py`'s pure
validate/merge functions port as-is; 4,300 writes/day is 0.05 writes/sec —
SQLite in WAL mode is comically sufficient and Litestream makes it durable;
the edge cache takes effectively all read traffic off the box. Serverless
alternative if zero-box is preferred: Cloudflare Workers + D1 + Pages, same
data model.

## Identity & client

- **GitHub OAuth creates an account** (zero passwords; the Vim crowd already
  lives there). Store the **immutable numeric GitHub ID** plus a login
  snapshot — username recycling solved structurally.
- The account page issues a long-lived API token; the user sets
  `g:gt_hub_token` once. The plugin gains **`:GT publish`** (~30 lines:
  ExportBundle to a temp file + async curl POST). Submission UX collapses to
  one Vim command — no git, no fork, no clone.
- Per-token and per-IP rate limits; 1 MB body cap; the same sanitization
  rules the static build uses today.

## Data model (SQLite)

```
users(id /* github numeric id */, login, created_at, banned_at, token_hash)
machines(user_id, machine_id, total_chars, correct_chars,
         total_time_seconds, sessions_count, best_wpm, updated_at,
         PK(user_id, machine_id))            -- canonical merged state
submissions(id, user_id, received_at, bundle_sha256, deltas_json, flagged)
                                             -- append-only audit log
sessions(user_id, book_id, offset, last_active)
```

- `machines` keeps the CRDT semantics server-side: ingest merges
  **union-max per machine**, so an old or replayed upload can never shrink
  anything — exactly the bundle format's contract.
- `submissions` is simultaneously the audit log, the time-series for profile
  sparklines, and the anti-cheat input. **It replaces what git history
  provides today.**

## Anti-cheat & moderation (first-class)

- Ingest-time plausibility on **deltas between submissions**: chars gained
  bounded by elapsed time × claimed WPM × slack; per-machine monotonicity
  enforced (shrinking counters rejected — already the format contract);
  ceiling breaches flag rather than reject.
- The default board shows unflagged entries; an "open" view shows everything.
  Honesty: client-owned data can't be proven, only made expensive to fake.
- Moderation is an admin CLI against the same API: ban (tombstone, audit
  kept), unflag, purge. Today's `denylist.txt` becomes `users.banned_at`.
- Bundle format v2 (optional, additive, incident-driven only): per-session
  timestamped records for richer signals. v1 accepted forever.

## Frontend

Same Dracula/Vim-buffer identity. Board = top-100 + `/` search + "find me"
against paginated JSON; per-user profile pages with sparkline history from
`submissions`; card layout under 640 px; a community strip (total chars
typed, books finished). Still vanilla JS, still served static — the board
JSON re-materializes every ~30 s and edge-caches.

## Ops & cost

systemd + uv on one box; Caddy auto-TLS; CF cache rules for board JSON;
Litestream → R2 (~$1/mo); a **nightly public dataset export** committed to
the archival git repo keeps the public-data ethos the git design had.
Metrics endpoint + external uptime ping. It's a leaderboard — minutes of
downtime are acceptable, which is exactly what makes one box fine.
**Total: ~$7–10/month.**

## Migration from the git-native system

1. An importer reads `bundles/*.json` AND replays the full `git log` into
   `submissions` — the git history seeds the time-series (it was collected
   for exactly this).
2. Claim flow: first OAuth login whose login matches an existing bundle
   filename links the history; the numeric ID is recorded from then on.
3. Transition: `submit` gains an HTTP mode; the fork-PR path runs through a
   deprecation window, then automerge turns off; the repo stays as code +
   nightly data archive.
4. The plugin ships `:GT publish`; `:GT export`/`:GT import` are unchanged.

## Verification plan

- pytest against the FastAPI app: upload/merge/monotonicity/flagging/auth,
  plus the existing merge-parity suite ported as property tests.
- Load sanity on the actual VPS class: 10× expected peak (2 req/s sustained
  uploads, 100 req/s cached reads) with hey/wrk.
- Migration rehearsal: replay the real repo's git history into a staging DB;
  diff the resulting board against the live `data.json`.
- End-to-end: `:GT publish` from a real Vim session against staging.
