# Capacity: how many users, how many instances, what to do next

**Written:** 2026-10-29 (Phase 3). **Status of the numbers:** the model and the tooling are built and tested; **the load
measurements in section 6 have NOT been taken**, because they need a reachable staging database (G1-12), a paid instance
size, the seed data and the Render and Supabase dashboards. Every number marked *assumption* is the founder's design target
or a hypothesis and must be replaced by a measurement. Numbers marked *measured here* come from this laptop (a local
Postgres, Redis and pgbouncer in Docker) and show behaviour, not capacity.

> **Provider note (founder rule, 2026-10-29: nothing is permanent).** Render and Supabase are today's host and database, not a commitment. The formulas, the triggers and the measurement protocol below are generic; every pooler limit, plan size, price and free-tier behaviour is an input read from a provider's page on a given date. On another provider (a managed Postgres on AWS or Azure, a VPS on Hostinger, a self-run pgbouncer) replace those inputs and re-measure; the code only needs a Postgres URL, a Redis URL and environment variables.

Design targets (assumptions): **1,000** registered users at launch, **10,000** comfortable, **100,000** reachable by adding
instances and following the triggers in section 5. Peak concurrent users about 3 percent of registered; one request per user
every 5 seconds; about 80 percent of traffic is public reads.

## 1. What Phase 3 changed (the structure, without changing behaviour)

| Before | Now | Where |
|---|---|---|
| Cache in each worker's memory; rate-limit counters per worker | One shared cache (Redis, `REDIS_URL`); rate limits and the places lists live in it, so any number of workers and instances behave like one. Without `REDIS_URL` it is per-process memory, as before. | `apps/core/cache.py`, `cache_backend.py` |
| A Redis outage would add seconds to every request | It cannot: a circuit breaker serves without the cache and retries every 10 s. Rate limits fail open. | `cache_backend.py` |
| Public places lists cached 60 s per worker; a change showed up to a minute later on other workers (F5-04) | Shared, jittered, single-flight; a hostel, room, locality, city or alias write (and the bulk deactivate command) refreshes every worker at once | `places_cache.py` |
| Session pooler only | `DB_POOL_MODE=session` (default) or `transaction` | `db_options.py` |
| Cache headers on four public reads only | plus `s-maxage` for an edge, and `private, no-store` on everything else | `http_cache.py` |
| No way to reject traffic that skips the edge; no client identifier in logs | `EDGE_SHARED_SECRET`; a masked `client` field in every request log line | `edge.py`, `observability.py` |
| One instance, migrations in the build | `render.scale.yaml`: two instances, a Key Value cache, `preDeployCommand` for migrations (not applied) | repo root |

Rate limits were **not** changed: anon 60/min, user 120/min, otp_send 20/min, otp_verify 30/min (a test holds them).
Password hashing rounds were not changed. No payment or booking code was changed.

## 2. The database connection budget

```
connections = instances x WEB_CONCURRENCY x GUNICORN_THREADS
              + cron jobs + deploy migrate + admin sessions
```

Each gunicorn thread keeps its own database connection open between requests (`CONN_MAX_AGE` = 60 s, and Django only
closes an idle one when that thread next serves a request, so under steady traffic every thread holds one). Standing
extras: the clean-up cron (1), `migrate` during a deploy (1), a person or script in `/admin/` (1 to 2). **Rule: stay at or
under 80 percent of the pooler's limit** (`tools/capacity_model.py` checks it).

| Scenario | Connections | Free session pooler (15) | A 60-connection limit | A 200-connection limit |
|---|---|---|---|---|
| 1 instance, 2 workers x 4 threads (today) | 12 | fits (80 percent is 12) | fits | fits |
| 1 instance, 3 x 4 | 16 | **no** | fits | fits |
| 2 instances, 3 x 4 (the proposed target) | 28 | **no** | fits (48 allowed) | fits |
| A deploy where old and new overlap (2 + 2 instances, 3 x 4) | up to 52 | no | no | fits |
| 8 instances, 3 x 4 (the 100,000-user model below) | 100 | no | **no** | fits |

The 60 and 200 are what `LOADTEST.md` read from Supabase's pricing page on 2026-10-19 (*unverified here*); read your
plan's real session-pooler and transaction-pooler limits in the Supabase dashboard before relying on any row.

**With 2 or more instances the free 15-slot pooler is exceeded.** Two ways out (a founder decision; both cost money or
risk):

1. **A larger Supabase plan** (a bigger pooler limit). Simplest; nothing changes in the app.
2. **Transaction-mode pooling** (`DB_POOL_MODE=transaction`, Supabase port 6543). Many app connections share few server
   connections, so the budget stops being the limit. It changes what the app may rely on, described next.

A third lever is fewer threads per worker (`GUNICORN_THREADS`), at the cost of less concurrency per instance.

### Transaction mode: what was built and what was proven

In transaction mode the pooler lends a server connection for **one transaction only**. So the app must not depend on state
that lives on a connection between transactions:

- **Server-side cursors** are turned off (`DISABLE_SERVER_SIDE_CURSORS=True`).
- **Prepared statements**: psycopg 3 prepares a statement after 5 uses; `prepare_threshold` is set to `None`.
- **Statement timeout**: a session-level `SET statement_timeout` is wrong here (it lands on whichever server connection the
  pooler had, and then stays on it for the next client). Instead `SET LOCAL statement_timeout` is sent at the start of
  **every transaction block** and ends with it.
- **Single statements outside a transaction block** (most reads run in autocommit) cannot carry a `SET LOCAL` without extra
  round trips. For those the timeout must be set on the database **role**. `pool_check` reports this as `WARN` until it is.

*Measured here*, with a real pgbouncer 1.26.1 in transaction mode (pool size 2) in front of Postgres 16, running
`manage.py pool_check`:

| Run | select for update in a transaction | parameterised query x 25 | statement_timeout in a transaction | statement_timeout outside one |
|---|---|---|---|---|
| App in `transaction` mode | PASS | PASS | PASS (25s) | WARN (0: nothing covers it yet) |
| Same, plus `ALTER ROLE ... SET statement_timeout = '25s'` | PASS | PASS | PASS | PASS |

And the reason for the `SET LOCAL` design, also measured: after the app ran through that pooler, a **different** client's
`SHOW statement_timeout` read `0` when the app used `SET LOCAL` (transaction mode), but **`25s`** when the app used the
old session-level `SET` (session mode through a transaction pooler). The session `SET` leaks onto other clients' queries.

*Not proven:* Supabase's pooler (Supavisor) itself; only the same four checks run against pgbouncer. Run
`python manage.py pool_check` on staging (point `DATABASE_URL` at the transaction pooler, set `DB_POOL_MODE=transaction`
and `DB_STATEMENT_TIMEOUT_MS=25000`) before relying on it. **Production stays in session mode in this phase.**

**For the role-level timeout** (needed in transaction mode for single statements) use a dedicated role for the web service,
not the role that runs migrations and the cron, because a role-level timeout would also cut a long migration. In the
Supabase SQL editor (names only; you choose the password and put it into `DATABASE_URL` yourself, never into a file):

```
create role hh_web login password '<choose one, store it only in Render>';
grant <the privileges the app needs, see the existing role>;   -- a founder/database task; ask Claude for the exact grants
alter role hh_web set statement_timeout = '25s';
```

Also in transaction mode: run `migrate` over a **session or direct** connection (a separate `MIGRATION_DATABASE_URL`
used only by the pre-deploy command, set in the dashboard; not implemented because it is only needed when this mode is
switched on), because DDL and long statements do not belong behind a transaction pooler. Nothing in the code uses advisory
locks, LISTEN, session-level SETs or temporary tables (searched 2026-10-29); every `select_for_update` runs inside
`transaction.atomic`, which is what `pool_check` exercises.

## 3. Instance size and workers

*Hypothesis, to be decided by measurement:* 1 CPU and 2 GB (`standard` in the blueprint) runs **3 workers x 4 threads**
(gthread). Rule of thumb behind it: about one worker per CPU plus one, memory per worker unknown until measured. If memory
climbs under load, lower `WEB_CONCURRENCY` first; if connections are the limit, lower `GUNICORN_THREADS` or use section 2.
Change `WEB_CONCURRENCY`, `GUNICORN_THREADS` and the connection arithmetic together.

## 4. The capacity model (`tools/capacity_model.py`)

```
peak concurrent users = registered users x 3 percent
requests per second   = peak concurrent users / 5
origin load           = requests per second x (1 - public share x edge hit rate)       public share = 80 percent
instances             = origin load / (0.6 x measured requests per second per instance), never fewer than 2
```

Run it with your numbers: `python tools/capacity_model.py --rps-per-instance <measured> --edge-hit <measured>`.
With the **placeholder** inputs 50 requests per second per instance, an edge hit rate of 0.8, 3 x 4 threads and a
60-connection pooler (every input an assumption):

| Registered | Peak users | Requests/s | Origin requests/s | Instances | DB connections | Fits 80 percent of 60 |
|---|---|---|---|---|---|---|
| 1,000 | 30 | 6.0 | 2.2 | 2 | 28 | yes |
| 10,000 | 300 | 60.0 | 21.6 | 2 | 28 | yes |
| 100,000 | 3,000 | 600.0 | 216.0 | 8 | 100 | **no** |

Reading it: at 1,000 and 10,000 users two instances are already more than the traffic needs, and the minimum of two is
about failover, not load. At 100,000 the origin needs about 8 instances **and** the connections stop fitting a 60-slot pooler,
so transaction pooling (or a much larger pooler) comes before the eighth instance. If the edge hit rate is poor the instance
count rises fast: it is the number most worth measuring.

## 5. Scale triggers (what to do when)

| Watch | Threshold | Then |
|---|---|---|
| Instance CPU (Render Metrics) | **60 percent sustained** | add an instance (or enable autoscaling with `targetCPUPercent: 60`, needs a Pro workspace per Render's docs) |
| Database connections (Supabase, Reports) | **above 70 percent of the pooler limit** | move to transaction pooling (section 2), or a larger plan |
| Database CPU (Supabase) | **above 60 percent after caching** | add a read replica (reads of the public lists first) |
| Outbox backlog (when the outbox exists) | **older than 15 minutes** | move the outbox job to a Render background worker |
| 429 share of public reads | above 1 percent | see "Many students on one address" below |
| Redis memory or `evicted_keys` (`manage.py cache_stats`) | evictions rising | a larger Key Value plan; check for an unbounded key |

## 6. Measurements to take on staging (NOT YET TAKEN)

Preconditions (all on the founder's deferred list, `FOUNDER_DEFERRED.md`): staging database restored; staging seeded
(`seed_loadtest`); staging on the planned paid size; `REDIS_URL` set from a staging Key Value instance;
`THROTTLE_ANON` and `THROTTLE_USER` raised for Pass B only (`LOADTEST.md`); Render and Supabase dashboards open for CPU,
memory and connections. Commands are in `LOADTEST.md`.

| # | Run | How | Record |
|---|---|---|---|
| 1 | Pass B, 50 users | `LOADTEST.md`, medium | req/s per instance, p95 per group, CPU, memory, DB connections, cache hit rate |
| 2 | Pass B, 200 users | the 200-user command | same |
| 3 | Pass B, 300 users | `locust ... -u 300 -r 5 --run-time 13m` | same |
| 4 | Stress to saturation | `locust -f locustfile.py,stress_shape.py ...` | the user count at which p95 or errors fail the thresholds; which resource ran out first |
| 5 | Run 2 with 1 instance, then with 2 | change `numInstances` between runs | req/s per instance in each (a good result: close to equal, twice the total); DB connections in each |
| 6 | One instance restarted under load | during run 2 with 2 instances, "Restart" one in Render | errors during the restart (expect none beyond a few connection resets), time until it serves again, whether the other instance coped |

**Cache hit rate:** run `python manage.py cache_stats` before and after each run (where the shell works: a Render shell on
a paid service, or against the same Key Value instance from a laptop with its external address, which needs an
`ipAllowList` entry first). Use the difference between the two snapshots. Redis counts every command, including rate-limit
reads, so also compare `duration_ms` and `db_queries` of `GET /api/v1/cities/` in `summarize_log.py` output: a hit shows 0
queries.

Fill in (never edit an old row):

| # | Date | Size / instances | Users | Req/s total | Req/s per instance | p95 public | p95 auth | Peak CPU | Peak memory | Peak DB connections | Cache hit rate | Result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 to 6 | | | | | | | | | | | | **NOT MEASURED** |

What was measured on the laptop in Phase 3 (behaviour only):

| What | Result |
|---|---|
| Cached read through the helpers, Redis up (200 reads) | median 3.45 ms (two Redis round trips: the version, then the value) |
| First cache call after Redis was stopped | 287 ms (one connect attempt; the timeout is 0.25 s) |
| The next 200 calls with the breaker open | median 0.04 ms each |
| After Redis came back and the cool-down passed | normal again on the next call (median 3.3 ms) |
| 8 threads asking for one expired key | the builder ran once (a test holds this) |

## Many students on one address (a recommendation; rates were not changed)

Anonymous browsing is limited to 60 a minute per client address. On a campus Wi-Fi, or behind a mobile carrier's shared
address (carrier-grade NAT puts many phones behind one public address), the 60 a minute is shared by everyone behind that
address. With Cloudflare in front and `TRUSTED_PROXY_COUNT` right, each phone with its own address gets its own allowance; a
shared address still shares. In order of preference, all needing the founder's approval:

1. **Let the edge answer the public lists.** A cached answer never reaches the origin, so it never counts against the origin
   limit (`EDGE_SETUP.md`, cache rules). This removes most public traffic for free.
2. **Send the sign-in token on public reads when the user is signed in** (an app change, Phase 10): those requests count per
   user (120 a minute), not per address.
3. **Give public reads their own, higher scope** than other anonymous endpoints (for example 300 a minute per address for the
   list, cities and localities, while OTP and login stay strict, as the OTP limits that protect people live on the OTP
   record itself and do not depend on the address).
4. Only if `429` answers are still common after 1 to 3 (measure the share in the request log): raise the anonymous rate.

Do not loosen `otp_send` or `otp_verify` for this reason: they protect against abuse, and the per-record cooldown already
protects a person on a shared address.

## What the founder must approve (nothing here was applied or paid for)

See also the numbered list at the top of `render.scale.yaml` and `EDGE_SETUP.md`.

1. The Key Value instances (the production one is a paid plan; check the price).
2. Production web on a paid size with `numInstances: 2`.
3. `migrate` as a pre-deploy command (runs once per deploy; a failed migration blocks the release).
4. A Supabase plan or transaction pooling (section 2), and the dedicated web role if transaction mode is used.
5. Cloudflare (a domain and the settings in `EDGE_SETUP.md`).
6. The measured `WEB_CONCURRENCY` and `GUNICORN_THREADS` after the load test.
