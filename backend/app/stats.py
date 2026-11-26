"""Read-side queries: PRs, session lists, weekly volume, per-lift history."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from .config import INTENSITY_ZONES, LIFTS, REP_CURVE_MAX, REP_MAX_TABLE
from .estimate import SetObs, dots, estimate_1rm, estimate_series

_SET_COLS = """s.session_id, ss.date, ss.title, s.exercise, s.weight_kg, s.reps,
               s.volume_kg, s.e1rm_kg"""


def _set_row(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return {
        "session_id": row["session_id"],
        "date": row["date"],
        "title": row["title"],
        "exercise": row["exercise"],
        "weight_kg": row["weight_kg"],
        "reps": row["reps"],
        "volume_kg": row["volume_kg"],
        "e1rm_kg": row["e1rm_kg"],
    }


def _best_set(conn: sqlite3.Connection, lift: str, order: str, where: str = "", params=()) -> dict | None:
    # Ties go to the earliest date: that's when the PR was first set.
    row = conn.execute(
        f"""SELECT {_SET_COLS} FROM sets s JOIN sessions ss ON ss.id = s.session_id
            WHERE s.lift = ? {where}
            ORDER BY {order}, ss.date ASC, ss.finished_at ASC LIMIT 1""",
        (lift, *params),
    ).fetchone()
    return _set_row(row)


def prs(conn: sqlite3.Connection, today: date | None = None) -> dict:
    out = {}
    days_since = pr_timeline(conn, today)["days_since"]
    for lift in LIFTS:
        est = lift_estimate(conn, lift)["current"]
        session_row = conn.execute(
            """SELECT s.session_id, ss.date, ss.title, SUM(s.volume_kg) AS volume_kg,
                      COUNT(*) AS sets, SUM(s.reps) AS reps
               FROM sets s JOIN sessions ss ON ss.id = s.session_id
               WHERE s.lift = ? GROUP BY s.session_id
               ORDER BY volume_kg DESC, ss.date ASC LIMIT 1""",
            (lift,),
        ).fetchone()
        out[lift] = {
            "heaviest": _best_set(conn, lift, "s.weight_kg DESC, s.reps DESC"),
            "best_e1rm": _best_set(conn, lift, "s.e1rm_kg DESC", "AND s.e1rm_kg IS NOT NULL"),
            "best_set_volume": _best_set(conn, lift, "s.volume_kg DESC"),
            "best_session_volume": dict(session_row) if session_row else None,
            "estimated_1rm": est,
            "days_since_pr": days_since[lift],
            # N-RM = heaviest weight lifted for at least N reps.
            "rep_maxes": {
                str(n): _best_set(conn, lift, "s.weight_kg DESC, s.reps DESC", "AND s.reps >= ?", (n,))
                for n in REP_MAX_TABLE
            },
        }
    return out


_SESSION_SUMMARY = """
    SELECT ss.id, ss.date, ss.finished_at, ss.title, ss.program, ss.iso_year, ss.iso_week,
           COALESCE(SUM(s.volume_kg), 0) AS volume_kg,
           COUNT(s.id) AS sets,
           COALESCE(SUM(s.reps), 0) AS reps
    FROM sessions ss LEFT JOIN sets s ON s.session_id = ss.id
"""


def _exercises_for(conn: sqlite3.Connection, session_ids: list[str]) -> dict[str, list[str]]:
    if not session_ids:
        return {}
    marks = ",".join("?" * len(session_ids))
    rows = conn.execute(
        f"""SELECT session_id, exercise, MIN(exercise_idx) AS idx FROM sets
            WHERE session_id IN ({marks}) GROUP BY session_id, exercise
            ORDER BY session_id, idx""",
        session_ids,
    ).fetchall()
    out: dict[str, list[str]] = {}
    for r in rows:
        out.setdefault(r["session_id"], []).append(r["exercise"])
    return out


def list_sessions(conn: sqlite3.Connection, limit: int = 50, offset: int = 0) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    rows = conn.execute(
        _SESSION_SUMMARY
        + " GROUP BY ss.id ORDER BY ss.date DESC, ss.finished_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    items = [dict(r) for r in rows]
    exercises = _exercises_for(conn, [i["id"] for i in items])
    for item in items:
        item["exercises"] = exercises.get(item["id"], [])
    return {"total": total, "limit": limit, "offset": offset, "items": items}


def session_detail(conn: sqlite3.Connection, session_id: str) -> dict | None:
    row = conn.execute(_SESSION_SUMMARY + " WHERE ss.id = ? GROUP BY ss.id", (session_id,)).fetchone()
    if row is None:
        return None
    detail = dict(row)
    sets = conn.execute(
        "SELECT * FROM sets WHERE session_id = ? ORDER BY exercise_idx, set_idx", (session_id,)
    ).fetchall()
    groups: dict[int, dict] = {}
    for s in sets:
        g = groups.setdefault(
            s["exercise_idx"],
            {"exercise": s["exercise"], "lift": s["lift"], "volume_kg": 0.0, "best_e1rm_kg": None, "sets": []},
        )
        g["sets"].append(
            {k: s[k] for k in ("set_idx", "weight_kg", "reps", "volume_kg", "e1rm_kg")}
        )
        g["volume_kg"] = round(g["volume_kg"] + s["volume_kg"], 2)
        if s["e1rm_kg"] is not None and (g["best_e1rm_kg"] is None or s["e1rm_kg"] > g["best_e1rm_kg"]):
            g["best_e1rm_kg"] = s["e1rm_kg"]
    detail["exercises"] = list(groups.values())
    return detail


def weekly_volume(conn: sqlite3.Connection, weeks: int = 12, today: date | None = None) -> list[dict]:
    """Total kg per ISO week for the last `weeks` weeks (ending with today's week), zero-filled."""
    today = today or date.today()
    this_monday = today - timedelta(days=today.weekday())
    mondays = [this_monday - timedelta(weeks=i) for i in range(weeks - 1, -1, -1)]

    rows = conn.execute(
        """SELECT ss.iso_year, ss.iso_week, COALESCE(s.lift, 'other') AS bucket,
                  SUM(s.volume_kg) AS volume_kg
           FROM sets s JOIN sessions ss ON ss.id = s.session_id
           GROUP BY ss.iso_year, ss.iso_week, bucket"""
    ).fetchall()
    by_week: dict[tuple[int, int], dict[str, float]] = {}
    for r in rows:
        by_week.setdefault((r["iso_year"], r["iso_week"]), {})[r["bucket"]] = r["volume_kg"]
    counts = {
        (r[0], r[1]): r[2]
        for r in conn.execute("SELECT iso_year, iso_week, COUNT(*) FROM sessions GROUP BY 1, 2")
    }

    out = []
    for monday in mondays:
        iso = monday.isocalendar()
        key = (iso.year, iso.week)
        buckets = by_week.get(key, {})
        entry = {
            "iso_year": iso.year,
            "iso_week": iso.week,
            "week_start": monday.isoformat(),
            "sessions": counts.get(key, 0),
        }
        for b in (*LIFTS, "other"):
            entry[b] = round(buckets.get(b, 0.0), 2)
        entry["total"] = round(sum(buckets.values()), 2)
        out.append(entry)
    return out


def lift_history(conn: sqlite3.Connection, lift: str) -> list[dict]:
    rows = conn.execute(
        f"""SELECT {_SET_COLS}, ss.finished_at FROM sets s JOIN sessions ss ON ss.id = s.session_id
            WHERE s.lift = ? ORDER BY ss.date, ss.finished_at, s.exercise_idx, s.set_idx""",
        (lift,),
    ).fetchall()
    sessions: dict[str, dict] = {}
    for r in rows:
        h = sessions.setdefault(
            r["session_id"],
            {"session_id": r["session_id"], "date": r["date"], "title": r["title"],
             "best_e1rm_kg": None, "top_set": None, "volume_kg": 0.0, "sets": 0},
        )
        h["volume_kg"] = round(h["volume_kg"] + r["volume_kg"], 2)
        h["sets"] += 1
        if r["e1rm_kg"] is not None and (h["best_e1rm_kg"] is None or r["e1rm_kg"] > h["best_e1rm_kg"]):
            h["best_e1rm_kg"] = r["e1rm_kg"]
        top = h["top_set"]
        if top is None or (r["weight_kg"], r["reps"]) > (top["weight_kg"], top["reps"]):
            h["top_set"] = {"weight_kg": r["weight_kg"], "reps": r["reps"], "exercise": r["exercise"]}
    return list(sessions.values())


# --- advanced stats -------------------------------------------------------------

def _lift_sets(conn: sqlite3.Connection, lift: str) -> list[sqlite3.Row]:
    return conn.execute(
        f"""SELECT {_SET_COLS} FROM sets s JOIN sessions ss ON ss.id = s.session_id
            WHERE s.lift = ? ORDER BY ss.date, ss.finished_at, s.exercise_idx, s.set_idx""",
        (lift,),
    ).fetchall()


def _obs(rows) -> list[SetObs]:
    return [SetObs(date.fromisoformat(r["date"]), r["weight_kg"], r["reps"]) for r in rows]


def lift_estimate(conn: sqlite3.Connection, lift: str) -> dict:
    rows = _lift_sets(conn, lift)
    series = estimate_series(_obs(rows))
    return {"current": series[-1] if series else None, "series": series}


def actual_maxes(conn: sqlite3.Connection, lift: str) -> list[dict]:
    """Heaviest set (any reps) of each session, with a running best and PR flag.

    A set of 150 x 2 proves a 150 kg single just as well as 150 x 1, so reps don't matter here.
    """
    top: dict[str, sqlite3.Row] = {}
    for r in _lift_sets(conn, lift):  # chronological, so dict order follows sessions
        cur = top.get(r["session_id"])
        if cur is None or (r["weight_kg"], r["reps"]) > (cur["weight_kg"], cur["reps"]):
            top[r["session_id"]] = r
    out, best = [], 0.0
    for r in top.values():
        is_pr = r["weight_kg"] > best
        best = max(best, r["weight_kg"])
        out.append({**_set_row(r), "is_pr": is_pr, "running_best_kg": best})
    return out


def rep_max_curve(conn: sqlite3.Connection, lift: str, today: date | None = None) -> list[dict]:
    """Best weight for >= N reps (N = 1..REP_CURVE_MAX) over all time, last 90 and last 30 days."""
    today = today or date.today()
    rows = _lift_sets(conn, lift)
    windows = {"all": None, "d90": today - timedelta(days=90), "d30": today - timedelta(days=30)}
    out = []
    for n in range(1, REP_CURVE_MAX + 1):
        point: dict = {"reps": n}
        for key, since in windows.items():
            cands = [r["weight_kg"] for r in rows
                     if r["reps"] >= n and (since is None or r["date"] > since.isoformat())]
            point[key] = max(cands) if cands else None
        out.append(point)
    return out


def _zone(frac: float) -> str:
    label = INTENSITY_ZONES[0][0]
    for name, lo in INTENSITY_ZONES:
        if frac >= lo:
            label = name
    return label


def intensity_distribution(
    conn: sqlite3.Connection, weeks: int = 12, lift: str | None = None, today: date | None = None
) -> list[dict]:
    """Weekly set counts per intensity zone (% of the rolling 1RM estimate on that day)."""
    today = today or date.today()
    this_monday = today - timedelta(days=today.weekday())
    mondays = [this_monday - timedelta(weeks=i) for i in range(weeks - 1, -1, -1)]
    zones = [z for z, _ in INTENSITY_ZONES]
    buckets = {m: dict.fromkeys(zones, 0) for m in mondays}
    for lf in [lift] if lift else LIFTS:
        rows = _lift_sets(conn, lf)
        obs = _obs(rows)
        est_cache: dict[date, float | None] = {}
        for o in obs:
            monday = o.date - timedelta(days=o.date.weekday())
            if monday not in buckets:
                continue
            if o.date not in est_cache:
                est_cache[o.date] = estimate_1rm(obs, o.date)
            est = est_cache[o.date]
            if est:
                buckets[monday][_zone(o.weight_kg / est)] += 1
    return [{"week_start": m.isoformat(), **buckets[m]} for m in mondays]


def pr_timeline(conn: sqlite3.Connection, today: date | None = None) -> dict:
    """Chronological feed of PR events, plus days since the last PR per lift."""
    today = today or date.today()
    events: list[dict] = []
    last: dict[str, str | None] = {}
    for lift in LIFTS:
        best_e1rm = best_vol = 0.0
        best_rm = dict.fromkeys(REP_MAX_TABLE, 0.0)
        last[lift] = None
        for r in _lift_sets(conn, lift):
            base = {"lift": lift, **_set_row(r)}
            found = []
            # 1RM (heaviest weight for >= 1 rep) is part of REP_MAX_TABLE.
            for n in REP_MAX_TABLE:
                if r["reps"] >= n and r["weight_kg"] > best_rm[n]:
                    found.append((f"{n}RM", r["weight_kg"], best_rm[n]))
                    best_rm[n] = r["weight_kg"]
            if r["e1rm_kg"] is not None and r["e1rm_kg"] > best_e1rm:
                found.append(("e1RM", r["e1rm_kg"], best_e1rm))
                best_e1rm = r["e1rm_kg"]
            if r["volume_kg"] > best_vol:
                found.append(("set volume", r["volume_kg"], best_vol))
                best_vol = r["volume_kg"]
            for kind, value, prev in found:
                events.append({**base, "kind": kind, "value": value, "previous": prev or None})
            if found:
                last[lift] = r["date"]
    events.sort(key=lambda e: e["date"], reverse=True)
    days_since = {
        lift: (today - date.fromisoformat(d)).days if d else None for lift, d in last.items()
    }
    return {"events": events, "last_pr_date": last, "days_since": days_since}


def list_bodyweight(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT date, kg FROM bodyweight ORDER BY date")]


def set_bodyweight(conn: sqlite3.Connection, day: date, kg: float) -> None:
    conn.execute(
        "INSERT INTO bodyweight(date, kg) VALUES (?, ?) ON CONFLICT(date) DO UPDATE SET kg = excluded.kg",
        (day.isoformat(), kg),
    )
    conn.commit()


def delete_bodyweight(conn: sqlite3.Connection, day: date) -> bool:
    cur = conn.execute("DELETE FROM bodyweight WHERE date = ?", (day.isoformat(),))
    conn.commit()
    return cur.rowcount > 0


def _bw_at(bw: list[dict], d: str) -> float | None:
    """Latest bodyweight on or before d, else the earliest one recorded."""
    if not bw:
        return None
    before = [b["kg"] for b in bw if b["date"] <= d]
    return before[-1] if before else bw[0]["kg"]


def total_series(conn: sqlite3.Connection, sex: str = "m") -> list[dict]:
    """Per training date: estimated SBD total and best-ever actual total (heaviest set, any reps), with DOTS."""
    obs = {lift: _obs(_lift_sets(conn, lift)) for lift in LIFTS}
    singles = {lift: [(o.date, o.weight_kg) for o in obs[lift] if o.reps >= 1] for lift in LIFTS}
    bw = list_bodyweight(conn)
    dates = sorted({o.date for lift in LIFTS for o in obs[lift]})
    out = []
    for d in dates:
        ests = {}
        for lift in LIFTS:
            # Latest estimate up to d (lifts aren't all trained on the same day).
            past = [o for o in obs[lift] if o.date <= d]
            ests[lift] = estimate_1rm(past, max(o.date for o in past)) if past else None
        best = {lift: max((w for sd, w in singles[lift] if sd <= d), default=None) for lift in LIFTS}
        est_total = round(sum(ests.values()), 2) if all(ests.values()) else None
        act_total = round(sum(best.values()), 2) if all(best.values()) else None
        body = _bw_at(bw, d.isoformat())
        out.append({
            "date": d.isoformat(),
            "estimated": {**ests, "total": est_total},
            "actual": {**best, "total": act_total},
            "bodyweight_kg": body,
            "dots_estimated": dots(est_total, body, sex) if est_total and body else None,
            "dots_actual": dots(act_total, body, sex) if act_total and body else None,
        })
    return out


def last_sync(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute("SELECT * FROM sync_log ORDER BY id DESC LIMIT 1").fetchone()
    if row is None:
        return None
    out = dict(row)
    ok = conn.execute(
        "SELECT finished_at FROM sync_log WHERE ok = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    out["last_success_at"] = ok[0] if ok else None
    return out


def exercise_names(conn: sqlite3.Connection) -> list[dict]:
    """Distinct exercise names seen in history (for the lift-mapping picker)."""
    rows = conn.execute(
        """SELECT exercise, lift, COUNT(*) AS sets, MAX(s.date) AS last_date
           FROM sets JOIN sessions s ON s.id = sets.session_id
           GROUP BY exercise ORDER BY sets DESC"""
    ).fetchall()
    return [dict(r) for r in rows]
