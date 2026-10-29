# Known gaps register (Hostel Hunt)

**Started:** 2026-10-18 · **Last reviewed:** 2026-10-29 (after Phase 2 of the stay plan; no gap was closed, notes added) · **Owner:** the developer and Claude, together

This file lists what we have **not** built, **not** verified, or **chosen to ignore**, phase by phase, and how much each
item matters. It exists because no phase gets finished at 100%: many things need a paid service, infrastructure that
does not exist yet, a person's action, or a later product decision. Writing them down means we choose what to ignore
instead of forgetting it.

It covers the work done in chat sessions from 2026-09-23 to 2026-10-18 (both repos, staging, and the infrastructure).
The sources are the chat history, each phase's "NOT DONE / HYPOTHESIS / Human steps" lists, and checks run on 2026-10-18.

## How to use this file

**For the developer:** read "Top gaps to watch", then "What unlocks what". Ask Claude to explain any ID.

**For Claude (every session):**
1. Read this file before the Part 1 of any phase. Say which gaps the phase touches.
2. At the end of a phase, add the gaps it leaves (use that phase's NOT DONE list), and update the status of any it closes.
3. Never delete a row. Move closed items to "Closed gaps" with the date and the proof.
4. Do not trust a status older than its date: re-check cheap facts (for example `/healthz` on production) before relying on them.
5. Do not put secrets, keys, connection strings or personal data here. Names of environment variables only.

### Impact scale
| Level | Meaning |
|---|---|
| **High** | Can lose or wrongly charge money, lose or expose user data, stop a core flow (sign up, book, pay) for real users, or blocks the Play Store launch. |
| **Moderate** | Weakens a feature, creates manual work, hides failures, or only shows up under load. A workaround exists. |
| **Low** | Cosmetic, tech debt, rare, or only affects development. |

Impact is judged **at launch with real users**. Today (pre-production, a few testers) most items are lower; the "Today" note says so where it differs.

### Cause tags (why it was left)
| Tag | Meaning |
|---|---|
| **PAID** | Needs a paid plan or service. |
| **INFRA** | The infrastructure does not exist yet (hosting, domain, accounts). |
| **HUMAN** | Needs the developer's action (dashboard clicks, keys, device tests). Claude cannot do it. |
| **FUTURE** | A feature or integration planned for later (not forgotten, not scheduled). |
| **UNVERIFIED** | Built and tested in code or CI, but never proven live, on staging or on a device. |
| **CHOICE** | The developer decided to ignore it for now (for example security hardening, on 2026-10-10 and 2026-10-11). |
| **DEFERRED** | Planned for a later phase of the playbook. |

## Where things stand (2026-10-18)

| Environment | State |
|---|---|
| **Staging** (Render free, Singapore, Supabase `Hostel-hunt-staging`) | Runs the latest `main`: F1, F2, F3, the "11 API calls" fix, T1, T2, T3, T4 and F4. Database is **empty** (the seed never landed). Healthy. |
| **Production** (`hostel-hunt-backend.onrender.com`) | **Old code** (re-checked 2026-10-29 by read-only GET: unchanged). `/healthz` and `/readyz` answer 404, the old `/debug-version/` route answers 200, DEBUG was set to True. Auto-deploy is off. None of F1 to F4 or T1 to T4 is live there, and none of their migrations ran. |
| **Laptop** | `backend/.env` points at the **production** Supabase database (checked 2026-10-18, region only, no secrets read) with DEBUG on. Claude's test runs override it with environment variables, but a plain `runserver` or script from the laptop touches production data. |
| **Admin site** (Next.js) | Not hosted anywhere as far as we know (2026-10-10 statement). Runs locally only. |
| **App** | Built and installed on a test phone only. No Play Console app. Uses `com.example.rohii_hostel_hunt` as its id. |

| Phase | Code | Live-proven |
|---|---|---|
| Razorpay wiring in the app (Sept) | Built and merged | Not recorded |
| Baseline check (called F0 in chat) | Done (git sync, tests) | Lean Core F0 measurements **not** done |
| F1 production config | Merged | Staging only |
| F2 observe | Merged | No Sentry, no monitors |
| F3 change pipeline | Merged | Branch protection **off** |
| "F4" 11 API calls (our own name) | Merged | Staging, empty data |
| T1 location | Merged | Staging, empty data |
| T2 profile and photo | Merged | Not run live |
| T3 voice, saved, detail | Merged | Not run on a phone |
| T4 admin data safety | Merged | Not opened in a browser |
| Lean Core F4 payments and OTP | Merged | Staging payment test **not run** |
| Lean Core F5 data path | Built 2026-10-18 | Staging check after deploy; no production numbers yet |
| Lean Core F6 phone resilience | Merged 2026-10-19 (app PR #12) | Tests and APK build only; **no phone run yet** (F6-05) |
| Lean Core F7 launch gate | Tooling built 2026-10-19 (backend PR and app PR, see Closed gaps C-17 to C-19) | **No staging load run, no backup running, no signed release in use** (F7-04 to F7-09) |

## Top gaps to watch

These are the High items. Details are in the phase sections.

| ID | Gap | Why it matters |
|---|---|---|
| X-01 | Production runs old code and is missing many migrations | Everything we built is invisible to real users until a controlled deploy. |
| L4-02 | No email provider anywhere | Email sign-up and forgot-password cannot send codes on Render free (SMTP is blocked). |
| L4-01 | Staging payment test never run | Money flow changed in F4 and was proven only by tests. |
| L4-12 | A paid bed never becomes free again | A refund, cancellation or checkout does not release the bed or change the booking. |
| F3-02 | Laptop `.env` points at the production database | A local run can change real data. |
| X-06 | No backups and no restore rehearsal | A data loss cannot be undone. |
| X-08 | Android release blockers (application id `com.example...`, debug signing, cleartext) | The Play Store will reject the build, and the id cannot change after the first upload. |
| F6-05 | F6 is proven by tests and a debug build only, never on a phone | The payment resume flow and the waking banner need one real device run (script in the app's `docs/F6-PHONE-RESILIENCE.md`). |

## What unlocks what

| To close these... | ...you or Claude need |
|---|---|
| L4-01, L4-02, L4-03 (payments and OTP live) | An email provider key on staging (Brevo needs one verified sender address, no domain; Resend needs a domain), Razorpay **TEST** keys on staging, the webhook added in Razorpay, a seeded staging database. |
| T2-01, T3-03, T1-02, T4-09 (live checks) | The staging seed (`seed_staging` output last 10 lines, no connection string). |
| X-01, F1-01, T1-01, A-06 (production current) | Your explicit OK for a production deploy, a backup first (X-06), `ALLOWED_HOSTS` and `DEBUG` set on Render, then staging-first checks. |
| F2-01, F2-02, L4-07 (see failures) | A free Sentry account (two projects) and two uptime monitors. Free. |
| T4-01 (owners can use the admin site) | A host for the Next.js admin and three build variables (names in DEPLOY.md). |
| X-06, X-07 (backups, always-on) | **PAID:** Supabase Pro (backups, from $25/month per its pricing page) and Render always-on (Starter about $7/month, confirm). Free alternative for backups: an `age` key pair and two GitHub secrets (RELEASE.md). |
| F7-01, F7-04, F7-05 (a measured capacity) | Your decision on the instance size to test; the staging database URL on your laptop for the seed (never the production one); two staging variables for Pass B (LOADTEST.md). |
| F7-02, F7-06 (Play) | An application id you choose, an upload keystore you make and back up, a Google Play account, a privacy-policy page (docs/ANDROID_RELEASE.md in the app repo). |
| L4-05 (clean-up job) | **PAID:** a Render cron job (about $1/month, confirm). |
| X-08 (Play Store) | A final application id, a signing keystore kept outside git, a Play Console account (one-time fee, confirm), F7. |
| L4-06 | One log line from production or staging showing `xff_hops` (no addresses in it). |

---

# Gaps by phase

Columns: **ID** · what is missing or ignored · **why** · **impact** · **how it affects us** · **status**.

## P. Before the playbook (Sept 2026: Razorpay in the app, local setup, secrets)

| ID | Gap | Why | Impact | Effect | Status |
|---|---|---|---|---|---|
| P-01 | The app's Razorpay flow (UPI intent and card, `razorpay_flutter`, confirming screen) has no recorded device test with a real payment. UPI deep links are mobile-only and the web build shows a message instead. | HUMAN, UNVERIFIED | High | Money flow unproven end to end on a phone. | Open |
| P-02 | `SECRET_KEY` printing was removed in code (PR #2). The rotation on Render was never confirmed. Whether production still prints it depends on its last deploy, which is unknown. | CHOICE (security ignored 2026-10-11) | Moderate | A leaked key lets someone forge sessions. Pre-launch with few users. | Open, accepted. **Phase 2 (2026-10-29):** Phase 2: see G2-01: the old committed `.env` evidence makes rotation a launch step (checklist step 0). |
| P-03 | On 2026-10-06 three migrations were unapplied on the shared Supabase database (`hostels.0004`, `payments.0004`, `rooms.0004`) and approval was asked. The outcome was not recorded, so the schema state of production versus its code is unknown. | HUMAN, UNVERIFIED | High (at deploy) | A deploy or a restore may fail or lose columns unless checked. | Open. **Phase 2 (2026-10-29):** Phase 2: the expected migration list and a read-only SQL query for the founder are in the checklist (step 8.1). The live state is still unknown. |
| P-04 | There are no automated backups (stated 2026-10-06). | PAID | High | Any data loss is permanent. Same as X-06. | Open. **Phase 2 (2026-10-29):** Phase 2: see X-06. |
| P-05 | Render free sleeps after 15 minutes and takes 30 to 60 seconds to wake. | PAID | Moderate | First request after idle looks broken. Same as F6-02. | Open. **Phase 2 (2026-10-29):** Phase 2: see F1-04. |
| P-06 | Phone testing needs the PC's LAN IP and a firewall rule for port 8000 (needs admin). | HUMAN | Low | Dev convenience only. | Open |

## F0. Baseline (Lean Core F0 as written was never run)

| ID | Gap | Why | Impact | Effect | Status |
|---|---|---|---|---|---|
| F0-01 | No `hh-baseline/` folder, no timing script, no `BASELINE.md`, no cold-start time, no database round-trip measure. We only did a git baseline check and tests. Render plan, region, start command and Python version of production are unknown. | DEFERRED, HUMAN | Moderate | Decisions such as "move the database closer to Render" rest on a guess. F5 Part 1 measured query counts and headers only. | Open |
| F0-02 | A stash labelled "temp before filter-branch" suggests a past history rewrite to remove a secret. Whether secrets were rotated is unknown. | CHOICE | Low | Old secrets could still exist in clones. | Open, accepted. **Phase 2 (2026-10-29):** Phase 2: see G2-01. |
| F0-03 | `db.sqlite3`, `django.log` and a data dump were tracked in git. They were untracked in F1, but history was not purged, and both repos are **public**. | CHOICE | Moderate | Possible personal data in public history. Needs a coordinated history rewrite and secret rotation. | Open, accepted. **Phase 2 (2026-10-29):** Phase 2: the newest non-empty committed `db.sqlite3` held 3 owner accounts, 1 hostel and no bookings; whether they are real people is the founder's call (checklist step 0). History rewrite not done. |
| F0-04 | The manual scripts in `backend/sele tests/` hit live endpoints and were never run or reviewed. One contains the Cloudinary cloud name and preset (not secrets). | DEFERRED | Low | Clutter and risk of someone running them against production. | Open |

## F1. Define production

| ID | Gap | Why | Impact | Effect | Status |
|---|---|---|---|---|---|
| F1-01 | Production does not run F1: debug routes are live, no health checks, DEBUG was True, `ALLOWED_HOSTS` unchecked. | HUMAN | High at launch, Moderate today | Debug information exposed, settings unsafe. Same root as X-01. | Open. **Phase 2 (2026-10-29):** Phase 2: re-checked 2026-10-29: `/api/v1/debug-logs/` still answers 200 on production. Closed only by the deploy (X-01). |
| F1-02 | Secret rotation after exposure in git and logs was skipped by choice. | CHOICE | Moderate | See P-02, F0-03. | Open, accepted. **Phase 2 (2026-10-29):** Phase 2: see G2-01 (checklist step 0). |
| F1-03 | Both repos are public (checked 2026-10-18). | CHOICE | Moderate | Source code and history readable by anyone. | Open, accepted |
| F1-04 | Render plan stays free: sleeps, blocks SMTP, 750 shared hours. | PAID | Moderate | See P-05, L4-02. | Open. **Phase 2 (2026-10-29):** Phase 2: plan decision is checklist step 2 (Phase 1 measured a 42.4 s wake on staging). Plans not changed in `render.yaml`. |
| F1-05 | Phone-number OTP (Twilio) is not integrated; phone sign-up and forgot-password answer 503 outside development. | FUTURE | Moderate | Users who choose the phone option cannot register. | Open |
| F1-06 | HSTS is off (`SECURE_HSTS_SECONDS=0`) until HTTPS is proven. | CHOICE | Low | Browsers may use plain HTTP on first visit. | Open, accepted. **Phase 2 (2026-10-29):** Phase 2: recommended value and the condition (HTTPS proven on the final domain) are in the checklist; stays 0. |
| F1-07 | Gunicorn was verified only through staging. The worker count in Render logs and rollback on Render were never tested. | UNVERIFIED | Low | Config values may differ from what runs. | Open. **Phase 2 (2026-10-29):** Phase 2: staging rollback rehearsal added to the checklist (8.3); not done. |
| F1-08 | The AGENTS and CLAUDE files inside `hostel-hunt-admin-next/` were left stale. | DEFERRED | Low | Misleading docs for the admin site. | Open |
| F1-09 | Local Python is 3.14 while Render and CI use 3.13.5. | DEFERRED | Low | A bug could appear only on one version. | Open |

## F2. Observe

| ID | Gap | Why | Impact | Effect | Status |
|---|---|---|---|---|---|
| F2-01 | No Sentry project or DSN exists, so no error is reported from the backend or the app. No test event was ever delivered. | HUMAN (free) | Moderate | Crashes and flagged payments (L4-07) go unnoticed. | Open. **Phase 2 (2026-10-29):** Phase 2: the Sentry alert rules are written (`backend/docs/ALERTS.md`), set-up is checklist step 3. Still no project or DSN. |
| F2-02 | No uptime monitors on `/healthz` and `/readyz`. Do not monitor staging (it must sleep to save hours). | HUMAN (free) | Moderate | An outage is found by users first. | Open. **Phase 2 (2026-10-29):** Phase 2: monitors specified (ALERTS 5 and 6, checklist step 4); none created. Staging must not be monitored. |
| F2-03 | `pg_stat_statements` is not confirmed enabled in Supabase. | HUMAN | Low | F5 index decisions lack real query data. | Open. **Phase 2 (2026-10-29):** Phase 2: how to enable and check it is in checklist step 3; needs a reachable database, Phase 3 reads it. |
| F2-04 | Production runs old code, so it has no request log and no `db_ms`. | see X-01 | Moderate | We cannot measure production latency or the database distance. | Open. **Phase 2 (2026-10-29):** Phase 2: solved by the production deploy (X-01); checklist step 9 records `db_ms` and `xff_hops`. |
| F2-05 | App builds are not obfuscated, so no symbol upload is set up. | DEFERRED | Low | Stack traces readable, which is fine for now. | Open. **Phase 2 (2026-10-29):** Phase 2: not touched (stays LATER). |
| F2-06 | Android build warns that three plugins apply the Kotlin Gradle plugin a future Flutter may reject. | DEFERRED | Low | A future Flutter upgrade may break the build. | Open. **Phase 2 (2026-10-29):** Phase 2: not touched (stays LATER). |
| F2-07 | Sentry performance tracing is off (sample rate 0). The Flutter SDK's PII behaviour is assumed, not proven. | DEFERRED | Low | No slow-request view in Sentry. | Open. **Phase 2 (2026-10-29):** Phase 2: checklist step 3 recommends 0.1 once wanted; stays 0 until the founder sets it. No personal-data option is on. |
| F2-08 | The release tag from `RENDER_GIT_COMMIT` was never seen on a real Render run. | UNVERIFIED | Low | Events may lack a version. | Open. **Phase 2 (2026-10-29):** Phase 2: the chain `GIT_COMMIT` to settings to Sentry options is now tested (`test_phase2.ReleaseTagTests`) and the cron sets `GIT_COMMIT` too. Never seen on a real Render run; checklist step 9 checks the log field. |

## F3. Change pipeline

| ID | Gap | Why | Impact | Effect | Status |
|---|---|---|---|---|---|
| F3-01 | **Branch protection is off** in both repos (checked 2026-10-18: "Branch not protected"). Nothing enforces a green CI before merging to `main`. | HUMAN | Moderate | A red change could reach `main` and auto-deploy to staging. | Open. **Phase 2 (2026-10-29):** Phase 2: checklist step 6 gives the exact check names; still off (re-checked in Phase 1). |
| F3-02 | **The laptop `.env` points at the production database** (region checked, no secret read) with DEBUG on. | CHOICE | High | A local `runserver`, `migrate` or script changes production data. | Open, accepted |
| F3-03 | The staging seed never landed (command ran but staging stayed empty; the last 10 lines of its output were never sent). | HUMAN | Moderate | All authenticated live checks are blocked (T2-01, T3-03, T1-02, T4-09, L4-01). | Open |
| F3-04 | The app analyzer ratchet sits at 61 to 64 issues (warnings and infos), never cleaned. | DEFERRED | Low | Quality debt. | Open |
| F3-05 | About 28 plain `APIView` endpoints have no serializer, so `schema.yml` omits them. The contract test covers their routes only, not their response shapes. | DEFERRED | Low | A response-shape change there is not caught by CI. | Open |
| F3-06 | The admin site's CI has no ESLint (its config was already broken). | DEFERRED | Low | Style and some bug classes unchecked. | Open |
| F3-07 | The app's CI does **not** build an APK. A broken plugin version (`permission_handler` 13.0.2) passed CI and failed locally. | DEFERRED | Moderate | Android build breakage shows up late. | Open |
| F3-08 | CI tests on Postgres 16; Supabase runs 17.x. | DEFERRED | Low | Rare version differences. | Open |
| F3-09 | `render.yaml` is a **reference** only. Dashboard settings are copied by hand, so they drift (F4 added email variables and a cron entry that exist only in the file). | HUMAN | Moderate | The live service can differ from the repo without anyone noticing. | Open. **Phase 2 (2026-10-29):** Phase 2: `render.yaml` reconciled with the code (cron variables and start command, list of names that must not exist on production). The comparison with the live dashboard is checklist step 2a and is not done. |
| F3-10 | Render's 750 free hours are shared by all free services. Two always-on services would not fit. | PAID | Low | Staging must be allowed to sleep. | Open |

## A. The "F4" of 2026-10-11 (11 broken or ignored API calls; our own name, not the playbook's F4)

| ID | Gap | Why | Impact | Effect | Status |
|---|---|---|---|---|---|
| A-01 | Changing email or phone in the profile is refused ("needs verification, which isn't available yet"). | FUTURE | Low | Users cannot change contact details. | Open |
| A-02 | The admin Payments page is read-only. The old "Add Record" and "Mark Paid" buttons were removed because no model exists for an offline rent ledger. | FUTURE | Moderate | Owners cannot record offline payments there (they can mark a booking paid instead). | Open |
| A-03 | Photo upload to Cloudinary was tested against a mock only. | HUMAN, UNVERIFIED | Moderate | The first real upload may fail (preset, limits). | Open |
| A-04 | The admin Payments page and notice delete were type-checked and built but never opened in a browser. | UNVERIFIED | Low | Possible UI bugs. | Open |
| A-05 | GitHub Pages turned out to be enabled on the backend repo. | HUMAN | Low | An unintended public site build. | Open |
| A-06 | Not live on production, including migration `owners.0005`. | see X-01 | High at deploy | See X-01. | Open. **Phase 2 (2026-10-29):** Phase 2: see X-01. |
| A-07 | `search` and `amenity` filter only the public list, not the owner's own list. | DEFERRED | Low | Owners cannot search their own hostels. | Open |

## T1. Location, search, hostel list

| ID | Gap | Why | Impact | Effect | Status |
|---|---|---|---|---|---|
| T1-01 | Production has no T1: its migrations (`hostels` 0004 to 0006 and older pending ones) did not run, and **Test City and Bengaluru hostels are still in the live list**. `deactivate_test_hostels` was never run on production (it needs approval). | HUMAN | Moderate (High if users meet test data) | Real users would see test data and unfiltered lists. | Open |
| T1-02 | City and locality filtering, paging and the empty state were never seen on real data (staging is empty). | HUMAN, UNVERIFIED | Moderate | Possible surprises on first real data. | Open |
| T1-03 | "Auto Detect" location is hidden behind `ENABLE_AUTO_DETECT`; the manifest has no location permission. Live GPS is out of scope by product decision. | FUTURE | Low | Users pick city and locality by hand. | Open |
| T1-04 | No locality aliases exist, and existing hostels carry the word "Unknown" as locality. Spelling variants (for example Dilsuknagar and Dilsukhnagar) need staff to add aliases in the Django admin. | HUMAN | Moderate | Search and filters miss variant spellings until data is cleaned. | Open |
| T1-05 | Localities are staff-managed only. Owners cannot add a new locality from the wizard. | CHOICE | Moderate | Owner onboarding needs staff help for new areas. | Open |
| T1-06 | Failures when saving the chosen location are reported to Sentry only (and Sentry is not set up, F2-01). The user sees nothing. | DEFERRED | Low | A silent failure to remember the city. | Open |
| T1-07 | The old `city` and `locality` text columns on hostels are kept "for one release" and need a later cleanup migration. | DEFERRED | Low | Tech debt, two sources of truth. | Open |

## T2. Errors, profile, photo upload

| ID | Gap | Why | Impact | Effect | Status |
|---|---|---|---|---|---|
| T2-01 | The live authenticated checks never ran: profile edit, refused fields, counts, Cloudinary photo, 405/401 shapes. The check script is ready; it waits for the seed. | HUMAN | Moderate | Authenticated behaviour proven by tests only. | Open |
| T2-02 | The device test script (photo pick, progress, cancel, offline retry, contact dialog, log out and in as another user) was not run. | HUMAN | Moderate | Screens may differ from what tests assume. | Open |
| T2-03 | Whether the Cloudinary variables are set on **staging** was reported as done by the developer on 2026-10-15 but never checked live (an upload answers 503 if missing). | UNVERIFIED | Low | Photo upload may be off. | Open |
| T2-04 | The Cloudinary upload preset is **unsigned**: anyone who knows the cloud name and preset can upload to the account. Monthly credits are limited (confirm on the pricing page). | CHOICE, PAID | Moderate | Storage abuse and cost. | Open, accepted |
| T2-05 | The old local-disk `profile_photo` field still exists. Old photos were never migrated. | DEFERRED | Low | Leftover field. | Open |
| T2-06 | The student stats count only bookings linked to the account; anonymous and guest bookings are not counted. | CHOICE | Low | Guests see nothing in their stats. | Open |

## T3. Voice search, saved hostels, detail screens

| ID | Gap | Why | Impact | Effect | Status |
|---|---|---|---|---|---|
| T3-01 | Voice search was never tried on a phone: permission states, "no match", languages, no speech service. Tested with a fake speech engine only. | HUMAN, UNVERIFIED | Moderate | The headline feature is unproven. | Open |
| T3-02 | Hindi and Telugu voice search finds nothing until locality aliases exist in those scripts (T1-04). | HUMAN | Low | The language options look broken. | Open |
| T3-03 | Hearts and the Saved page were not run against real data (empty staging) or on a phone. | HUMAN, UNVERIFIED | Moderate | Rollback and paging unproven live. | Open |
| T3-04 | A student **cannot cancel a booking**: the backend has no student cancel route. The fake Cancel button was removed. | FUTURE | Moderate | Students must contact owners outside the app. | Open |
| T3-05 | "Recently Viewed" shows "Coming soon". | FUTURE | Low | A visible placeholder. | Open |
| T3-06 | iOS usage texts were added but iOS was never built or tested. | DEFERRED | Low | Unknown iOS behaviour. | Open |
| T3-07 | `permission_handler` is pinned to 12.0.3 because 13 needs Android SDK 37. | DEFERRED | Low | Upgrade debt. | Open |

## T4. Admin analytics and data safety

| ID | Gap | Why | Impact | Effect | Status |
|---|---|---|---|---|---|
| T4-01 | The admin site is not hosted anywhere (statement of 2026-10-10; confirm). `NEXT_PUBLIC_API_URL` and the two Cloudinary variables are not set on any host. It runs only on the developer's machine. | INFRA, HUMAN | Moderate to High | Owners cannot manage hostels, bookings and payments remotely. | Open |
| T4-02 | No admin page was opened in a browser against a live server; the refresh and log-out flows are unproven. | HUMAN, UNVERIFIED | Moderate | Possible UI or login bugs. | Open |
| T4-03 | 8 legacy bookings have no student account (7 have no phone), so `link_legacy_bookings` would link none. They stay visible to the owner and staff only. | CHOICE | Low | Old bookings never reach a student. | Open |
| T4-04 | Media uploaded by an abandoned hostel wizard stays unclaimed and cannot be deleted by the owner. | DEFERRED | Low | Orphaned files in Cloudinary. | Open |
| T4-05 | Room photos collected by the wizard are thrown away by the backend; no feature stores them. | FUTURE | Low | Owners think they uploaded room photos. | Open |
| T4-06 | The booking heatmap uses the latest 100 bookings, not a full year. | DEFERRED | Low | Misleading for busy hostels. | Open |
| T4-07 | The dashboard totals were not compared with the database on a known dataset. | UNVERIFIED | Low | Possible miscount. | Open |
| T4-08 | Admin tokens live in `localStorage`. | CHOICE | Low | Standard browser-storage risk. | Open, accepted |

## L4. Lean Core F4 (safe request path and payments, merged 2026-10-18)

| ID | Gap | Why | Impact | Effect | Status |
|---|---|---|---|---|---|
| L4-01 | The staging payment test (`backend/docs/PAYMENT_TEST.md`) was never run. | HUMAN | High | Confirm, refund, replay and flagging proven by tests only. | Open |
| L4-02 | **No email provider is configured.** The new code has no sender on staging or production, and Render free blocks SMTP. Email sign-up and forgot-password cannot send a code. | HUMAN, PAID | High | New users cannot register by email. | Open |
| L4-03 | Brevo's single-sender route is untested; whether a new account can use its transactional API without a domain is unconfirmed. Resend needs a verified domain and none is planned. | UNVERIFIED, INFRA | Moderate | The chosen provider may refuse to send. A paid Render instance (SMTP allowed) is the fallback. | Open |
| L4-04 | Razorpay **TEST** keys and the webhook are not set up on staging. Live-mode readiness (keys, KYC, webhook) on production is unverified. UPI intent in test mode is unproven. | HUMAN | High | No real or test payment can be exercised on staging. | Open |
| L4-05 | The Render cron job for `cleanup_expired` is not created. Old OTP rows, webhook ids and tokens are not purged. Holds still expire when read. | PAID | Low to Moderate | Tables slowly grow. | Open. **Phase 2 (2026-10-29):** Phase 2: the cron is wrapped with `ping_heartbeat` and has Sentry and heartbeat variables in `render.yaml`. The job itself is not created (checklist step 5). |
| L4-06 | `TRUSTED_PROXY_COUNT` defaults to 1 but Render's real proxy chain is unverified. If the last forwarded address were a shared edge address, all users would share one 20-per-minute send limit. | UNVERIFIED | Moderate | Could throttle sign-ups. Check one `xff_hops` log line. | Open |
| L4-07 | A payment captured but not honoured (late capture, wrong amount, duplicate, unknown refund) is only flagged `needs_review` and logged. There is no alert (Sentry is not set up, F2-01) and no student-facing explanation: the student sees "failed". | DEFERRED | Moderate | Money could sit unrefunded unnoticed. | Open. **Phase 2 (2026-10-29):** Phase 2: a flagged payment and an unknown-outcome refund now raise one Sentry alert with no personal data (`test_phase2.PaymentFlaggedAlertTests`; payment code unchanged). Reaches nobody until the Sentry project and rule exist (F2-01). The student still sees failed. |
| L4-08 | The owner action `/bookings/<id>/verify/` marks an online booking paid without a Razorpay payment. Left unchanged by decision. | CHOICE | Low | An owner override with no money behind it. | Open, accepted |
| L4-09 | A refund whose outcome is unknown stays RESERVED and needs a person; there is no reconcile job against Razorpay. | DEFERRED | Low to Moderate | Manual follow-up. | Open |
| L4-10 | Password login has no limit beyond the default 60 per minute per address. | CHOICE | Low | Guessing attempts are not slowed. | Open, accepted |
| L4-11 | The second OTP app (`apps.otp_auth`) is reduced to a proxy model and still installed. | DEFERRED | Low | Dead code to delete later. | Open |
| L4-12 | **A paid bed never becomes free again.** Nothing releases the bed or updates the booking after a full refund, a cancellation or a checkout (no vacate flow exists). Offline "mark paid" now also takes a bed. | FUTURE | High at launch | Beds stay unavailable forever; owners cannot re-let them. Found by reading the code on 2026-10-18; not yet reproduced by a test. | Open |

## F5. Data path and payload (built 2026-10-18; evidence in `backend/docs/AFTER-F5.md`)

| ID | Gap | Why | Impact | Effect | Status |
|---|---|---|---|---|---|
| F5-01 | The distance from Render (Singapore) to the production database (Mumbai) is **unmeasured**, because production has no request log yet (F2-04). The rule to decide is written in AFTER-F5.md (40 ms or more per query and database time above half of the request means move it). | HUMAN | Moderate | The query cuts help whatever the distance is, but we cannot say whether moving the database is worth it. | Open |
| F5-02 | The statement timeout (`DB_STATEMENT_TIMEOUT_MS=25000`) is in `render.yaml` only. Render's dashboard start command must be edited by hand on staging and production (same drift risk as F3-09). | HUMAN | Low | A runaway query is not cut off until then. | Open. **Phase 2 (2026-10-29):** Phase 2: how to confirm it is live is recorded (checklist 2a: start command text and the `==> Running` line in the deploy log). Not yet confirmed. |
| F5-03 | Image savings were **not measured** (no staging photo, no Cloudinary access). The sized URLs are tested; the byte saving is an expectation. Cloudinary credits will be used by the transformations (X-09). | HUMAN, UNVERIFIED | Low | Possible surprise in data use or credits. | Open |
| F5-04 | The cities and localities cache is per worker for 60 s: a bulk update (the deactivate command) or a change saved on the other worker shows after up to a minute. | CHOICE | Low | A just-added locality can be missing briefly on one worker. | Open, accepted |
| F5-05 | Cache headers (`ETag`, `max-age`) only help once something caches: a browser, a CDN, or the app's HTTP cache (F6). Render's edge does not cache JSON by itself. | DEFERRED | Low | No bandwidth saving yet. | Open |
| F5-06 | A room deactivated by a hostel update (it had bookings) still counts in the owner's own views and in the stored `total_rooms`/`total_beds` numbers, and the admin site has no button to reactivate it other than sending it again. | DEFERRED | Low | Owners may wonder where a room went. | Open |
| F5-07 | Owner queries grow linearly with bookings (18 to 31 ms at 60,000 on a local database). No index helped. Revisit when one dashboard request shows `db_ms` above about 100 or bookings pass roughly 200,000. | DEFERRED | Low | Slower dashboards at larger sizes. | Open |
| F5-08 | The database pool has 3 to 4 slots of headroom (11 to 12 of 15 in use). Any extra script or a second cron job uses it. | DEFERRED | Moderate | An earlier `EMAXCONNSESSION` error can return. | Open |

## F6 and F7 (F6 built 2026-10-19; F7 not started)

F6-01 and F6-02 are closed (see Closed gaps C-14, C-15). C-16 closed the decode and asset part of F6-03.

| ID | Gap | Why | Impact | Effect | Status |
|---|---|---|---|---|---|
| F6-03 | Pictures have no disk cache: `Image.network` keeps decoded pictures in memory only, so a cold start downloads them again. `cached_network_image` was deliberately not added (new dependency, disk growth to manage). | DEFERRED | Low to Moderate | More data use and slower first scroll after a restart. | Open |
| F6-04 | Heavy card rendering (blur, shadows) is a hypothesis until profiled (G34). Nothing was changed. Needs profile-mode numbers from a phone (steps in `docs/F6-PHONE-RESILIENCE.md`). | HUMAN | Low | Possible dropped frames. | Open |
| F6-05 | F6 was proven by tests and a debug APK build only. The payment resume, the waking banner and the offline copy were never run on a phone or against staging. | HUMAN | Moderate | Bugs tests cannot see (Android back stack, process kill timing, UPI app return). | Open |
| F6-06 | Saved copies cover only the hostel list, cities and localities. Search results, hostel detail, rooms, saved list and bookings show an error with Retry when offline. Personal data is deliberately never cached. | CHOICE | Low | Offline browsing is partial. | Open, accepted |
| F6-07 | A card payment whose verify answer is lost relies on the Razorpay webhook to confirm. Until the webhook is configured on staging (L4-01) the status screen stays at "Still Waiting" for such a payment. | HUMAN | Moderate | A paid student sees "Still Waiting" until the webhook arrives. | Open |
| F6-08 | The payment method icons load from three third-party sites (flaticon, uxwing, iconscout). If one moves or blocks, the app falls back to a built-in icon. | DEFERRED | Low | Cosmetic. | Open |
| F6-09 | The "payment waiting" banner shows on the home screen only, and a note older than 24 hours is dropped. A student who never returns to home sees it only on the payment screen. | CHOICE | Low | A late confirmation is found the next time home opens. | Open, accepted |
| F7-01 | The load test **tooling** exists (`tools/loadtest`, `LOADTEST.md`) but no run on staging has happened, so "thousands of users" is still unmeasured (G25). The only run (#0) was on a laptop and proves the script, not capacity. | HUMAN | Moderate | Capacity unknown. Blocked by F7-04. | Open |
| F7-02 | Android release blockers that remain after F7: the application id is still the placeholder (you must choose one, it cannot change after the first upload); no real upload keystore exists; the launcher icon is Flutter's default. The build refuses to make a Play bundle until the id and key are set. | HUMAN | High at release | No Play upload possible yet. | Open |
| F7-03 | `RELEASE.md` exists, but the backup has never run (its two secrets are not set), the restore rehearsal has only been done on a laptop, and Render rollback has never been tried. | HUMAN | High | Same as X-06. | Open. **Phase 2 (2026-10-29):** Phase 2: see X-06. Staging rollback rehearsal added to checklist step 8.3; not done. |
| F7-04 | **Nothing can be load-tested yet:** the instance size to pay for is undecided, the staging seed has never landed (F3-03; whether Render's free plan has a shell is unverified, so the plan seeds from your laptop), staging has no email provider or Razorpay TEST keys, and two environment variables must be set on staging for Pass B. | HUMAN | Moderate | The measured answer waits on you. | Open |
| F7-05 | Two likely bottlenecks are unmeasured hypotheses: a login costs about 1.6 s of CPU on this laptop (PBKDF2 with 1,000,000 rounds), so a login rush on a small server could stall it; and public browsing is limited to 60 requests a minute per address, counted per worker, so a campus sharing one address could be throttled. | UNVERIFIED | Moderate to High | Slow or refused requests at a launch rush. | Open |
| F7-06 | Play Console is not started: no account, no store listing, no privacy-policy page (needed, GitHub Pages is free), no data-safety form. I could not verify Google's current rules for new accounts (a closed-testing requirement I recall). | HUMAN | High at release | Cannot publish. | Open |
| F7-07 | R8 shrinking and the new `<queries>` entries (UPI, https) were proven only by a successful bundle build and file checks, never on a phone. Shrinking could remove something Razorpay or speech search needs at run time. | UNVERIFIED | Moderate | A release-only crash or a dead UPI button. | Open |
| F7-08 | No "update required" screen in the app, so an old, broken app cannot be forced to update. | FUTURE | Low to Moderate | Bad versions linger. | Open |
| F7-09 | The Brevo free plan's 300 sends a day is from its help page; whether transactional OTP mail counts towards it is unconfirmed. At launch volume this may cap new sign-ups (L4-02). | UNVERIFIED | Moderate | Sign-up codes stop arriving after the daily cap. | Open |
| F7-10 | Backend folder holds old helper scripts: `reset_db*.py` (guarded), `query_db.py` and `sele tests/` (some aimed at production). Not routed, but they ship with the code. | DEFERRED | Low | Clutter and an accident risk. | Open |

---

## G. Found in the stay plan's Phase 1 and 2 (2026-10-29)

Evidence for G1 is in `backend/docs/STAY_BASELINE.md` and `backend/docs/GAP_TRIAGE.md`.

| ID | Gap | Why | Impact | Effect | Status |
|---|---|---|---|---|---|
| G1-01 | The backup workflow file was invalid YAML (`backup.yml` line 32), so it could never run, even with its secrets. | (fixed in code) | High | No backup possible. | Fixed on the Phase 2 branch (`actionlint` clean, `test_phase2.BackupWorkflowTests`); it now fails on purpose until the secrets exist. Close after the merge shows it in GitHub's workflow list and a manual run succeeds (X-06). |
| G1-02 | `BookingViewSet.verify` has no status guard (cancelled, rejected or paid bookings can be set to paid again). | DEFERRED | High for Phase 5 | A repeated call would create duplicate stays and dues. | Open |
| G1-03 | `confirm_payment` and the hold logic cannot be reused for rent: the 15-minute age rule fails a payment with no live hold, `confirm_payment` flags "bed already taken", and `create-order` refuses paid bookings. | DEFERRED | High for Phase 6 | A rent payment would be failed or flagged. | Open |
| G1-04 | Offline revenue trusts `Booking.amount`, which any anonymous client can set. | DEFERRED | Moderate | Dashboard totals can be wrong. | Open |
| G1-05 | The cleanup cron lacked the variables later work needs. | DEFERRED | Moderate | Reminder email, Razorpay and push work would fail there. | Open. Partly done in Phase 2 (Sentry and heartbeat added); email, Razorpay and push variables are added by the phase that needs them. |
| G1-06 | Webhook-confirmed payments are always recorded as method CARD. | DEFERRED | Low | Wrong method label only. | Open |
| G1-07 | A booking can become paid in Django admin or the load-test seed with no bed and no payment. | DEFERRED | Low | Staff-only; no stay would be created for it later. | Open |
| G1-08 | Two web instances do not fit the 15-slot database pool (16 needed; a deploy overlap can exceed 15). | PAID | High at scale | Scaling out fails first on connections. | Open |
| G1-09 | The backend test suite takes 7.5 to 13.4 minutes on the laptop (CI: 2.8 minutes). | DEFERRED | Low | Slow local phases. | Open |
| G1-10 | `Room.available_beds` is never updated after a payment, and `Bed.is_available` is never set back to True. | FUTURE | Moderate | A room never shows as full; a freed bed would not show as free (see L4-12). | Open |
| G1-11 | Nothing in the code ever sets a booking to `cancelled`. | FUTURE | Low | Several refusals of cancelled bookings are unreachable. | Open |
| G1-12 | **The staging database was unreachable on 2026-10-29** (`/readyz` 503 and data endpoints 500 after 15 s; `/healthz` ok). Probably a paused free Supabase project. | HUMAN | High (blocks staging work) | No staging payment test, seed or load test. | Open; checklist step 0 |
| G2-01 | **Credentials in the public git history are still current.** An old committed `backend/.env` (5 commits in the backend repository, 3 in the app repository) held a filled `SECRET_KEY`, `DATABASE_URL` and `EMAIL_HOST_PASSWORD`. By hash comparison the backend repository's old database address and password, and old email password, equal those in the laptop `.env`, which points at the production database (F3-02). The default secret scanner (gitleaks) found nothing, so a clean scan proves nothing here. | HUMAN, CHOICE | High | Anyone can read the production database password from a public repository. | Open; rotate before the production deploy (checklist step 0). The founder's 2026-10-11 decision to ignore security hardening predates this evidence. |

# Cross-cutting gaps

| ID | Gap | Why | Impact | Effect | Status |
|---|---|---|---|---|---|
| X-01 | **Production is stale.** It runs code from before F1 (2026-10-10; its exact last deploy date is unknown), and these migrations are pending: `owners` 0005 and 0006, `hostels` 0004 to 0006, `payments` 0004 and 0005, `rooms` 0004 and 0005 (and anything older still unapplied). | HUMAN | High at launch, Moderate today | A first production deploy is a large, risky step. It needs a backup, staging first, and the owner's OK. | Open. **Phase 2 (2026-10-29):** Phase 2: the pending migrations were read and their SQL printed (all additive; the two renames are SQL no-ops; `backend/docs/MIGRATION_POLICY.md`). Deploy steps and `ops/post_deploy_check.py` are ready. Production re-checked 2026-10-29 (read-only GET): `/healthz` 404, `/readyz` 404, debug route 200. Needs the founder's deploy (checklist step 8). |
| X-02 | **Live-verification debt.** Phases T1 to T4 and F4 were proven by tests and CI, plus staging checks that need no login. No authenticated flow, device test or browser test exists. | HUMAN | Moderate | Bugs that tests cannot see will appear on first real use. | Open |
| X-03 | Staging has no data and no test users, so nothing authenticated can be tried there. | HUMAN | Moderate | Same cause as F3-03. | Open |
| X-04 | No branch protection (F3-01) and no code review other than CI. Solo developer. | HUMAN | Moderate | Mistakes merge unreviewed. | Open |
| X-05 | Both repositories are public, with history that once held a database file and logs. | CHOICE | Moderate | See F0-03. | Open, accepted |
| X-06 | **No backups and no restore rehearsal.** The free Supabase plan has no daily backups. A daily encrypted-dump workflow now exists but is switched off until you add its two secrets; see F7-03. | PAID, HUMAN | High | Permanent data loss if anything goes wrong. | Open. **Phase 2 (2026-10-29):** Phase 2: the backup workflow is fixed (it was invalid YAML, G1-01) and now FAILS until its two secrets exist. Secrets, first run and restore rehearsal are founder steps (checklist step 1). Still no backup. |
| X-07 | Supabase free projects pause after a week of inactivity (staging); the production plan is unconfirmed. | PAID | Moderate | A paused project looks like an outage. | Open. **Phase 2 (2026-10-29):** Phase 2: staging's database was found unreachable on 2026-10-29 (G1-12), probably this. Production plan decision is checklist step 2. |
| X-08 | The app has no Play Console entry and the application id is a placeholder (see F7-02, F7-06). The release build is now wired for your key and id. | INFRA, HUMAN | High at release | The first upload fixes the id for good. | Open |
| X-09 | Cloudinary free credits are limited and image transforms (F5-03) will consume them. | PAID | Low to Moderate | An overrun stops uploads or costs money. | Open |
| X-10 | Dependency drift: 52 Flutter packages have newer versions that the constraints block. | DEFERRED | Low | Upgrade work accumulates. | Open |

# Closed gaps (for reference)

| ID | Gap | Closed | Proof |
|---|---|---|---|
| C-01 | Hostel list cards showed no price or cover image (model read the wrong keys). | 2026-10-11 (F3) | Fixture test, merged. |
| C-02 | 11 broken or ignored API calls (profile edit, photo upload, my bookings, saved count, search and amenity filters, admin payments and notice delete). | 2026-10-11 | Contract test, merged, staging 401 shapes. |
| C-03 | City and locality filter ignored for logged-in users, unordered pages, two fetches at launch. | 2026-10-11 (T1) | 202 backend tests, 50 app tests. |
| C-04 | Admin pages read the wrong response shape and showed empty lists. | 2026-10-15 (T4) | 59 admin tests, failing-before proof. |
| C-05 | Students could see other students' bookings through a shared display name. | 2026-10-11 (T2) | Tests with two students sharing a name. |
| C-06 | Double tap on Pay returned 500; two confirmations could race; refunds and webhooks were not idempotent; late captures could pay one bed twice. | 2026-10-18 (F4) | 20 reproducing tests failing before, passing after; CI green. |
| C-07 | OTP hashing took about 0.6 s each; no attempt cap; spoofable throttle; send and verify shared one limit. | 2026-10-18 (F4) | Same. |
| C-08 | Outbound calls had no timeouts. | 2026-10-18 (F4) | Source-scan test in CI. |
| C-10 | Owner dashboard needed 9 queries, activity 12 (a lazy join per row). | 2026-10-18 (F5) | 4 and 2 queries, held by `assertNumQueries`-style tests that also compare every number. |
| C-11 | A hostel save was not one transaction, crashed with a 500 on an unknown room field, inserted rooms one by one, and an update deleted left-out rooms (with their beds, and their bookings lost the room). | 2026-10-18 (F5) | `test_f5.HostelSaveTests`. Rooms with bookings are deactivated, never deleted. |
| C-12 | No compression or cache headers in Django; public photos were raw originals; the places lists hit the database every time. | 2026-10-18 (F5) | `test_f5.HttpHeaderTests`, `ImageTests`, `ImageSerializerTests`. Byte saving unmeasured (F5-03). |
| C-13 | No database connect timeout. | 2026-10-18 (F5) | `DatabaseOptionTests`. |
| C-14 | (F6-01) The payment confirming screen could overlap polls, gave up at 75 s, "Try Again" could create a second order, and a killed app forgot a pending payment. | 2026-10-19 (F6) | `test/features/payments/` (27 tests): one question at a time with a time budget, Try Again asks the server first, no order while the first is undecided, note survives a simulated restart, cleared at Log Out. Not yet run on a phone (F6-05). |
| C-15 | (F6-02) No shared HTTP client, no retry or backoff, a timeout that did not close the socket, no waking message, a network error during token refresh logged the person out, concurrent 401s refreshed several times, no offline copy, every chip refetched. | 2026-10-19 (F6) | `test/core/http_transport_test.dart`, `api_service_resilience_test.dart`, `last_good_cache_test.dart`, `test/features/f6_resilience_test.dart`. GET retried and POST not; one refresh for concurrent 401s; refresh network error keeps the session. |
| C-16 | (part of F6-03) Pictures decoded at full size; 4 unused or duplicate bundled pictures; card entrance delay grew with list position. | 2026-10-19 (F6) | `cacheWidth` on every network picture (tests assert `ResizeImage`), `images/` 7.9 MB to 4.7 MB, a test fails if a bundled picture is unused or duplicated. Disk cache still open (F6-03). |
| C-17 | (F7-02, part) Release build allowed plain HTTP, was signed with the debug key, had no shrinking, a `rohii_hostel_hunt` app name, backup of saved logins on, and no `<queries>` entries so UPI and WhatsApp links could report "no app" on Android 11+. | 2026-10-19 (F7) | `android_release_config_test.dart`; a signed `bundleRelease` built with a throwaway key and test id (59.2 MB, of which 29.2 MB are debug symbols not sent to phones); the bundle task refuses the debug key and the `com.example` id. Not yet on a phone (F7-07). |
| C-18 | (part of F7-02) 4.7 MB of bundled images. | 2026-10-19 (F7) | 2.0 MB after resizing the five logos to the largest size drawn. |
| C-19 | (part of F7-01, F7-03) No load-test tooling and no backup, restore or release documents. | 2026-10-19 (F7) | `test_f7.py` (33 tests): production refusal rules, thresholds, seed refusal outside staging, log summary, backup and restore script refusals; a local backup, restore and `verify_restore` rehearsal that turns FAIL when rows are removed. The runs themselves are F7-01 and F7-03. |
| C-09 | Debug routes, tracebacks and OTP values leaked in responses. | 2026-10-10 (F1) on `main` and staging | Tests. Still live on production (F1-01). |

# Changing this file

- New gap: add a row with the next free number in its phase, a cause tag, an impact, and what it affects.
- Closing a gap: set Status to Closed, move the row to "Closed gaps" with the date and the proof, never delete it.
- Review the impact column at each phase end. Some items that are Low today become High at launch.
