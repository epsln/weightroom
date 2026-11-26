from datetime import date

import pytest

from app import stats


def test_weekly_totals_equal_sum_of_sessions(conn):
    weeks = stats.weekly_volume(conn, weeks=60, today=date(2026, 11, 25))
    sessions = stats.list_sessions(conn, limit=500)["items"]
    assert sessions

    nonzero = [w for w in weeks if w["total"]]
    assert {(w["iso_year"], w["iso_week"]) for w in nonzero} == {(2025, 47), (2026, 48)}

    for w in weeks:
        in_week = [s for s in sessions if (s["iso_year"], s["iso_week"]) == (w["iso_year"], w["iso_week"])]
        assert w["total"] == pytest.approx(sum(s["volume_kg"] for s in in_week))
        assert w["total"] == pytest.approx(w["squat"] + w["bench"] + w["deadlift"] + w["other"])
        assert w["sessions"] == len(in_week)


def test_weekly_window_is_zero_filled_and_ordered(conn):
    weeks = stats.weekly_volume(conn, weeks=4, today=date(2026, 11, 25))
    assert [w["week_start"] for w in weeks] == ["2026-11-02", "2026-11-09", "2026-11-16", "2026-11-23"]
    assert weeks[-1]["total"] > 0
    assert weeks[0]["total"] == 0


def test_session_volume_matches_sets(conn):
    items = stats.list_sessions(conn)["items"]
    for item in items:
        total = conn.execute(
            "SELECT COALESCE(SUM(volume_kg),0), COUNT(*), COALESCE(SUM(reps),0) FROM sets WHERE session_id=?",
            (item["id"],),
        ).fetchone()
        assert item["volume_kg"] == pytest.approx(total[0])
        assert (item["sets"], item["reps"]) == (total[1], total[2])


def test_sessions_list_sorted_newest_first_and_paginated(conn):
    page = stats.list_sessions(conn, limit=2, offset=0)
    assert page["total"] == 5
    assert [i["date"] for i in page["items"]] == ["2026-11-24", "2026-11-23"]
    assert page["items"][0]["exercises"][0] == "Deadlift (Barbell)"
    page2 = stats.list_sessions(conn, limit=2, offset=2)
    assert page2["items"][0]["date"] == "2025-11-21"


def test_session_detail_groups_by_exercise(conn):
    sid = conn.execute("SELECT id FROM sessions WHERE date='2026-11-24'").fetchone()[0]
    detail = stats.session_detail(conn, sid)
    names = [e["exercise"] for e in detail["exercises"]]
    assert names[0] == "Deadlift (Barbell)"
    dl = detail["exercises"][0]
    assert dl["lift"] == "deadlift"
    assert dl["sets"][-1]["weight_kg"] == 125.0
    assert sum(e["volume_kg"] for e in detail["exercises"]) == pytest.approx(detail["volume_kg"])
    assert stats.session_detail(conn, "nope") is None


def test_prs(conn):
    p = stats.prs(conn)
    assert set(p) == {"squat", "bench", "deadlift"}

    dl = p["deadlift"]
    assert dl["heaviest"]["weight_kg"] == 125.0
    assert dl["heaviest"]["date"] == "2026-11-24"

    sq = p["squat"]
    assert sq["best_e1rm"]["e1rm_kg"] == pytest.approx(111, abs=0.5)

    # Rep-max table is monotonic: more reps never means more weight.
    for lift in p.values():
        rm = [lift["rep_maxes"][k] for k in ("1", "3", "5", "8", "10")]
        weights = [r["weight_kg"] if r else 0 for r in rm]
        assert weights == sorted(weights, reverse=True)
        for n, r in zip((1, 3, 5, 8, 10), rm):
            if r:
                assert r["reps"] >= n

    # Variations never show up in PRs.
    for lift in p.values():
        for key in ("heaviest", "best_e1rm", "best_set_volume"):
            assert lift[key]["exercise"] in {
                "Squat (Barbell)", "Squat", "Bench Press (Barbell)", "Bench Press",
                "Deadlift (Barbell)", "Deadlift",
            }


def test_best_session_volume_is_max_of_lift_history(conn):
    p = stats.prs(conn)
    for lift in ("squat", "bench", "deadlift"):
        hist = stats.lift_history(conn, lift)
        assert p[lift]["best_session_volume"]["volume_kg"] == pytest.approx(max(h["volume_kg"] for h in hist))


def test_lift_history(conn):
    hist = stats.lift_history(conn, "deadlift")
    assert [h["date"] for h in hist] == ["2025-11-21", "2026-11-24"]
    last = hist[-1]
    assert last["top_set"]["weight_kg"] == 125.0
    assert last["best_e1rm_kg"] == pytest.approx(125 * 36 / 33, abs=0.01)
