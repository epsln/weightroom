"""FastAPI routes + static frontend serving."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import stats
from .auth import TokenManager
from .boostcamp import run_sync
from .config import LIFTS, Settings
from .db import connect, init_schema
from .scheduler import create_scheduler

Day = date


class BodyweightIn(BaseModel):
    date: Day
    kg: float = Field(gt=20, lt=400)


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(settings: Settings | None = None, enable_scheduler: bool = True) -> FastAPI:
    settings = settings or Settings.from_env()
    conn = connect(settings.database_path)
    init_schema(conn)
    tokens = TokenManager(settings.refresh_token, settings.firebase_api_key)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        scheduler = create_scheduler(conn, tokens, settings) if enable_scheduler else None
        if scheduler:
            scheduler.start()
        try:
            yield
        finally:
            if scheduler:
                scheduler.shutdown(wait=False)
            conn.close()

    app = FastAPI(title="Weightroom", lifespan=lifespan)
    app.state.conn = conn
    app.state.settings = settings

    def local_today() -> date:
        return (datetime.now(timezone.utc) + timedelta(hours=settings.timezone_offset)).date()

    # Endpoints are `async` on purpose: they run on the event loop thread, which
    # serializes access to the single SQLite connection.

    @app.get("/api/prs")
    async def get_prs():
        return stats.prs(conn, today=local_today())

    @app.get("/api/sessions")
    async def get_sessions(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
        return stats.list_sessions(conn, limit, offset)

    @app.get("/api/sessions/{session_id}")
    async def get_session(session_id: str):
        detail = stats.session_detail(conn, session_id)
        if detail is None:
            raise HTTPException(404, "Session not found")
        return detail

    @app.get("/api/volume/weekly")
    async def get_weekly(weeks: int = Query(12, ge=1, le=520)):
        return stats.weekly_volume(conn, weeks, today=local_today())

    def check_lift(lift: str) -> None:
        if lift not in LIFTS:
            raise HTTPException(404, f"Unknown lift; expected one of {', '.join(LIFTS)}")

    @app.get("/api/lifts/{lift}/history")
    async def get_lift_history(lift: str):
        check_lift(lift)
        return stats.lift_history(conn, lift)

    @app.get("/api/lifts/{lift}/estimate")
    async def get_lift_estimate(lift: str):
        check_lift(lift)
        return stats.lift_estimate(conn, lift)

    @app.get("/api/lifts/{lift}/actual-maxes")
    async def get_actual_maxes(lift: str):
        check_lift(lift)
        return stats.actual_maxes(conn, lift)

    @app.get("/api/lifts/{lift}/rep-curve")
    async def get_rep_curve(lift: str):
        check_lift(lift)
        return stats.rep_max_curve(conn, lift, today=local_today())

    @app.get("/api/intensity")
    async def get_intensity(weeks: int = Query(12, ge=1, le=520), lift: str | None = None):
        if lift is not None:
            check_lift(lift)
        return stats.intensity_distribution(conn, weeks, lift, today=local_today())

    @app.get("/api/prs/timeline")
    async def get_pr_timeline():
        return stats.pr_timeline(conn, today=local_today())

    @app.get("/api/total")
    async def get_total(sex: Literal["m", "f"] = "m"):
        return stats.total_series(conn, sex)

    @app.get("/api/bodyweight")
    async def get_bodyweight():
        return stats.list_bodyweight(conn)

    @app.post("/api/bodyweight")
    async def post_bodyweight(body: BodyweightIn):
        stats.set_bodyweight(conn, body.date, body.kg)
        return stats.list_bodyweight(conn)

    @app.delete("/api/bodyweight/{day}")
    async def delete_bodyweight(day: date):
        if not stats.delete_bodyweight(conn, day):
            raise HTTPException(404, "No entry for that date")
        return stats.list_bodyweight(conn)

    @app.post("/api/sync")
    async def post_sync():
        return await run_sync(conn, tokens, settings.timezone_offset)

    @app.get("/api/sync/status")
    async def get_sync_status():
        return {
            "last": stats.last_sync(conn),
            "configured": settings.has_credentials,
            "interval_hours": settings.sync_interval_hours,
        }

    @app.api_route("/api/{_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def api_not_found(_path: str):
        raise HTTPException(404, "Not found")

    dist = Path(settings.frontend_dist).resolve()
    if (dist / "index.html").is_file():

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str):
            target = (dist / path).resolve()
            if path and target.is_file() and target.is_relative_to(dist):
                return FileResponse(target)
            if path.startswith("assets/"):
                raise HTTPException(404, "Not found")
            return FileResponse(dist / "index.html")

    return app
