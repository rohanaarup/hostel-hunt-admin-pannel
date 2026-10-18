# F5 results: data path and payload

Measured on 2026-10-18. Query counts and payload sizes come from a local copy with **30 hostels, 3 rooms and 3 photos
each, 12 bookings** (a count does not depend on the database, so SQLite and Postgres agree). Timings come from a
**scratch Postgres 16 with 60,000 bookings, 13,000 payments, 300 hostels, 20,000 OTP rows** on the same machine, so they
show the cost of the query itself, not the network. The phase prompt asked for `hh-baseline/AFTER-F5.md`; F0 never
created that folder, so this file lives in the repo where it is versioned.

## Before and after

| What | Before | After | Test that holds it |
|---|---|---|---|
| Owner dashboard stats, queries | 9 (bed total added up in Python) | **4** | `QueryCountTests.test_owner_stats_use_four_queries_and_the_same_numbers` (also compares every number with a plain Python calculation) |
| Owner dashboard activity, queries for 10 rows | 12 (a lazy join per row) | **2** | `test_owner_activity_uses_two_queries` |
| Public hostel list, queries | 2 | 2 (already fine; now guarded) | `test_public_list_stays_at_two_queries` |
| Cities list, queries on a repeat request | 1 | **0** (served from memory, 60 s) | `test_the_city_list_is_served_from_memory_and_a_change_shows_at_once` |
| Localities list, queries on a repeat request | 2 | **0** | same |
| Create a hostel with 6 rooms: queries / room INSERTs | 12 / 6 | **9 / 1** | `test_create_makes_the_hostel_and_all_rooms_in_few_queries` |
| Update a hostel with 6 rooms: queries | 17 (grew with every room) | **16, and the same for 3 or 12 rooms** | `test_the_number_of_queries_does_not_grow_with_the_number_of_rooms` |
| A save that fails half way | hostel (and some rooms) stay behind | **nothing saved** | `test_a_failure_while_saving_rooms_rolls_the_hostel_back` |
| A room with an unknown field | **500** | **400** naming the room and field | `test_a_bad_room_leaves_nothing_behind_and_answers_400` |
| Update that leaves a room out | the room is **deleted**, its beds go with it, its bookings lose their room | deleted only if nothing refers to it; a room with bookings is **deactivated**, hidden from the public hostel and list prices, and comes back if sent again | `test_update_keeps_rooms_that_have_bookings_but_hides_them` and `test_an_inactive_room_comes_back_when_the_owner_sends_it_again` |
| Compression | none in Django (Render's edge compressed large responses) | gzip in Django too, when the client accepts it | `test_responses_are_gzipped_when_the_client_accepts_it` |
| Cache headers on anonymous public reads | none | `Cache-Control: public, max-age=30` (list) or `120` (cities, localities), `ETag`, `Vary: Authorization`, 304 on a matching `If-None-Match` | `test_anonymous_public_reads_get_cache_headers_and_vary`, `test_a_matching_etag_answers_304_with_no_body` |
| Same routes with a token | no headers | `Cache-Control: private, no-store`, no `ETag` | `test_a_request_with_a_token_is_never_publicly_cached` |
| Hostel detail (carries bed availability) | no headers | still none | `test_the_owner_list_and_the_detail_are_not_cached` |
| Public list cover image URL | raw Cloudinary original | `.../upload/f_auto,q_auto,c_limit,w_640/...` | `ImageSerializerTests`, `ImageTests` |
| Public detail photos (`file_url` and `remote_url`) | raw original | `...w_1600...` | same |
| Owner and admin views of photos | original | original (unchanged) | `test_the_owner_still_sees_the_original` |
| Connect timeout to the database | none | 5 s (`DB_CONNECT_TIMEOUT`) | `DatabaseOptionTests` |
| Statement timeout | none | off by default; `DB_STATEMENT_TIMEOUT_MS` on the web process only | `StatementTimeoutAppliedTests` (runs on Postgres in CI) |

Payload size of the public list is unchanged apart from the longer cover URL (10 hostels: 5.4 KB to 5.7 KB, about 1.0 KB
gzipped). **Image bytes saved were not measured here** (no Cloudinary access): a camera original of several MB versus a
640 px WebP of a few tens of KB is the expectation, and it is a HYPOTHESIS until a real photo is checked on staging.

## Do we need indexes? (EXPLAIN on 60,000 bookings)

| Query | Time | Plan |
|---|---|---|
| Owner stats, bookings aggregate | 18 ms | sequential scan of bookings (the owner's hostels are about 5% of them) |
| Owner activity (10 latest) | 23 ms | sequential scan |
| Owner bookings list | 26 ms | sequential scan |
| Owner payments list | 31 ms | sequential scan |
| Student stats, my bookings | 0.05 ms and 1.5 ms | **index** (the `student_id` index already exists) |
| Public list, search, cities | 0.2 to 1.2 ms | small tables |
| OTP lookup | 1.8 ms | sequential scan of 20,000 rows; the clean-up job keeps this table to about a day of codes |
| Clean-up of old OTP rows, 20,000 rows | 5 ms per batch | sequential scan, fine |

I created the two candidate indexes, `bookings (hostel_id, updated_at DESC)` and `bookings (hostel_id, status)`, in the
scratch database and ran the same queries again: **no change** (18 to 19 ms, 23 ms, 26 ms), because an owner reads about
5% of the table and the planner still prefers one scan. **No index migration is added.** The owner queries grow
linearly with bookings; at 60,000 bookings they are still 20 to 30 ms. Revisit when one owner dashboard request shows
`db_ms` above about 100 in the request log, or bookings pass roughly 200,000, and read `pg_stat_statements` then.

## Connection arithmetic (G07)

Gunicorn runs 2 workers x 4 threads = **8** database connections, each kept open for `CONN_MAX_AGE` = 60 s. The
Supabase session-mode pooler allows **15**. Add the clean-up cron job (1), `migrate` during a deploy (1) and a person at
`/admin/` or a script (1 to 2): about **11 to 12 of 15**, headroom of 3 to 4. **Mode stays as configured** (no switch to
the transaction pooler): the earlier `EMAXCONNSESSION` came from the laptop sharing the pool, and nothing measured says
the pool is the limit now. If it returns: lower `WEB_CONCURRENCY` or `GUNICORN_THREADS` first. Moving to transaction mode
(port 6543) would also need `DISABLE_SERVER_SIDE_CURSORS=True` and psycopg prepared statements off.

## Should the database move closer to Render? (G06)

**Still undecidable: the number does not exist yet.** Staging's database is in the same region as Render, and
production runs code from before F2, so it has no `db_ms` in its log. What is certain is the structure: each query on a
page pays one round trip, so the query counts above (9 to 4 and 12 to 2) cut the cost of the dashboard by more than half
whatever the distance is. To decide:

1. Deploy current `main` to production (needs your OK and a backup first, see `KNOWN_GAPS.md` X-01).
2. Paste about 20 request log lines for `GET /api/v1/dashboard/activity/` and `GET /api/v1/hostels/` (they hold no
   personal data).
3. Compute `db_ms / db_queries`. **A round trip of 40 ms or more per query, with `db_ms` above half of `duration_ms`,
   means moving the database to Singapore is worth a planned dump and restore.** Below 15 ms it is not.

## Decisions made

1. Caching is limited to the public list, cities and localities. The detail is excluded because it carries bed availability.
2. The places cache is per worker process with a 60 s TTL. Saving a city, locality, alias or hostel refreshes the saving
   process at once; bulk updates (the deactivate command) and other workers show the change when the TTL ends.
3. GZip is on by default (`GZIP_RESPONSES`), because your own server will not have Render's edge.
4. Rooms with bookings are deactivated, never deleted; the public hostel, the list prices and the room counts ignore
   inactive rooms. Owners and staff still see them.
5. The statement timeout is applied with a `SET` when a connection opens (poolers reject unknown startup options), and
   only where `DB_STATEMENT_TIMEOUT_MS` is set, which is the web start command, never the build, migrations or cron.
6. No indexes (evidence above). No new dependency. No migration.

## Not done

- A real photo on staging to measure the saved bytes (needs staging data, `KNOWN_GAPS.md` F3-03).
- Changing the app to keep an HTTP cache (F6).
- The production deploy.

## Deploy order and commands

No migration, no environment variable is required.

1. Merge; staging redeploys by itself after CI.
2. Optional, on the web service only (staging first): put `DB_STATEMENT_TIMEOUT_MS=25000` in front of the start command,
   as `render.yaml` shows. Without it nothing changes. Do **not** set it on the cron job or the build.
3. Check on staging: `/readyz`; `GET /api/v1/cities/` twice (second answer carries the same `ETag`); a request with
   `Accept-Encoding: gzip` answers `Content-Encoding: gzip`.
4. Production later, together with everything else (X-01).

Rollback: redeploy the previous commit. There is no schema change to undo; rooms deactivated by an update stay
deactivated until the owner sends them again or staff set `is_active` in the admin.
