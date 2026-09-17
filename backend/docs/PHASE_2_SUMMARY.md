# Hostel Hunt — Phase 2 Implementation Summary

Companion to `TENANCY_DESIGN.md` (the Phase 1 design doc). This is the record of what
was actually built, group by group, plus the manual QA checklist for the three real
clients (admin panel, Flutter app, React website).

No migrations were applied to production. No frontend code was touched. Every group
was verified with `manage.py check` and the full test suite (`USE_DB=sqlite` override —
`.env`'s `USE_DB=supabase` was never touched).

---

## Group 1 — Core infrastructure + model classification

**New:** `apps/core/tenancy/` package — `models.py` (`TenantScopedModel`, `UserScopedModel`,
`GlobalModel`), `querysets.py` (`TenantScopedQuerysetMixin`, `UserScopedQuerysetMixin`,
`tenant_scope_q`/`user_scope_q`), `utils.py` (`get_scoped_object_or_404`, `is_tenant_owner`,
`is_resource_user`), `serializers.py` (`TenantOwnershipValidationMixin`,
`UserOwnershipValidationMixin`), `permissions.py` (`IsTenantOwner`, `IsResourceUser`),
`checks.py` (two system checks — see below), `_lookups.py` (internal Q-building helpers,
supports a tuple of alternative paths for models reachable via more than one FK).

`apps/core/{models,querysets,utils,serializers,checks}.py` are now thin re-export shims
so every existing `from apps.core.models import TenantScopedModel`-style import keeps
working unchanged.

**Consolidated 4 competing mechanisms down to 1:** `TenantScopedQuerysetMixin` family
(already correct), `utils/permissions.py:IsOwner` (deleted), the 3x duplicated inline
checks in `media_uploads/views.py` (Group 2), the inline checks in `dashboard/views.py`
(Group 7).

**Model classification:** `MediaItem` → `TenantScopedModel` (tuple `OWNER_LOOKUP`:
`hostel__owner` or `room__hostel__owner`), `Wishlist` → `UserScopedModel`
(`USER_LOOKUP="user"`), `Booking`/`Payment` → dual-scope (`+UserScopedModel`),
`PaymentAttempt` → dual-scope, one hop further out.

**New startup system check (`core.E001`):** every concrete model in `hostels`, `rooms`,
`bookings`, `residents`, `notices`, `payments`, `media_uploads` must inherit
`TenantScopedModel`, `UserScopedModel`, or `GlobalModel` — this is what stops the "new
model, forgot to scope it" bug class from coming back. It fired immediately against the
3 models above the moment it was turned on, confirming it works.

**Migrations:** `payments/0004_tenancy_scope_classification.py`,
`rooms/0004_tenancy_scope_classification.py` — both pure `RenameField` (Python attribute
name only, `db_column` unchanged, so no actual `ALTER TABLE`). **Not applied.**
Side finding, unrelated to tenancy: these expose a pre-existing migration-state drift
(model code already had `id` with an explicit `db_column`, but migration history still
had the field named `payment_id`/`bed_id`) — worth applying once reviewed, independent
of this work.

**Also fixed:** the `ModuleNotFoundError: No module named 'decouple'` you hit earlier —
your terminal had the *other* project's venv (`ROHIIs_hostel_hunt\.venv`) active instead
of this project's own `envhh` venv (sitting right next to `backend/`). Installed the
also-missing `razorpay` package into `envhh` (declared in `requirements.txt`, just not
installed there yet).

---

## Group 2 — MediaItem

`apps/media_uploads/views.py`: all 3 views (`MediaUploadView`, `MediaDetailView`,
`MediaReorderView`) now use `get_scoped_object_or_404`/`is_tenant_owner`/`tenant_scope_q`
instead of 3 independently-written inline `hostel.owner != request.user` checks.

**Tests:** `apps/media_uploads/tests.py` — 6 tests (upload/delete/reorder × cross-tenant
reject + same-tenant allow).

---

## Group 3 — Notice

`Notice.OWNER_LOOKUP` was `"posted_by"` — a proxy that only worked by coincidence under
today's one-login-per-hostel setup. Fixed to `"hostel__owner"`, with an explicit fallback
for legacy/global notices (`hostel=NULL`) scoped to whoever posted them
(`NoticeTenantScopedQuerysetMixin` in `apps/notices/views.py`, plus a matching
`IsNoticeTenantOwner` object-permission — the generic `IsTenantOwner` can't express the
null-hostel fallback and would have wrongly rejected an owner editing their own global
notice; caught by a test before the fix landed).

**Tests:** `apps/notices/tests.py` — 6 tests, including the global-notice edge case.

---

## Group 4 — Hostel, Room, Booking (+ two real vulnerabilities found)

Refactored `HostelViewSet`/`RoomViewSet` off the manual `filter(owner=request.user)` /
old `IsOwner` onto `tenant_scope_q`/`IsTenantOwner`.

**Found and fixed, not just refactored:**
1. **Room reparenting** — `PATCH /hostels/<h>/rooms/<id>/` with
   `{"hostel": "<another owner's hostel id>"}` let an owner move their own room into a
   hostel they don't own. `get_queryset()` correctly scoped *which* room you could fetch,
   but nothing stopped the client-supplied `hostel` field from pointing anywhere on save.
   Fixed with a `perform_update` ownership check mirroring the existing `perform_create`
   one. Reproduced with a failing test first.
2. **Booking generic-PATCH bypass** — the view's own docstring claimed
   "PATCH /bookings/<pk>/ — disabled via http_method_names," but that setting doesn't
   actually disable it; the router still mapped it to `partial_update()`. Any writable
   `BookingSerializer` field — `status`, `amount`, `hostel` — could be set directly,
   letting an owner skip payment verification (`status` straight to `'paid'`) or reparent
   a booking onto another owner's hostel. Fixed by explicitly overriding
   `update`/`partial_update` to return 405, matching what the docstring always claimed.
   Confirmed `approve`/`reject`/`verify`/`mark_paid` still work.

**Tests:** `apps/hostels/tests.py` (5), `apps/rooms/tests.py` (3), `apps/bookings/tests.py`
(6 tenant-isolation + the two vulnerability regression tests).

---

## Group 5 — Booking student-facing surface (new, not a retrofit)

`BookingViewSet` was owner-scoped only — a student calling `GET /bookings/` or
`GET /bookings/<their own booking>/` got an empty/404 result even for their own data.
Not a leak, but a missing feature (this is what the original brief's "student-facing
leakage" concern turned out to be).

**New:** `MyBookingListView`/`MyBookingDetailView` (`apps/bookings/views.py`), mounted at
`GET /api/v1/bookings/my/` and `GET /api/v1/bookings/my/<uuid:pk>/`
(`apps/bookings/urls.py` — ordered before the router's UUID-unrestricted `<pk>` pattern),
scoped via `UserScopedQuerysetMixin`/`Booking.USER_LOOKUP="student"`.

**Tests:** 4, including confirming the hostel owner (a different relationship to the
same booking) gets nothing back from this student-scoped route.

---

## Group 6 — Payment / PaymentAttempt

`IsPaymentOwner`/`IsHostelOwnerOfPayment` (`apps/payments/permissions.py`) were fully
written and documented but never attached to any view — deleted, replaced by the
consolidated `IsTenantOwner`/`IsResourceUser` wired in with an explicit
`self.check_object_permissions(...)` call on `RefundView` and the 4 student-facing
manual-fetch views (`InitiateUpiIntentView`, `InitiateCardCheckoutView`,
`PaymentStatusPollView`, `VerifyPaymentView`) — real defense-in-depth now, not decorative.

**Tests:** `apps/payments/tests.py` — 6 tests (owner side: admin-list, refund; student
side: payment-list, status-poll; plus confirming the two scopes don't cross).

---

## Group 7 — Wishlist

`apps/dashboard/views.py`'s `WishlistView`/`WishlistDetailView` now use
`user_scope_q`/`get_scoped_object_or_404` instead of inline `filter(user=request.user)`.

**Tests:** `apps/dashboard/tests.py` — 3 tests.
**Note:** the delete-not-found response body changed from `{"error": "Not found"}` to
DRF's standard `{"detail": "Not found."}` (still 404) — flag if any frontend matches on
the exact string.

---

## Group 8 — Dashboard stats/activity fix

`DashboardStatsView`/`DashboardActivityView` referenced `Payment.hostel`/`amount_due`/
`amount_paid`/`resident_name` — none of which exist on the current schema (an older
offline-payment model was removed; the fields never got updated here). These two routes
are confirmed live and used by the admin-panel website — they would `500` on every call.

Rewritten against the current schema: revenue = `Payment.amount` (online, status=SUCCESS)
+ `Booking.amount` (offline, payment_mode='offline', status='paid'); activity feed uses
`Payment.amount`/`booking.student_name` instead of the removed fields.

**Tests:** 2, proving both the fix (no crash, correct totals) and tenant isolation.

**Flutter mobile app currently shows nothing on this screen** (per your confirmation) —
that's a frontend gap, out of scope for this backend-only pass. See QA checklist below.

---

## Also added (not a separate group — closing test-coverage gaps on already-correct code)

- `apps/hostels/tests.py`, `apps/residents/tests.py` — these models needed no scoping
  fix but had zero regression tests despite being real tenant-scoped models with real
  endpoints.
- `apps/dashboard/tests.py` — added a `StudentDashboardStatsView` isolation test.

---

## Group 9 — Review model: not started (as agreed)

No `Review` app/model exists yet. Per the Phase 1 design doc (Step 4): when it's built,
inherit both `TenantScopedModel` (`OWNER_LOOKUP="hostel__owner"`, read-only for the
owner) and `UserScopedModel` (`USER_LOOKUP="author"`, full CRUD for the student) from
day one, following the `Payment` pattern already proven here.

---

## Explicitly deferred (per your answers)

- **Platform-admin bypass** — no platform-admin UI exists; skipped per your instruction.
  The fail-closed default holds with no bypass at all.
- **`StudentDashboardStatsView`'s legacy name-match fallback** — left as-is per your
  "best judgement" answer; still a known low-severity soft spot (documented in
  `TENANCY_DESIGN.md`).

---

## Manual QA checklist

Run this by hand across all three real clients before considering this done.

### Admin panel (Next.js + legacy Vite — both hit the same backend)

1. Log in as **Owner A**. Confirm:
   - Hostel list, hostel detail/edit screens show only Owner A's hostels.
   - Rooms tab (per hostel) shows only that hostel's rooms; editing a room never lets
     you move it to a different hostel in the dropdown/payload.
   - Bookings list/detail shows only bookings on Owner A's hostels; approve/reject/verify/
     mark-paid buttons work on A's own bookings.
   - Residents list shows only Owner A's residents; adding a resident to a hostel_id you
     don't own is rejected (try tampering the request if you have devtools access).
   - Notices list shows only Owner A's notices (plus any of A's own global/no-hostel
     notices); editing/deleting Owner B's notice ID directly via URL fails.
   - Payments admin list and refund screen show only Owner A's payments.
   - Media (photo) upload/reorder/delete on Owner A's hostel/room works; attempting it
     against Owner B's hostel/room ID fails.
   - **Dashboard stats/activity screen loads without an error** (this was 500ing before)
     and shows only Owner A's numbers.
2. Repeat all of the above logged in as **Owner B**, confirming the reverse — none of
   Owner A's data appears anywhere.
3. As Owner A, open browser devtools and try directly PATCHing a booking's `status` or
   `hostel` field via the network tab / a raw request — confirm it's rejected (405) and
   that approve/reject/verify/mark-paid are the only way to change a booking's state.

### Flutter app (students)

4. Log in as **Student A**. Confirm:
   - Any "my bookings" screen (new — `/bookings/my/`) shows only Student A's bookings.
   - Payment history screen shows only Student A's payments.
   - Wishlist shows only hostels Student A saved; removing an item only ever removes
     Student A's own entry.
   - Dashboard/stats screen (if wired up) shows only Student A's own numbers — note the
     backend fix in Group 8 didn't include a Flutter-side change, since you confirmed
     this screen currently shows nothing there; this is the point to decide whether the
     Flutter team should wire it up now that the backend endpoint works correctly.
5. Log in as **Student B** and confirm the reverse — none of Student A's bookings,
   payments, or wishlist items appear.
6. Confirm a booking made as a guest (no account) still works end-to-end (payment_mode,
   create-order, verify) — Groups 5/6 only added new access, they shouldn't have touched
   the existing create/pay flow.

### React website (public + student-facing)

7. Public hostel/room browsing (logged out) still shows all active hostels/rooms from
   every owner — this is intentional public behavior, not a leak; confirm it still works
   unauthenticated.
8. If the website exposes any student-facing booking/wishlist/payment views, repeat
   steps 4–5 there too.

### Cross-cutting

9. Confirm `python manage.py check` is clean in whatever environment actually deploys
   (not just the sqlite override used for this session's testing) — the new system
   check will hard-fail startup if a future model is added without classifying it.
10. Before applying the two generated migrations (`payments/0004_...`,
    `rooms/0004_...`) to production, have someone review them — they're expected to be
    pure no-op renames, but they touch primary-key field definitions, so treat that
    review as non-optional given the stakes.
