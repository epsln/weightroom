"""Boostcamp history fetch + raw upsert + full sync orchestration."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from datetime import datetime, timezone

import httpx

from . import normalize
from .auth import BoostcampAuthError, TokenManager

HISTORY_URL = "https://newapi.boostcamp.app/api/www/programs/history"


class BoostcampError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def fetch_history(
    tokens: TokenManager, timezone_offset: int, client: httpx.AsyncClient | None = None
) -> dict:
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=60)
    try:
        for attempt in range(2):
            id_token = await tokens.get_id_token()
            resp = await client.post(
                HISTORY_URL,
                params={"_": int(time.time() * 1000)},
                json={"timezone_offset": timezone_offset},
                headers={
                    "Authorization": f"FirebaseIdToken:{id_token}",
                    "Content-Type": "application/json; charset=UTF-8",
                    "Origin": "https://www.boostcamp.app",
                    "Referer": "https://www.boostcamp.app/",
                },
            )
            if resp.status_code in (401, 403) and attempt == 0:
                tokens.invalidate()  # cached token may have been revoked; retry once
                continue
            break
    except httpx.HTTPError as exc:
        raise BoostcampError(f"History request failed: {exc}") from exc
    finally:
        if own_client:
            await client.aclose()

    if not resp.is_success:  # Boostcamp answers this POST with 201 Created
        raise BoostcampError(f"History request failed: HTTP {resp.status_code} {resp.text[:200]}")
    body = resp.json()
    if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
        raise BoostcampError("Unexpected history response shape (missing 'data' object)")
    return body


def iter_sessions(history: dict):
    """Yield raw session dicts from a `{"data": {date: [session, ...]}}` payload."""
    for day, sessions in (history.get("data") or {}).items():
        for session in sessions or []:
            if not isinstance(session, dict) or not session.get("id"):
                continue
            if not session.get("finished_at"):
                session = {**session, "finished_at": f"{day} 00:00:00"}
            yield session


def upsert_raw(conn: sqlite3.Connection, history: dict) -> int:
    fetched_at = _now()
    rows = [
        (s["id"], s["finished_at"], json.dumps(s, separators=(",", ":")), fetched_at)
        for s in iter_sessions(history)
    ]
    with conn:
        conn.executemany(
            """INSERT INTO raw_sessions (id, finished_at, payload, fetched_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET finished_at = excluded.finished_at,
                   payload = excluded.payload, fetched_at = excluded.fetched_at""",
            rows,
        )
    return len(rows)


def import_history(conn: sqlite3.Connection, history: dict) -> int:
    """Upsert a history payload and rebuild normalized tables. Returns sessions seen."""
    seen = upsert_raw(conn, history)
    normalize.rebuild(conn)
    return seen


_sync_lock = asyncio.Lock()


async def run_sync(conn: sqlite3.Connection, tokens: TokenManager, timezone_offset: int) -> dict:
    """Fetch + import, recording the attempt in sync_log. Never raises; returns the log row."""
    async with _sync_lock:
        with conn:
            cur = conn.execute("INSERT INTO sync_log (started_at, ok) VALUES (?, 0)", (_now(),))
        log_id = cur.lastrowid
        ok, seen, error = 0, None, None
        try:
            history = await fetch_history(tokens, timezone_offset)
            seen = import_history(conn, history)
            ok = 1
        except (BoostcampAuthError, BoostcampError) as exc:
            error = str(exc)
        except Exception as exc:  # keep the scheduler alive on unexpected failures
            error = f"{type(exc).__name__}: {exc}"
        with conn:
            conn.execute(
                "UPDATE sync_log SET finished_at = ?, ok = ?, sessions_seen = ?, error = ? WHERE id = ?",
                (_now(), ok, seen, error, log_id),
            )
        return dict(conn.execute("SELECT * FROM sync_log WHERE id = ?", (log_id,)).fetchone())
