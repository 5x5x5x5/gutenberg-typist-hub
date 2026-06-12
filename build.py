#!/usr/bin/env python3
"""Build the gutenberg-typist leaderboard.

Reads :GT export bundles from bundles/<github-username>.json, validates and
derives comparable metrics, and writes a static site to _site/.

Usage:
  build.py                      build _site/ (skipping invalid bundles)
  build.py --strict             build; exit 1 if any bundle is invalid
  build.py --merge LOCAL EXPORT merge an export file into a user's bundle
  build.py --summary USER       print USER's derived stats and rank
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parent
BUNDLES = ROOT / "bundles"
SITE = ROOT / "site"
OUT = ROOT / "_site"

FORMAT_VERSION = 1
MAX_BUNDLE_BYTES = 1_000_000
SUSPICIOUS_WPM = 250

Counters = dict[str, int]
Machines = dict[str, Counters]
Session = dict[str, int]
Sessions = dict[str, Session]


class CleanBundle(TypedDict):
    machines: Machines
    sessions: Sessions
    exported_at: int


class Row(TypedDict):
    user: str
    best_wpm: int
    avg_wpm: float
    accuracy: float
    hours: float
    total_chars: int
    sessions: int
    books: int
    machines_count: int
    exported_at: int
    suspicious: bool
    machines: Machines
    books_detail: list[Session]


class Skipped(TypedDict):
    user: str
    reason: str


def as_int(value: object) -> int | None:
    """Coerce a JSON number to a non-negative int; reject everything else.

    bool is excluded explicitly (it subclasses int), and negative values are
    rejected because every counter in the format is grow-only from zero.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = round(value)
    return number if number >= 0 else None


def clean_machines(raw: object) -> Machines:
    machines: Machines = {}
    if not isinstance(raw, dict):
        return machines
    for machine_id, record in raw.items():
        if not isinstance(machine_id, str) or machine_id == "" or not isinstance(record, dict):
            continue
        clean: Counters = {}
        for key, value in record.items():
            number = as_int(value)
            if isinstance(key, str) and number is not None:
                clean[key] = number
        if clean:
            machines[machine_id] = clean
    return machines


def clean_sessions(raw: object) -> Sessions:
    sessions: Sessions = {}
    if not isinstance(raw, dict):
        return sessions
    for book_id, record in raw.items():
        if not isinstance(book_id, str) or not book_id.isdigit() or not isinstance(record, dict):
            continue
        offset = as_int(record.get("offset"))
        if offset is None:
            continue
        clean: Session = {"book_id": int(book_id), "offset": offset}
        for key in ("total_chars_typed", "correct_chars", "last_active"):
            number = as_int(record.get(key))
            if number is not None:
                clean[key] = number
        sessions[book_id] = clean
    return sessions


def merge_machines(local: Machines, incoming: Machines) -> Machines:
    """Field-wise max over the union of keys — mirrors autoload/gt/storage.vim."""
    merged: Machines = {machine_id: dict(record) for machine_id, record in local.items()}
    for machine_id, record in incoming.items():
        current = merged.setdefault(machine_id, {})
        for key, value in record.items():
            current[key] = max(current.get(key, 0), value)
    return merged


def merge_sessions(local: Sessions, incoming: Sessions) -> Sessions:
    """Newer last_active wins; ties keep local — mirrors gt#storage#MergeSession."""
    merged = dict(local)
    for book_id, record in incoming.items():
        current = merged.get(book_id)
        if current is None or record.get("last_active", 0) > current.get("last_active", 0):
            merged[book_id] = record
    return merged


def load_bundle(path: Path) -> tuple[CleanBundle | None, str | None]:
    try:
        if path.stat().st_size > MAX_BUNDLE_BYTES:
            return None, "bundle larger than 1 MB"
        data: object = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as err:
        return None, f"unreadable ({err.__class__.__name__})"
    if not isinstance(data, dict):
        return None, "not a JSON object"
    version = data.get("format_version")
    if version != FORMAT_VERSION:
        return None, f"format_version {version!r} not supported"
    machines = clean_machines(data.get("machines"))
    if not machines:
        return None, "no valid machine records"
    return {
        "machines": machines,
        "sessions": clean_sessions(data.get("sessions")),
        "exported_at": as_int(data.get("exported_at")) or 0,
    }, None


def derive(user: str, bundle: CleanBundle) -> Row:
    machines = bundle["machines"]
    chars = sum(record.get("total_chars", 0) for record in machines.values())
    correct = sum(record.get("correct_chars", 0) for record in machines.values())
    seconds = sum(record.get("total_time_seconds", 0) for record in machines.values())
    sessions_count = sum(record.get("sessions_count", 0) for record in machines.values())
    best_wpm = max((record.get("best_wpm", 0) for record in machines.values()), default=0)
    minutes = seconds / 60
    avg_wpm = (chars / 5) / minutes if minutes > 0 else 0.0
    accuracy = correct * 100 / chars if chars > 0 else 0.0
    return {
        "user": user,
        "best_wpm": best_wpm,
        "avg_wpm": round(avg_wpm, 1),
        "accuracy": round(accuracy, 1),
        "hours": round(seconds / 3600, 1),
        "total_chars": chars,
        "sessions": sessions_count,
        "books": len(bundle["sessions"]),
        "machines_count": len(machines),
        "exported_at": bundle["exported_at"],
        "suspicious": best_wpm > SUSPICIOUS_WPM or correct > chars,
        "machines": machines,
        "books_detail": sorted(bundle["sessions"].values(), key=lambda s: -s.get("last_active", 0)),
    }


def collect(bundles_dir: Path = BUNDLES) -> tuple[list[Row], list[Skipped]]:
    rows: list[Row] = []
    skipped: list[Skipped] = []
    for path in sorted(bundles_dir.glob("*.json")):
        bundle, error = load_bundle(path)
        if bundle is None:
            skipped.append({"user": path.stem, "reason": error or "invalid"})
        else:
            rows.append(derive(path.stem, bundle))
    rows.sort(key=lambda row: (-row["best_wpm"], row["user"]))
    return rows, skipped


def build(
    strict: bool = False,
    bundles_dir: Path = BUNDLES,
    site_dir: Path = SITE,
    out_dir: Path = OUT,
) -> int:
    rows, skipped = collect(bundles_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(site_dir, out_dir)
    payload = {"generated_at": int(time.time()), "users": rows, "skipped": skipped}
    (out_dir / "data.json").write_text(json.dumps(payload, indent=1) + "\n")
    print(f"built {out_dir.name}: {len(rows)} user(s), {len(skipped)} skipped")
    for item in skipped:
        print(f"  skipped {item['user']}: {item['reason']}")
    return 1 if (strict and skipped) else 0


def merge_into(local_path: Path, export_path: Path) -> int:
    incoming, error = load_bundle(export_path)
    if incoming is None:
        print(f"refusing to merge {export_path}: {error}", file=sys.stderr)
        return 1
    merged = incoming
    if local_path.exists():
        local, local_error = load_bundle(local_path)
        if local is None:
            print(
                f"existing {local_path.name} invalid ({local_error}); replacing",
                file=sys.stderr,
            )
        else:
            merged = {
                "machines": merge_machines(local["machines"], incoming["machines"]),
                "sessions": merge_sessions(local["sessions"], incoming["sessions"]),
                "exported_at": max(local["exported_at"], incoming["exported_at"]),
            }
    out: dict[str, object] = {"format_version": FORMAT_VERSION, **merged}
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text(json.dumps(out, indent=1) + "\n")
    print(
        f"merged into {local_path.name}: "
        f"{len(merged['machines'])} machine(s), {len(merged['sessions'])} book(s)"
    )
    return 0


def summary(user: str, bundles_dir: Path = BUNDLES) -> int:
    rows, _ = collect(bundles_dir)
    for rank, row in enumerate(rows, 1):
        if row["user"] == user:
            print(
                f"{user}: best {row['best_wpm']} WPM · avg {row['avg_wpm']} WPM · "
                f"accuracy {row['accuracy']}% · {row['hours']} h · "
                f"rank {rank} of {len(rows)}"
            )
            return 0
    print(f"{user}: no valid bundle on the board yet", file=sys.stderr)
    return 1


def main(argv: list[str]) -> int:
    args = argv[1:]
    if not args:
        return build()
    if args == ["--strict"]:
        return build(strict=True)
    if args[0] == "--merge" and len(args) == 3:
        return merge_into(Path(args[1]), Path(args[2]))
    if args[0] == "--summary" and len(args) == 2:
        return summary(args[1])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
