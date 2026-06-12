"""Tests for build.py: validation, merge semantics, and derived metrics."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

import build  # noqa: E402


def make_bundle(**overrides: object) -> dict[str, object]:
    bundle: dict[str, object] = {
        "format_version": 1,
        "exported_from": "test-box",
        "exported_at": 1718200000,
        "machines": {
            "test-box": {
                "total_chars": 6000,
                "correct_chars": 5700,
                "total_time_seconds": 600,
                "sessions_count": 4,
                "best_wpm": 72,
            }
        },
        "sessions": {
            "4300": {
                "book_id": 4300,
                "offset": 1847,
                "total_chars_typed": 1847,
                "correct_chars": 1742,
                "last_active": 1718199000,
            }
        },
    }
    bundle.update(overrides)
    return bundle


def write_bundle(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data))
    return path


# ── as_int ──────────────────────────────────────────────────────────────────


def test_as_int_accepts_ints_and_rounds_floats() -> None:
    assert build.as_int(12) == 12
    assert build.as_int(12.6) == 13
    assert build.as_int(0) == 0


def test_as_int_rejects_junk() -> None:
    assert build.as_int(True) is None
    assert build.as_int("12") is None
    assert build.as_int(None) is None
    assert build.as_int({"x": 1}) is None
    assert build.as_int(-5) is None


# ── cleaning ────────────────────────────────────────────────────────────────


def test_clean_machines_drops_junk_values_and_records() -> None:
    machines = build.clean_machines(
        {
            "good": {"total_chars": 100.7, "best_wpm": {"x": 1}, "note": "hi"},
            "empty": {"only_junk": "yes"},
            "": {"total_chars": 5},
            "list": [1, 2],
        }
    )
    assert machines == {"good": {"total_chars": 101}}


def test_clean_sessions_enforces_numeric_keys_and_offsets() -> None:
    sessions = build.clean_sessions(
        {
            "4300": {"offset": 10, "last_active": "junk", "total_chars_typed": 9},
            "../evil": {"offset": 10},
            "999": {"offset": "10"},
            "888": "not a dict",
        }
    )
    assert sessions == {"4300": {"book_id": 4300, "offset": 10, "total_chars_typed": 9}}


# ── merge semantics ─────────────────────────────────────────────────────────


def test_merge_machines_is_field_wise_max_over_union() -> None:
    local = {"a": {"total_chars": 100, "best_wpm": 60}}
    incoming = {"a": {"total_chars": 80, "new_metric": 5}, "b": {"total_chars": 7}}
    merged = build.merge_machines(local, incoming)
    assert merged == {
        "a": {"total_chars": 100, "best_wpm": 60, "new_metric": 5},
        "b": {"total_chars": 7},
    }


def test_merge_machines_idempotent_and_commutative() -> None:
    a = {"m1": {"total_chars": 100}, "m2": {"total_chars": 50, "best_wpm": 70}}
    b = {"m2": {"total_chars": 60, "best_wpm": 65}}
    ab = build.merge_machines(a, b)
    assert build.merge_machines(ab, b) == ab
    assert build.merge_machines(ab, ab) == ab
    assert build.merge_machines(b, a) == ab


def test_merge_sessions_newer_last_active_wins_ties_keep_local() -> None:
    local = {"1": {"book_id": 1, "offset": 500, "last_active": 100}}
    newer = {"1": {"book_id": 1, "offset": 20, "last_active": 200}}
    stale = {"1": {"book_id": 1, "offset": 9999, "last_active": 50}}
    tie = {"1": {"book_id": 1, "offset": 9999, "last_active": 100}}
    assert build.merge_sessions(local, newer)["1"]["offset"] == 20
    assert build.merge_sessions(local, stale)["1"]["offset"] == 500
    assert build.merge_sessions(local, tie)["1"]["offset"] == 500
    assert build.merge_sessions({}, local) == local


# ── load_bundle ─────────────────────────────────────────────────────────────


def test_load_bundle_roundtrip(tmp_path: Path) -> None:
    path = write_bundle(tmp_path / "u.json", make_bundle())
    bundle, error = build.load_bundle(path)
    assert error is None
    assert bundle is not None
    assert bundle["machines"]["test-box"]["total_chars"] == 6000
    assert bundle["exported_at"] == 1718200000


def test_load_bundle_rejects_bad_input(tmp_path: Path) -> None:
    cases = [
        ("notjson.json", "{not json"),
        ("list.json", "[1,2]"),
        ("v2.json", json.dumps(make_bundle(format_version=2))),
        ("noversion.json", json.dumps({"machines": {}})),
        ("nomachines.json", json.dumps(make_bundle(machines={"m": {"x": "junk"}}))),
    ]
    for name, content in cases:
        path = tmp_path / name
        path.write_text(content)
        bundle, error = build.load_bundle(path)
        assert bundle is None, name
        assert error, name


# ── derive ──────────────────────────────────────────────────────────────────


def test_derive_math() -> None:
    bundle: build.CleanBundle = {
        "machines": {
            "a": {
                "total_chars": 6000,
                "correct_chars": 5700,
                "total_time_seconds": 600,
                "sessions_count": 4,
                "best_wpm": 72,
            },
            "b": {
                "total_chars": 1000,
                "correct_chars": 900,
                "total_time_seconds": 300,
                "sessions_count": 1,
                "best_wpm": 80,
            },
        },
        "sessions": {"1": {"book_id": 1, "offset": 5}},
        "exported_at": 5,
    }
    row = build.derive("alice", bundle)
    assert row["best_wpm"] == 80
    assert row["avg_wpm"] == 93.3  # (7000/5) / 15min
    assert row["accuracy"] == 94.3
    assert row["hours"] == 0.2  # 900 s = 0.25 h, round-half-even
    assert row["sessions"] == 5
    assert row["books"] == 1
    assert row["machines_count"] == 2
    assert not row["suspicious"]


def test_derive_flags_suspicious() -> None:
    bundle: build.CleanBundle = {
        "machines": {"a": {"total_chars": 100, "correct_chars": 200, "best_wpm": 300}},
        "sessions": {},
        "exported_at": 0,
    }
    assert build.derive("x", bundle)["suspicious"]


# ── collect / build / merge_into / summary ──────────────────────────────────


def test_collect_skips_invalid_and_sorts(tmp_path: Path) -> None:
    write_bundle(tmp_path / "alice.json", make_bundle())
    fast = make_bundle()
    fast["machines"] = {"m": {"total_chars": 1, "best_wpm": 99}}
    write_bundle(tmp_path / "bob.json", fast)
    (tmp_path / "mallory.json").write_text("broken{")
    rows, skipped = build.collect(tmp_path)
    assert [r["user"] for r in rows] == ["bob", "alice"]
    assert skipped == [{"user": "mallory", "reason": "unreadable (JSONDecodeError)"}]


def test_build_writes_site_and_strict_fails_on_bad_bundle(tmp_path: Path) -> None:
    bundles = tmp_path / "bundles"
    site = tmp_path / "site"
    out = tmp_path / "_site"
    bundles.mkdir()
    site.mkdir()
    (site / "index.html").write_text("<html></html>")
    write_bundle(bundles / "alice.json", make_bundle())
    assert build.build(strict=True, bundles_dir=bundles, site_dir=site, out_dir=out) == 0
    data = json.loads((out / "data.json").read_text())
    assert data["users"][0]["user"] == "alice"
    assert (out / "index.html").exists()
    (bundles / "bad.json").write_text("nope")
    assert build.build(strict=True, bundles_dir=bundles, site_dir=site, out_dir=out) == 1
    assert build.build(strict=False, bundles_dir=bundles, site_dir=site, out_dir=out) == 0


def test_merge_into_accumulates_without_double_count(tmp_path: Path) -> None:
    local = tmp_path / "alice.json"
    export = write_bundle(tmp_path / "export.json", make_bundle())
    assert build.merge_into(local, export) == 0
    assert build.merge_into(local, export) == 0  # idempotent re-submit
    saved = json.loads(local.read_text())
    assert saved["machines"]["test-box"]["total_chars"] == 6000
    assert saved["format_version"] == 1

    laptop = make_bundle()
    laptop["machines"] = {"laptop": {"total_chars": 500, "best_wpm": 90}}
    export2 = write_bundle(tmp_path / "export2.json", laptop)
    assert build.merge_into(local, export2) == 0
    saved = json.loads(local.read_text())
    assert set(saved["machines"]) == {"test-box", "laptop"}


def test_merge_into_refuses_invalid_export(tmp_path: Path) -> None:
    local = tmp_path / "alice.json"
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    assert build.merge_into(local, bad) == 1
    assert not local.exists()


def test_summary_reports_rank(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_bundle(tmp_path / "alice.json", make_bundle())
    assert build.summary("alice", tmp_path) == 0
    out = capsys.readouterr().out
    assert "rank 1 of 1" in out
    assert build.summary("ghost", tmp_path) == 1
