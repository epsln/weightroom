"""Settings from the environment, plus the editable lift mapping."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Exact Boostcamp exercise names that count toward each competition lift.
# Variations (front squat, close grip, sumo, paused, ...) are deliberately NOT
# listed: they get lift = NULL but still count toward volume.
LIFT_MAP: dict[str, str] = {
    "Squat (Barbell)": "squat",
    "Squat": "squat",
    "Bench Press (Barbell)": "bench",
    "Bench Press": "bench",
    "Deadlift (Barbell)": "deadlift",
    "Deadlift": "deadlift",
}
LIFTS: tuple[str, ...] = ("squat", "bench", "deadlift")

LB_PER_KG = 2.20462
WEIGHT_STEP_KG = 0.25
E1RM_MAX_REPS = 12
REP_MAX_TABLE: tuple[int, ...] = (1, 3, 5, 8, 10)

# Rolling 1RM estimate (see estimate.py).
ESTIMATE_WINDOW_DAYS = 42
ESTIMATE_HALF_LIFE_DAYS = 14.0
ESTIMATE_PERCENTILE = 0.9
ESTIMATE_MAX_REPS = 10

# Intensity zones as fraction of the estimated 1RM: (label, lower bound inclusive).
INTENSITY_ZONES: tuple[tuple[str, float], ...] = (
    ("<70", 0.0), ("70-80", 0.70), ("80-90", 0.80), ("90+", 0.90),
)
REP_CURVE_MAX = 12

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


@dataclass(frozen=True)
class Settings:
    refresh_token: str
    firebase_api_key: str
    timezone_offset: int
    sync_interval_hours: int
    database_path: str
    frontend_dist: str
    sync_on_startup: bool

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            refresh_token=os.environ.get("BOOSTCAMP_REFRESH_TOKEN", "").strip(),
            firebase_api_key=os.environ.get("FIREBASE_API_KEY", "").strip(),
            timezone_offset=_env_int("TIMEZONE_OFFSET", 1),
            sync_interval_hours=_env_int("SYNC_INTERVAL_HOURS", 6),
            database_path=os.environ.get("DATABASE_PATH", "").strip()
            or str(_REPO_ROOT / "data" / "weightroom.db"),
            frontend_dist=os.environ.get("FRONTEND_DIST", "").strip()
            or str(_REPO_ROOT / "frontend" / "dist"),
            sync_on_startup=os.environ.get("SYNC_ON_STARTUP", "1").strip() != "0",
        )

    @property
    def has_credentials(self) -> bool:
        return bool(self.refresh_token and self.firebase_api_key)
