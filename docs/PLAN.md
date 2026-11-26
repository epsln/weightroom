# Weightroom – Implementation Plan

Self-hosted dashboard for gym progress, built from Boostcamp history data.

## Goals
- History of past sessions, with a detail view for each one.
- Personal records (PRs) for squat, bench and deadlift: heaviest weight, best estimated 1RM, best set volume and best session volume.
- Volume for each session, and total weight moved per week.

## Data source (reverse-engineered Boostcamp API)

- **Endpoint:** `POST https://newapi.boostcamp.app/api/www/programs/history?_=<epoch_ms>`. The `_` parameter only busts the cache and is optional.
- **Body:** `{"timezone_offset": 1}`
- **Headers:**
  - `Authorization: FirebaseIdToken:<id_token>`
  - `Content-Type: application/json; charset=UTF-8`
  - `Origin: https://www.boostcamp.app`
  - `Referer: https://www.boostcamp.app/`
- **Response:** the whole history in one call, with no pagination.

### Auth
- The Firebase project is `boost-be7fe`. You sign in with Google.
- An ID token is valid for 1 hour. Exchange the long-lived refresh token for a new one:
  ```
  POST https://securetoken.googleapis.com/v1/token?key=<FIREBASE_API_KEY>
  Content-Type: application/x-www-form-urlencoded
  grant_type=refresh_token&refresh_token=<REFRESH_TOKEN>
  -> { id_token, refresh_token, expires_in, ... }
  ```
- **Where to find the refresh token and API key:** log in to www.boostcamp.app, open DevTools and go to Application → IndexedDB → `firebaseLocalStorageDb` → `firebaseLocalStorage`. The refresh token is at `value.stsTokenManager.refreshToken` and the API key at `value.apiKey`.
- Store both in `.env` only. Never commit them.

### Response shape
```
{ "data": { "YYYY-MM-DD": [ session, ... ] } }

session: id, program_id (nullable), finished_at ("YYYY-MM-DD HH:MM:SS", local time),
         name (program name), title ("Week 2 · Day 2"), week, day, type, records[]
record:  id, name ("Squat (Barbell)"), type ("Barbell"), sets[], alternatives[]
set:     value, amount (planned/prefilled; may be STALE),
         archived_weight (ACTUAL, stored in LB), archived_reps (ACTUAL),
         skipped (bool), target_type, weight_unit, maxValue? (Boostcamp PR markers)
```

### Field rules (verified against Boostcamp's own `maxValue` numbers and the user's confirmation)
- Actual weight = `archived_weight / 2.20462`, rounded to the nearest 0.25 kg.
  - Example: 203.9276 lb → 92.5 kg.
- Actual reps = `archived_reps`. Confirmed with the 2026-11-24 deadlift: 125 kg × 4.
- Exclude a set if any of these is true:
  - `skipped == true`
  - `archived_reps` is missing or 0
  - `archived_weight` is missing or 0
- Ignore `alternatives[]`. It lists swap options, not completed work.
- `value` and `amount` are not reliable, so never use them for stats.

### Lift mapping (variations do NOT count toward PRs)
| Lift     | Exercise names that count                   |
|----------|---------------------------------------------|
| squat    | `Squat (Barbell)`, `Squat`                  |
| bench    | `Bench Press (Barbell)`, `Bench Press`      |
| deadlift | `Deadlift (Barbell)`, `Deadlift`            |

Everything else (Front/Low Bar/Paused/Tempo Squat, Close Grip/Larsen/Spoto/Dumbbell bench, Sumo/Romanian/Paused/Deficit deadlift, …) gets `lift = NULL`. Those sets still count toward session and weekly volume. The table above is the default in `config.py`. Users can change it in onboarding or Settings; it is stored in `profile.lift_map` and saving it triggers `normalize.rebuild()`.

### Estimated 1RM
- Use Brzycki, to match Boostcamp: `e1RM = w × 36 / (37 − reps)`.
  - Check: 92.5 kg × 7 → about 111 kg, which matches Boostcamp's 244.71 lb.
- Only compute e1RM when reps ≤ 12. For higher reps, leave e1RM as NULL but keep counting the set's volume.

### Time
- `finished_at` is local time (UTC+1). Use the date part for sessions.
- Weeks are ISO weeks, Monday to Sunday.

## Stack
- **Backend:** Python 3.12, FastAPI, httpx, SQLite (sqlite3 or SQLModel), APScheduler, pytest. Manage dependencies with `uv`.
- **Frontend:** Vite, React, TypeScript, Recharts.
- **Deploy:** one Docker image. The frontend is built into static files and FastAPI serves them. Use docker-compose with a volume for the SQLite file.

## Project layout
```
weightroom/
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── config.py      # settings from env + LIFT_MAP
│   │   ├── auth.py        # refresh-token -> id-token, cached, refreshed 5 min before expiry
│   │   ├── boostcamp.py   # fetch history, upsert raw sessions
│   │   ├── db.py          # schema + connection
│   │   ├── normalize.py   # raw JSON -> sessions/sets rows
│   │   ├── stats.py       # PRs, volume, trends
│   │   ├── api.py         # FastAPI routes + static file serving
│   │   └── scheduler.py   # periodic sync
│   └── tests/
│       ├── fixtures/history_sample.json   # anonymised subset (no user_id/email)
│       ├── test_normalize.py
│       └── test_stats.py
├── frontend/
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── docs/PLAN.md
```

## Database schema
```sql
raw_sessions(id TEXT PRIMARY KEY, finished_at TEXT, payload JSON, fetched_at TEXT)
sessions(id TEXT PRIMARY KEY, finished_at TEXT, date TEXT, iso_year INT, iso_week INT,
         program TEXT, title TEXT)
sets(id INTEGER PRIMARY KEY, session_id TEXT REFERENCES sessions(id),
     exercise_idx INT, exercise TEXT, lift TEXT NULL, set_idx INT,
     weight_kg REAL, reps INT, volume_kg REAL, e1rm_kg REAL NULL)
sync_log(id INTEGER PRIMARY KEY, started_at TEXT, finished_at TEXT,
         ok INT, sessions_seen INT, error TEXT NULL)
profile(id = 1, name, sex m|f|other, dots_formula m|f, units kg|lb, height_cm, birth_year,
        training_start, sync_interval_hours, lift_map JSON,
        refresh_token_enc, api_key_enc,  -- Fernet; key = WEIGHTROOM_SECRET or data/secret.key
        onboarded_at, updated_at)
```
Each sync upserts `raw_sessions` and then fully rebuilds `sessions` and `sets` from it. This makes syncs idempotent, so normalization rules can change without re-fetching.

## API
| Method | Path | Returns |
|---|---|---|
| GET  | `/api/prs` | For each lift, with date and session: heaviest set, best e1RM, best set volume, best session volume, and rep-max table (1/3/5/8/10RM) |
| GET  | `/api/sessions?limit&offset` | List of sessions: date, title, program, total volume, sets, reps, exercises |
| GET  | `/api/sessions/{id}` | Session detail with its sets grouped by exercise |
| GET  | `/api/volume/weekly?weeks=N` | Total kg per ISO week, split by squat, bench, deadlift and other |
| GET  | `/api/lifts/{lift}/history` | For each session: best e1RM, top set and lift volume |
| POST | `/api/sync` | Trigger a sync; returns the `sync_log` row |
| GET  | `/api/sync/status` | Result of the last sync |

## Implementation steps
1. **Scaffold:** backend with uv, frontend with Vite, `.gitignore` (excluding `.env` and `*.db`), `.env.example`.
2. **`auth.py`:** token exchange, in-memory cache, refresh before expiry. On a 400 error (`TOKEN_EXPIRED` or `INVALID_REFRESH_TOKEN`), raise a clear error.
3. **`boostcamp.py`:** fetch history and upsert `raw_sessions`.
4. **`db.py`:** schema creation.
5. **`normalize.py`:** apply the field rules, lift mapping and Brzycki formula above.
6. **Tests.** Build the fixture from the user's real response and strip out `user_id`. Assert that:
   - 2026-11-24 `Deadlift (Barbell)` last set → 125 kg × 4
   - 2025-11-17 `Squat (Barbell)` last set → 92.5 kg × 7, e1RM ≈ 111 kg
   - skipped sets are excluded, and `alternatives` are ignored
   - variation exercises get `lift = NULL` but still add to volume
   - weekly totals equal the sum of their sessions
7. **`stats.py` and `api.py`:** implement the endpoints above.
8. **`scheduler.py`:** sync on startup, then every `SYNC_INTERVAL_HOURS` (default 6).
9. **Frontend:**
   - PR cards for each lift
   - e1RM trend line chart
   - weekly volume stacked bar chart
   - sessions table with a detail drawer
   - "Sync now" button and last-sync time
10. **Docker:** multi-stage Dockerfile (Node build stage, then Python runtime) and docker-compose. Write a README covering token setup.

## Onboarding & profile
- On first load the SPA calls `GET /api/profile`. While `onboarded` is false it shows a 4-step wizard (about you, body & units, Boostcamp, lifts) instead of the dashboard. Each step saves with `PUT /api/profile`, and the last one sends `complete: true`.
- With sex "other", the user picks the DOTS formula. `/api/total` uses `profile.dots_formula` unless `?sex=` is given.
- Units are display-only. The API stays in kg, and the frontend converts with helpers in `api.ts` (`kg()`, `wr()`, `toKg()`).
- Credentials: `.env` wins. Otherwise they are stored encrypted. The scheduler always runs and skips while unconfigured. Rotated refresh tokens are persisted.

## Environment (`.env.example`)
```
BOOSTCAMP_REFRESH_TOKEN=
FIREBASE_API_KEY=
TIMEZONE_OFFSET=1
SYNC_INTERVAL_HOURS=6
DATABASE_PATH=/data/weightroom.db
WEIGHTROOM_SECRET=
```

## Notes and risks
- This is an unofficial API and may change. Keeping the raw JSON means the data can be re-parsed later.
- The refresh token can be revoked, for example by logging out everywhere. If that happens, copy it again from DevTools.
- The sample data includes the user's email and user_id. Never put real tokens or personal data in fixtures or commits.
