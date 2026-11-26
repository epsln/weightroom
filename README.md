# Weightroom

[![CI](https://github.com/epsln/weightroom/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/epsln/weightroom/actions/workflows/ci.yml)

Self-hosted dashboard for gym progress, built from your [Boostcamp](https://www.boostcamp.app) history.

- PRs for squat, bench and deadlift: heaviest set, best e1RM (Brzycki), best set volume, best session volume, and 1/3/5/8/10RM. "Actual max" means the heaviest weight lifted for any number of reps.
- e1RM trend chart, weekly volume split by lift, and session history with a per-session detail view.
- Syncs with Boostcamp at startup and every `SYNC_INTERVAL_HOURS`, or on demand with **Sync now**.

See [`docs/PLAN.md`](docs/PLAN.md) for the data rules (unit conversion, excluded sets, lift mapping).

## 1. First run (onboarding)

On first launch the app walks you through a short setup:

1. **About you:** name (optional), sex (man / woman / other), birth year and height (optional). With **other** you choose which DOTS formula (male or female) to be scored with.
2. **Body:** display units (kg or lb), current bodyweight, and when you started training.
3. **Boostcamp:** paste your refresh token and API key (see below), and pick the sync interval. This step can be skipped.
4. **Lifts:** choose which Boostcamp exercise names count as squat, bench and deadlift.

Everything can be changed later under **Settings**.

### How the pasted token is protected

- Weightroom checks the credentials with Google before saving them. It never sends them back to the browser; the UI only shows the last 4 characters.
- They are stored **encrypted** (Fernet) in SQLite. The key comes from `WEIGHTROOM_SECRET`. When that's unset, a random key is generated in `secret.key` next to the database (mode `0600`). A copy of `weightroom.db` alone does not reveal the token. If the key changes, re-enter the credentials in Settings.
- If Google rotates the refresh token, the new one is saved, again encrypted.
- Credentials in `.env` take priority over stored ones and can't be edited from the UI.
- The onboarding page warns when it's served over plain HTTP from a host other than localhost.

## 2. Get your Boostcamp credentials

Weightroom uses Boostcamp's unofficial web API, which authenticates with Firebase. You need two values:

1. Log in to <https://www.boostcamp.app> (Google sign-in).
2. Open DevTools and go to **Application → IndexedDB → `firebaseLocalStorageDb` → `firebaseLocalStorage`**.
3. Expand the single entry:
   - `value.stsTokenManager.refreshToken` → `BOOSTCAMP_REFRESH_TOKEN`
   - `value.apiKey` → `FIREBASE_API_KEY`
4. Paste both values into the onboarding step or **Settings → Boostcamp**. Alternatively, copy `.env.example` to `.env` and put them there.

```sh
cp .env.example .env
```

`.env` is gitignored. Never commit it. The refresh token is long-lived but can be revoked, for example by "log out everywhere". If a sync fails with `TOKEN_EXPIRED` or `INVALID_REFRESH_TOKEN`, paste a fresh token in Settings (or update `.env` and restart).

| Variable | Default | |
|---|---|---|
| `BOOSTCAMP_REFRESH_TOKEN` | – | optional; overrides credentials entered in the app |
| `FIREBASE_API_KEY` | – | optional; overrides credentials entered in the app |
| `WEIGHTROOM_SECRET` | – | encryption key for stored credentials; auto-generated `secret.key` when unset |
| `TIMEZONE_OFFSET` | `1` | hours, sent to Boostcamp and used to compute "this week" |
| `SYNC_INTERVAL_HOURS` | `6` | default; the interval chosen in Settings wins |
| `DATABASE_PATH` | `/data/weightroom.db` | `./data/weightroom.db` when unset in dev |
| `SYNC_ON_STARTUP` | `1` | set to `0` to skip the startup sync |

## 3. Run with Docker

```sh
docker compose up -d --build
```

Open <http://localhost:8000>. The SQLite database lives in the `weightroom-data` volume.

The dashboard has **no authentication**. Keep it on your LAN or put it behind a reverse proxy with auth.

Prebuilt images are published to GHCR:

```sh
docker pull ghcr.io/epsln/weightroom:latest   # latest release (also :X.Y.Z, :X.Y)
docker pull ghcr.io/epsln/weightroom:develop  # tip of develop
```

## Branching and releases

The project uses gitflow. CI (`.github/workflows/ci.yml`) runs ruff and pytest on the backend, and oxlint and the build on the frontend, for every PR into `develop`/`main` and every push to `main`, `develop`, `release/*` and `hotfix/*`.

| Branch | Image tags published |
|---|---|
| `develop` | `develop`, `sha-<short>` |
| `release/X.Y.Z`, `hotfix/X.Y.Z` | `X.Y.Z-rc`, `sha-<short>` |
| PR from `release/X.Y.Z` or `hotfix/X.Y.Z` merged into `main` | tag `vX.Y.Z` is created automatically, and `X.Y.Z`, `X.Y`, `latest` are published with a GitHub release |

To release: branch `release/X.Y.Z` from `develop`, open a PR into `main` and merge it, then merge `main` back into `develop`. Don't tag by hand; release and hotfix branches must be named exactly `X.Y.Z`.

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

Each sync calls `POST /api/www/programs/history`, upserts every session's raw JSON into `raw_sessions`, and then fully rebuilds the `sessions` and `sets` tables from it. Syncs are idempotent, and changing a normalization rule (for example the lift mapping, editable in Settings; defaults live in `backend/app/config.py`) only needs a re-sync or `normalize.rebuild()`, not a re-fetch.

| Endpoint | |
|---|---|
| `GET /api/prs` | PRs per lift |
| `GET /api/sessions?limit&offset` | session list |
| `GET /api/sessions/{id}` | session detail, sets grouped by exercise |
| `GET /api/volume/weekly?weeks=N` | kg per ISO week, split squat/bench/deadlift/other |
| `GET /api/lifts/{lift}/history` | per-session best e1RM, top set, volume |
| `POST /api/sync` | sync now; returns the `sync_log` row |
| `GET /api/sync/status` | last sync result |
| `GET /api/profile` | profile, preferences, lift mapping and Boostcamp status (never secrets) |
| `PUT /api/profile` | partial update; optional `bodyweight` entry and `complete: true` to finish onboarding |
| `GET /api/exercises` | distinct exercise names in history, for the lift mapping |
| `PUT /api/boostcamp/credentials` | verify and store `{refresh_token, api_key}` encrypted |
| `DELETE /api/boostcamp/credentials` | forget stored credentials |
