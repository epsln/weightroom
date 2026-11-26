"""Periodic Boostcamp sync: once at startup, then every SYNC_INTERVAL_HOURS."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .auth import TokenManager
from .boostcamp import run_sync
from .config import Settings

log = logging.getLogger("weightroom.sync")


def create_scheduler(conn: sqlite3.Connection, tokens: TokenManager, settings: Settings) -> AsyncIOScheduler | None:
    if not settings.has_credentials:
        log.warning("Boostcamp credentials missing; periodic sync disabled (see .env.example)")
        return None

    async def job() -> None:
        result = await run_sync(conn, tokens, settings.timezone_offset)
        if result["ok"]:
            log.info("Sync ok: %s sessions", result["sessions_seen"])
        else:
            log.error("Sync failed: %s", result["error"])

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        job,
        "interval",
        hours=max(1, settings.sync_interval_hours),
        id="boostcamp-sync",
        next_run_time=datetime.now() if settings.sync_on_startup else None,
        max_instances=1,
        coalesce=True,
    )
    return scheduler
