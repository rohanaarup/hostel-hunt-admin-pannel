# Founder actions, deferred to the end

Rule (set by the founder on 2026-10-29): build everything that can be done by prompt first. Steps only the founder can do (dashboards, accounts, keys, devices, money) are collected here and done together at the end. A step is raised during a phase only when that phase cannot go on without it.

Detailed instructions for most of these are in `FOUNDER_CHECKLIST_PROD.md` (steps in brackets). Names only; never put a secret value in this file.

**Status key:** Deferred = not needed by the next build phases; Before deploy = must be done before the production deploy; Blocking = stops a phase (none at the moment).

## From Phases 1 and 2 (2026-10-29)

| # | Action | Why | Needed by | Status | How to know it worked |
|---|---|---|---|---|---|
| 1 | Restore the paused staging Supabase project (`Hostel-hunt-staging`) | Staging database unreachable (G1-12); blocks every staging measurement and test | Phase 3 and 11 measurements, payment test, load test | Deferred | staging `/readyz` says ok |
| 2 | Rotate the production database password, the email password and `SECRET_KEY`; decide on Razorpay key [step 0] | Old values are in the public git history and still current (G2-01) | Before the production deploy | Before deploy (high priority; can be done any time earlier) | decision table in `FOUNDER_CHECKLIST_PROD.md` filled |
| 3 | Make the `age` key pair; add repo secrets `BACKUP_AGE_PUBLIC_KEY` and `BACKUP_DATABASE_URL`; run the backup once; restore rehearsal [step 1] | No backup exists (X-06); the workflow now fails until the secrets exist | Before the production deploy | Deferred | green backup run with an artifact; `RESULT: PASS` from verify_restore |
| 4 | Decide plan sizes: Render web (never sleeps), Supabase Pro, Render cron [step 2] | 42 s wake on free hosting; no automatic backups on free Supabase | Before go-live; Phase 3 sizing | Deferred | plans shown in the dashboards |
| 5 | Compare `render.yaml` with the Render dashboard (names, commands, statement timeout) [step 2a] | F3-09, F5-02 | Before the production deploy | Deferred | all lines ticked |
| 6 | Create the Sentry project, set `SENTRY_DSN`, create alert rules 1 to 4 [step 3] | No error reporting; the payment-flagged alert needs it | Before go-live | Deferred | test event and drill event arrive |
| 7 | Uptime monitors on production `/healthz` and `/readyz`, a heartbeat monitor for the cron [step 4] | Nobody is told about an outage | Before go-live | Deferred | test alerts reach the phone |
| 8 | Create the production cleanup cron job in Render [step 5] | L4-05; reminders later depend on a cron | After the production deploy | Deferred | heartbeat pings every 5 minutes |
| 9 | Turn on branch protection in both repositories [step 6] | F3-01 | Any time | Deferred | `gh api .../branches/main --jq .protected` prints true |
| 10 | Point the laptop `backend/.env` at local or staging, not production [step 7] | F3-02 | Any time (safety) | Deferred | printed host is not the production host |
| 11 | Production deploy of current `main`, then the post-deploy checks [steps 8, 9] | X-01, P-03, A-06, F1-01, T1-01 | The end | Deferred (last) | `post_deploy_check.py` ends `RESULT: PASS`; results pasted in `RELEASE.md` |

## From Phase 1 (needed only for the staging tests)

| # | Action | Why | Needed by | Status |
|---|---|---|---|---|
| 12 | Email provider on staging (Brevo or Resend), sender address verified (L4-02) | Students cannot sign up by email; payment test cannot start | Staging payment test, go-live | Deferred |
| 13 | Razorpay TEST keys and the webhook on staging (L4-04) | No payment can be tried on staging | Staging payment test, go-live | Deferred |
| 14 | Seed staging data (F3-03) and, for Pass B load tests, the two throttle variables on staging | Staging is empty | Load tests (Phase 3, 11) | Deferred |
| 15 | Paste Render and Supabase metrics and about 20 `hh.request` lines per route | C2 to C5 of `STAY_BASELINE.md` could not be measured | Phase 3, 11 | Deferred |
| 16 | Application id, upload keystore, Play Console account, privacy-policy page (F7-02, F7-06, X-08) | Cannot publish the Android app | Release | Deferred |
| 17 | Device runs: payment on a phone, F6 resilience script, R8/UPI check (P-01, F6-05, F7-07) | Proven by tests and a debug build only | Release | Deferred |

## Added by later phases

(none yet)
