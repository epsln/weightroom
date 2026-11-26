import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.auth import BoostcampAuthError, TokenManager
from app.boostcamp import import_history
from app.config import Settings


def make_settings(tmp_path, **kw):
    base = {
        "refresh_token": "", "firebase_api_key": "", "timezone_offset": 1, "sync_interval_hours": 6,
        "database_path": str(tmp_path / "t.db"), "frontend_dist": str(tmp_path / "nodist"),
        "sync_on_startup": False,
    }
    base.update(kw)
    return Settings(**base)


@pytest.fixture
def client(tmp_path, history):
    app = create_app(make_settings(tmp_path), enable_scheduler=False)
    import_history(app.state.conn, history)
    with TestClient(app) as c:
        yield c


def test_api_endpoints(client):
    assert client.get("/api/prs").json()["deadlift"]["heaviest"]["weight_kg"] == 125.0
    sessions = client.get("/api/sessions?limit=2").json()
    assert sessions["total"] == 5 and len(sessions["items"]) == 2
    sid = sessions["items"][0]["id"]
    assert client.get(f"/api/sessions/{sid}").json()["id"] == sid
    assert client.get("/api/sessions/missing").status_code == 404
    assert len(client.get("/api/volume/weekly?weeks=8").json()) == 8
    assert client.get("/api/lifts/squat/history").status_code == 200
    assert client.get("/api/lifts/curl/history").status_code == 404
    assert client.get("/api/nope").status_code == 404


def test_stats_endpoints(client):
    assert client.get("/api/lifts/squat/estimate").json()["current"] is not None
    am = client.get("/api/lifts/squat/actual-maxes").json()
    assert [(m["weight_kg"], m["reps"], m["is_pr"]) for m in am] == [(92.5, 7, True)]
    assert len(client.get("/api/lifts/bench/rep-curve").json()) == 12
    assert client.get("/api/lifts/curl/estimate").status_code == 404
    assert len(client.get("/api/intensity?weeks=4&lift=deadlift").json()) == 4
    assert "events" in client.get("/api/prs/timeline").json()
    assert client.get("/api/total?sex=f").status_code == 200
    assert client.get("/api/total?sex=x").status_code == 422
    prs = client.get("/api/prs").json()["squat"]
    assert prs["estimated_1rm"] and "best_single" not in prs


def test_bodyweight_crud(client):
    assert client.post("/api/bodyweight", json={"date": "2026-01-01", "kg": 80}).json() == [
        {"date": "2026-01-01", "kg": 80.0}]
    assert client.post("/api/bodyweight", json={"date": "2026-01-01", "kg": 81}).json()[0]["kg"] == 81
    assert client.post("/api/bodyweight", json={"date": "2026-01-01", "kg": 5}).status_code == 422
    assert client.delete("/api/bodyweight/2026-01-01").json() == []
    assert client.delete("/api/bodyweight/2026-01-01").status_code == 404


def test_sync_without_credentials_logs_error(client):
    row = client.post("/api/sync").json()
    assert row["ok"] == 0
    assert "BOOSTCAMP_REFRESH_TOKEN" in row["error"]
    status = client.get("/api/sync/status").json()
    assert status["last"]["id"] == row["id"]
    assert status["configured"] is False
    # Existing data is untouched by a failed sync.
    assert client.get("/api/sessions").json()["total"] == 5


def test_spa_fallback(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>app</html>")
    (dist / "assets" / "a.js").write_text("js")
    app = create_app(make_settings(tmp_path, frontend_dist=str(dist)), enable_scheduler=False)
    with TestClient(app) as c:
        assert c.get("/").text == "<html>app</html>"
        assert c.get("/sessions/abc").text == "<html>app</html>"
        assert c.get("/assets/a.js").text == "js"
        assert c.get("/assets/missing.js").status_code == 404
        assert c.get("/../../etc/passwd").text == "<html>app</html>"
        assert c.get("/api/unknown").status_code == 404


# --- auth ----------------------------------------------------------------------

def _mock_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _token(tm):
    return await tm.get_id_token()


def test_token_cached_and_refreshed_before_expiry():
    import asyncio

    calls = []
    now = [0.0]

    def handler(req):
        calls.append(req)
        return httpx.Response(200, json={"id_token": f"tok{len(calls)}", "expires_in": "3600",
                                         "refresh_token": "rotated"})

    tm = TokenManager("rt", "key", client=_mock_client(handler), clock=lambda: now[0])
    assert asyncio.run(_token(tm)) == "tok1"
    assert b"refresh_token=rt" in calls[0].content
    now[0] = 3600 - 301
    assert asyncio.run(_token(tm)) == "tok1"
    now[0] = 3600 - 299  # inside the 5-minute margin
    assert asyncio.run(_token(tm)) == "tok2"
    assert b"refresh_token=rotated" in calls[1].content


@pytest.mark.parametrize("code", ["TOKEN_EXPIRED", "INVALID_REFRESH_TOKEN"])
def test_token_rejected_raises_clear_error(code):
    import asyncio

    tm = TokenManager("rt", "key", client=_mock_client(
        lambda req: httpx.Response(400, json={"error": {"code": 400, "message": code}})))
    with pytest.raises(BoostcampAuthError, match=code):
        asyncio.run(_token(tm))


@pytest.mark.parametrize("status", [200, 201])
def test_fetch_history_accepts_2xx(status, history):
    import asyncio

    from app.boostcamp import fetch_history

    class FakeTokens:
        async def get_id_token(self):
            return "tok"

        def invalidate(self):
            pass

    def handler(req):
        assert req.headers["Authorization"] == "FirebaseIdToken:tok"
        return httpx.Response(status, json=history)

    body = asyncio.run(fetch_history(FakeTokens(), 1, client=_mock_client(handler)))
    assert body["data"].keys() == history["data"].keys()


# --- profile / onboarding -------------------------------------------------

def test_profile_defaults_and_onboarding(client):
    p = client.get("/api/profile").json()
    assert p["onboarded"] is False and p["units"] == "kg" and p["dots_formula"] == "m"
    assert p["boostcamp"] == {"configured": False, "source": None, "token_hint": None, "decrypt_error": False}
    assert "Squat (Barbell)" in p["lift_map"]["squat"]

    p = client.put("/api/profile", json={
        "name": "Sam", "sex": "f", "units": "lb", "height_cm": 170, "birth_year": 1990,
        "training_start": "2024-03-01", "sync_interval_hours": 12,
        "bodyweight": {"date": "2026-01-01", "kg": 65}, "complete": True,
    }).json()
    assert p["onboarded"] and p["sex"] == "f" and p["dots_formula"] == "f" and p["units"] == "lb"
    assert p["sync_interval_hours"] == 12 and p["training_start"] == "2024-03-01"
    assert client.get("/api/bodyweight").json() == [{"date": "2026-01-01", "kg": 65.0}]
    assert client.get("/api/sync/status").json()["interval_hours"] == 12
    # Partial update keeps other fields.
    assert client.put("/api/profile", json={"name": "S"}).json()["units"] == "lb"


def test_profile_other_requires_formula(client):
    assert client.put("/api/profile", json={"sex": "other"}).status_code == 422
    p = client.put("/api/profile", json={"sex": "other", "dots_formula": "f"}).json()
    assert p["sex"] == "other" and p["dots_formula"] == "f"
    assert client.put("/api/profile", json={"units": "stone"}).status_code == 422
    assert client.put("/api/profile", json={"height_cm": 20}).status_code == 422


def test_total_uses_profile_formula(client):
    client.post("/api/bodyweight", json={"date": "2020-01-01", "kg": 80})
    m = client.get("/api/total").json()
    client.put("/api/profile", json={"sex": "other", "dots_formula": "f"})
    f = client.get("/api/total").json()
    assert f == client.get("/api/total?sex=f").json() and f != m


def test_lift_map_rebuilds(client):
    names = {e["exercise"] for e in client.get("/api/exercises").json()}
    assert "Squat (Barbell)" in names
    assert client.get("/api/lifts/squat/history").json()
    client.put("/api/profile", json={"lift_map": {"squat": [], "bench": ["Bench Press (Barbell)"], "deadlift": []}})
    assert client.get("/api/lifts/squat/history").json() == []
    ex = {e["exercise"]: e["lift"] for e in client.get("/api/exercises").json()}
    assert ex["Squat (Barbell)"] is None


TOKEN = "AMf-refresh-token-0123456789abcd"


def test_credentials_encrypted_and_never_returned(client, monkeypatch):
    async def ok(refresh, key):
        return refresh

    monkeypatch.setattr("app.api.verify_credentials", ok)
    p = client.put("/api/boostcamp/credentials", json={"refresh_token": TOKEN, "api_key": "AIzaSyTestKey"}).json()
    assert p["boostcamp"] == {"configured": True, "source": "db", "token_hint": "…abcd", "decrypt_error": False}
    assert client.get("/api/sync/status").json()["configured"] is True
    conn = client.app.state.conn
    row = conn.execute("SELECT refresh_token_enc, api_key_enc FROM profile").fetchone()
    assert row[0] and TOKEN not in row[0] and "AIzaSyTestKey" not in row[1]
    for path in ("/api/profile", "/api/sync/status"):
        assert TOKEN not in client.get(path).text
    p = client.delete("/api/boostcamp/credentials").json()
    assert p["boostcamp"]["configured"] is False
    assert client.get("/api/sync/status").json()["configured"] is False


def test_credentials_rejected(client, monkeypatch):
    async def bad(refresh, key):
        raise BoostcampAuthError("INVALID_REFRESH_TOKEN")

    monkeypatch.setattr("app.api.verify_credentials", bad)
    r = client.put("/api/boostcamp/credentials", json={"refresh_token": TOKEN, "api_key": "AIzaSyTestKey"})
    assert r.status_code == 400
    assert client.get("/api/profile").json()["boostcamp"]["configured"] is False


def test_env_credentials_win(tmp_path):
    app = create_app(make_settings(tmp_path, refresh_token=TOKEN, firebase_api_key="k" * 12), enable_scheduler=False)
    with TestClient(app) as c:
        assert c.get("/api/profile").json()["boostcamp"]["source"] == "env"
        r = c.put("/api/boostcamp/credentials", json={"refresh_token": TOKEN, "api_key": "AIzaSyTestKey"})
        assert r.status_code == 409


def test_credentials_survive_restart_and_key_file(tmp_path, monkeypatch):
    async def ok(refresh, key):
        return refresh

    monkeypatch.setattr("app.api.verify_credentials", ok)
    settings = make_settings(tmp_path)
    with TestClient(create_app(settings, enable_scheduler=False)) as c:
        c.put("/api/boostcamp/credentials", json={"refresh_token": TOKEN, "api_key": "AIzaSyTestKey"})
    key = tmp_path / "secret.key"
    assert key.is_file() and (key.stat().st_mode & 0o777) == 0o600
    with TestClient(create_app(settings, enable_scheduler=False)) as c:
        assert c.get("/api/profile").json()["boostcamp"]["token_hint"] == "…abcd"
    key.unlink()  # lost key -> stored secrets unreadable, reported instead of crashing
    with TestClient(create_app(settings, enable_scheduler=False)) as c:
        b = c.get("/api/profile").json()["boostcamp"]
        assert b["configured"] is False and b["decrypt_error"] is True


def test_explicit_secret(tmp_path, monkeypatch):
    async def ok(refresh, key):
        return refresh

    monkeypatch.setattr("app.api.verify_credentials", ok)
    settings = make_settings(tmp_path, secret="s3cret")
    with TestClient(create_app(settings, enable_scheduler=False)) as c:
        c.put("/api/boostcamp/credentials", json={"refresh_token": TOKEN, "api_key": "AIzaSyTestKey"})
    assert not (tmp_path / "secret.key").exists()
    with TestClient(create_app(settings, enable_scheduler=False)) as c:
        assert c.get("/api/profile").json()["boostcamp"]["configured"] is True


def test_token_rotation_callback():
    import asyncio

    seen = []

    def handler(request):
        return httpx.Response(200, json={"id_token": "id", "expires_in": 3600, "refresh_token": "new"})

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            tm = TokenManager("old", "key", client=http, on_rotate=seen.append)
            return await tm.get_id_token()

    assert asyncio.run(go()) == "id"
    assert seen == ["new"]
