# Observability

Smallest-tools setup: one structured log line per request, Sentry free tier for errors, `/healthz` and `/readyz`, and an uptime monitor. No OpenTelemetry, no Grafana, nothing paid.

## Where to read each golden signal

| Signal | Where | What to look at |
|---|---|---|
| **Latency** | Request log (`hh.request`) | `duration_ms` per `route`; `db_ms` shows how much of it was the database |
| **Traffic** | Request log | Number of lines per minute, grouped by `route` and `method` |
| **Errors** | Request log + Sentry | Lines with `status >= 500` (`level: error`, `exc` = exception class). Sentry holds the stack trace and is the place to be alerted. |
| **Saturation** | Request log, host graphs, database | `inflight` (requests running in one worker when this one started; compare with the thread count, 4 by default), Render CPU and memory graphs, `pg_stat_activity` below |
| **Is it up?** | Uptime monitor | `/healthz` (process up, no database) and `/readyz` (database reachable) |

## The request log line

One JSON object per request on stdout, logger `hh.request`. `/healthz` is not logged.

```
{"ts":"2026-10-10T09:49:10.156Z","level":"info","event":"request","request_id":"858defe6...","method":"GET","route":"api/v1/hostels/","view":"hostels-list","status":200,"duration_ms":25.9,"db_queries":2,"db_ms":1.8,"resp_bytes":437,"inflight":1,"user_id":null,"release":"abc1234","pid":41960}
```

| Field | Meaning |
|---|---|
| `request_id` | Also sent back in the `X-Request-ID` response header. Quote it when reporting a problem. A client may send its own `X-Request-ID` (8-64 characters of letters, digits, `.`, `_`, `-`). |
| `route` | URL template (`api/v1/hostels/<pk>/`), never the real path. `unmatched` = no route (404s, scanners); `static` = static files. |
| `view` | URL name. |
| `duration_ms` | Total time in the app, including all middleware. Excludes time queued in gunicorn or the host's proxy. |
| `db_queries`, `db_ms` | Number of queries and total time in them. |
| `inflight` | Requests in progress in this worker process when this request started. |
| `user_id` | Internal owner id (a UUID string) when the request was authenticated, otherwise `null`. |
| `exc` | Present only if a view raised: the exception class name, never the message. |
| `release` | Deployed git commit (`GIT_COMMIT` or `SENTRY_RELEASE`). |

**Never in the line:** the path, query string, headers (so no Authorization, Cookie, User-Agent or IP), request or response bodies, emails, phone numbers, tokens, OTPs. Other log lines get `[request_id]` in their prefix, and any email or phone-like number is masked before it is written.

Measured cost (this machine, Python 3.14): about 67 microseconds per request for the middleware and no measurable cost per query. A typical request here takes 1 to 25 milliseconds.

### Reading the log
On Render, use the service's Logs page and search for text such as `"status":500` or a `request_id`. To analyse a saved copy of the logs in PowerShell (each line that starts with `{"ts"`):

```powershell
$lines = Get-Content saved.log | Where-Object { $_ -like '{"ts"*' } | ForEach-Object { $_ | ConvertFrom-Json }
$d = $lines.duration_ms | Sort-Object
"requests=$($lines.Count) p95_ms=" + $d[[math]::Min($d.Count-1,[int][math]::Floor($d.Count*0.95))]
"5xx=" + ($lines | Where-Object status -ge 500 | Measure-Object).Count
$lines | Group-Object route | Sort-Object Count -Descending | Select-Object Count,Name
```

## Errors: Sentry
Sentry is off unless `SENTRY_DSN` is set. It receives unhandled exceptions and `logger.error` / `logger.exception` calls, 100% of them. Traces are off by default (`SENTRY_TRACES_SAMPLE_RATE=0`). Not sent: request bodies, local variables, cookies, `Authorization` and other sensitive headers, query strings, client IP, user details other than the id. Emails and phone-like numbers in messages are masked. Dropped as noise: 404, permission errors, and `DisallowedHost`.

Send a safe test error from your computer (it makes one synthetic event tagged `synthetic=true`):

```powershell
cd backend
$env:USE_DB='sqlite'; $env:DEBUG='True'
$env:SENTRY_DSN='<the Django project DSN>'; $env:SENTRY_ENVIRONMENT='test'
python manage.py sentry_test
```

## Uptime
Create two monitors in your uptime service, checking every 5 minutes:
- `https://<host>/healthz` should return 200 and `{"status": "ok"}` (the process is alive).
- `https://<host>/readyz` should return 200 (the database answers).

## Database (Supabase / Postgres)
Enable the extension once (Supabase dashboard, Database, Extensions, `pg_stat_statements`), or in the SQL editor:

```sql
create extension if not exists pg_stat_statements;
```

Slowest queries by total time (statement text is normalised, so values appear as `$1`):

```sql
select round(total_exec_time::numeric, 0) as total_ms,
       calls,
       round(mean_exec_time::numeric, 1)  as mean_ms,
       round(max_exec_time::numeric, 0)   as max_ms,
       rows,
       left(query, 150)                   as query
from pg_stat_statements
order by total_exec_time desc
limit 20;
```

Slowest per call (ignore rarely-run statements):

```sql
select round(mean_exec_time::numeric, 1) as mean_ms, calls, left(query, 150) as query
from pg_stat_statements
where calls >= 20
order by mean_exec_time desc
limit 20;
```

Connection saturation and long-running work:

```sql
select state, count(*) from pg_stat_activity
where datname = current_database() group by state order by count(*) desc;

select pid, now() - query_start as running_for, state, left(query, 100) as query
from pg_stat_activity
where state <> 'idle' and pid <> pg_backend_pid()
order by query_start;
```

Compare `count(*)` with the database's connection limit, remembering each gunicorn worker holds persistent connections (`DB_CONN_MAX_AGE`, default 60 seconds).

## Environment variable names
`SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_RELEASE`, `GIT_COMMIT`, `SENTRY_TRACES_SAMPLE_RATE`, `GUNICORN_ACCESSLOG`, `DJANGO_LOG_LEVEL`. See `backend/.env.example`.
