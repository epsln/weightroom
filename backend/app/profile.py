"""Single-row user profile: onboarding answers, preferences and encrypted credentials."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

from .config import LIFT_MAP, LIFTS, Settings
from .crypto import Cipher, SecretError

PUBLIC_FIELDS = (
    "name", "sex", "dots_formula", "units", "height_cm", "birth_year",
    "training_start", "sync_interval_hours", "onboarded_at",
)
EDITABLE_FIELDS = (
    "name", "sex", "dots_formula", "units", "height_cm", "birth_year",
    "training_start", "sync_interval_hours", "lift_map",
)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _row(conn: sqlite3.Connection) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    if row is None:  # schema always seeds it, but be defensive
        with conn:
            conn.execute("INSERT OR IGNORE INTO profile (id) VALUES (1)")
        row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    return row


def default_lift_map() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {lift: [] for lift in LIFTS}
    for exercise, lift in LIFT_MAP.items():
        out[lift].append(exercise)
    return out


def lift_map(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Lift -> list of exact Boostcamp exercise names counted as that lift."""
    raw = _row(conn)["lift_map"]
    if not raw:
        return default_lift_map()
    stored = json.loads(raw)
    return {lift: list(stored.get(lift, [])) for lift in LIFTS}


def exercise_to_lift(conn: sqlite3.Connection) -> dict[str, str]:
    return {name.strip(): lift for lift, names in lift_map(conn).items() for name in names}


def sync_interval(conn: sqlite3.Connection, settings: Settings) -> int:
    return _row(conn)["sync_interval_hours"] or settings.sync_interval_hours


def dots_formula(conn: sqlite3.Connection) -> str:
    return _row(conn)["dots_formula"]


def credentials(conn: sqlite3.Connection, settings: Settings, cipher: Cipher) -> tuple[str, str, str | None]:
    """(refresh_token, api_key, source) where source is 'env', 'db' or None."""
    if settings.has_credentials:
        return settings.refresh_token, settings.firebase_api_key, "env"
    row = _row(conn)
    if row["refresh_token_enc"] and row["api_key_enc"]:
        try:
            return cipher.decrypt(row["refresh_token_enc"]), cipher.decrypt(row["api_key_enc"]), "db"
        except SecretError:
            return "", "", None
    return "", "", None


def save_credentials(conn: sqlite3.Connection, cipher: Cipher, refresh_token: str, api_key: str) -> None:
    with conn:
        conn.execute(
            "UPDATE profile SET refresh_token_enc = ?, api_key_enc = ?, updated_at = ? WHERE id = 1",
            (cipher.encrypt(refresh_token), cipher.encrypt(api_key), _now()),
        )


def save_refresh_token(conn: sqlite3.Connection, cipher: Cipher, refresh_token: str) -> None:
    with conn:
        conn.execute(
            "UPDATE profile SET refresh_token_enc = ? WHERE id = 1 AND refresh_token_enc IS NOT NULL",
            (cipher.encrypt(refresh_token),),
        )


def clear_credentials(conn: sqlite3.Connection) -> None:
    with conn:
        conn.execute(
            "UPDATE profile SET refresh_token_enc = NULL, api_key_enc = NULL, updated_at = ? WHERE id = 1",
            (_now(),),
        )


def public(conn: sqlite3.Connection, settings: Settings, cipher: Cipher) -> dict:
    """Profile as exposed over the API. Never contains secrets."""
    row = _row(conn)
    refresh, _, source = credentials(conn, settings, cipher)
    out = {f: row[f] for f in PUBLIC_FIELDS}
    out["sync_interval_hours"] = sync_interval(conn, settings)
    out["lift_map"] = lift_map(conn)
    out["onboarded"] = row["onboarded_at"] is not None
    out["boostcamp"] = {
        "configured": bool(source),
        "source": source,
        "token_hint": f"…{refresh[-4:]}" if refresh else None,
        "decrypt_error": bool(row["refresh_token_enc"]) and source is None and not settings.has_credentials,
    }
    return out


def update(conn: sqlite3.Connection, fields: dict, complete: bool = False) -> None:
    fields = {k: v for k, v in fields.items() if k in EDITABLE_FIELDS}
    if fields.get("sex") in ("m", "f"):
        fields["dots_formula"] = fields["sex"]
    if "lift_map" in fields and fields["lift_map"] is not None:
        fields["lift_map"] = json.dumps(
            {lift: sorted({n.strip() for n in fields["lift_map"].get(lift, []) if n.strip()}) for lift in LIFTS}
        )
    if "training_start" in fields and fields["training_start"] is not None:
        fields["training_start"] = str(fields["training_start"])
    fields["updated_at"] = _now()
    if complete:
        fields["onboarded_at"] = _row(conn)["onboarded_at"] or _now()
    sets = ", ".join(f"{k} = :{k}" for k in fields)
    with conn:
        conn.execute(f"UPDATE profile SET {sets} WHERE id = 1", fields)
