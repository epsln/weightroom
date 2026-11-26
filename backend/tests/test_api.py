import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.auth import BoostcampAuthError, TokenManager
from app.boostcamp import import_history
from app.config import Settings


def make_settings(tmp_path, **kw):
    base = dict(
        refresh_token="", firebase_api_key="", timezone_offset=1, sync_interval_hours=6,
        database_path=str(tmp_path / "t.db"), frontend_dist=str(tmp_path / "nodist"),
        sync_on_startup=False,
    )
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
    assert client.get("/api/lifts/squat/actual-maxes").json() == []
    assert len(client.get("/api/lifts/bench/rep-curve").json()) == 12
    assert client.get("/api/lifts/curl/estimate").status_code == 404
    assert len(client.get("/api/intensity?weeks=4&lift=deadlift").json()) == 4
    assert "events" in client.get("/api/prs/timeline").json()
    assert client.get("/api/total?sex=f").status_code == 200
    assert client.get("/api/total?sex=x").status_code == 422
    prs = client.get("/api/prs").json()["squat"]
    assert prs["estimated_1rm"] and prs["best_single"] is None


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
