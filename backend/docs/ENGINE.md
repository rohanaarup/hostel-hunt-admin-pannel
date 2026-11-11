# The stay engine: reminders, the outbox and the cron jobs (Phase 8)

Decision E1: **a Postgres outbox table plus Render cron**, no Celery and no Redis queue. The same commands can later run as a Render
background worker. This page is what an operator needs.

## The pieces

| Piece | What it does | How it runs |
|---|---|---|
| `OutboxEvent` (`apps/stays`) | One row per thing to do outside a request: `stay.created`, `rent.paid`, `stay.vacate_requested`, `rent.reminder`, `rent.reminder_manual`. Unique `dedupe_key`; `priority` (overdue first); ids only in the payload. | Written in the same transaction as the change that causes it. |
| `stays_daily` | Activates UPCOMING stays on their join date; creates the next Due when the latest is paid or its payable window has opened; queues the reminder the ladder calls for today (7, 3, 1 days before, the due day, 1, 3, 7 days after); heals recently paid bookings that have no stay. | Cron `hostel-hunt-daily`, **03:30 UTC = 09:00 IST**, wrapped in `ping_heartbeat`. |
| `process_outbox` | Claims due events in batches, runs their handlers, records the result (inbox notices, emails). | Cron `hostel-hunt-outbox` every 5 minutes, wrapped in `ping_heartbeat`; or a background worker with `--loop`. |
| `cleanup_expired` | Also deletes finished outbox rows, reminder logs, notifications and job runs older than 90 days (`NOTIFICATION_RETENTION_DAYS`), in batches of 1,000, each its own isolated step. | The existing 5-minute cron. |
| `GET /api/v1/ops/status/` | Admin only: outbox pending and failed counts, the age of the oldest pending event, the last successful run of each job, whether Redis answers. No personal data. | On demand. |

## How `process_outbox` is safe

1. **Claim** (one short transaction): `SELECT ... FOR UPDATE SKIP LOCKED` the most urgent due rows (highest priority, then oldest), push their
   `next_attempt_at` forward by a 10-minute lease and count the attempt. Two copies can run together and never take the same row. A copy that
   dies after claiming leaves rows that come back when the lease ends.
2. **Handle** with no transaction held (an email is an HTTP call, rule S4). One failing event never stops the others; its error is logged with the
   event id and the exception type only, and Sentry sees the log line.
3. **Record**: DONE; or FAILED with a backoff of 60 s, 120 s, 240 s ... at most 6 hours, retried up to `OUTBOX_MAX_ATTEMPTS` (8), then left FAILED for a person;
   or a **deferral** (quiet hours, the email cap, a provider outage), which waits for its time and is not counted as a failure unless the provider was down.

Handlers are idempotent: each notice has a unique `dedupe_key`, each reminder channel a unique `NotificationLog` row `(due, kind, channel, bucket)`. A second
run, a retry or a second worker sends nothing twice.

## Reminders

| Rule | Behaviour |
|---|---|
| Ladder | 7, 3, 1 days before, the due day, 1, 3, 7 days after. WAIVED and CANCELLED dues and ended stays are skipped. A step that is a day or more late is dropped if it is an "upcoming" step (the next step follows); an overdue step is worded for today. |
| Channels | **Inbox** always (unless the student switched it off). **Push**: not built (Part F is skipped, see below); `NotificationPreference.push` is stored and honoured once push exists. **Email**: the due day and overdue steps only. |
| Quiet hours | Nothing is sent from 21:00 to 08:00 IST (`QUIET_HOURS_START`, `QUIET_HOURS_END`). Reminder events are simply not claimed at night and go out at 08:00. Payment and stay notices are inbox-only and are not held. |
| Email cap | At most `EMAIL_DAILY_CAP` (default **80**) reminder emails per IST day, most severe first (the longer overdue, the sooner), the rest deferred to 08:00 the next day. **Set it from your real email plan**: the free plans are small and the limit is unconfirmed (KNOWN_GAPS F7-09). A 429 or a provider outage defers to the next run and stops trying for that batch; other errors are logged (a code, never an address) and the event still finishes. |
| Preferences | `NotificationPreference` per user: inbox, push, email, all default on. `GET` and `PATCH /notifications/preferences/`. |
| Manual reminder | `POST /stays/dues/<id>/send-reminder/` (owner or admin): only for a payable or overdue due, once per due per IST day (a unique `NotificationLog` row with the date as its bucket), queued through the outbox, honours quiet hours and preferences. |

### Wording

The push and email wording is `apps/notifications/templates.py`, tested word for word against `docs/ui/text/PushPreview.txt` and `EmailPreview.txt`. The boards give
wording for 7, 3 and 1 days before, the due day and 3 days overdue. We wrote the rest in the same voice: "Rent is 1 day overdue", "Rent is 7 days overdue",
"Rent due in N days" for a manual reminder on any other day, and the overdue email (subject "Your rent of ₹6,000 is overdue", "... was due on 18 Oct. Please pay as soon as you can.").
The in-app notice uses the push wording. The Inbox board's sample bodies differ slightly from the push wording ("You can pay now in the app."); the push wording wins.

## The cron services (render.yaml)

Two new cron services, each with its own environment list and its own heartbeat monitor (its own `HEARTBEAT_URL`):

- `hostel-hunt-outbox`: `*/5 * * * *`, `ping_heartbeat process_outbox`. Needs the database, Sentry, the heartbeat URL, the email provider variables (`EMAIL_API_PROVIDER`, `EMAIL_API_KEY`, `DEFAULT_FROM_EMAIL`) and `EMAIL_DAILY_CAP`. No Razorpay.
- `hostel-hunt-daily`: `30 3 * * *`, `ping_heartbeat stays_daily`. Needs the database, Sentry, the heartbeat URL, `RECONCILE_STAYS_MAX_AGE_DAYS`.

Each costs about a dollar a month at least (confirm on Render's pricing page). Production only; staging does not need them.

### Moving `process_outbox` to a background worker

When the backlog is more than about 15 minutes old (`/ops/status/` shows `oldest_pending_age_seconds`), create a Render **Background Worker** from the same repo and
environment, with the start command `python manage.py process_outbox --loop --sleep 5` (the `--max-seconds` limit is off in loop mode), then delete the cron. Nothing else
changes: the claim uses `SKIP LOCKED`, so for a while both can even run together. Run more than one worker if one is not enough.

## What the daily job will not do

`stays_daily` calls `reconcile_stays --max-age-days 3`: it heals a booking paid in the last three days whose stay was not created. It never turns old paid bookings into stays,
because an old booking of a student who has left would become an ACTIVE stay with an overdue rent (KNOWN_GAPS G5-03). A deliberate backfill is a separate manual run:
`reconcile_stays --dry-run --since 2026-10-01`, read the counts, then run it without `--dry-run`.

## Measured (the scratch Postgres on a laptop, 2026-11-11; a guide, not a promise about Render)

| Test | Result |
|---|---|
| `stays_daily` over **20,000** synthetic stays (batch 1,000, 22 batches) | **23.5 s** (about 850 stays a second). Memory 179 MB after the first batch, 174 MB after the second, 182 MB at the end: **flat** (+7 MB over 20 batches). A second pass adds nothing. |
| `process_outbox` draining **100,000** synthetic events through a fake sender (batch 500, 200 batches) | **46 s = 2,164 events a second.** |
| The real reminder handler (bulk reads and inserts, inbox only) over **20,000** reminders | **23.8 s = 840 events a second.** |

**A defect the scale test found and fixed:** the first version of the claim query asked for "PENDING or FAILED" rows in priority order, which made Postgres sort the whole backlog on
every batch: 100,000 events took **6,465 s (15 events a second)** against 6,170 a second for 5,000 events. The claim now reads PENDING rows alone, straight from the
`(status, -priority, next_attempt_at)` index, and FAILED rows (a small set) only to fill the batch. A test that always runs (20,000 events, rate must stay steady and above 300 a second) guards it.

Reading the numbers: at 840 reminders a second, 100,000 students' reminders on one day take about two minutes of handler time; the real limit that day is the email cap and the email provider, not the engine.

## Part F (push) is not built

The gate (KNOWN_GAPS F7-02: the Android application id is a placeholder and no upload keystore exists) is open, so Firebase push was skipped, as the plan allows.
When it is resolved: the founder creates the Firebase project and the service account (`FCM_SERVICE_ACCOUNT_JSON` as a Render secret), then Part F is built behind `PUSH_ENABLED`
(default false). The outbox, the preference and the inbox are ready for it.
