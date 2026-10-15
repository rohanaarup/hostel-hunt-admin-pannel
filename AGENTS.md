# Hostel Hunt backend

Django 5.2 (LTS) + Django REST Framework API for the Hostel Hunt mobile app. Python 3.13 (`backend/.python-version`).
Everything below was checked against the code or run on 2026-10-10; things not run are listed under "Not verified".

## Layout
- `backend/` – the Django project (`config/` settings and URLs, `apps/` feature apps, `utils/`). `manage.py` is here; run all commands from this folder.
- `hostel-hunt-admin-next/` – Next.js owner admin. Separate project with its own docs; not covered here.
- `render.yaml` – reference for the Render web service (copy values into the dashboard by hand). Nothing in the Django code depends on Render.
- `DEPLOY.md` – deploy, verify and rollback steps.

## Architecture
- `apps/owners` – custom user model `owners.Owner`; OTP, register, login, reset-password under `/api/v1/auth/`. `auth/me/` supports GET and PATCH (display name, gender, date of birth, null clears the last two; any other field is refused with a 400 naming it; email and phone changes are refused until OTP verification exists). Errors from DRF itself (401, 403, 404, 405, 429) keep their `{detail}` body; the app's error reader depends on both shapes. `dashboard/student/stats/` counts only bookings linked to the user (never matched by name). The wishlist (saved hostels): `GET /wishlist/` (paginated, active hostels only, rows carry what a card needs), `POST /wishlist/` (idempotent: 201 then 200), `GET /wishlist/ids/` (just the hostel ids), `DELETE /wishlist/hostel/<hostel id>/` (safe to repeat) and the older `DELETE /wishlist/<row id>/`. Search (`?search=`) also matches `LocalityAlias` spellings, and `match_key` keeps Telugu/Hindi letters, so staff can add aliases in those scripts. `POST /bookings/` fills a blank student name and phone from the signed-in user. `auth/me/photo/` uploads a profile photo to Cloudinary (unsigned preset) and stores its URL; it needs `CLOUDINARY_CLOUD_NAME` and `CLOUDINARY_UPLOAD_PRESET`.
- `apps/otp_auth` – separate email-OTP endpoints under `/api/v1/send/`, `/verify/`.
- `apps/hostels`, `rooms`, `bookings`, `payments` (Razorpay), `dashboard`, `residents`, `notices`, `media_uploads` (stores image URLs only; the backend has no Cloudinary code or settings).
- `apps/core` – tenant scoping (`core/tenancy`), `health.py` (`/healthz`, `/readyz`), `observability.py` (request id and the one-JSON-line-per-request log), `sentry_config.py` and `privacy.py` (Sentry setup, scrubbing, masking), `dev.py` (the OTP-exposure switch), `async_utils.py` (in-process thread pool for email sends).
- Auth: JWT (SimpleJWT), 30-minute access and 30-day refresh by default. DRF default permission is `IsAuthenticated`. Throttles: anon 60/min, user 120/min, otp 5/min, counted per worker process (no shared cache).
- Database: `USE_DB` unset or `supabase` -> Postgres from `DATABASE_URL`; `local` -> `LOCAL_DATABASE_URL`; `sqlite` -> `backend/db.sqlite3`. **The default is the remote database, so always set `USE_DB` for local work and tests.**
- Static files: WhiteNoise serves `backend/staticfiles/` (created by `collectstatic`). Uploaded media is served only when `DEBUG` is on.
- Health: `/healthz` answers from a middleware with no database, host or HTTPS checks. `/readyz` runs `SELECT 1` and returns 503 on failure.
- Observability: every request except `/healthz` writes one JSON line to stdout (logger `hh.request`; no paths, queries, headers or bodies). Sentry runs only when `SENTRY_DSN` is set. See `backend/docs/observability.md`.

## Commands (PowerShell; each was run in a clean copy of the committed code)
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:USE_DB='sqlite'; $env:DEBUG='True'      # local development
python manage.py migrate
python manage.py runserver 0.0.0.0:8000      # /healthz and /readyz answer; /api/v1/debug-logs/ is 404

$env:USE_DB='sqlite'
python manage.py test apps utils             # 136 tests, all pass
python manage.py makemigrations --check --dry-run   # "No changes detected"
python manage.py spectacular --file schema.yml      # regenerate the OpenAPI schema after an API change

# production-style check (set SECRET_KEY, ALLOWED_HOSTS, DATABASE_URL first, DEBUG unset)
python manage.py check --deploy              # one expected warning: SECURE_HSTS_SECONDS
python manage.py collectstatic --noinput
```
Staging only: `APP_ENV=staging python manage.py seed_staging` loads 3 sample hostels (refuses elsewhere).
Safe Sentry test (needs `SENTRY_DSN`; use `SENTRY_ENVIRONMENT=test`): `python manage.py sentry_test`.
Production start command (Linux): `gunicorn config.wsgi:application -c gunicorn.conf.py`.

## Environment variables
Names and defaults are in `backend/.env.example` (a test fails if a variable read in `settings.py` is missing there).
Required when `DEBUG` is off: `SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL` – the server refuses to start and names the missing ones.
Also used: `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_UPLOAD_PRESET`, `APP_ENV`, `DEBUG`, `USE_DB`, `LOCAL_DATABASE_URL`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `TRUST_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `JWT_ACCESS_MINUTES`, `JWT_REFRESH_DAYS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`, `TWILIO_*`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `EXPOSE_DEV_OTP`, `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_RELEASE`, `GIT_COMMIT`, `SENTRY_TRACES_SAMPLE_RATE`, `GUNICORN_ACCESSLOG`, `DB_CONN_MAX_AGE`, `DJANGO_LOG_LEVEL`, `PORT`, `WEB_CONCURRENCY`, `GUNICORN_*`.
Never print, log or commit secret values; refer to variables by name.

## Change pipeline
- CI (`.github/workflows/backend.yml`, check name `backend / test`) runs on every push and PR: pinned install, `check --deploy` (warnings fail), `makemigrations --check`, `collectstatic`, the schema diff, then all tests on Postgres with DEBUG off.
- `backend/schema.yml` is the committed OpenAPI schema; an API change must regenerate it in the same PR.
- `backend/contract/endpoints.txt` lists every endpoint the app and admin call. `apps/core/test_contract.py` fails on a renamed route, a wrong method, or an `expected-fail` marker that now passes. Remove the marker when you fix the route.
- `backend/contract/fixtures/hostels_list.json` is a sample of the real list response; regenerate with `UPDATE_CONTRACT_FIXTURES=1 python manage.py test apps.core.test_contract.HostelListFixtureTests` and copy it to the app repo's `test/fixtures/`.
- Places: `City`, `Locality` and `LocalityAlias` (apps/hostels/models.py) are staff-managed in Django admin. `Hostel.city_ref` / `locality_ref` link to them; the old `city` / `locality` / `state` text columns are kept for one release and kept in step. Case, spaces, hyphens, dots and accents never create a second place (`match_key` in apps/hostels/locations.py); a genuinely different spelling is added once as an alias.
- `GET /hostels/` is the public list, the same for everyone whether or not a token is sent: active hostels, parameters `city`, `locality` (name, slug, alias or id; legacy values still work), `search` (name, locality, address; 2+ characters), `amenity`, `gender_type`, `page`, `page_size` (default 10, maximum 50). Newest first, then id. `?scope=mine` is the signed-in owner's own hostels (including inactive); `?scope=all` is staff only. Owners write through the same routes as before.
- `GET /cities/` and `GET /cities/{slug}/localities/`: active entries that have an active hostel, with counts; `?include_empty=true` lists every active entry (the admin wizard). `GET /hostels/localities/` is kept for older apps.
- `python manage.py deactivate_test_hostels` (staging only): dry run by default; `--apply` hides test-looking hostels and writes an undo file; `--restore <file>` reverses it.
- CI also builds the admin site (`.github/workflows/admin.yml`, check `admin / build`: `npm ci`, `tsc --noEmit`, `npm run build`).
- Swagger UI (`/api/docs/`) and `/api/schema/` exist only when DEBUG is on or `APP_ENV=staging`.

## Rules for changes
- Settings come from environment variables only. No host-specific code.
- OTP values may appear in a response or log only when `DEBUG` and `EXPOSE_DEV_OTP` are both on. Provider/SMTP error text stays in server logs.
- Logs and error reports must not contain emails, phone numbers, tokens, OTPs or request bodies. Do not log identifiers; masking in `privacy.py` is only a safety net.
- No debug endpoints. Errors return a message and the right HTTP status, never a traceback.
- `reset_db.py` and `reset_db_auto.py` drop every table; they refuse unless the database host is local and `--i-understand-this-drops-all-tables` is passed.
- Keep what the shipped mobile app uses; add fields and endpoints first, remove later. Every bug fix ships with a test that failed before it.
- Do not change Razorpay payment flow, OTP login or tenant scoping unless the task says so.

## Known gaps
- Twilio SMS is not integrated; phone OTPs fail with 503 outside development.
- gunicorn cannot run on Windows, so the production server settings were not exercised locally; see "Not verified".
- Git history still contains old `db.sqlite3`, `django.log` and `data_dump.json`; they are untracked now but not purged.

## Not verified
- `gunicorn.conf.py` under a real gunicorn process, and the Render build/start/health-check settings (needs a Linux run or a Render deploy).
- Python 3.13 (tests were run on 3.14.3).

## Data safety (T4)
- `/dashboard/stats/` (owner) also returns `total_beds`, `bookings_by_status` and `bookings_by_payment_mode`, counted over ALL the owner's bookings (the bookings list is paged, so the admin must not count one page).
- Media: `file_url` must be an `https://res.cloudinary.com/<CLOUDINARY_CLOUD_NAME>/...` address (any cloud when the variable is unset). Creating or updating a hostel links `media_ids` only for media nobody has claimed yet or that is on the owner's own hostels; other owners' media is skipped, never moved.
- `python manage.py link_legacy_bookings` (staging only; dry run by default, `--apply`, `--restore`): links old bookings with no student account only when the typed phone matches exactly one VERIFIED account. It prints counts only. Unmatched legacy bookings stay visible to the hostel owner and staff only.
