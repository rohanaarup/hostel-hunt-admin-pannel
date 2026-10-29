# Releasing Hostel Hunt, and getting back from a bad release

Three parts: **release** (backend and app), **backups and restore**, **rollback**. A last page says **where to look**
when something is wrong. Everything here names environment variables but never holds their values.

Status of each step is in `KNOWN_GAPS.md`. Items marked **NOT DONE** have not been performed by anyone yet.

## 1. Environments

| | Staging | Production |
|---|---|---|
| Backend | Render service deployed from `main` after CI passes; `APP_ENV=staging` | Render service deployed **by hand** from a commit that already ran on staging |
| Database | Its own Supabase project | Its own Supabase project |
| Payments | Razorpay TEST keys (**NOT DONE**: not set yet) | Razorpay live keys (unverified) |
| App points at | `--dart-define=API_BASE_URL=...` | The built-in default (the production host) |

**Production is currently running old code** (KNOWN_GAPS X-01). The first production deploy is a large step. Do it
only with a fresh backup (section 3), staging proven first, and your explicit decision.

## 2. Release steps

### Backend

1. Merge to `main` through a pull request with green CI. Staging deploys by itself.
2. On staging: open `/healthz` (must say `"env":"staging"`) and `/readyz`; run the smoke test in `LOADTEST.md`;
   for payment changes run `backend/docs/PAYMENT_TEST.md`.
3. **Back up production first** (section 3, manual run). Do not continue without a dump you have checked.
4. Deploy the same commit to production in Render (Manual Deploy, choosing that commit). The build runs `migrate`.
5. Check `/healthz` says `production` and `/readyz` says ok, then look at the first requests in the Render log (section 5).
6. If anything is wrong: section 4.

Migrations must work with the **previous** code too (add things first, remove them in a later release), so that
rolling the code back never needs rolling the database back.

### App (Android)

One-time setup is in `docs/ANDROID_RELEASE.md` in the app repository (keystore, application id, Play Console).
Per release:

1. Raise the build number in `pubspec.yaml` (`version: 1.0.0+N`). Play rejects an upload whose number it has seen.
2. `flutter analyze` and `flutter test` must be green.
3. Build with the signing variables set (names in `docs/ANDROID_RELEASE.md`): `flutter build appbundle --release`.
4. Upload to **Internal testing** first. Install it from Play on a real phone and run the checks in `docs/F6-PHONE-RESILIENCE.md`.
5. Promote to production as a **staged rollout** (start at a small percentage), watching crashes and the backend log.

### Post-deploy checks (paste the results here after every production deploy)

Run `python backend/ops/post_deploy_check.py https://<host> --expect-env production` (read-only GET requests; `staging` for staging), then look at one `hh.request` line in the Render log.

| Date | Commit | Host | healthz | env | readyz | debug route 404 | `release` field set | `xff_hops` | Result | Done by |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-29 (before any Phase 2 deploy) | old code | production | 404 | n/a | 404 | **200 (route still live)** | n/a | n/a | FAIL (expected: production runs old code, KNOWN_GAPS X-01) | Claude, read-only GETs, status codes only |
| (pending) | | production | | | | | | | **NOT DONE: needs the founder's deploy** | |

Also record here, once: the date the rollback was rehearsed on staging (**NOT DONE**), and which of the pending migrations the production database already had (`FOUNDER_CHECKLIST_PROD.md` step 8.1, **NOT DONE**).

## 3. Backups and restore

### What exists

* `backend/ops/backup.sh`: an encrypted dump (pg_dump 17 in Docker, encrypted with the public half of an `age` key).
* `.github/workflows/backup.yml`: runs it every day at 03:00 India time and keeps the file as a workflow artifact for 30 days.
  It **fails on purpose** (a red run and an email) until the two secrets below exist, so a green run always means a backup was made. (Before 2026-10-29 the file was invalid YAML and could never run at all, KNOWN_GAPS G1-01; fixed in Phase 2.) **NOT DONE: no backup exists today.**
* `backend/ops/restore.sh` and `backend/ops/verify_restore.py`: restore into a database and prove the copy is complete.
* Supabase's own daily backups (kept 7 days) exist only on the Pro plan (supabase.com/pricing). They are the first
  line of defence once you pay; the encrypted dump is a second copy that you own.

The repository is public and artifacts of public repositories can be downloaded by any GitHub user, which is why the
dump is encrypted before upload. Without your private key the file is unreadable.

### Set it up (you, once)

1. Make the key pair. The private half goes in a password manager **and** one offline copy; losing it makes every backup useless.
   ```
   docker run --rm alpine:3.20 sh -c "apk add -q age >/dev/null && age-keygen"
   ```
   It prints a `# public key: age1...` line and an `AGE-SECRET-KEY-...` line. Save the secret line; never commit it or paste it into chat.
2. In the backend repository: Settings, Secrets and variables, Actions, add
   `BACKUP_AGE_PUBLIC_KEY` (the `age1...` line) and `BACKUP_DATABASE_URL`.
3. `BACKUP_DATABASE_URL` is the **session pooler** URL from the Supabase dashboard (the direct URL can need IPv6, which
   the GitHub runners may lack: unverified). It is a secret; GitHub hides it in logs.
4. Run the workflow once by hand (Actions, backup, Run workflow) and download the artifact to check it exists and is more than a few KB.

### Restore rehearsal (do once on staging, then after any big change)

1. Take a dump: `BACKUP_DATABASE_URL=<staging URL> BACKUP_AGE_PUBLIC_KEY=<age1...> bash backend/ops/backup.sh staging.dump.age`
2. Restore it into an **empty scratch database** (a second free Supabase project or a local Postgres), never into the live one:
   `AGE_IDENTITY_FILE=<path to private key file> RESTORE_CONFIRM=not-production bash backend/ops/restore.sh staging.dump.age "<scratch URL>"`
3. Prove it: `python backend/ops/verify_restore.py "<source URL>" "<scratch URL>"` must end with `RESULT: PASS`.
4. Point a local copy of the backend at the scratch database and open `/readyz`, log in and open a hostel.
5. Write the row below.

`restore.sh` refuses to run without `RESTORE_CONFIRM=not-production` because it **drops** every table in its target first.

| Date | Source to target | Dump size | Backup time | Restore time | verify_restore | Done by |
|---|---|---|---|---|---|---|
| 2026-10-19 | Local Postgres 16 (load-test data) to a second local database | 150 KB | 32 s (includes first download of the Postgres 17 image) | 7 s | PASS, 28 tables, 1,568 rows; deleting rows in the copy turned it into FAIL | Claude (script check only) |
| (pending) | **Staging to a scratch database** | | | | | **NOT DONE: needs the secrets above and a scratch database** |

The local run used a Postgres 16 target, so `pg_restore` printed one harmless warning about a setting Postgres 17
introduced. A restore into Supabase (Postgres 17, per the CI note in F3-08) should show none. If it shows others, read them.

## 4. Rollback

### Backend code

1. In Render, open the service, Events or Deploys, and roll back to the previous successful deploy.
   **NOT DONE: never rehearsed on staging (F1-07).** Rehearse it once: deploy a harmless change, roll back, check `/healthz`.
2. If the bad release ran a migration, the old code must still work with it (section 2). If it cannot, restore the
   database from the last good dump instead (below). Do not guess; check the migration first.

### Database

Order of preference: (1) fix forward with a new migration; (2) restore from the last backup into a **new** database,
check it, then point `DATABASE_URL` at it; (3) restore over the live one only if there is no other way and nobody is
using the app. Every restore loses the changes made since the backup, so say so to the owners.

### App

Play cannot send people back to an older build. You can:
* **halt the staged rollout** so nobody else gets the bad build;
* publish the previous code again as a **new, higher build number**;
* if the problem is on the server, fix or roll back the server; the app does not have to change.

There is no "this version is too old" screen in the app yet, so a very old app cannot be forced to update (**NOT DONE**, FUTURE).

## 5. Where to look

| Symptom | Look here | What it tells you |
|---|---|---|
| App says "waking the server" or cannot connect | `<host>/healthz`, then `<host>/readyz` | `healthz` ok but `readyz` 503: database problem. No answer: the service is asleep or down |
| Slow screens | Render logs, `hh.request` lines: `duration_ms`, `db_ms`, `db_queries`, `route` | Slow with high `db_ms`: database. Slow with low `db_ms`: CPU or waiting for a free thread (`inflight`) |
| Many errors | Render logs filtered for `"level":"error"`; `route` and `status` | Which route fails, how often, since which deploy (`release` field) |
| People cannot log in or sign up | Render logs for the send-otp route; the email provider's dashboard | A 503 "Email service is not configured" means no provider is set (L4-02) |
| Payment did not complete | Razorpay dashboard (payment and webhook delivery logs); Render logs for the webhook route; the payment's `needs_review` flag | Paid at Razorpay but not in the app: webhook not delivered or signature mismatch |
| Pictures missing | Cloudinary dashboard; the hostel's media rows | Photos are not served by the backend |
| Database full, slow or paused | Supabase dashboard: Reports, connections, size, project status | Free projects pause after a week without activity |
| Crash on a phone | Sentry (**NOT DONE**: no project exists, F2-01); Play Console, Android vitals | Until Sentry exists the only source is Play's crash reports |
| A deploy broke something | Render Events: which commit; GitHub Actions: did CI pass | Roll back (section 4) |

Environment variable **names** the services use are listed in `render.yaml` and `DEPLOY.md`. Values live only in the
Render and GitHub dashboards.
