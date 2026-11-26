"""SQLite schema and connection helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_sessions (
    id          TEXT PRIMARY KEY,
    finished_at TEXT,
    payload     JSON NOT NULL,
    fetched_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    finished_at TEXT,
    date        TEXT NOT NULL,
    iso_year    INT NOT NULL,
    iso_week    INT NOT NULL,
    program     TEXT,
    title       TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(date);
CREATE INDEX IF NOT EXISTS idx_sessions_week ON sessions(iso_year, iso_week);

CREATE TABLE IF NOT EXISTS sets (
    id           INTEGER PRIMARY KEY,
    session_id   TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    exercise_idx INT NOT NULL,
    exercise     TEXT NOT NULL,
    lift         TEXT NULL,
    set_idx      INT NOT NULL,
    weight_kg    REAL NOT NULL,
    reps         INT NOT NULL,
    volume_kg    REAL NOT NULL,
    e1rm_kg      REAL NULL
);
CREATE INDEX IF NOT EXISTS idx_sets_session ON sets(session_id);
CREATE INDEX IF NOT EXISTS idx_sets_lift ON sets(lift);

CREATE TABLE IF NOT EXISTS bodyweight (
    date TEXT PRIMARY KEY,
    kg   REAL NOT NULL
);

-- Single-row user profile (id is always 1). Boostcamp secrets are Fernet-encrypted.
CREATE TABLE IF NOT EXISTS profile (
    id                  INTEGER PRIMARY KEY CHECK (id = 1),
    name                TEXT NULL,
    sex                 TEXT NULL CHECK (sex IN ('m', 'f', 'other')),
    dots_formula        TEXT NOT NULL DEFAULT 'm' CHECK (dots_formula IN ('m', 'f')),
    units               TEXT NOT NULL DEFAULT 'kg' CHECK (units IN ('kg', 'lb')),
    height_cm           REAL NULL,
    birth_year          INT NULL,
    training_start      TEXT NULL,
    sync_interval_hours INT NULL,
    lift_map            JSON NULL,
    refresh_token_enc   TEXT NULL,
    api_key_enc         TEXT NULL,
    onboarded_at        TEXT NULL,
    updated_at          TEXT NULL
);
INSERT OR IGNORE INTO profile (id) VALUES (1);

CREATE TABLE IF NOT EXISTS sync_log (
    id            INTEGER PRIMARY KEY,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    ok            INT NOT NULL DEFAULT 0,
    sessions_seen INT,
    error         TEXT NULL
);
"""


def connect(path: str) -> sqlite3.Connection:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
