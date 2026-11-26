from datetime import date, timedelta

import pytest

from app import stats
from app.estimate import SetObs, dots, estimate_1rm, estimate_series, set_e1rm, weighted_percentile

D0 = date(2026, 1, 1)


def test_set_e1rm():
    assert set_e1rm(100, 1) == 100
    assert set_e1rm(100, 5) == pytest.approx((116.667 + 112.5) / 2, abs=0.01)
    assert set_e1rm(100, 11) is None
    assert set_e1rm(0, 5) is None


def test_weighted_percentile():
    assert weighted_percentile([(1, 1), (2, 1), (3, 1), (4, 1)], 0.5) == 2
    assert weighted_percentile([(1, 1), (10, 9)], 0.5) == 10


def test_constant_lifter_is_stable():
    sets = [SetObs(D0 + timedelta(days=3 * i), 100, 5) for i in range(14)]
    series = estimate_series(sets)
    assert len({p["e1rm_kg"] for p in series}) == 1
    assert series[0]["e1rm_kg"] == pytest.approx(set_e1rm(100, 5), abs=0.01)


def test_backoff_volume_does_not_drag_estimate_down():
    sets = [SetObs(D0, 140, 3)] + [SetObs(D0, 100, 8)] * 5
    assert estimate_1rm(sets, D0) == pytest.approx(set_e1rm(140, 3), abs=0.01)


def test_floored_by_actual_single():
    sets = [SetObs(D0, 100, 5), SetObs(D0, 100, 5), SetObs(D0, 125, 1)]
    assert estimate_1rm(sets, D0, percentile=0.1) == 125


def test_window_and_recency():
    old = SetObs(D0, 130, 8)
    assert estimate_1rm([old], D0 + timedelta(days=60)) is None
    recent = SetObs(D0 + timedelta(days=30), 135, 2)
    # Recent sets weigh more, so a mid percentile picks the newer set over the older, higher-e1RM one.
    assert set_e1rm(130, 8) > set_e1rm(135, 2)
    assert estimate_1rm([old, recent], D0 + timedelta(days=30), percentile=0.5) == pytest.approx(
        set_e1rm(135, 2), abs=0.01)


def test_floor_at_heaviest_weight_any_reps():
    # 150 x 2 proves at least 150 even if the weighted estimate would land lower.
    sets = [SetObs(D0, 100, 10)] * 20 + [SetObs(D0, 150, 2)]
    assert estimate_1rm(sets, D0, percentile=0.1) == 150


def test_ignores_future_and_high_reps():
    assert estimate_1rm([SetObs(D0 + timedelta(days=1), 200, 1)], D0) is None
    assert estimate_1rm([SetObs(D0, 50, 15)], D0) is None


def test_dots_reference():
    # 80 kg male, 600 kg total ~ 413.8 DOTS
    assert dots(600, 80) == pytest.approx(413.8, abs=0.5)
    assert dots(400, 60, "f") > dots(400, 80, "f")


def test_lift_estimate_from_fixture(conn):
    est = stats.lift_estimate(conn, "squat")
    # Top set 92.5x7 drives the estimate; volume 55x10 does not.
    assert est["current"]["e1rm_kg"] == pytest.approx(set_e1rm(92.5, 7), abs=0.01)
    assert stats.lift_estimate(conn, "bench")["series"][0]["date"] == "2026-11-23"


def _add_single(conn, lift, day, kg):
    sid = f"single-{lift}-{day}"
    d = date.fromisoformat(day)
    iso = d.isocalendar()
    conn.execute("INSERT INTO sessions(id, finished_at, date, iso_year, iso_week) VALUES (?,?,?,?,?)",
                 (sid, day, day, iso.year, iso.week))
    conn.execute("""INSERT INTO sets(session_id, exercise_idx, exercise, lift, set_idx, weight_kg, reps,
                    volume_kg, e1rm_kg) VALUES (?,0,'x',?,0,?,1,?,?)""", (sid, lift, kg, kg, kg))


def test_actual_maxes_running_best(conn):
    for day, kg in [("2026-01-01", 100), ("2026-02-01", 95), ("2026-03-01", 105)]:
        _add_single(conn, "squat", day, kg)
    # The fixture's 2025 squat session (top set 92.5 x 7) comes first.
    am = stats.actual_maxes(conn, "squat")
    assert [(m["weight_kg"], m["is_pr"]) for m in am] == [(92.5, True), (100, True), (95, False), (105, True)]
    assert [m["running_best_kg"] for m in am] == [92.5, 100, 100, 105]


def test_actual_maxes_counts_multi_rep_sets(conn):
    _add_single(conn, "deadlift", "2027-01-01", 140)
    sid = "multi-2027-01-08"
    conn.execute("INSERT INTO sessions(id, finished_at, date, iso_year, iso_week) VALUES (?,?,?,?,?)",
                 (sid, "2027-01-08", "2027-01-08", 2027, 1))
    for i, (kg, reps) in enumerate([(130, 5), (150, 2), (150, 2)]):
        conn.execute("""INSERT INTO sets(session_id, exercise_idx, exercise, lift, set_idx, weight_kg, reps,
                        volume_kg, e1rm_kg) VALUES (?,0,'x','deadlift',?,?,?,?,NULL)""",
                     (sid, i, kg, reps, kg * reps))
    last = stats.actual_maxes(conn, "deadlift")[-1]
    assert (last["weight_kg"], last["reps"], last["is_pr"]) == (150, 2, True)


def test_rep_curve(conn):
    curve = stats.rep_max_curve(conn, "squat", today=date(2025, 11, 30))
    by = {p["reps"]: p for p in curve}
    assert by[1]["all"] == 92.5 and by[7]["all"] == 92.5 and by[8]["all"] == 55.0
    assert by[11]["all"] is None
    assert by[5]["d30"] == 92.5
    assert stats.rep_max_curve(conn, "squat", today=date(2026, 11, 30))[0]["d30"] is None


def test_pr_timeline(conn):
    tl = stats.pr_timeline(conn, today=date(2026, 11, 25))
    dl = [e for e in tl["events"] if e["lift"] == "deadlift" and e["date"] == "2026-11-24"]
    assert {e["kind"] for e in dl} >= {"1RM", "3RM"}
    assert tl["days_since"]["deadlift"] == 1
    assert tl["events"][0]["date"] >= tl["events"][-1]["date"]


def test_intensity_and_total(conn):
    weeks = stats.intensity_distribution(conn, weeks=2, today=date(2026, 11, 25))
    assert sum(weeks[-1][z] for z in ("<70", "70-80", "80-90", "90+")) == 16
    for lift in ("squat", "bench", "deadlift"):
        _add_single(conn, lift, "2026-11-25", 100)
    stats.set_bodyweight(conn, date(2026, 1, 1), 80)
    last = stats.total_series(conn)[-1]
    # Deadlift keeps the fixture's 125 kg multi-rep set: any reps count toward the actual total.
    assert last["actual"]["deadlift"] == 125
    assert last["actual"]["total"] == 325
    assert last["dots_actual"] == pytest.approx(dots(325, 80), abs=0.01)
    assert last["estimated"]["total"] is not None
