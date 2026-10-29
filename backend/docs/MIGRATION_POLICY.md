# Migration policy

**Why:** Render runs `migrate` in the *build*, while the previous version of the app is still serving real users, and a rollback means redeploying the previous code against the new database. So **every migration must be safe while the previous app version is still running**, and the database must never need to be rolled back to roll the code back (S6, `RELEASE.md` section 2).

## The rules

1. **Additive only.** In one release you may: add a table, add a nullable column, add a column that has a **database default**, add an index, add a constraint that existing rows already satisfy.
2. **Defaults live in the database.** A new NOT NULL column uses `db_default=` (Django 5), not only `default=`. Plain `default=` is dropped from the table after the column is added, so the *previous* code, which does not know the column, fails on every insert. (F4's `attempts`, `needs_review` and friends are the working examples; `sqlmigrate` shows `DEFAULT 0 NOT NULL` with no later `DROP DEFAULT`.)
3. **Never rename or drop in the same release** that stops using the old name. No `RenameField`, `RenameModel`, `RemoveField`, `DeleteModel`, no narrowing `AlterField` (shorter `max_length`, `null=False` on an existing column, a new unique constraint on existing data) while any running version still reads or writes it.
   *Exception, proven per migration:* a `RenameField` on a field that has `db_column=` set changes Django's name only. Check with `python manage.py sqlmigrate <app> <number>`: it must print `-- (no-op)`. The two such migrations production still has pending (`payments.0004`, `rooms.0004`) were checked this way on 2026-10-29.
4. **Data migrations (`RunPython`)** must have a reverse function, be safe to run twice, and touch rows in batches of 1,000 or fewer (S5). Never call an outside service in one.
5. **Big tables:** an index on a table with more than about 100,000 rows is created with `AddIndexConcurrently` in a migration marked `atomic = False` (Postgres otherwise blocks writes while it builds). Today's tables are small, so the plain index in `hostels.0004` is fine.
6. **Read the SQL.** Every migration PR includes the output of `python manage.py sqlmigrate <app> <number>` in its description, and says in one line why the previous version still works with it.
7. **Roll back code, not data.** Production is never migrated backwards. If a migration was wrong, fix forward with a new migration. A restore from backup is the last resort (`RELEASE.md` section 4).
8. **Nothing is run by hand on production.** The founder deploys; the build runs `migrate`; nobody runs a migration from a laptop (the laptop's `.env` points at production, F3-02).

## Expand, then contract (renaming or removing something) in five lines

1. **Release 1 (expand):** add the new column or table next to the old one, with a database default or nullable. Code writes to both and still reads the old one.
2. **Release 2:** backfill old rows into the new column in batches (a data migration or a management command with `--dry-run`). Code now reads the new one and still writes both.
3. **Release 3:** code stops using the old column entirely. Wait until no previous version can still be running (after the app's old versions have aged out, or the app forces an update).
4. **Release 4 (contract):** drop the old column or table in its own migration. This is the only kind of release allowed to contain a `RemoveField` or `DeleteModel`.
5. If any step goes wrong, redeploy the previous code: every step above works with the one before it.

## Checklist for a migration pull request

- [ ] Only additive operations, or a documented contract release (rule 3, step 4 above).
- [ ] New NOT NULL columns use `db_default`.
- [ ] `sqlmigrate` output pasted; no `DROP`, no `RENAME`, no `SET NOT NULL` on an existing column.
- [ ] `python manage.py makemigrations --check --dry-run` is clean and `schema.yml` is regenerated if the API changed.
- [ ] A new Django app is added to `BUSINESS_APP_LABELS` (`apps/core/tenancy/checks.py`) and its models use the tenancy base classes.
- [ ] The previous version still works: said in one line in the PR.

## Review of the migrations production still has to run (2026-10-29)

Production runs code from before F1 and, per `KNOWN_GAPS.md` X-01, has these migrations pending (it may have more; the founder confirms with the query in `FOUNDER_CHECKLIST_PROD.md` step 8). Each was read, and its real SQL printed with `sqlmigrate` against a scratch Postgres 16 (nothing was run on production):

| Migration | What it does in SQL | Old code keeps working? |
|---|---|---|
| `owners.0005_profile_fields_and_photo_url` | `ADD COLUMN` x 3, all NULL | Yes |
| `owners.0006_otprecord_attempts` | `ADD COLUMN attempts ... DEFAULT 0 NOT NULL` (`db_default`) | Yes |
| `hostels.0004_hostel_search_indexes` | `pg_trgm` extension, `CREATE INDEX` on city, state and gender (small table) | Yes (a brief write lock on `hostels` while indexes build) |
| `hostels.0005_city_and_locality_tables` | new tables, two nullable links on `hostels`, one index | Yes |
| `hostels.0006_link_existing_hostels_to_places` | `RunPython` data migration with a reverse | Yes (old columns untouched) |
| `payments.0004_tenancy_scope_classification` | `RenameField` with `db_column` kept: **`-- (no-op)`** | Yes |
| `payments.0005_payment_review_refunds_webhook_events` | 2 new tables, `ADD COLUMN` x 3 with defaults | Yes |
| `rooms.0004_tenancy_scope_classification` | `RenameField` with `db_column` kept: **`-- (no-op)`** | Yes |
| `rooms.0005_bed_hold_payment_id` | `ADD COLUMN hold_payment_id uuid NULL` | Yes |

None of them breaks the rules above, so none needs rewriting before the first production deploy. This is a reading of the code and its SQL, **not** a check of the live schema (P-03 stays open until the founder compares the real list; see the checklist).
