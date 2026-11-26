# Weightroom

Self-hosted dashboard for gym progress, built from your [Boostcamp](https://www.boostcamp.app) history.

- PRs for squat, bench and deadlift: heaviest set, best e1RM (Brzycki), best set volume, best session volume, and 1/3/5/8/10RM.
- e1RM trend chart, weekly volume split by lift, and session history with a per-session detail view.
- Syncs with Boostcamp at startup and every `SYNC_INTERVAL_HOURS`, or on demand with **Sync now**.

See [`docs/PLAN.md`](docs/PLAN.md) for the data rules (unit conversion, excluded sets, lift mapping).

## 1. Get your Boostcamp credentials

Weightroom uses Boostcamp's unofficial web API, which authenticates with Firebase. You need two values:

1. Log in to <https://www.boostcamp.app> (Google sign-in).
2. Open DevTools and go to **Application → IndexedDB → `firebaseLocalStorageDb` → `firebaseLocalStorage`**.
3. Expand the single entry:
   - `value.stsTokenManager.refreshToken` → `BOOSTCAMP_REFRESH_TOKEN`
   - `value.apiKey` → `FIREBASE_API_KEY`
4. Copy `.env.example` to `.env` and paste both values into it.

```sh
cp .env.example .env
```

`.env` is gitignored. Never commit it. The refresh token is long-lived but can be revoked, for example by "log out everywhere". If a sync fails with `TOKEN_EXPIRED` or `INVALID_REFRESH_TOKEN`, copy a fresh token and restart.

| Variable | Default | |
|---|---|---|
| `BOOSTCAMP_REFRESH_TOKEN` | – | required for sync |
| `FIREBASE_API_KEY` | – | required for sync |
| `TIMEZONE_OFFSET` | `1` | hours, sent to Boostcamp and used to compute "this week" |
| `SYNC_INTERVAL_HOURS` | `6` | |
| `DATABASE_PATH` | `/data/weightroom.db` | `./data/weightroom.db` when unset in dev |
| `SYNC_ON_STARTUP` | `1` | set to `0` to skip the startup sync |

## 2. Run with Docker

```sh
docker compose up -d --build
```

Open <http://localhost:8000>. The SQLite database lives in the `weightroom-data` volume.

The dashboard has **no authentication**. Keep it on your LAN or put it behind a reverse proxy with auth.

## Development

Requirements: Python 3.12 with [uv](https://docs.astral.sh/uv/), and Node 20+.

```sh
# backend (http://localhost:8000)
cd backend
uv sync
set -a; source ../.env; set +a; export DATABASE_PATH=../data/weightroom.db
uv run uvicorn --factory app.api:create_app --reload

# frontend (http://localhost:5173, proxies /api to :8000)
cd frontend
npm install
npm run dev
```

Useful commands:

```sh
cd backend
uv run pytest                                   # tests
uv run python -m app.cli sync                   # one-off sync using .env
uv run python -m app.cli import history.json    # load a saved /programs/history response
```

## How it works

Each sync calls `POST /api/www/programs/history`, upserts every session's raw JSON into `raw_sessions`, and then fully rebuilds the `sessions` and `sets` tables from it. Syncs are idempotent, and changing a normalization rule (for example the lift map in `backend/app/config.py`) only needs a re-sync or `normalize.rebuild()`, not a re-fetch.

| Endpoint | |
|---|---|
| `GET /api/prs` | PRs per lift |
| `GET /api/sessions?limit&offset` | session list |
| `GET /api/sessions/{id}` | session detail, sets grouped by exercise |
| `GET /api/volume/weekly?weeks=N` | kg per ISO week, split squat/bench/deadlift/other |
| `GET /api/lifts/{lift}/history` | per-session best e1RM, top set, volume |
| `POST /api/sync` | sync now; returns the `sync_log` row |
| `GET /api/sync/status` | last sync result |
