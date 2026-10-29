# Stay plan baseline (Phase 1 of 11: ground truth)

**Date:** 2026-10-29 · **Commit read:** `ab91a87` (backend `main`) and `c6f34c1` (app `main`) · **Branch:** `phase-1-ground-truth`
**What this is:** what exists, what was proven to work, what could not be measured, and what should change in the plan. No application code, settings, workflows or migrations were changed. The only files added are this one and `GAP_TRIAGE.md`.
**Names that differ from the prompt:** none of the file, function and class names in Part A differed from the code. Where the prompt's wording is slightly off it is noted in the row (for example the route is `mark-paid`, the method is `mark_paid`). `docs/` does not exist at the backend repo root, so both documents live in `backend/docs/` next to `AFTER-F5.md`.

## Summary for the founder

1. **Part A (reading the code): all ten items answered with line evidence.** Nine confirmed as the prompt states; A2 found extra ways a booking can become paid, and A1 and A8 produced findings that change Phases 5 and 6 (see "Surprises").
2. **Part B:** B1 green on all three workflows, but a fourth, the backup workflow, **cannot start** (invalid file). B2 stopped as the prompt requires (no secrets exist). B3 and the staging half of B4 could not be run (see below).
3. **Part C: mostly blocked.** The staging web service wakes in 42.4 s, but **the staging database is unreachable today**, so no database-based measurement, no load test and no payment test was possible. Nothing below is estimated or invented; blocked items say what is needed.
4. **Part D:** `GAP_TRIAGE.md` classifies all 119 open gaps and adds 12 new ones.

## Part A. Code facts

Verdicts: **Confirmed**, **Refuted**, **Partly** (with the difference stated).

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| A1 | `expire_if_lapsed` and `expire_stale` fail a payment attempt older than 15 minutes | **Partly.** A payment is failed when its *hold has lapsed*. With a live hold that is `held_until <= now` (15 minutes after the order, `BED_HOLD_MINUTES = 15`, `holds.py:26`, set at `payments/views.py:267`). The "older than 15 minutes" rule applies only when the bed has no recorded holder, or there is no bed (`holds.py:44-51`). If another payment holds the bed, the payment counts as lapsed at once (`holds.py:48-49`). | `holds.py:44-51, 98-110, 125-147`. **Callers of `expire_if_lapsed`:** `payments/views.py:354` (create UPI intent), `:421` (create card checkout), `:456` (status poll, after a read-only `peek_hold_has_lapsed` at `:455`), and `holds.py:133` (inside `expire_stale`). **Callers of `expire_stale`:** `cleanup_expired.py:60` and the older `expire_stale_holds.py:27` command. **Would a payment not tied to a bed hold be affected? Yes.** For such a payment (no usable bed, or a bed whose `hold_payment_id` is empty) the age rule fails it 15 minutes after creation, on the first status poll or cleanup run after that. This is the basis of G1-03. |
| A2 | A booking becomes paid in exactly three places: `confirm_payment`, `BookingViewSet.verify`, `mark_paid`; does `verify` have a status guard? | **Partly: those three are the live API paths, but there are two more writers.** `verify` has **no status guard**. | `confirm.py:127`; `bookings/views.py:161` (verify) and `:181` (mark_paid). `verify` checks only `payment_mode == 'online'` (`:152`); a cancelled, rejected or already paid booking can be set to paid again (G1-02). `mark_paid` guards (`:172`, pending or confirmed only). **Fourth/fifth places:** Django admin `BookingAdmin` (`bookings/admin.py`, no read-only fields, so staff can set `status` to paid) and `seed_loadtest.py:137` (staging tool). `Payment.status = SUCCESS` is set only in `confirm.py:123`. |
| A3 | `BookingCreateSerializer`: AllowAny, student may be null, room optional | **Confirmed** | `AllowAny` for `create`: `bookings/views.py:82-85`. `student` is nullable: `bookings/models.py:39-44`; it is not a serializer field and is filled from `request.user` only when signed in (`serializers.py:80-84`). `room` optional: model `:30` (`null=True`), serializer `:53`. `amount` is also optional and **client-supplied** (`:49`, `:61`) (G1-04). |
| A4 | No booking cancel endpoint; cross-check T3-04 | **Confirmed** | `bookings/urls.py:12-14` plus the router: the only routes are list, create, retrieve, `approve`, `reject`, `verify`, `mark-paid`, `my/` and `my/<id>/`; `http_method_names` has no delete and `update` is closed (`views.py:62, 69-80`). Nothing in `apps/` ever sets `status = 'cancelled'` (G1-11). KNOWN_GAPS T3-04 is correct. |
| A5 | The webhook handler hard-codes method CARD | **Confirmed** | `payments/views.py:607`: `method=PaymentAttempt.Method.CARD,  # Best guess; the webhook lacks method info`. (The card verify call at `:521` also passes CARD; that one is the card flow.) |
| A6 | Cleanup cron has only PYTHON_VERSION, SECRET_KEY, ALLOWED_HOSTS, DATABASE_URL; what it lacks | **Confirmed** | `render.yaml:128-146` (`plan: starter`, `schedule: "*/5 * * * *"`). **Lacks for email work:** `EMAIL_API_PROVIDER`, `EMAIL_API_KEY`, `DEFAULT_FROM_EMAIL` (and `EMAIL_TIMEOUT` if tuned). **Lacks for Razorpay work:** `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` (webhook secret only if it ever verifies webhooks; it does not today). **Also lacks:** `SENTRY_DSN`/`SENTRY_ENVIRONMENT` (cron errors invisible), `APP_ENV`, and for push (D4) the Firebase credentials, which do not exist yet. Also: the cron exists only in this reference file (F3-09, L4-05). |
| A7 | Tenancy startup check uses an explicit app list | **Confirmed** | `BUSINESS_APP_LABELS` set in `apps/core/tenancy/checks.py:12-20`: `hostels, rooms, bookings, residents, notices, payments, media_uploads` (re-exported by `apps/core/checks.py`). The check `check_business_models_are_classified` (a Django system check, so it runs at `check`, `runserver` and tests) makes every concrete model in those apps inherit `TenantScopedModel`, `UserScopedModel` or `GlobalModel`. **To add an app:** put its label in that set, and give each model one of the three bases with `OWNER_LOOKUP` / `USER_LOOKUP` declared (otherwise warnings `core.W001`/`W002`). Note: `owners`, `dashboard`, `core` and `otp_auth` are **not** in the list. |
| A8 | What do Booking.amount and the paid Payment.amount cover? | **Answered: one month's rent only, nothing else.** | `Payment.amount = Room.price_per_month`, the whole monthly price (`payments/views.py:148, 263`; model help text `payments/models.py:71`). There is **no deposit, token advance or fee** anywhere in the Room, Hostel, Booking or Payment models (searched for deposit, advance, security, token). `Booking.amount` is a separate optional number that the client sends and nobody validates (`serializers.py:49,61`); it feeds only the owner dashboard's offline revenue (`dashboard/views.py:334-335`) and display. For an online booking it normally equals nothing the server computed. |
| A9 | CACHES LocMem; throttles anon 60/min and user 120/min on that cache; NUM_PROXIES from TRUSTED_PROXY_COUNT default 1; CONN_MAX_AGE 60 | **Confirmed (all four)** | `config/settings.py:205` (`LocMemCache`), `:279-284` (rates; `THROTTLE_ANON`/`THROTTLE_USER` can override), `:296` (`NUM_PROXIES` from `TRUSTED_PROXY_COUNT`, default 1), `:162` (`DB_CONN_MAX_AGE` default 60, passed at `:150`). Consequence: every counter is per worker process, so the real limit per address is about 60/min **times the number of workers**, and a restart resets it. |
| A10 | gunicorn: gthread, WEB_CONCURRENCY default 2, GUNICORN_THREADS default 4; compute connections vs pooler limit | **Confirmed; computed below** | `gunicorn.conf.py` (`worker_class = 'gthread'`, `workers = ... 'WEB_CONCURRENCY', '2'`, `threads = ... 'GUNICORN_THREADS', '4'`, `preload_app` off). |

### A10 arithmetic

Django keeps one connection per thread. One instance = 2 workers x 4 threads = **8 connections at most**. `CONN_MAX_AGE = 60` only closes an idle connection when its thread next handles a request, so under steady traffic all 8 stay open.

| Scenario | Connections | Against the 15-slot session pooler (AFTER-F5.md) |
|---|---|---|
| 1 web instance | 8 | fits |
| + cleanup cron (1) + `migrate` during a deploy (1) + a person at `/admin/` or a script (1 to 2) | 11 to 12 | fits with 3 to 4 spare (matches AFTER-F5.md) |
| **2 web instances** | **16** (+3 to 4 = 19 to 20) | **does not fit** |
| A deploy where the old and new instance briefly overlap | up to 16 | **can exceed 15** (unmeasured) |
| Largest count of instances that fit | (15 - 4) / 8 = **1** | |

For reference, LOADTEST.md quotes Supabase Pro at 60 direct and 200 pooler connections (from the pricing page, unverified here). By the same arithmetic that allows about (200 - 4) / 8 = 24 instances at 8 threads each. Lowering `GUNICORN_THREADS` is the other lever. The requirement "two instances behave exactly like one" (S1) is therefore **not met today on the free pooler** (G1-08, F5-08).

## Part B. Existing tooling

### B1. CI on `main`

| Repo | Workflow | Result | Commit | When |
|---|---|---|---|---|
| backend | `backend` | **success** | `ab91a87` | 2026-10-19 |
| backend | `admin` | **success** | `ab91a87` | 2026-10-19 |
| app | `app` | **success** | `c6f34c1` | 2026-10-19 |
| backend | `backup` (`.github/workflows/backup.yml`) | **FAILURE on every push** (runs 39227131826, 39227677174) | `ab91a87` | 2026-10-19 |
| backend | `pages-build-deployment` | success (GitHub Pages is on, A-05) | | |

**The backup failure is a real bug, not a skipped job.** GitHub says "workflow file issue". `actionlint` (run read-only in Docker) reports `backup.yml:32: could not parse as YAML: mapping values are not allowed in this context`: the line `run: echo "::warning::Backup skipped: BACKUP_DATABASE_URL ..."` is an unquoted value that contains `: `. A workflow that does not parse never runs, including its daily schedule, so **even after the founder adds both secrets, no backup would happen** (G1-01). Not fixed here (workflows are out of scope for Phase 1).

Local re-run of the CI steps on 2026-10-29 (scratch Postgres 16 in Docker, `DEBUG=False`, same environment as `backend.yml`; Python 3.14.3 locally, CI uses 3.13):

| Step | Result |
|---|---|
| `check --deploy --fail-level WARNING` | no issues (21 silenced) |
| `makemigrations --check --dry-run` | No changes detected |
| `collectstatic --dry-run` | ok |
| OpenAPI schema diff (`--strip-trailing-cr`) | no difference |
| `manage.py test apps utils --noinput` | **392 tests, OK**, 805 s on this laptop (the last green CI run of the whole backend job took 2.8 min) |
| App: `flutter analyze --no-pub` | 0 errors, 10 warnings, 51 infos = **61** (limit 64; AGENTS says 64 at its last count) |
| App: `flutter test --no-pub` | **307 passed**, 0 failed |

A first run on the same machine was discarded: it ran while another run used the same scratch database, and it read `DEBUG=True` from the laptop's `backend/.env` (python-decouple reads that file; `unset DEBUG` does not override it). Anyone running tests locally must set `DEBUG=False` and the database variables explicitly, or they use the `.env` values, which point at **production** (F3-02).

Working-tree notes (not mine, not committed): backend `backend/schema.yml` shows as modified but differs from `HEAD` only in line endings; `backend/start-backend.ps1` is untracked. App repo: five generated plugin-registrant files are modified (they change when Flutter regenerates them).

### B2. Backups (read, then stopped as instructed)

| Item | Finding |
|---|---|
| Secrets the founder must add | Repo secrets `BACKUP_DATABASE_URL` (the Supabase **session pooler** URL) and `BACKUP_AGE_PUBLIC_KEY` (starts with `age1`). `gh secret list` shows **no secrets at all** today. |
| Key pair | Made once with the Docker command in `RELEASE.md` section 3. The private half (`AGE-SECRET-KEY-...`) must be kept in a password manager **and** an offline copy; it never goes to GitHub or chat. |
| Where the file ends up | A workflow artifact `hh-backup-<run id>` on GitHub for **30 days** (`retention-days: 30`). That is outside Render and Supabase, as required, but: it expires after 30 days; on a public repository any GitHub user can download it (it is age-encrypted, so unreadable without the private key); and it sits with the same GitHub account as the code. A second durable copy somewhere else is advisable. This is a proposal for Phase 2, not done. |
| Blocker found | `backup.yml` does not parse (G1-01), so adding the secrets alone does not start backups. |
| Run, restore, `verify_restore.py` | **Not run.** The prompt says to stop when secrets are missing. The only earlier rehearsal is the laptop-to-laptop run recorded in `RELEASE.md` (2026-10-19). |

### B3. Staging payment test (`PAYMENT_TEST.md`): **not run**

Prerequisites that are not met (from `KNOWN_GAPS.md`, and today's probe):
1. The staging database is unreachable (Part C1), so no sign-up, booking or payment can work.
2. No email provider on staging (L4-02): a student cannot sign up with an email code.
3. No Razorpay TEST keys or webhook on staging (L4-04). I cannot read the Render environment, so this is the register's statement, not something I verified.
4. Staging has no sample data (F3-03).

So there are **no results** for success, duplicate webhook (`replay_webhook.py`) or failure; none are claimed.

### B4. `cleanup_expired --dry-run`

| Target | Result |
|---|---|
| **Staging** | **Not run**: needs the staging `DATABASE_URL` (not available to me) and a reachable staging database. |
| Scratch Postgres 16 (migrated, empty) | `holds: {payments_expired: 0, beds_freed: 0}`, `otp_records: 0`, `webhook_events: 0`, `tokens: skipped in a dry run`, exit 0. This proves the command starts and runs on a clean schema; it says nothing about real volumes. |

What it would purge when there is data (from `cleanup_expired.py` and `holds.py`): open payments whose bed hold lapsed (they become FAILED), beds whose `held_until` has passed (hold cleared), OTP records expired for more than 1 day, Razorpay webhook event ids older than 30 days (deleted 1,000 rows at a time), and expired JWT blacklist rows (skipped in a dry run).

## Part C. Measurements

**Plans in use (what the files say; I could not open either dashboard to confirm):** Render staging `plan: free`, region Singapore (`render.yaml`); the cron is declared `plan: starter`. Supabase staging project `Hostel-hunt-staging`, free plan per KNOWN_GAPS (ap-southeast-1). **The free plans are not representative of launch.**

### C1. Cold start and wake time (staging, public GET only)

| Probe | Result |
|---|---|
| First `GET /healthz` after idle (2026-10-29 12:19 UTC) | **200 after 42.4 s** (DNS 0.04 s, TLS done 0.10 s, then 42.3 s waiting for the service to wake) |
| Warm `GET /healthz`, 8 requests | 0.088 to 0.222 s, median 0.117 s (`"env": "staging"`) |

The 42.4 s wake is the platform waking the web process, matching the register's "30 to 60 seconds" (P-05). It happens after every 15 minutes without traffic.

### C2 to C5: blocked by the staging database

| Probe (2026-10-29, 12:20 and 14:16 UTC) | Result |
|---|---|
| `GET /readyz` x 8 | **503 after 15.2 s each** (body `{"status":"unavailable"}`) |
| `GET /api/v1/hostels/` x 8 | **500 after about 15.2 s each** |
| `GET /api/v1/cities/` x 7 | **500 after about 15.2 s each** |
| Same calls at 14:16 UTC | no answer within 30 s |

`/healthz` never touches the database; `/readyz` runs `SELECT 1`. A 15-second failure that repeats means the web service cannot connect to its database. KNOWN_GAPS (2026-10-18) listed staging as healthy, so something changed since. The most likely cause is that the free Supabase project paused after a week of inactivity (X-07; last known staging activity 2026-10-19). **This is a hypothesis; I cannot see the dashboard.** Founder action: open `Hostel-hunt-staging` in Supabase and restore the project if it is paused (G1-12).

| Item | Status | What is needed |
|---|---|---|
| C2 database round trip (`db_ms / db_queries` from `hh.request` lines, GET `/hostels/` and dashboard activity) | **Not measurable.** There is no Render log access from here, and the database is unreachable anyway. The decision rule (40 ms or more matters, under 15 ms does not; AFTER-F5.md) **cannot be applied yet.** | A reachable staging database, and about 20 `hh.request` log lines per route pasted from the Render dashboard (they hold no personal data). |
| C3 ten most expensive queries (`pg_stat_statements`) | **Not possible.** F2-03 says it is not confirmed enabled, and there is no database access. | Founder enables the extension in Supabase; then one query from the SQL editor. |
| C4 smoke (5 users) and medium (50 users), Pass B | **Not run.** Needs the seed (F3-03: staging is empty), a reachable database, `LOADTEST_PASSWORD`, and the two Pass B variables `THROTTLE_ANON` / `THROTTLE_USER` set on the staging service. The tool refuses anything but staging. | See `LOADTEST.md` section "One-time setup". |
| C4 peak CPU, memory, database connections from dashboards | **Not available** (no dashboard access). | Founder pastes the Render Metrics and Supabase Reports numbers. |
| C5 login rush (30 users) | **Not run** (same prerequisites). Local facts only: below. | |

**C5 local facts (not a server measurement).** Django 5.2.15 is installed here and `PASSWORD_HASHERS` is not overridden anywhere in `config/` or `apps/`, so passwords use `PBKDF2PasswordHasher.iterations = 1,000,000` (read from the installed library). Timing the same primitive (PBKDF2-HMAC-SHA256) directly on this laptop, 5 runs each, machine otherwise idle: **1,000,000 rounds: median 1.13 s (range 1.00 to 1.61 s); 600,000 rounds: median 0.94 s (range 0.88 to 1.08 s).** That is one password check, single-threaded; it matches the register's "about 1.6 s" order of magnitude (this laptop is a little faster, and the sample is small and noisy). The 600,000 figure saved only about 17% here although the rounds drop 40%, so do not rely on a saving until it is measured on the real server. The number of rounds was **not changed**, as instructed. Options for the later phase, with their trade-offs: keep the rounds and add instance CPU or a login queue; lower toward OWASP's 600,000 for PBKDF2-SHA256 (hashes upgrade on next login; saving unproven, see above); move to a different hasher (needs a new dependency); or reduce how many logins happen at once (the app keeps the login, so rushes come from new installs). The founder decides after a real login-rush run.

### Latency table (what was actually measured)

| Endpoint | Where | n | Result |
|---|---|---|---|
| `/healthz`, first request (staging asleep) | staging, from this laptop | 1 | 42.4 s |
| `/healthz`, warm | staging | 8 | 0.088 to 0.222 s, median 0.117 s |
| `/readyz` | staging | 8 | 503 at about 15.2 s |
| `GET /api/v1/hostels/` | staging | 8 | 500 at about 15.2 s |
| `GET /api/v1/cities/` | staging | 7 | 500 at about 15.2 s |
| `GET /api/v1/hostels/` (200 answers, 1 to 5 queries depending on the test) | **local scratch DB, no network distance** | 57 | server time median 29.0 ms (21 to 156), `db_ms` median 7.1, median 2.5 ms per query (the clean test run's own `hh.request` lines; code cost only) |
| `GET /api/v1/dashboard/activity/` (2 queries) | local scratch DB | 2 | 15.6 ms, `db_ms` 6.5, 3.2 ms per query |

The two local rows are **not** evidence about staging or production distance: the database was on the same machine.

## Surprises that should change the plan

| # | Finding | Why it matters | Phase |
|---|---|---|---|
| 1 | **Staging's database is unreachable** (G1-12). | Staging cannot be used for any payment test, seed or load test until restored. Phase 2 must start with it. If it was paused, it will pause again after a week of silence unless it is paid for or pinged (X-07). | 2 |
| 2 | **The backup workflow cannot run** (G1-01). | The register says only the secrets are missing; the file is also broken. | 2 |
| 3 | **`confirm_payment` and the hold logic cannot be reused as they are for rent** (G1-03). A rent payment would be failed after 15 minutes by the poll or cleanup, flagged "bed already taken" at confirmation (`confirm.py:98-101`), and `create-order` refuses paid bookings (`views.py:137`). | E6/E7 say rent never uses holds; the code assumes every payment has a hold. Phase 6 needs a payment kind (new field) or separate functions, plus tests for all three. | 6 |
| 4 | **`verify` has no status guard** (G1-02). | E2 says a stay and its dues are created in the same transaction for all three paid paths. A repeated or late call to `verify` would create them twice unless Phase 5 adds a guard (and idempotency). | 5 |
| 5 | **Beds are never freed, and `Room.available_beds` is never updated** (L4-12, G1-10); **nothing ever cancels a booking** (G1-11). | The stay-end flow must define one source of truth for availability. | Stay phases |
| 6 | **`Booking.amount` is client-supplied** (A8, G1-04) while `Payment.amount` is one month's rent. | Stay and due amounts must come from the room price, never from `Booking.amount`. There is no deposit in the data model at all, so if a deposit is wanted it is a new concept. | 5 |
| 7 | **Two web instances do not fit the 15-slot pooler** (A10, G1-08). | Scaling out needs Supabase Pro (or fewer threads) first. | 3 |
| 8 | **Wake time is 42 s** (C1). | Real users on free hosting would hit this after every quiet 15 minutes; paid always-on hosting is a launch requirement in practice, and the paid cron is needed anyway (L4-05). | 2 |
| 9 | **The local `.env` silently overrides `DEBUG`, and points at production** (F3-02). | Every local test or script must pass its own database and `DEBUG` values; one mistake touches live data. | 2 |
| 10 | The cron job has none of the variables that email, Razorpay or push work needs (A6, G1-05). | Each later phase that adds cron work must also add its variables to `render.yaml` and the Render dashboard (they drift, F3-09). | each |

## Not verified in this phase

- Anything that needs the Render or Supabase dashboards (plans, CPU, memory, connections, logs, `xff_hops`, `pg_stat_statements`).
- Production (not touched; the prompt allows production reads only in Phases 2 and 11).
- Razorpay behaviour (no keys, no staging database).
- Python 3.13 (tests ran on 3.14.3).
