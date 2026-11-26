"""Periodic Boostcamp sync: once at startup, then every N hours (profile or SYNC_INTERVAL_HOURS)."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .auth import TokenManager
from .boostcamp import run_sync
from .config import Settings

log = logging.getLogger("weightroom.sync")
JOB_ID = "boostcamp-sync"


def create_scheduler(
    conn: sqlite3.Connection,
    tokens: TokenManager,
    settings: Settings,
    interval_hours: Callable[[], int],
) -> AsyncIOScheduler:
    """Always created; the job is a no-op until credentials exist (they can be added at runtime)."""

    async def job() -> None:
        if not tokens.configured:
            return
        result = await run_sync(conn, tokens, settings.timezone_offset)
        if result["ok"]:
            log.info("Sync ok: %s sessions", result["sessions_seen"])
        else:
            log.error("Sync failed: %s", result["error"])

    if not tokens.configured:
        log.warning("Boostcamp credentials missing; add them in the app (Settings) to enable sync")

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        job,
        "interval",
        hours=max(1, interval_hours()),
        id=JOB_ID,
        next_run_time=datetime.now() if settings.sync_on_startup and tokens.configured else None,
        max_instances=1,
        coalesce=True,
    )
    return scheduler


def reschedule(scheduler: AsyncIOScheduler | None, hours: int) -> None:
    if scheduler is not None:
        scheduler.reschedule_job(JOB_ID, trigger="interval", hours=max(1, hours))
