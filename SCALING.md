# Scaling playbook

What strains as the board grows, and what to do about it — **act on the
trigger signals below, not on user counts** (user count is a lagging proxy).
Platform numbers verified June 2026.

## Already done (the 10–100 phase + hardening)

Fork+PR submissions auto-merged by bot; per-PR bundle validation; `/` filter;
denylist; machine-id display sanitization; compact data.json; sha-guarded
merges; deploy dispatch after bot merges.

## What strains at ~1,000 users (~430 submissions/day)

The #1 strain is **trust, not infrastructure**: strangers replace friends.
Sub-threshold fakes, sybil accounts, junk in display text. The levers, in
order: the first-time-contributor approval gate (each new account costs the
maintainer one "Approve workflows" click — that is the gate working),
`denylist.txt`, and plausibility heuristics (below).

The #2 strain is the **shared GITHUB_TOKEN budget: 1,000 API requests/hour
per repo** across ALL workflows. Automerge (~6/PR) plus deploy (~5/merge)
brushes the cap around 80–100 merges/hour. When it bites, automerge starts
403ing and PRs strand with green checks.

Non-issues, verified: Pages' 10-builds/hour limit does NOT apply to
Actions-based deploys; Actions minutes are free and unlimited on public
repos (20 concurrent jobs).

## What strains at ~10,000 users (~4,300 submissions/day)

Git-as-write-path is the wrong model: ~1.6M commits/year, PR spam swamps
notifications and the 20-job concurrency cap at peak, first-contributor
approvals become dozens of clicks/day, and unsplit data.json (~30MB raw)
blows both the page and the 100GB/month Pages bandwidth limit. The exit is
the **ingress service** (bottom row) — the bundle format was designed for it:
identity-free bundles, identity attributed at upload, pure validate/merge
functions in build.py that port directly.

## Trigger table

| Action | Trigger |
| --- | --- |
| Split data.json → slim summary + per-user detail shards; debounce the filter | data.json > ~1 MB gzipped, or > ~300 rows |
| Cron-coalesced deploys (every 10–15 min instead of per-merge; frees ~half the API budget) | First 403 in automerge/deploy logs, or sustained > 100 submissions/hr |
| Cron sweep re-attempting eligible unmerged green PRs | First "my PR passed but never merged" report |
| Record immutable numeric GitHub user ID alongside login (logins get recycled!) | First rename/recycle dispute, or before ~1k users |
| Plausibility heuristics from git-history deltas (chars gained bounded by elapsed × WPM) | First confirmed hand-edited fake |
| Notification triage; recruit a second maintainer | > 20 PRs/day; > 1 hr/week on moderation |
| Mobile/responsive table treatment | Complaints, or > 25% mobile traffic |
| Custom domain fronting the board (later reused by the API) | Before the next user cohort — the only item where earlier is strictly cheaper (github.io URLs are baked into every clone of `submit`) |
| **Ingress service**: GitHub OAuth, POST bundle, KV/SQLite store, ported validate/merge; repo becomes code-only | Any two of: > 150 submissions/hr peak; p95 merge-to-board > 15 min; first-time approvals > 10/day; repo > 1 GB |
| Bundle format v2 with per-session logs (anti-cheat) | Only if a real incident proves aggregate counters insufficient |

## GitHub exit ramp (pricing/policy shock)

Everything here is portable by construction except the free compute and the
social graph. Read path: `build.py` → static files → any host (~1 hour;
invisible behind a custom domain). Write path: the ingress service above —
a pricing shock is just another trigger for the same work. Git hosting:
`git push --mirror` to Codeberg/Forgejo (Forgejo Actions is
GitHub-syntax-compatible for validate; automerge is replaced by the ingress
anyway). Identity: bundles carry no identity, so swap OAuth providers and
run a one-time claim flow (numeric-ID row above doubles as prep). Real exit
cost: ~$5–20/month of compute and the loss of GitHub-native discoverability.

For the from-scratch 10k design (FastAPI + SQLite + `:GT publish` tokens,
anti-cheat at ingest, profile pages with history), see `DESIGN-10K.md` on
the `scaling/part2-greenfield-design` branch / PR.
