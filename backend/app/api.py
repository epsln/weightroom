"""FastAPI routes + static frontend serving."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import normalize, profile, stats
from .auth import BoostcampAuthError, TokenManager, verify_credentials
from .boostcamp import run_sync
from .config import LIFTS, Settings
from .crypto import load_cipher
from .db import connect, init_schema
from .scheduler import create_scheduler, reschedule

Day = date


class BodyweightIn(BaseModel):
    date: Day
    kg: float = Field(gt=20, lt=400)


Lift = Literal["squat", "bench", "deadlift"]


class ProfileIn(BaseModel):
    """Partial update: only fields that are sent are changed."""

    name: str | None = Field(None, max_length=60)
    sex: Literal["m", "f", "other"] | None = None
    dots_formula: Literal["m", "f"] | None = None
    units: Literal["kg", "lb"] | None = None
    height_cm: float | None = Field(None, ge=100, le=250)
    birth_year: int | None = Field(None, ge=1900, le=2100)
    training_start: Day | None = None
    sync_interval_hours: int | None = Field(None, ge=1, le=168)
    lift_map: dict[Lift, list[str]] | None = None
    bodyweight: BodyweightIn | None = None
    complete: bool = False


class CredentialsIn(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=4096)
    api_key: str = Field(min_length=10, max_length=200)


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# httpx logs full URLs at INFO, which include the Firebase API key as a query param.
logging.getLogger("httpx").setLevel(logging.WARNING)


def create_app(settings: Settings | None = None, enable_scheduler: bool = True) -> FastAPI:
    settings = settings or Settings.from_env()
    conn = connect(settings.database_path)
    init_schema(conn)
    cipher = load_cipher(settings)
    refresh, api_key, _source = profile.credentials(conn, settings, cipher)

    def persist_rotated(new_token: str) -> None:
        # Only DB-stored tokens are persisted; .env is the user's to manage.
        if profile.credentials(conn, settings, cipher)[2] == "db":
            profile.save_refresh_token(conn, cipher, new_token)

    tokens = TokenManager(refresh, api_key, on_rotate=persist_rotated)
    state: dict = {"scheduler": None}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if enable_scheduler:
            state["scheduler"] = create_scheduler(
                conn, tokens, settings, lambda: profile.sync_interval(conn, settings)
            )
            state["scheduler"].start()
        try:
            yield
        finally:
            if state["scheduler"]:
                state["scheduler"].shutdown(wait=False)
            conn.close()

    app = FastAPI(title="Weightroom", lifespan=lifespan)
    app.state.conn = conn
    app.state.settings = settings

    def local_today() -> date:
        return (datetime.now(UTC) + timedelta(hours=settings.timezone_offset)).date()

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
    async def get_total(sex: Literal["m", "f"] | None = None):
        return stats.total_series(conn, sex or profile.dots_formula(conn))

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
            "configured": tokens.configured,
            "interval_hours": profile.sync_interval(conn, settings),
        }

    @app.get("/api/profile")
    async def get_profile():
        return profile.public(conn, settings, cipher)

    @app.put("/api/profile")
    async def put_profile(body: ProfileIn):
        fields = body.model_dump(exclude_unset=True, exclude={"bodyweight", "complete"})
        if fields.get("sex") == "other" and "dots_formula" not in fields:
            raise HTTPException(422, "Choose a DOTS formula (m or f) when sex is 'other'")
        old_map = profile.lift_map(conn)
        old_interval = profile.sync_interval(conn, settings)
        profile.update(conn, fields, complete=body.complete)
        if body.bodyweight:
            stats.set_bodyweight(conn, body.bodyweight.date, body.bodyweight.kg)
        if profile.lift_map(conn) != old_map:
            normalize.rebuild(conn)
        new_interval = profile.sync_interval(conn, settings)
        if new_interval != old_interval:
            reschedule(state["scheduler"], new_interval)
        return profile.public(conn, settings, cipher)

    @app.get("/api/exercises")
    async def get_exercises():
        return stats.exercise_names(conn)

    @app.put("/api/boostcamp/credentials")
    async def put_credentials(body: CredentialsIn):
        if settings.has_credentials:
            raise HTTPException(409, "Credentials are set in the environment (.env); edit them there")
        refresh_token, api_key = body.refresh_token.strip(), body.api_key.strip()
        try:
            refresh_token = await verify_credentials(refresh_token, api_key)
        except BoostcampAuthError as exc:
            raise HTTPException(400, f"Boostcamp rejected these credentials: {exc}") from exc
        profile.save_credentials(conn, cipher, refresh_token, api_key)
        tokens.set_credentials(refresh_token, api_key)
        return profile.public(conn, settings, cipher)

    @app.delete("/api/boostcamp/credentials")
    async def delete_credentials():
        if settings.has_credentials:
            raise HTTPException(409, "Credentials are set in the environment (.env); remove them there")
        profile.clear_credentials(conn)
        tokens.set_credentials("", "")
        return profile.public(conn, settings, cipher)

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
