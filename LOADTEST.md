# Load testing Hostel Hunt

Goal: replace guessing about "thousands of users" with a measured number on the server size we plan to pay for.
The target is **200 users active at the same moment** (a generous launch figure for several thousand registered
users). The test also steps past 200 to find where the server stops coping.

**Staging only.** `tools/loadtest/locustfile.py` refuses to start against the production host, against any host that
is not on the staging list, and against any server whose `/healthz` does not say `"env": "staging"`. Overriding that
needs `HH_LOADTEST_ALLOW_PRODUCTION=yes` and prints a warning on every run. Do not.

## What is tested, and what is not

| Share of actions | What a virtual student does | Group in the report |
|---|---|---|
| 45% | Browse: hostel list (city, filter chip, sometimes page 2), localities | `public` |
| 25% | Open a hostel and its rooms | `detail` |
| 10% | Search | `search` |
| 10% | Logged-in reads: profile, saved ids, my bookings | `auth` |
| 3% | Save then unsave a hostel | `write` |
| 3% | Poll a settled payment's status (the app polls every 2.5 s while paying) | `auth` |
| 2% | Request a booking (offline mode, no bed is taken) | `write` |
| 1% | Renew the login token | `auth` |

Each student logs in once when it starts, then pauses 2 to 8 seconds between actions.

Not in the normal mix, on purpose:

* **OTP and email.** Test students log in by password, so no email is sent. Real sign-ups need an email provider
  (L4-02); Brevo's free plan allows 300 sends a day per its help page (whether transactional mail counts towards that is unconfirmed).
* **Razorpay.** We never load-test the provider. `PaymentCreateUser` creates real Razorpay TEST orders at a handful of
  users; run it only after TEST keys exist on staging (L4-04).
* **Photo upload** (limited to 10 an hour) and **webhooks** (use `backend/ops/replay_webhook.py`).
* **Pictures.** They are served by Cloudinary, so this measures the API only.

Other scenarios: `LoginStormUser` (everyone logging in at once; password hashing is the heaviest CPU work),
`stress_shape.py` (steps 50, 100, 200, 300, 400 users).

## One-time setup (you)

1. **Decide the size to test** and put staging on it for the test hours (see "Instance size" below).
2. **Load the test data into the staging database** (staging only; it refuses anything else). From your laptop, in PowerShell:
   ```
   cd "C:\PROJECTS DEV\HH CORE\admin pannel HH\backend"
   $env:APP_ENV = "staging"
   $env:DATABASE_URL = "<staging database URL, copied from the Render staging service; never the production one>"
   $env:LOADTEST_PASSWORD = "<a new password of 12+ characters; keep it, you need it again below>"
   ..\envhh\Scripts\python manage.py migrate
   ..\envhh\Scripts\python manage.py seed_loadtest
   ```
   It makes 300 students (`load0001@example.test` and so on), 40 hostels with rooms and beds and 50 settled payments.
   It refuses unless `APP_ENV=staging`, and refuses if the database holds any user whose email does not end in
   `@example.test`, so pointing it at production by mistake does nothing. Run it again with `--reset-activity` between
   runs to remove the bookings and saved hostels the last run created.
   Close the PowerShell window afterwards so the staging database URL does not stay in your session.
3. **Install the tool** (once):
   ```
   cd "C:\PROJECTS DEV\HH CORE\admin pannel HH\tools\loadtest"
   python -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   ```
4. **For Pass B only**, add two environment variables to the staging service on Render and remove them afterwards:
   `THROTTLE_ANON=100000/min` and `THROTTLE_USER=100000/min`. Why: the server limits public browsing to 60 requests
   a minute per address, and every virtual user shares your computer's address. Without the change you measure the
   limit, not the server.

## Commands

Every command runs from `tools\loadtest`. Set these first in the same window:
```
$env:LOADTEST_PASSWORD = "<the same password>"
$staging = "https://hostel-hunt-admin-pannel.onrender.com"
```

| Run | Command |
|---|---|
| **Smoke** (5 users, 2 min; checks the script and wakes the server) | `.\.venv\Scripts\locust -f locustfile.py StudentUser --headless -u 5 -r 1 --run-time 2m --host $staging --csv ..\..\loadtest-results\smoke` |
| **50 users** | `.\.venv\Scripts\locust -f locustfile.py StudentUser --headless -u 50 -r 5 --run-time 7m --host $staging --csv ..\..\loadtest-results\u50` |
| **200 users** | `.\.venv\Scripts\locust -f locustfile.py StudentUser --headless -u 200 -r 2 --run-time 13m --host $staging --csv ..\..\loadtest-results\u200` |
| **Find the limit** (steps to 400) | `.\.venv\Scripts\locust -f locustfile.py,stress_shape.py StudentUser --headless --host $staging --csv ..\..\loadtest-results\stress` |
| **Login rush** | `.\.venv\Scripts\locust -f locustfile.py LoginStormUser --headless -u 30 -r 5 --run-time 3m --host $staging --csv ..\..\loadtest-results\login` |
| **Payments** (needs Razorpay TEST keys) | `.\.venv\Scripts\locust -f locustfile.py PaymentCreateUser --headless -u 3 -r 1 --run-time 5m --host $staging --csv ..\..\loadtest-results\pay` |

* **Wait for the server to be awake.** Open `$staging/readyz` in a browser first, or let the smoke run do it. The first
  minute after a sleep is not a result (a free instance takes about a minute to wake).
* Ignore the first two minutes of every run (warm-up).
* The run ends with a `=== Thresholds ===` block and `RESULT: PASS` or `FAIL` (exit code 0 or 1). The limits are in
  `thresholds.json`; they are proposals until the first real run and the instance size are known.
* With the web view instead of headless: leave out `--headless -u -r --run-time` and open http://localhost:8089.

### Two passes

* **Pass A, real limits** (no env change): shows what happens when many people share one address (a campus, a mobile
  network). Expect `429` answers; they are counted apart from errors. The response times are not meaningful here.
* **Pass B, limits raised** (step 4 above): measures what the server can do. This is the pass the thresholds judge.

## While a run is going

| Look at | Where | A bad sign |
|---|---|---|
| CPU and memory | Render, the service's Metrics tab | CPU pinned near 100%; memory climbing and not falling |
| Server time per request | Render logs, the `hh.request` JSON lines | `duration_ms` far above `db_ms` means the app is waiting for CPU or a thread |
| Database connections | Supabase dashboard, Reports, Database | Near the pooler limit; log lines mentioning `EMAXCONNSESSION` |
| Database CPU | Same | Sustained high use |
| Workers | Render logs: `Booting worker`, `WORKER TIMEOUT` | Workers restarting during a run |
| Your own computer | Task Manager while Locust runs | Locust above 80% CPU means the result is about your laptop |
| Errors | Sentry | Not set up yet (F2-01); the logs are the only source |

After a run: copy the Render logs for the run's minutes into a text file and summarise them:
```
python tools\loadtest\summarize_log.py render-log.txt --from 2026-10-20T10:05:00Z --to 2026-10-20T10:20:00Z
```
It prints a table per route (count, server time p50/p95/p99, database time, queries per request, status counts,
highest in-flight requests). The lines hold no addresses or personal data, so you can paste the output to me together
with the Locust `RESULT` block and the Render CPU and memory numbers.

## Numbers to record for each run

| Number | Source |
|---|---|
| Date, commit, instance size (Render and Supabase), pass (A or B), users, duration | you |
| Requests per second reached | Locust, Aggregated row |
| p50, p95, p99 per group (`public`, `detail`, `search`, `auth`, `write`, `login`) | Locust CSV |
| Error ratio, 5xx ratio, throttled ratio | Locust `=== Thresholds ===` block |
| Server time vs database time per route; queries per request | `summarize_log.py` |
| Peak CPU %, peak memory | Render Metrics |
| Peak database connections; database CPU | Supabase |
| Highest in-flight requests; worker restarts | `summarize_log.py`; Render logs |
| The largest user count that still passed; which resource ran out first | the stress run |

## Results that mislead (read before believing a number)

* **Cold start.** A sleeping free instance takes about a minute to wake (Render docs). Warm up first and drop minute one.
* **A weak load machine.** If Locust uses more than 80% of your CPU, or Wi-Fi drops packets, the slowness is yours.
  Use a wired connection. Judge the server by its own `duration_ms` from the log; the Locust time also holds your
  distance to Singapore.
* **Shared database compute.** Free Supabase projects share CPU. A bad minute can be a neighbour. Repeat any surprising run.
* **A free instance is not the paid instance.** Results are only worth anything on the size you will pay for.
* **Worker recycling.** Gunicorn restarts a worker about every 1,000 requests, which makes small latency blips.
* **429 is not a crash.** It is the address limit; Pass B removes it.
* **Connection reuse.** Locust reuses connections more than phones do; real phones pay more handshakes.
* **The first run of anything.** The places cache is empty and the database is cold; a second identical run is the fairer one.
* **Test data.** 40 hostels is small. A catalogue of thousands changes the list and search cost; say so when quoting a result.

## Phase 3 measurements

The runs that decide the number of instances (50, 200 and 300 users, a stress run, one versus two instances, a restart
under load, the cache hit rate) are listed in `backend/docs/CAPACITY.md` section 6, with the table to fill. Start the
shared cache first (`REDIS_URL`) or the rate limits and caches will be per worker, as in the earlier runs.

## Instance size

Prices and sizes below come from provider pages read on 2026-10-19 and need re-reading before you pay (they change).

| Choice | What is known |
|---|---|
| Render **Free** | Sleeps after 15 minutes without traffic, about a minute to wake, 750 instance hours a month per workspace, blocks outgoing SMTP ports (render.com/docs/free). Not representative of a paid server. |
| Render **Starter** | 0.5 CPU, 512 MB, $7 a month (a search result about 200 days old; the pricing page itself did not load; confirm). |
| Render **Standard** | 1 CPU, 2 GB, $25 a month (same caveat). Billing is per second, so a test of a few hours costs little. |
| Supabase **Free** | $0, no automatic backups, paused after a week without activity, shared CPU with 500 MB RAM. |
| Supabase **Pro** | From $25 a month, daily backups kept 7 days, Micro compute (1 GB) with 60 direct and 200 pooler connections (supabase.com/pricing). |

The code today runs 2 gunicorn workers with 4 threads each (8 requests at once) and each thread can hold a database
connection, against a pooler of 15 slots on the free plan (F5-08). More workers need more connection headroom first.

## Runs

Add one row per run. Never edit an old row.

| # | Date | Target | Size | Pass | Users | Result | Notes |
|---|---|---|---|---|---|---|---|
| 0 | 2026-10-19 | **This computer** (Django dev server, local Postgres) | n/a | B-like | 8 | Script validated: every endpoint group answered, 0 failures in 1,484 requests | **Not a capacity number.** One finding: a login took 2.5 to 2.9 s with 8 at once; one password check costs about 1.6 s of CPU on this laptop (PBKDF2, 1,000,000 rounds). See "Candidates" below. |

## Candidates to check first on the first real run (hypotheses, not findings)

1. **Login cost.** Django hashes passwords with 1,000,000 PBKDF2 rounds. At about 1.6 s a check on a fast laptop, a
   0.5-CPU server could spend several seconds per login and stall other requests during a rush (launch day, a push
   notification, a morning rush). The app keeps the login, so rushes come from new installs. A lower round count
   (600,000 is the figure OWASP lists for PBKDF2-SHA256) or a different hasher would cut it; hashes upgrade by themselves at the next login.
   Decide after the login-rush run, because it trades some password-guessing resistance for speed.
2. **The per-address limit.** 60 public requests a minute per address, counted separately in each of the 2 workers,
   with every phone on one campus network sharing an address. Pass A shows what that does; the fix (a higher limit,
   or sending the token on public reads so they count per user) is a product decision.
3. **Threads against the connection pool.** 8 simultaneous requests can take 8 of the pooler's slots.
