"""Raw Boostcamp JSON -> normalized `sessions` / `sets` rows.

Field rules (see docs/PLAN.md):
- weight = archived_weight (lb) / 2.20462, rounded to the nearest 0.25 kg
- reps   = archived_reps
- drop sets that are skipped, or have no/zero reps or weight
- ignore `alternatives[]`, `value` and `amount`
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Iterable
from datetime import date
from typing import Any

from .config import E1RM_MAX_REPS, LB_PER_KG, LIFT_MAP, WEIGHT_STEP_KG


def lb_to_kg(lb: float) -> float:
    kg = lb / LB_PER_KG
    return math.floor(kg / WEIGHT_STEP_KG + 0.5) * WEIGHT_STEP_KG


def brzycki(weight_kg: float, reps: int) -> float | None:
    """Estimated 1RM (Brzycki). None when reps are outside 1..E1RM_MAX_REPS."""
    if reps < 1 or reps > E1RM_MAX_REPS:
        return None
    return round(weight_kg * 36 / (37 - reps), 2)


def lift_for(exercise: str, mapping: dict[str, str] | None = None) -> str | None:
    return (LIFT_MAP if mapping is None else mapping).get(exercise.strip())


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def normalize_set(raw: dict) -> tuple[float, int] | None:
    """Return (weight_kg, reps) for a completed set, or None if it must be excluded."""
    if raw.get("skipped") is True:
        return None
    reps = _num(raw.get("archived_reps"))
    weight_lb = _num(raw.get("archived_weight"))
    if not reps or reps <= 0 or not weight_lb or weight_lb <= 0:
        return None
    weight_kg = lb_to_kg(weight_lb)
    if weight_kg <= 0:
        return None
    return weight_kg, int(reps)


def normalize_session(raw: dict, mapping: dict[str, str] | None = None) -> tuple[dict, list[dict]]:
    finished_at = raw.get("finished_at") or ""
    day = date.fromisoformat(finished_at[:10])
    iso = day.isocalendar()
    session = {
        "id": raw["id"],
        "finished_at": finished_at,
        "date": day.isoformat(),
        "iso_year": iso.year,
        "iso_week": iso.week,
        "program": raw.get("name"),
        "title": raw.get("title"),
    }
    sets: list[dict] = []
    for ex_idx, record in enumerate(raw.get("records") or []):
        exercise = (record.get("name") or "").strip() or "Unknown"
        lift = lift_for(exercise, mapping)
        for set_idx, raw_set in enumerate(record.get("sets") or []):
            parsed = normalize_set(raw_set)
            if parsed is None:
                continue
            weight_kg, reps = parsed
            sets.append(
                {
                    "session_id": raw["id"],
                    "exercise_idx": ex_idx,
                    "exercise": exercise,
                    "lift": lift,
                    "set_idx": set_idx,
                    "weight_kg": weight_kg,
                    "reps": reps,
                    "volume_kg": round(weight_kg * reps, 2),
                    "e1rm_kg": brzycki(weight_kg, reps),
                }
            )
    return session, sets


def rebuild(conn: sqlite3.Connection) -> int:
    """Fully rebuild `sessions` and `sets` from `raw_sessions`. Returns session count.

    Uses the lift mapping from the user profile (defaults to config.LIFT_MAP).
    """
    from .profile import exercise_to_lift

    mapping = exercise_to_lift(conn)
    rows = conn.execute("SELECT payload FROM raw_sessions").fetchall()
    sessions, sets = [], []
    for row in rows:
        s, ss = normalize_session(json.loads(row[0]), mapping)
        sessions.append(s)
        sets.extend(ss)
    with conn:
        conn.execute("DELETE FROM sets")
        conn.execute("DELETE FROM sessions")
        _insert(conn, "sessions", sessions)
        _insert(conn, "sets", sets)
    return len(sessions)


def _insert(conn: sqlite3.Connection, table: str, rows: Iterable[dict]) -> None:
    rows = list(rows)
    if not rows:
        return
    cols = list(rows[0])
    conn.executemany(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)})",
        rows,
    )
