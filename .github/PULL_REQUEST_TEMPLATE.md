## What and why
<!-- One or two sentences. Link the finding or issue if there is one. -->

## Done when
- [ ] Measured first: a failing test or a measurement shows the problem. For a bug fix, the test fails before the fix and passes after (output pasted below).
- [ ] CI is green (`backend / test`).
- [ ] API changed? `backend/schema.yml` regenerated, `backend/contract/endpoints.txt` updated, and the hostels fixture regenerated and copied to the app repo.
- [ ] No `expected-fail` marker left on something that now works, and none added without a one-line reason.
- [ ] Backward compatible: fields and endpoints are added before anything the shipped app uses is removed or renamed. Backend deploys before the app.
- [ ] No secrets or personal data in code, tests, logs or this description (environment variables by NAME only).
- [ ] Docs updated if behaviour or commands changed (`AGENTS.md`, `DEPLOY.md`, `backend/docs/`).
- [ ] Human steps listed below, or "none".

## Human steps
<!-- Environment variables to set (names only), Render redeploy, device test. -->

## Evidence
<!-- Trimmed command output: tests before and after, schema or contract diff. -->
