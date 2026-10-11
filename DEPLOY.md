# Deploy and rollback

Replaces the old `Deployment_Troubleshooting_Guide.md`, which described a setup that no longer exists.
Names only below; set values in the host's environment, never in the repository.

## Environment variables to set on the host
Required (the server will not start without them, and says which are missing):
`SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL`.

Set `DEBUG` to `False` (an absent `DEBUG` also means off).

Keep the ones already set: `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`.

Profile photo uploads need `CLOUDINARY_CLOUD_NAME` and `CLOUDINARY_UPLOAD_PRESET` (the cloud name and an UNSIGNED upload preset from the Cloudinary dashboard; no API secret). Without them `POST /auth/me/photo/` answers 503 "Photo upload is not configured".

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
