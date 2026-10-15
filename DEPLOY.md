# Deploy and rollback

Replaces the old `Deployment_Troubleshooting_Guide.md`, which described a setup that no longer exists.
Names only below; set values in the host's environment, never in the repository.

## Environment variables to set on the host
Required (the server will not start without them, and says which are missing):
`SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL`.

Set `DEBUG` to `False` (an absent `DEBUG` also means off).

Keep the ones already set: `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`.

OTP emails need ONE of: `EMAIL_API_PROVIDER` (`brevo` or `resend`) with `EMAIL_API_KEY` (an HTTPS call with a 6 second worst case, works on Render's free plan), or `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` (SMTP; blocked on Render's free plan). Set `DEFAULT_FROM_EMAIL` to a sender address the provider has verified. `TRUSTED_PROXY_COUNT` (default 1) is how many proxies sit in front of gunicorn; the request log's `xff_hops` shows what Render really sends. Without a provider, OTP emails answer 503 "Email service is not configured".

Profile photo uploads need `CLOUDINARY_CLOUD_NAME` and `CLOUDINARY_UPLOAD_PRESET` (the cloud name and an UNSIGNED upload preset from the Cloudinary dashboard; no API secret). Without them `POST /auth/me/photo/` answers 503 "Photo upload is not configured". The upload holds one server thread while it talks to Cloudinary, so it is limited: 10 second timeout to Cloudinary, 5 MB (a larger request is refused with 413 before its body is read), 25 megapixels, and 10 uploads per hour per user (throttle scope `photo`, answers 429 with `Retry-After`).

Optional: `SENTRY_DSN` (turns on error reporting), `SENTRY_ENVIRONMENT`, `SENTRY_RELEASE`, `GIT_COMMIT` (set from `RENDER_GIT_COMMIT` by the start command in `render.yaml`), `CORS_ALLOWED_ORIGINS` (only if a browser site calls the API), `CSRF_TRUSTED_ORIGINS` (for `/admin/` login over HTTPS). Full list: `backend/.env.example`.

`ALLOWED_HOSTS` **must contain the public hostname** the app calls. The mobile app calls `hostel-hunt-backend.onrender.com`. Earlier code ignored this variable and allowed every host, so its current value may be wrong; check it before deploying. A wrong value makes every API call return 400.

## Service settings (Render dashboard; mirrors `render.yaml`)
- Root directory: `backend`
- Build command: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate --noinput`
- Start command: `GIT_COMMIT=$RENDER_GIT_COMMIT gunicorn config.wsgi:application -c gunicorn.conf.py`
- Health check path: `/healthz`
- Python: `PYTHON_VERSION` = `3.13.5` (same as `backend/.python-version`)

## Database migrations
The build command runs `migrate`. Migration `owners.0005_profile_fields_and_photo_url` only ADDS three nullable columns (`gender`, `date_of_birth`, `profile_photo_url`) to the owners table, so it removes and rewrites nothing and is safe to roll back by redeploying the previous commit (the extra columns are simply unused). Deploy to staging first and check `/readyz` and `/api/v1/auth/me/` before production.

## T1 migrations (places) and the test-hostel command
Two migrations in `hostels`: `0005_city_and_locality_tables` (new tables, two nullable links on hostels, one index) and `0006_link_existing_hostels_to_places` (builds a City and Locality entry from each distinct text already on a hostel and links the hostel). The legacy text columns are never changed; the data migration is reversible and safe to run twice.

A database that was last migrated before `hostels.0004` (the shared database was at `0003`) also gets `0004` (the `pg_trgm` extension and search indexes) and the older pending migrations of other apps in the same run. Staging proved `pg_trgm` is allowed on Supabase. Order: staging first, check `/readyz`, `/api/v1/cities/` and `/api/v1/hostels/`, then production only with the owner's approval.

Hiding test hostels (staging only; the command refuses elsewhere):
```
python manage.py deactivate_test_hostels                          # dry run: lists, changes nothing
python manage.py deactivate_test_hostels --apply --undo-file undo.json   # hides them, writes the undo file
python manage.py deactivate_test_hostels --restore undo.json      # reverses it
```
`--ids a,b` names hostels explicitly. Nothing is ever deleted.

Roll back the migrations (if ever needed): `python manage.py migrate hostels 0004` unlinks the hostels and removes the new tables; the text columns are untouched.

## Deploy
1. Set or change the environment variables above. Confirm `ALLOWED_HOSTS`.
2. Deploy the commit (merging to the deploy branch is a human step).
3. Check, replacing the host:
   - `GET /healthz` returns `{"status": "ok"}`
   - `GET /readyz` returns `{"status": "ok"}` (this one touches the database)
   - `GET /api/v1/debug-logs/` returns 404
   - Log in from the app; place a test booking.
4. Backend deploys before any app release.

## Rollback
This release adds no migrations, so rolling back needs no database action.
Redeploy the previous successful deploy from the host's deploy history.

A build older than this release also needs the old environment. Older code cannot pass its own checks with `DEBUG` off (its CORS setting is invalid), so a build-time `migrate` would fail, and it ignored `ALLOWED_HOSTS`. That means rolling back past this release is an emergency measure that re-opens the debug routes, and `DEBUG=True` would have to be set again. Prefer fixing forward: the usual cause of a failed deploy is a missing or wrong environment variable, and the log names it. (Not tested on Render.)

## Common failures
- Every API call returns 400: `ALLOWED_HOSTS` does not include the hostname.
- Build fails with "Missing required environment variables": the message names them; set them for the build environment too.
- Admin pages have no styling: `collectstatic` did not run in the build command.
- Redirect loop over HTTPS: the proxy is not sending `X-Forwarded-Proto`; set `TRUST_PROXY_SSL_HEADER=False` only if there is no TLS proxy at all.

## Staging
A second Render service (`hostel-hunt-backend-staging` in `render.yaml`) runs the same code against its own Supabase project, so changes can be tried without touching production data. It deploys from `main` after CI passes; production is deployed by hand from a commit that already ran on staging.

Staging environment variable NAMES (values come from the staging project, never production's): `APP_ENV=staging`, `DEBUG=False`, `SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL`, `SENTRY_ENVIRONMENT=staging`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` (Razorpay TEST-mode keys), optionally `SENTRY_DSN`.

Load the sample data once, from a computer with the staging variables set (the command refuses unless `APP_ENV=staging`, and refuses if the database holds owners that are not seed data):

```
python manage.py seed_staging
```

Swagger UI is then at `https://<staging-host>/api/docs/`. It is not served in production.

## Admin site (hostel-hunt-admin-next)
The admin site must be built with `NEXT_PUBLIC_API_URL`, the backend's `/api/v1` address. Without it `next build` and `next dev` stop with a clear message, so a build can never quietly talk to the wrong server. It is read at BUILD time (it ends up in the browser), so change it and rebuild.
- development: `.env.local` (see `.env.example`), usually `http://127.0.0.1:8000/api/v1`
- staging: `NEXT_PUBLIC_API_URL=https://hostel-hunt-admin-pannel.onrender.com/api/v1`
- production: `NEXT_PUBLIC_API_URL=https://hostel-hunt-backend.onrender.com/api/v1`
Also set `NEXT_PUBLIC_CLOUDINARY_CLOUD_NAME` and `NEXT_PUBLIC_CLOUDINARY_UPLOAD_PRESET` (the same cloud as the backend's `CLOUDINARY_CLOUD_NAME`: the backend only accepts media addresses on that cloud). Tests: `npm test` (runs in CI).

## Legacy bookings (staging only)
Old bookings made before an account existed have no student. `link_legacy_bookings` links one to an account only when the phone number typed on the booking matches EXACTLY ONE verified account; it prints counts only. Run it from a computer with the STAGING variables set (`APP_ENV=staging` and the staging `DATABASE_URL`); it refuses to run anywhere else.
```
python manage.py link_legacy_bookings                                   # dry run (the default): counts only, changes nothing
python manage.py link_legacy_bookings --apply --undo-file undo.json     # link them; undo.json holds booking ids only
python manage.py link_legacy_bookings --restore undo.json               # reverse exactly what --apply linked
```
Bookings that cannot be matched stay unlinked and are visible to the hostel owner and staff only.

## F4 migrations (safe request path and payments)
Three additive migrations, applied by the build command's `migrate`: `owners.0006_otprecord_attempts` (wrong-guess counter), `rooms.0005_bed_hold_payment_id` (which payment placed a bed hold) and `payments.0005_payment_review_refunds_webhook_events` (refund and webhook-event tables, `refunded_amount`, `needs_review`, `review_note`). Every new column has a database default, so the previous release keeps working while the migration runs. Roll back by redeploying the previous commit: the new columns and tables are simply unused.

Order: staging first (build runs the migrations), run the staging payment test (`backend/docs/PAYMENT_TEST.md`), then production only with the owner's approval. Production has not received any change since before F1, so a production deploy carries every migration since then.

### Scheduled clean-up
`python manage.py cleanup_expired` (every 5 minutes) closes payments whose bed hold lapsed, frees beds with no live hold, deletes OTP records older than a day and webhook event ids older than 30 days, and flushes expired JWT tokens. `render.yaml` has a production cron job for it (about $1 per month on Render; confirm the price). Nothing depends on it for correctness: a lapsed hold is also treated as lapsed whenever it is read or written. Check it any time with `python manage.py cleanup_expired --dry-run`.

### Payments that need a person
A payment with `needs_review` set means Razorpay captured money that the system could not honour (the bed was taken, the booking was cancelled, the amount differed, a duplicate capture, or a refund whose outcome is unknown). Nothing is refunded automatically. Filter Payments by "needs review" in `/admin/`, read the note, and refund in the Razorpay dashboard. The same event is logged at ERROR level (and reaches Sentry).
