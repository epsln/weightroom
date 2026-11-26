import json

import pytest

from app.boostcamp import import_history
from app.normalize import brzycki, lb_to_kg, normalize_session, normalize_set, rebuild

from .conftest import find_session


def exercise_sets(conn, day, exercise):
    return conn.execute(
        """SELECT s.* FROM sets s JOIN sessions ss ON ss.id = s.session_id
           WHERE ss.date = ? AND s.exercise = ? ORDER BY s.set_idx""",
        (day, exercise),
    ).fetchall()


# --- unit rules ---------------------------------------------------------------

@pytest.mark.parametrize(
    "lb, kg",
    [(203.9275905, 92.5), (275.577825, 125.0), (2.20462 * 61.1, 61.0), (2.20462 * 61.13, 61.25)],
)
def test_lb_to_kg_rounds_to_quarter_kg(lb, kg):
    assert lb_to_kg(lb) == kg


def test_brzycki_matches_boostcamp():
    # Boostcamp shows 244.71 lb for 92.5 kg x 7
    assert brzycki(92.5, 7) == pytest.approx(244.71 / 2.20462, abs=0.05)
    assert brzycki(100, 1) == 100
    assert brzycki(100, 12) is not None
    assert brzycki(100, 13) is None


@pytest.mark.parametrize(
    "raw",
    [
        {"skipped": True, "archived_weight": 200, "archived_reps": 5},
        {"skipped": False, "archived_weight": 200, "archived_reps": 0},
        {"skipped": False, "archived_weight": 200, "archived_reps": None},
        {"skipped": False, "archived_weight": 200},
        {"skipped": False, "archived_weight": 0, "archived_reps": 5},
        {"skipped": False, "archived_weight": None, "archived_reps": 5},
        {"skipped": False, "archived_reps": 5, "value": "100", "amount": "5"},
    ],
)
def test_excluded_sets(raw):
    assert normalize_set(raw) is None


def test_value_and_amount_are_ignored():
    raw = {"skipped": False, "archived_weight": 220.462, "archived_reps": 3, "value": "999", "amount": "99"}
    assert normalize_set(raw) == (100.0, 3)


# --- against the real (anonymised) fixture -------------------------------------

def test_deadlift_2026_11_24_last_set(conn):
    sets = exercise_sets(conn, "2026-11-24", "Deadlift (Barbell)")
    last = sets[-1]
    assert (last["weight_kg"], last["reps"]) == (125.0, 4)
    assert last["lift"] == "deadlift"


def test_squat_2025_11_17_last_set(conn):
    last = exercise_sets(conn, "2025-11-17", "Squat (Barbell)")[-1]
    assert (last["weight_kg"], last["reps"]) == (92.5, 7)
    assert last["e1rm_kg"] == pytest.approx(111, abs=0.1)
    assert last["volume_kg"] == pytest.approx(647.5)


def test_skipped_sets_excluded(conn, history):
    # In the real data, skipped sets carry no weight; make sure fully filled-in
    # skipped sets are excluded too.
    session = find_session(history, "2026-11-24")
    deadlift = next(r for r in session["records"] if r["name"] == "Deadlift (Barbell)")
    deadlift["sets"][0]["skipped"] = True
    _session_row, sets = normalize_session(session)
    dl = [s for s in sets if s["exercise"] == "Deadlift (Barbell)"]
    assert len(dl) == len(deadlift["sets"]) - 1
    assert all(s["set_idx"] != 0 for s in dl)

    # Real skipped sets (e.g. weighted crunches on 2025-11-17) produce no rows.
    assert exercise_sets(conn, "2025-11-17", "Abs Crunch (Weighted)") == []


def test_alternatives_ignored(conn, history):
    session = find_session(history, "2025-11-17")
    alt_names = {a["name"] for r in session["records"] for a in r.get("alternatives") or []}
    record_names = {r["name"] for r in session["records"]}
    only_alts = alt_names - record_names
    assert only_alts, "fixture should contain alternatives that were not performed"
    stored = {r[0] for r in conn.execute(
        "SELECT DISTINCT exercise FROM sets s JOIN sessions ss ON ss.id=s.session_id WHERE ss.date=?",
        ("2025-11-17",),
    )}
    assert stored <= record_names
    assert not (stored & only_alts)


def test_alternatives_with_completed_looking_sets_ignored(history):
    session = find_session(history, "2026-11-24")
    before = normalize_session(session)[1]
    session["records"][0]["alternatives"] = [
        {"name": "Squat (Barbell)", "sets": [{"archived_weight": 500, "archived_reps": 5, "skipped": False}]}
    ]
    assert normalize_session(session)[1] == before


def test_variations_have_no_lift_but_count_toward_volume(conn):
    front = exercise_sets(conn, "2026-11-24", "Front Squat (Barbell)")
    rdl = exercise_sets(conn, "2025-11-21", "Romanian Deadlift (Barbell)")
    assert front and rdl
    assert all(s["lift"] is None for s in front + rdl)

    session_volume = conn.execute(
        "SELECT SUM(volume_kg) FROM sets s JOIN sessions ss ON ss.id=s.session_id WHERE ss.date=?",
        ("2026-11-24",),
    ).fetchone()[0]
    lift_volume = conn.execute(
        """SELECT SUM(volume_kg) FROM sets s JOIN sessions ss ON ss.id=s.session_id
           WHERE ss.date=? AND s.lift IS NOT NULL""",
        ("2026-11-24",),
    ).fetchone()[0]
    assert session_volume == pytest.approx(lift_volume + sum(s["volume_kg"] for s in front)
                                           + sum(s["volume_kg"] for s in exercise_sets(conn, "2026-11-24", "Leg Press")))


def test_lift_mapping_both_names(conn):
    names = dict(conn.execute("SELECT DISTINCT exercise, lift FROM sets").fetchall())
    assert names["Deadlift"] == "deadlift"
    assert names["Deadlift (Barbell)"] == "deadlift"
    assert names["Squat"] == "squat"
    assert names["Bench Press"] == "bench"
    assert names["Bench Press (Dumbbell)"] is None


def test_session_rows(conn):
    row = conn.execute("SELECT * FROM sessions WHERE date='2026-11-24'").fetchone()
    assert row["finished_at"].startswith("2026-11-24 ")
    assert (row["iso_year"], row["iso_week"]) == (2026, 48)
    assert row["title"]


def test_sync_is_idempotent(conn, history):
    def snapshot():
        return (
            conn.execute("SELECT COUNT(*), SUM(volume_kg) FROM sets").fetchone()[:],
            conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM raw_sessions").fetchone()[0],
        )

    first = snapshot()
    import_history(conn, json.loads(json.dumps(history)))
    rebuild(conn)
    assert snapshot() == first
