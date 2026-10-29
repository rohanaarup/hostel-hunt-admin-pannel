# Founder checklist: making production trustworthy

For the founder. Plain steps; each one ends with **how you know it worked**. Claude prepared everything in the repository, but **only you** can do these: they are dashboard actions, account sign-ups, money decisions and the production deploy. Claude never deploys, never runs anything that changes production, and never sees a secret.

Rules for the whole list
- **Never paste a password, key, token or database address into a chat, a file in the repository, a screenshot or an issue.** Paste values only into the dashboard field that asks for them. When you report back, say "done" or paste the *names* and the pass/fail lines.
- **Do not run `migrate`, `runserver` or any script from your laptop**: its `backend/.env` points at the production database (KNOWN_GAPS F3-02). Section 7 fixes that.
- Prices and plan limits change. Wherever a price is mentioned, **open the provider's pricing page and read it that day**. The figures in `LOADTEST.md` were read on 2026-10-19 and are only a hint.
- Staging's database was unreachable on 2026-10-29 (KNOWN_GAPS G1-12, probably paused by Supabase after a week of silence). **Step 0 first.**

## Step 0. Wake staging, and rotate what the public history exposed

**Why.** Claude scanned the git history on 2026-10-29 (names and yes/no comparisons only, no value was shown). Both repositories are **public**, and:
- an old committed `backend/.env` contained a filled `SECRET_KEY`, `DATABASE_URL` and `EMAIL_HOST_PASSWORD` (the app repository's copy and an admin-site `.env` also existed; the admin one only held public-style variables);
- comparing by hash, **the old database address and password, and the old email password, are the same as the ones in your current laptop `.env`**. That `.env` points at the production Supabase database (F3-02). So the production database password and the email password are public and still current;
- the old `SECRET_KEY` values differ from your current local one, but nobody knows which one production uses;
- the automatic scanner (gitleaks, default rules, 84 commits of the backend repository) found nothing, because it does not recognise database addresses or low-entropy passwords. A clean scan here is **not** proof of safety.

**Do (in this order).**
1. **Staging:** Supabase dashboard, project `Hostel-hunt-staging`. If it says paused, restore it. Check: open `https://hostel-hunt-admin-pannel.onrender.com/readyz`; it must say `{"status": "ok"}` (the first request can take a minute).
2. **Production database password:** Supabase, the production project, Project Settings, Database, reset the database password. Then put the new connection string into: Render production web service `DATABASE_URL`, the cleanup cron's `DATABASE_URL` (step 5), your laptop `backend/.env` (or better, section 7), and later the `BACKUP_DATABASE_URL` secret (step 1). **Do this before step 1** so no secret is ever stored with the old password.
3. **Email password:** if the old email password is a Gmail "app password", delete it in your Google account (Security, App passwords) and make a new one only if you will still use SMTP. Render's free plan blocks SMTP anyway, so the real fix is an email provider (L4-02); until then nothing sends mail from production, so revoking costs nothing.
4. **`SECRET_KEY`:** make a new long random value (Python: `python -c "import secrets; print(secrets.token_urlsafe(64))"`; run it, copy the result straight into Render, never into a file). Set it on the production web service **and** the cron. Effect: everyone's login stops working once and they sign in again; any OTP code sent in the last 10 minutes stops working. With no real users yet this costs nothing.
5. **Razorpay:** the old files do not list Razorpay variables, so nothing here shows a Razorpay key was exposed. Still, if the key secret was ever written in a file or pasted anywhere, regenerate it in Razorpay (Settings, API Keys) and update `RAZORPAY_KEY_SECRET` on Render. If you are sure it never was, write "kept" in the decision table.
6. **Record the decision** in the table at the end of this file: for each item, "rotated on <date>" or "accepted risk because ...".

**Do not** rewrite the git history as a substitute for rotating: the repositories are public, so copies and forks may already exist; only a new password protects you. Rewriting history is a separate, optional decision (see the table), mainly about the old files below.

**Old files still in the history (names only):** `backend/db.sqlite3` (7 versions; the newest non-empty one holds 3 owner accounts, 1 hostel and no bookings; whether those are real people is for you to say), `db.sqlite3.bak`, `data_dump.json`, `django.log` (8 versions) in the backend repository; `db.sqlite3` and `db_backup/db.sqlite3` in the app repository. If any held a real person's data, tell Claude and a history rewrite becomes a planned job (it needs your explicit approval, a fresh clone afterwards, and does not remove copies already taken).

**How you know it worked:** staging `/readyz` is ok; on Render the production web service shows a new deploy after you changed `DATABASE_URL` and `SECRET_KEY` only after step 8 (do **not** deploy yet; just save the values), and the decision table is filled.

## Step 1. Take a backup and rehearse the restore

**Why.** There is no backup today (X-06). The backup workflow was also broken: its file was invalid, so it could never run (G1-01). Claude fixed the file in this phase; **it now fails on purpose (red run, email) until the two secrets exist**, so "green" means a backup really exists.

**Secrets to add** (GitHub, backend repository, Settings, Secrets and variables, Actions, "New repository secret"):

| Secret name | What it is |
|---|---|
| `BACKUP_AGE_PUBLIC_KEY` | the public half of an `age` key pair; starts with `age1`. Not secret, but keep it with the key. |
| `BACKUP_DATABASE_URL` | the **production** database's **session pooler** connection string from Supabase (with the **new** password from step 0). Secret. |

**Do.**
1. Make the key pair once, with the command in `RELEASE.md` section 3 (needs Docker). It prints a `# public key: age1...` line and a `AGE-SECRET-KEY-...` line. Put the secret line in a password manager **and** one offline copy (a printed page or a USB stick). Losing it makes every backup unreadable. Never paste it anywhere else.
2. Add the two secrets above.
3. GitHub, Actions, **backup**, Run workflow. When it finishes, open the run: there must be an artifact `hh-backup-<number>` that is more than a few KB.
4. **Restore rehearsal** (once staging is awake, step 0): follow `RELEASE.md` section 3, "Restore rehearsal". It uses staging's database as the source and an empty scratch database as the target, never production. It ends with `RESULT: PASS`.
5. Write the result in the table in `RELEASE.md` (date, sizes, PASS).

**How you know it worked:** a green backup run with an artifact; `RESULT: PASS` from the rehearsal; the artifact list shows one new file every morning after that. Alert 7 in `ALERTS.md` covers the failures.

**Note.** The artifact is kept for 30 days on GitHub (outside Render and Supabase, as required). Because the repository is public anyone can download it, but it is encrypted and useless without your private key. For a second, longer-lived copy, download one artifact a month and keep it somewhere you control (a proposal, not done).

## Step 2. Decide the production sizes (money decision)

**Why.** On the free Render plan the service sleeps after 15 minutes and takes about **42 seconds** to wake (measured on staging on 2026-10-29). A real student would think the app is broken. Supabase's free plan has no automatic backups and pauses after a week of silence, which is exactly what probably happened to staging.

**Do.** Open the Render and Supabase pricing pages today and decide:
- Render **web service** on a paid plan that does not sleep (LOADTEST.md read "Starter about $7 a month" and "Standard about $25" on 2026-10-19; check). Phase 3 will measure what size is enough; for launch a plan that never sleeps is the requirement, and it also allows the paid cron job.
- Supabase **Pro** for the production project (daily backups kept 7 days; LOADTEST.md read "from $25 a month"; check). This does not replace step 1; it is the first line of defence and step 1 is the copy you own.
- The Render cron job is paid too (about $1 a month, check).

Claude did **not** change any plan or instance count in `render.yaml`; Phase 3 owns sizing.

**How you know it worked:** Render shows the paid plan on the service; after 30 minutes without traffic `/healthz` still answers in under a second; Supabase, Database, Backups lists daily backups.

### Step 2a. Compare `render.yaml` with the dashboard (F3-09, F5-02)

**Why.** `render.yaml` is only a reference; the live service can differ without anyone noticing. Claude cannot open your dashboard, so this comparison is yours.

**Do, for each of the three services** (production web, staging web, cleanup cron): open the service's Settings and Environment and compare with `render.yaml` at the repository root:
- build command, start command and health check path are the same (production health check `/healthz`);
- every variable **name** listed in the file exists in the dashboard, and **none of the forbidden names** listed at the top of the file exists on production (`THROTTLE_ANON`, `THROTTLE_USER`, `EXPOSE_DEV_OTP`, `USE_DB`, `LOCAL_DATABASE_URL`, `APP_ENV=staging`, `DEBUG=True`);
- `DEBUG` is `False` on production; `ALLOWED_HOSTS` contains `hostel-hunt-backend.onrender.com`.

**Statement timeout (F5-02), how you confirm it is live:** the web start command in the dashboard must start with `DB_STATEMENT_TIMEOUT_MS=25000 GIT_COMMIT=$RENDER_GIT_COMMIT gunicorn ...`. After the next deploy, open Logs for that deploy: near the top Render prints a line beginning `==> Running` with the start command; it must contain both words. The cron's start command must **not** contain `DB_STATEMENT_TIMEOUT_MS`.

**How you know it worked:** you can tick every line above; where they differ, either fix the dashboard or tell Claude what the dashboard is right about and `render.yaml` gets updated.

## Step 3. Create the Sentry project and the alert rules

1. Sentry (a free account is enough to start; confirm the current free limits): create a project, platform Django. Copy its **DSN**.
2. Render production web service and the cleanup cron: set `SENTRY_DSN` to that DSN. Web: `SENTRY_ENVIRONMENT` = `production` (already in `render.yaml`).
3. Recommended values (all through environment variables, no code change): `SENTRY_TRACES_SAMPLE_RATE` = `0.1` once you want slow-request views (default `0`, which is fine for launch). **Do not turn on any personal-data option**; the code already sends no request bodies, no cookies and no user details, and masks emails and phone numbers.
4. Send a test: in PowerShell on your laptop, in `backend`: `$env:USE_DB='sqlite'; $env:SENTRY_DSN='<dsn>'; $env:SENTRY_ENVIRONMENT='test'; ..\envhh\Scripts\python manage.py sentry_test`, then close the window. (`USE_DB='sqlite'` makes sure the laptop's production database setting is not even read.)
5. Create the alert rules 1 to 4 from `ALERTS.md` exactly as written there (new issue; error-rate; payment flagged; webhook).
6. **Drill the payment alert on staging** when you run the staging payment test (`PAYMENT_TEST.md`): after step 3 of that test run `python ops/replay_webhook.py --url https://<staging host>/api/v1/payments/webhook/ --order order_XXXX --payment pay_YYYY --amount-rupees 100 --times 1` against an order that is really for Rs 6500. The payment is flagged and an event "Payment flagged for manual review" must arrive (with staging's own DSN and `SENTRY_ENVIRONMENT=staging`).

7. Optional, for Phase 3's query measurements (F2-03): Supabase, Database, Extensions, enable `pg_stat_statements` (check: in the SQL Editor `select count(*) from pg_stat_statements;` returns a number instead of an error).

**How you know it worked:** the test event shows in Issues with environment `test`; the drill event shows with tags `alert: payment_flagged` and **no names, emails, phone numbers or ids in it**; the rule list shows 4 rules.

## Step 4. Uptime and heartbeat monitors

1. Pick an uptime and heartbeat service (examples: Healthchecks.io, Better Stack, UptimeRobot; read their free-plan limits first).
2. **Uptime checks on production only:** `https://hostel-hunt-backend.onrender.com/healthz` every minute, and `/readyz` every 5 minutes; alert after 2 failures; email and phone push. **Do not add staging** (it must be allowed to sleep).
3. **Heartbeat check for the cleanup job:** period 5 minutes, grace 10 minutes. Copy its **ping URL** (it contains a secret token; do not paste it anywhere but Render). Keep it for step 5.
4. Test each alert once (every service has a "send test notification" button, or pause the check).

**How you know it worked:** a test alert reaches your phone for each of the three checks. (They will report "down" until the production deploy in step 8, because production currently answers 404 on both health URLs.)

## Step 5. Create the production cleanup cron (L4-05)

1. Render, New, **Cron Job**, same repository, name `hostel-hunt-cleanup`, region Singapore, root directory `backend`, schedule `*/5 * * * *`, build command `pip install -r requirements.txt`, start command exactly as in `render.yaml`: `GIT_COMMIT=$RENDER_GIT_COMMIT python manage.py ping_heartbeat cleanup_expired`.
2. Environment (names as in `render.yaml`): `PYTHON_VERSION` = `3.13.5`; `SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL` (the same values as production web, after step 0); `SENTRY_DSN` (step 3); `SENTRY_ENVIRONMENT` = `production`; `HEARTBEAT_URL` = the ping URL from step 4.
3. Do **not** trigger it yet if production still runs old code (the command does not exist there). It is safe after step 8; until then, create it **suspended** or leave step 5.1 for after the deploy.
4. After step 8: Trigger run. Logs must end with `cleanup_expired: done`.
5. **Drill:** open `<your HEARTBEAT_URL>/fail` once in your browser: the monitor must go red and alert you; then wait for the next 5-minute run and watch it go green. Also pause the cron for 20 minutes once to see the "missed" alert, then resume it.

**How you know it worked:** the heartbeat monitor shows a ping every 5 minutes; the drill alerts arrived. Free-connection note: the cron uses one of the database's 15 connection slots (F5-08).

## Step 6. Turn on branch protection (F3-01)

For both repositories (`hostel-hunt-admin-pannel` and `Hostel-hunt-app`): Settings, Branches, add a rule for `main`:
- **Require status checks to pass before merging**, and tick the checks: backend repository `backend / test` and `admin / build`; app repository `app / test`.
- Do **not** tick "Require approvals" (you are the only person; it would block you).
- Leave "Allow force pushes" and "Allow deletions" off.

**How you know it worked:** `gh api repos/rohanaarup/hostel-hunt-admin-pannel/branches/main --jq .protected` prints `true` (same for the app repository). Claude merges through pull requests whose checks are green, so nothing changes for the normal flow.

## Step 7. Stop the laptop from pointing at production (F3-02)

Edit `backend/.env` on your laptop so `DATABASE_URL` is the **staging** or a local database, never production, and keep `DEBUG=True` only if it is pointing at a local one. Better still: keep production values only in Render. **How you know it worked:** `..\envhh\Scripts\python manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['HOST'])"` prints `localhost` or the staging host, not the production host.

## Step 8. Deploy current `main` to production (X-01, P-03, A-06, F1-01, T1-01)

**Only after:** steps 0 to 5 are ticked, the Phase 2 pull request is merged and CI is green, **staging runs that same commit** and passes `python backend/ops/post_deploy_check.py https://hostel-hunt-admin-pannel.onrender.com --expect-env staging` (`RESULT: PASS`).

1. **Look at what production's database really has (P-03), read-only.** Supabase, production project, SQL Editor, run: `select app, name from django_migrations where app in ('owners','hostels','payments','rooms') order by app, name;` Compare with the list in `MIGRATION_POLICY.md` ("Review of the migrations production still has to run"). Paste into `RELEASE.md` which of those names are already there. If anything looks unfamiliar, stop and tell Claude.
2. **Fresh backup** (step 1.3), downloaded and visible. Do not continue without it.
3. **Rehearse the rollback on staging once** (F1-07): in Render on the staging service find "Deploys", pick the previous successful deploy, roll back, check `/healthz`, then deploy `main` again. Write the date in `RELEASE.md`.
4. Production environment: set what `render.yaml` and `DEPLOY.md` list; `DEBUG` = `False`; `ALLOWED_HOSTS` includes the production host; new `DATABASE_URL` and `SECRET_KEY` (step 0).
5. **Manual Deploy**, choosing the exact commit that ran on staging. The build runs `migrate`.
6. If the deploy fails: Render keeps serving the old version. Read the build log (the message names a missing variable). Roll back from Render's deploy history if the new version is live and wrong; `DEPLOY.md`, "Rollback", explains what a rollback past this release re-opens.
7. After it is live: in Django admin `/admin/`, Hostels, hide the old test hostels (Test City, Bengaluru) by clearing "Active" (reversible; the staging-only cleanup command refuses to run on production, T1-01).
8. Now do step 5.3 and 5.4 (cron) and keep the production monitors from step 4.

## Step 9. Post-deploy checks, then record them

Run these from any computer (they only read; they send no password):

`python backend/ops/post_deploy_check.py https://hostel-hunt-backend.onrender.com --expect-env production`

Expected lines, all `PASS`: `/healthz answers ok`, `/healthz says env=production`, `/readyz answers ok`, `debug route is gone (404)`, then `RESULT: PASS`. (On 2026-10-29, before this deploy, production answered 404 on `/healthz` and `/readyz` and **200 on the debug route**.)

Also, in the Render production logs, find one `hh.request` line and check:
- `"release"` is not empty and starts with the commit shown in Render's deploy (proves the version tag, F2-08);
- `xff_hops` is `1` (if not, tell Claude: L4-06, the rate limit would be wrong);
- note `db_ms` and `db_queries` for `GET /api/v1/hostels/` (F5-01).

Paste the printout and these three facts into the "Post-deploy checks" table in `RELEASE.md`, then tell Claude "production deployed"; Claude then repeats the three read-only checks and updates `KNOWN_GAPS.md`.

## HSTS (do last, not now)

`SECURE_HSTS_SECONDS` stays **0** until HTTPS has been proven on your **final domain** for at least a few weeks, because browsers remember it and it cannot be undone quickly. Then set it to `31536000` (one year) on production only. Do not set it on a `*.onrender.com` address you may abandon.

## Decision record (fill in; no values)

| Item | Decision | Date |
|---|---|---|
| Production database password | rotated / accepted risk because ... | |
| Email password | revoked / accepted risk because ... | |
| `SECRET_KEY` | rotated / accepted risk because ... | |
| Razorpay key secret | checked and kept / regenerated | |
| Old data files in git history | left / history rewrite approved | |
| Laptop `.env` points at | local / staging | |
| Render web plan; Supabase plan | | |
