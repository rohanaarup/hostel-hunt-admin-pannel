# Gap triage (Phase 1 of 11)

**Written:** 2026-10-29, from a complete read of `KNOWN_GAPS.md` (last reviewed 2026-10-18) plus what Phase 1 found.
**Companion:** `backend/docs/STAY_BASELINE.md` (evidence for the new rows).
**Rule:** this file classifies gaps; it closes none. `KNOWN_GAPS.md` stays the register. Nothing was deleted from either file.

## Classes

| Class | Meaning |
|---|---|
| **LAUNCH-BLOCKER** | Must be fixed (or proven) before go-live with real users and real money. |
| **SCALE** | Needed before about 10,000 users, or to be able to measure / operate safely at that size. |
| **LATER** | Cosmetic, debt, rare, or a product decision that can wait. |

## How to read the "Owner phase" column (assumption, please confirm)

The prompt for this phase names the content of only some later phases. I used only these facts:
Phase 2 writes `docs/MIGRATION_POLICY.md` and is allowed to read production health URLs, so I treat it as **production safety and the deploy path**;
Phase 3 adds the shared cache and replaces the design targets with measurements, so it is **scale foundations**;
Phases 5 and 6 may change payment code; Phase 10 may change the app's payment flow; Phase 11 is the **launch gate** (production health reads, final measurements).
Where a gap belongs to a part of the plan I cannot place (stay lifecycle, notifications, owner screens) it says "Stay phases" and the founder should pin the number.
**HUMAN** means only the founder can do it (dashboards, accounts, devices, money); the phase listed is where Claude verifies it afterwards.

**Totals for the 119 register rows (after Phase 2 raised four of them):** 34 LAUNCH-BLOCKER (10 default, 20 added in Phase 1, P-02, F0-02, F0-03, F1-02 raised in Phase 2), 35 SCALE, 50 LATER. The 12 new G1 rows and the new G2-01 are counted separately below. Every register ID appears exactly once (checked by script against `KNOWN_GAPS.md`).

## Launch blockers at a glance

Founder's default list (kept in full): P-03, A-06, L4-12, F1-01, F7-02, F7-03, F7-06, X-01, X-06, X-08.

Added in Phase 1 (each has a reason in its row; the founder may question an addition, but removing a default needs the founder's approval):
P-01, P-04, P-05, F1-04, F2-01, F2-02, F3-02, T1-01, T4-01, L4-01, L4-02, L4-03, L4-04, L4-05, L4-07, F6-05, F6-07, F7-07, X-02, X-07, and the new rows G1-01 (backup workflow cannot run), G1-02 (verify has no status guard) and G1-03 (rent cannot reuse `confirm_payment`). A further new row, G1-12 (staging database unreachable), blocks Phase 1's own measurements and is a founder action, and G2-01 (credentials in public history) was found in Phase 2.

## Open gaps from KNOWN_GAPS.md (119 rows)

### P. Before the playbook

| ID | Gap (short) | Class | Owner phase | Note |
|---|---|---|---|---|
| P-01 | No recorded real-device payment test | LAUNCH-BLOCKER (added) | 10, 11 (HUMAN device run) | Money flow unproven on a phone. |
| P-02 | SECRET_KEY rotation never confirmed | LAUNCH-BLOCKER (raised in Phase 2) | 2 (HUMAN) | Phase 2 found the old committed `.env` files (see G2-01). Rotate with the database password; the only side effect is that logins end once (checklist step 0). |
| P-03 | Production schema vs code unknown (3 migrations unapplied on 2026-10-06) | LAUNCH-BLOCKER (default) | 2 | Phase 2 must compare the live schema read-only before any deploy. |
| P-04 | No automated backups | LAUNCH-BLOCKER (added; same as X-06) | 2 | See G1-01: the workflow cannot even start. |
| P-05 | Render free sleeps; slow wake | LAUNCH-BLOCKER (added) | 2 (HUMAN: paid plan) | Phase 1 measured a **42.4 s** wake on staging. A first-time user would see this. |
| P-06 | LAN IP and firewall for phone testing | LATER | none | Dev convenience. |

### F0. Baseline

| ID | Gap | Class | Owner phase | Note |
|---|---|---|---|---|
| F0-01 | No baseline measurements | SCALE | 1 (partial), 3, 11 | Phase 1 delivers a partial baseline: wake time and public-endpoint latency from outside. Log-based numbers still need Render log access (see STAY_BASELINE, Part C). |
| F0-02 | Possible past secret exposure; rotation unknown | LAUNCH-BLOCKER (raised in Phase 2) | 2 (HUMAN) | Now evidenced: see G2-01. |
| F0-03 | Old `db.sqlite3`, `django.log`, data dump in public git history | LAUNCH-BLOCKER (raised in Phase 2) | 2 (HUMAN decision) | Phase 1 said to verify first. Phase 2: the newest non-empty `db.sqlite3` holds 3 owner accounts, 1 hostel, no bookings; whether they are real people is the founder's call. A history rewrite needs approval and does not remove copies already taken. |
| F0-04 | `sele tests/` scripts hit live endpoints, unreviewed | LATER | 2 | Same as F7-10. |

### F1. Define production

| ID | Gap | Class | Owner phase | Note |
|---|---|---|---|---|
| F1-01 | Production does not run F1 (debug routes, DEBUG on) | LAUNCH-BLOCKER (default) | 2 | Same root as X-01. |
| F1-02 | Secret rotation skipped by choice | LAUNCH-BLOCKER (raised in Phase 2) | 2 (HUMAN) | See P-02 and G2-01. |
| F1-03 | Both repos public | LATER | none | Accepted. Revisit with F0-03. |
| F1-04 | Render plan stays free (sleeps, blocks SMTP) | LAUNCH-BLOCKER (added) | 2 (HUMAN) | See P-05 and L4-02. |
| F1-05 | Phone OTP (Twilio) not integrated | LATER | none | Decision D4 excludes SMS in v1. The app should not offer phone sign-up while it answers 503 (check in Phase 10). |
| F1-06 | HSTS off | LATER | 11 | Turn on once HTTPS is proven on production. |
| F1-07 | Gunicorn config and Render rollback never exercised | SCALE | 2 | Rollback rehearsal is also in RELEASE.md. |
| F1-08 | Stale docs inside `hostel-hunt-admin-next/` | LATER | none | |
| F1-09 | Local Python 3.14 vs Render/CI 3.13.5 | LATER | none | Phase 1 ran the tests on 3.14.3 locally; CI uses 3.13. |

### F2. Observe

| ID | Gap | Class | Owner phase | Note |
|---|---|---|---|---|
| F2-01 | No Sentry project | LAUNCH-BLOCKER (added) | 2 (HUMAN, free) | Without it L4-07 (money flagged for review) is silent. |
| F2-02 | No uptime monitors | LAUNCH-BLOCKER (added) | 2 (HUMAN, free) | Do not monitor staging. |
| F2-03 | `pg_stat_statements` not confirmed | SCALE | 3 | Needed for C3 in STAY_BASELINE. |
| F2-04 | Production has no request log / `db_ms` | SCALE | 2 | Solved by the X-01 deploy. |
| F2-05 | No obfuscation symbol upload | LATER | none | |
| F2-06 | Kotlin plugin warning | LATER | none | |
| F2-07 | Sentry tracing off | LATER | none | |
| F2-08 | Release tag never seen on Render | LATER | 2 | |

### F3. Change pipeline

| ID | Gap | Class | Owner phase | Note |
|---|---|---|---|---|
| F3-01 | Branch protection off (Phase 1 re-checked: `main` still "not protected" in both repos) | SCALE | 2 (HUMAN setting) | |
| F3-02 | Laptop `backend/.env` points at the production database, DEBUG on | LAUNCH-BLOCKER (added) | 2 (HUMAN) | High impact: a plain `runserver`/`migrate` here changes real data. Phase 1 overrode every database variable on the command line for all runs. Fix: point `.env` at local or staging. |
| F3-03 | Staging seed never landed (staging empty) | SCALE | 2 | **Blocks** C4/C5 (load tests) and B3 (payment test). Do first in Phase 2. |
| F3-04 | App analyzer ratchet near its limit | LATER | none | See STAY_BASELINE for today's count. |
| F3-05 | About 28 APIViews without serializers in `schema.yml` | LATER | none | |
| F3-06 | Admin CI has no ESLint | LATER | none | |
| F3-07 | App CI does not build an APK | SCALE | 2 | Plugin breakage found late (see memory note). |
| F3-08 | CI Postgres 16 vs Supabase 17 | LATER | 2 | Backup tool already uses pg_dump 17. |
| F3-09 | `render.yaml` is reference only; dashboard drifts | SCALE | 2 | See also G1-05 (cron variables). |
| F3-10 | 750 free hours shared | LATER | none | Moot once a paid plan is used (P-05). |

### A. The 2026-10-11 "F4"

| ID | Gap | Class | Owner phase | Note |
|---|---|---|---|---|
| A-01 | Email/phone change refused | LATER | none | |
| A-02 | Admin Payments page read-only; no offline rent ledger | SCALE | Stay phases | Closed by decision D3 when built. |
| A-03 | Cloudinary photo upload tested against a mock only | SCALE | 11 (HUMAN) | |
| A-04 | Admin Payments page never opened in a browser | LATER | 11 | |
| A-05 | GitHub Pages enabled on backend repo | LATER | 2 (HUMAN) | `pages-build-deployment` ran on every push in the CI list. |
| A-06 | Not live on production incl. `owners.0005` | LAUNCH-BLOCKER (default) | 2 | See X-01. |
| A-07 | `search`/`amenity` ignored on the owner's own list | LATER | none | |

### T1. Location

| ID | Gap | Class | Owner phase | Note |
|---|---|---|---|---|
| T1-01 | Production has no T1; test hostels in the live list | LAUNCH-BLOCKER (added) | 2 | Part of X-01; the cleanup command needs the founder's OK. |
| T1-02 | Filters never seen on real data | SCALE | 11 | |
| T1-03 | Auto Detect hidden | LATER | none | |
| T1-04 | No locality aliases; "Unknown" localities | SCALE | 11 (HUMAN data work) | |
| T1-05 | Owners cannot add localities | LATER | none | |
| T1-06 | Silent failure saving location | LATER | none | |
| T1-07 | Old `city`/`locality` text columns kept | LATER | none | Cleanup migration must follow the Phase 2 migration policy. |

### T2. Profile and photo

| ID | Gap | Class | Owner phase | Note |
|---|---|---|---|---|
| T2-01 | Authenticated live checks never run | SCALE | 11 (blocked by F3-03) | |
| T2-02 | Device test script not run | SCALE | 11 (HUMAN) | |
| T2-03 | Cloudinary vars on staging unchecked | LATER | 11 | |
| T2-04 | Unsigned upload preset | SCALE | 3 | Accepted risk today; abuse grows with users. |
| T2-05 | Old `profile_photo` field | LATER | none | |
| T2-06 | Stats ignore guest bookings | LATER | none | Related to E3/E4 (anonymous bookings). |

### T3. Voice, saved, detail

| ID | Gap | Class | Owner phase | Note |
|---|---|---|---|---|
| T3-01 | Voice search never run on a phone | SCALE | 11 (HUMAN) | |
| T3-02 | Hindi/Telugu voice finds nothing without aliases | LATER | none | |
| T3-03 | Saved page not run on real data/phone | SCALE | 11 | |
| T3-04 | No student cancel route (confirmed in `apps/bookings/urls.py`; see STAY_BASELINE A4) | SCALE | Stay phases | Tied to L4-12: a cancel must also release the bed. |
| T3-05 | "Recently Viewed" placeholder | LATER | none | |
| T3-06 | iOS never built | LATER | none | |
| T3-07 | `permission_handler` pinned to 12.0.3 | LATER | none | |

### T4. Admin and data safety

| ID | Gap | Class | Owner phase | Note |
|---|---|---|---|---|
| T4-01 | Admin site not hosted anywhere | LAUNCH-BLOCKER (added) | 2 (HUMAN host choice) | Owners cannot work without it; the plan's owner rent recording (D3) needs it. |
| T4-02 | Admin never opened against a live server | SCALE | 11 | |
| T4-03 | 8 legacy bookings without a student | LATER | none | |
| T4-04 | Orphan media from abandoned wizard | LATER | none | |
| T4-05 | Room photos from the wizard discarded | LATER | none | |
| T4-06 | Heatmap uses latest 100 bookings | LATER | none | |
| T4-07 | Dashboard totals not compared to DB on known data | SCALE | 11 | See G1-04: offline totals trust a client-supplied amount. |
| T4-08 | Admin tokens in `localStorage` | LATER | none | Accepted. |

### L4. Safe request path and payments

| ID | Gap | Class | Owner phase | Note |
|---|---|---|---|---|
| L4-01 | Staging payment test never run | LAUNCH-BLOCKER (added) | 2 (HUMAN keys), 11 | Phase 1 B3 is blocked on the same prerequisites (see STAY_BASELINE). |
| L4-02 | No email provider | LAUNCH-BLOCKER (added) | 2 (HUMAN) | New users cannot register by email. |
| L4-03 | Brevo single-sender route unconfirmed | LAUNCH-BLOCKER (added) | 2 (HUMAN) | Same cause as L4-02. |
| L4-04 | No Razorpay TEST keys/webhook on staging; live readiness unverified | LAUNCH-BLOCKER (added) | 2 (HUMAN) | |
| L4-05 | Cleanup cron job not created | LAUNCH-BLOCKER (added) | 2 (PAID, HUMAN) | Rent reminders (E8) also depend on a cron. See G1-05 for its missing variables. |
| L4-06 | `TRUSTED_PROXY_COUNT` default 1 unverified on Render | SCALE | 3 | Needs one `xff_hops` log line. If wrong, all users share one limit. |
| L4-07 | Flagged payments have no alert or student message | LAUNCH-BLOCKER (added) | 6 (code), 2 (Sentry) | |
| L4-08 | Owner `verify` marks paid with no money | LATER | 5 | Accepted, but see G1-02: it also lacks a status guard, which Phase 5 must fix before stays are created from it. |
| L4-09 | No refund reconcile job | SCALE | 6 | |
| L4-10 | Password login limited only by the general throttle | SCALE | 3 | |
| L4-11 | `otp_auth` dead app | LATER | none | |
| L4-12 | Paid bed never becomes free again | LAUNCH-BLOCKER (default) | Stay phases (stay end / vacate) | Confirmed again by reading `holds.py`/`confirm.py`: nothing sets `is_available` back to True. |

### F5. Data path

| ID | Gap | Class | Owner phase | Note |
|---|---|---|---|---|
| F5-01 | Render-to-database distance unmeasured | SCALE | 2 then 11 | The rule is in AFTER-F5.md. Needs request-log lines. |
| F5-02 | Statement timeout only in `render.yaml` | SCALE | 2 | |
| F5-03 | Image savings unmeasured | LATER | none | |
| F5-04 | Places cache is per worker | SCALE | 3 | Replaced by the shared cache (rule S2). |
| F5-05 | Cache headers help only once something caches | LATER | none | |
| F5-06 | Deactivated rooms still counted in owner totals | LATER | none | |
| F5-07 | Owner queries grow linearly with bookings | LATER | 11 | Revisit at `db_ms` above about 100. |
| F5-08 | Database pool headroom 3 to 4 of 15 | SCALE | 3 | **Phase 1 arithmetic: a second web instance does not fit** (see STAY_BASELINE A10). |

### F6 and F7

| ID | Gap | Class | Owner phase | Note |
|---|---|---|---|---|
| F6-03 | No disk image cache | LATER | none | |
| F6-04 | Card blur/shadow unprofiled | LATER | none | |
| F6-05 | F6 never run on a phone | LAUNCH-BLOCKER (added) | 10, 11 (HUMAN) | The payment resume flow is part of paying. |
| F6-06 | Offline copies partial | LATER | none | |
| F6-07 | Card payment with lost verify answer depends on webhook | LAUNCH-BLOCKER (added) | 2 (webhook set-up, HUMAN) | Closes together with L4-04. |
| F6-08 | Payment icons from third-party sites | LATER | 10 | |
| F6-09 | Waiting banner on Home only | LATER | none | |
| F7-01 | No staging load run | SCALE | 3, 11 | Phase 1 could not run it (see STAY_BASELINE C4). |
| F7-02 | Android release blockers (id, keystore, icon) | LAUNCH-BLOCKER (default) | 11 (HUMAN) | |
| F7-03 | Backup never run; restore only rehearsed on a laptop; rollback never tried | LAUNCH-BLOCKER (default) | 2 | See G1-01. |
| F7-04 | Nothing can be load-tested yet (size, seed, vars) | SCALE | 2 (HUMAN decisions) | |
| F7-05 | Login hash cost; per-address throttle | SCALE | 3 | Phase 1: Django 5.2.15 PBKDF2 = 1,000,000 rounds confirmed. Per the prompt the round count is not changed. |
| F7-06 | Play Console not started | LAUNCH-BLOCKER (default) | 11 (HUMAN) | |
| F7-07 | R8 shrinking and `<queries>` not run on a phone | LAUNCH-BLOCKER (added) | 10, 11 (HUMAN) | A release-only crash or dead UPI button would block paying. |
| F7-08 | No "update required" screen | LATER | 10 | |
| F7-09 | Brevo 300/day cap unconfirmed | SCALE | 2 | |
| F7-10 | Old helper scripts ship with the code | LATER | 2 | |

### X. Cross-cutting

| ID | Gap | Class | Owner phase | Note |
|---|---|---|---|---|
| X-01 | Production is stale; many migrations pending | LAUNCH-BLOCKER (default) | 2 | Needs backup first and the founder's explicit OK. |
| X-02 | Live-verification debt | LAUNCH-BLOCKER (added) | 11 | The final gate. |
| X-03 | Staging has no data or test users | SCALE | 2 | Same as F3-03. |
| X-04 | No branch protection or review | SCALE | 2 | Same as F3-01. |
| X-05 | Public repos with old DB file in history | SCALE | 2 | Same as F0-03; the app repository also has `db.sqlite3` copies and a `.env` in its history. |
| X-06 | No backups, no restore rehearsal | LAUNCH-BLOCKER (default) | 2 | See G1-01. |
| X-07 | Supabase free pauses; production plan unconfirmed | LAUNCH-BLOCKER (added) | 2 (HUMAN) | A paused database is an outage. |
| X-08 | Play Console entry and application id | LAUNCH-BLOCKER (default) | 11 (HUMAN) | |
| X-09 | Cloudinary credits | SCALE | 11 | |
| X-10 | 52 Flutter packages behind | LATER | none | |

## New gaps found in Phase 1 and 2

Evidence for the G1 rows is in `backend/docs/STAY_BASELINE.md`; G2-01 is from Phase 2 (`FOUNDER_CHECKLIST_PROD.md` step 0). Phase 1 left these in this file only; Phase 2 copied them into `KNOWN_GAPS.md` section G.

| ID | Gap | Impact | Class | Owner phase | Evidence / effect |
|---|---|---|---|---|---|
| G1-01 | **The backup workflow is invalid YAML and cannot run.** `.github/workflows/backup.yml` line 32 has an unquoted `run:` value containing `: ` ("Backup skipped: ..."). GitHub shows runs 39227131826 and 39227677174 as failures ("workflow file issue") and the daily schedule never starts, even after the two secrets are added. `KNOWN_GAPS` assumes only the secrets are missing. | High | LAUNCH-BLOCKER | 2 | `actionlint` output: "could not parse as YAML: mapping values are not allowed in this context". `gh secret list` shows no secrets at all. Not fixed in Phase 1 (workflows are out of scope). **Phase 2: fixed on branch `phase-2-production-foundation`** (the step now fails the run on purpose when secrets are missing; `actionlint` clean; `test_phase2.BackupWorkflowTests`). Close after the merge and a successful manual run. |
| G1-02 | **`BookingViewSet.verify` has no status guard.** It only checks `payment_mode == 'online'`, then takes the bed and sets `paid`. A cancelled, rejected or already paid booking can be set to paid again, and every repeat call would run again whatever Phase 5 attaches (E2: stay and dues created in the same transaction), creating duplicates. `mark_paid` does guard (`pending`/`confirmed` only). | High for Phase 5 | LAUNCH-BLOCKER | 5 | `apps/bookings/views.py:147-165`. Distinct from L4-08, which is about the missing money, not the missing guard. |
| G1-03 | **`confirm_payment` and the hold logic cannot be reused unchanged for rent (E6/E7).** (a) `holds.hold_has_lapsed` treats any payment whose bed has no live hold as lapsed after 15 minutes of age, and the status poll and cleanup then fail it; (b) `confirm_payment` flags a payment as "bed already taken" whenever `bed.is_available` is False, which is always true for a booking that is already paid; (c) `CreateOrderView` refuses bookings in status `paid` and bookings with a SUCCESS payment. A rent order built on the current Payment/booking path would be failed or flagged. | High for Phase 6 | LAUNCH-BLOCKER | 6 | `holds.py:44-51`, `holds.py:90-95`, `confirm.py:98-101`, `payments/views.py:137-154`. Phase 6 must branch on payment kind (a new field or a separate function) and add tests for all three. |
| G1-04 | **Offline revenue trusts a client-supplied amount.** `BookingCreateSerializer` accepts `amount` from anyone (the endpoint is `AllowAny`) and never checks it against the room price. The owner dashboard's offline revenue and "pending" totals sum `Booking.amount`. Online payments are safe (the amount comes from `Room.price_per_month`). | Moderate | SCALE | 5 | `serializers.py:49,61`; `dashboard/views.py:334-335`. Phase 5 should set `Booking.amount` server-side. |
| G1-05 | **The cleanup cron has too few variables for the later work.** `render.yaml` gives it only `PYTHON_VERSION`, `SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL`. Reminder email (E8, D4) needs `EMAIL_API_PROVIDER`, `EMAIL_API_KEY`, `DEFAULT_FROM_EMAIL`; any Razorpay reconcile job needs `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`; errors from the cron are invisible without `SENTRY_DSN`/`SENTRY_ENVIRONMENT`; push (D4) will need FCM credentials. | Moderate | SCALE | 2 and each feature phase | `render.yaml` lines 128-146. Also the cron is `plan: starter` (paid) and exists only in the file (L4-05, F3-09). **Phase 2: Sentry and heartbeat variables and `GIT_COMMIT` added; email, Razorpay and push variables are for the phases that need them.** |
| G1-06 | **Webhook-confirmed payments are always recorded as method CARD** even when paid by UPI. Only the payment-method label is wrong, not the money. | Low | LATER | 6 | `payments/views.py:607` (code comment already says "best guess"). Razorpay's event carries the method; Phase 6 can read it. |
| G1-07 | **A booking can also become `paid` in Django admin and in the load-test seed**, with no bed taken and no payment: `BookingAdmin` has no read-only fields (`apps/bookings/admin.py`), and `seed_loadtest.py:137` creates paid bookings directly. Staff-only today, but a stay would not be created for such a booking (E2 covers three paths only). | Low | LATER | 5 | Make `status` read-only in the admin when Phase 5 touches it. |
| G1-08 | **Two web instances do not fit the database pool.** One instance holds up to 8 connections (2 workers x 4 threads); the pooler allows 15; a deploy that briefly runs the old and new instance together can ask for 16. | High at scale | SCALE | 3 | Arithmetic in STAY_BASELINE A10. This sharpens F5-08. |
| G1-09 | **The backend test suite takes 7.5 to 13.4 minutes on this laptop** (450 s and 805 s in two runs; 392 tests), while the last green CI run took 2.8 minutes for the whole job. The cause is not profiled (candidates: Windows, Docker Postgres, Python 3.14, 1,000,000 PBKDF2 rounds on every test user). Not a CI risk today (limit 20 minutes), but it slows every local phase and grows with each one. | Low | LATER | 2 | A test-only fast password hasher in the test settings is the obvious first experiment (not done here). |
| G1-10 | **`Room.available_beds` is never updated after a bed is paid.** It is set only from the owner's hostel payload (and the seed). `Bed.is_available` is only ever set to False (`confirm.py:132`, `holds.py:166`), never back to True. The public room JSON exposes `available_beds` (`RoomSerializer` uses `fields = '__all__'`) and the app's bed screen uses it for its "full" state (`bed_selection_screen.dart:220`). So a room never shows as full from payments, and a freed bed (L4-12) would not show as free. | Moderate | SCALE | Stay phases | Whoever builds stay end / vacate must define one source of truth for bed availability (count from `Bed` rows, or update the counter in the same transaction). |
| G1-11 | **Nothing in the code ever sets a booking to `cancelled`.** The status exists as a choice and several checks refuse it, but no endpoint, command or admin action produces it (grep of `apps/`). Only the owner `reject` action ends a booking early. Confirms T3-04 / KNOWN_GAPS "no student cancel route". | Low | LATER | Stay phases | Those refusals are currently unreachable paths. |
| G1-12 | **The staging database is unreachable right now.** On 2026-10-29 (about 12:20 and 14:16 UTC) staging `/healthz` answered 200 in about 0.1 s, but `/readyz` answered 503 after about 15 s, `GET /api/v1/hostels/` and `/api/v1/cities/` answered 500 after about 15 s, and a later try hung past 30 s. KNOWN_GAPS (2026-10-18) said staging was healthy. Likely cause: the free Supabase project paused after a week without activity (X-07) or its connection settings changed; **not confirmed**, because no dashboard access exists from here. | High (blocks all staging work) | SCALE | 2 (HUMAN first) | STAY_BASELINE Part C. Founder: open the Supabase dashboard for `Hostel-hunt-staging`, restore the project if paused, then re-run the probe. |
| G2-01 | **Credentials in the public git history are still current.** An old committed `backend/.env` (5 commits in the backend repository, 3 in the app repository) held a filled `SECRET_KEY`, `DATABASE_URL` and `EMAIL_HOST_PASSWORD`. By hash comparison, the old database address and password and the old email password in the backend repository equal those in the laptop `.env`, which points at the production database (F3-02). gitleaks' default rules found nothing, so a clean scan proves nothing here. | High | LAUNCH-BLOCKER | 2 (HUMAN) | Found in Phase 2 by reading file names and comparing hashes; no value was shown. Rotate the production database password, the email password and `SECRET_KEY` before the production deploy: `FOUNDER_CHECKLIST_PROD.md` step 0. Raises P-02, F0-02, F0-03 and F1-02. |
