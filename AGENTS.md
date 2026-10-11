# Hostel Hunt backend

Django 5.2 (LTS) + Django REST Framework API for the Hostel Hunt mobile app. Python 3.13 (`backend/.python-version`).
Everything below was checked against the code or run on 2026-10-10; things not run are listed under "Not verified".

## Layout
- `backend/` – the Django project (`config/` settings and URLs, `apps/` feature apps, `utils/`). `manage.py` is here; run all commands from this folder.
- `hostel-hunt-admin-next/` – Next.js owner admin. Separate project with its own docs; not covered here.
- `render.yaml` – reference for the Render web service (copy values into the dashboard by hand). Nothing in the Django code depends on Render.
- `DEPLOY.md` – deploy, verify and rollback steps.

## Architecture
- `apps/owners` – custom user model `owners.Owner`; OTP, register, login, reset-password, `auth/me` under `/api/v1/auth/`.
- `apps/otp_auth` – separate email-OTP endpoints under `/api/v1/send/`, `/verify/`.
- `apps/hostels`, `rooms`, `bookings`, `payments` (Razorpay), `dashboard`, `residents`, `notices`, `media_uploads` (stores image URLs only; the backend has no Cloudinary code or settings).
- `apps/core` – tenant scoping (`core/tenancy`), `health.py` (`/healthz`, `/readyz`), `dev.py` (the OTP-exposure switch), `async_utils.py` (in-process thread pool for email sends).
- Auth: JWT (SimpleJWT), 30-minute access and 30-day refresh by default. DRF default permission is `IsAuthenticated`. Throttles: anon 60/min, user 120/min, otp 5/min, counted per worker process (no shared cache).
- Database: `USE_DB` unset or `supabase` -> Postgres from `DATABASE_URL`; `local` -> `LOCAL_DATABASE_URL`; `sqlite` -> `backend/db.sqlite3`. **The default is the remote database, so always set `USE_DB` for local work and tests.**
- Static files: WhiteNoise serves `backend/staticfiles/` (created by `collectstatic`). Uploaded media is served only when `DEBUG` is on.
- Health: `/healthz` answers from a middleware with no database, host or HTTPS checks. `/readyz` runs `SELECT 1` and returns 503 on failure.

## Commands (PowerShell; each was run in a clean copy of the committed code)
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:USE_DB='sqlite'; $env:DEBUG='True'      # local development
python manage.py migrate
python manage.py runserver 0.0.0.0:8000      # /healthz and /readyz answer; /api/v1/debug-logs/ is 404

$env:USE_DB='sqlite'
python manage.py test apps utils             # 89 tests, all pass
python manage.py makemigrations --check --dry-run   # "No changes detected"

# production-style check (set SECRET_KEY, ALLOWED_HOSTS, DATABASE_URL first, DEBUG unset)
python manage.py check --deploy              # one expected warning: SECURE_HSTS_SECONDS
python manage.py collectstatic --noinput
```
Production start command (Linux): `gunicorn config.wsgi:application -c gunicorn.conf.py`.

## Environment variables
Names and defaults are in `backend/.env.example` (a test fails if a variable read in `settings.py` is missing there).
Required when `DEBUG` is off: `SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL` – the server refuses to start and names the missing ones.
Also used: `DEBUG`, `USE_DB`, `LOCAL_DATABASE_URL`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `TRUST_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `JWT_ACCESS_MINUTES`, `JWT_REFRESH_DAYS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`, `TWILIO_*`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `EXPOSE_DEV_OTP`, `DB_CONN_MAX_AGE`, `DJANGO_LOG_LEVEL`, `PORT`, `WEB_CONCURRENCY`, `GUNICORN_*`.
Never print, log or commit secret values; refer to variables by name.

## Rules for changes
- Settings come from environment variables only. No host-specific code.
- OTP values may appear in a response or log only when `DEBUG` and `EXPOSE_DEV_OTP` are both on. Provider/SMTP error text stays in server logs.
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
