# Hostel Hunt — Data Isolation Design Doc

Status: **Phase 2 implementation complete.** All 8 planned groups landed (Review, group 9, is future work — no Review app exists yet). See "Resolutions" under Open Questions for the decisions that unblocked Phase 2, and `PHASE_2_SUMMARY.md` in this same folder for the full implementation report and manual QA checklist.
Scope: `admin pannel HH/backend` (Django REST Framework).

---

## Phase 0 — Existing scaffolding

**Existing scaffolding found** (already wired into real views, not dead code):

- `apps/core/models.py:4` — `TenantScopedModel` (abstract base, declares `OWNER_LOOKUP: str = None`)
- `apps/core/querysets.py:4` — `TenantScopedQuerysetMixin` (filters `get_queryset()` by `OWNER_LOOKUP=request.user`)
- `apps/core/utils.py:5` — `get_tenant_scoped_object_or_404()` (same filter, for single-object fetch, indistinguishable 404)
- `apps/core/serializers.py:4` — `TenantOwnershipValidationMixin` (validates a client-supplied `hostel` FK on create belongs to `request.user`)
- `apps/core/checks.py:6` — a Django system check, but it only verifies that models which *already* inherit `TenantScopedModel` have also set `OWNER_LOOKUP`. It does **not** check whether a model that *should* be tenant-scoped fails to inherit `TenantScopedModel` in the first place (see Step 3).
- Wired into: `Hostel` (`OWNER_LOOKUP="owner"`), `Room` (`"hostel__owner"`), `Bed` (`"room__hostel__owner"`), `Booking` (`"hostel__owner"`), `Resident` (`"hostel__owner"`), `Notice` (`"posted_by"` — see finding below), `Payment` (`"booking__hostel__owner"`), and the views in `rooms`, `bookings`, `residents`, `notices`, `payments` apps.

A **second, separate, redundant mechanism** also exists and is live:

- `utils/permissions.py:3` — `IsOwner` (a DRF object-permission class), used only in `hostels/views.py` and `rooms/views.py`. It duck-types `obj.owner` or falls back to `obj.hostel.owner`, so it silently returns `False` (fail-closed, but broken) for anything nested deeper than two hops (e.g. `Bed`, `Payment`). It is not used there today, but it is a landmine if reused, and it duplicates what `TenantScopedQuerysetMixin`/`get_tenant_scoped_object_or_404` already do more generally.

A **third** ad-hoc pattern: `apps/media_uploads/views.py` hand-rolls the same `hostel.owner != request.user` / `room.hostel.owner != request.user` check three separate times (upload, detail/delete, reorder) because `MediaItem` doesn't inherit `TenantScopedModel` at all.

A **fourth**: `apps/dashboard/views.py`'s student-facing views (`StudentDashboardStatsView`, `WishlistView`, `WishlistDetailView`) hand-roll `filter(student=request.user)` / `filter(user=request.user)` inline — correct in effect, but there is no shared "user-scoped" base to match `TenantScopedModel`.

**Assessment:** **Build on the `apps/core` mechanism, do not replace it.** `TenantScopedModel` / `TenantScopedQuerysetMixin` / `get_tenant_scoped_object_or_404` / `TenantOwnershipValidationMixin` are correctly designed and correctly wired everywhere they're used. The work is: (a) extend this same family with a parallel user-scope mechanism, (b) fold the three competing/duplicate patterns (`IsOwner`, the `media_uploads` inline checks, the `dashboard` inline checks) into it, (c) close the one real classification gap (`MediaItem` not inheriting anything), (d) fix the one mislabeled lookup (`Notice.OWNER_LOOKUP = "posted_by"`), and (e) strengthen the system check so it can't regress.

**Correction of a premise in the task brief:** I could not find any `OwnerListView` anywhere in the repo (grepped the whole tree), nor any file/comment referencing a "confirmed leak," a prior audit, or cross-tenant data exposure. Every owner-facing list/detail view I traced (`HostelViewSet`, `RoomViewSet`, `BookingViewSet`, `ResidentListView`, `NoticeListView`, `AdminPaymentListView`) is currently scoped correctly to `request.user`'s own hostel(s) — I could not reproduce "Hostel A's data leaking into Hostel B's owner view" against the code as it exists right now. I'm flagging this per your instructions rather than inventing a leak to match the brief. If you have a specific endpoint/repro from the prior audit, please share it — it may be a bug in the *Next.js admin panel's* API calls (out of scope per the "backend-only" rule, but worth checking: is it passing/caching another owner's ID in a query param the backend trusts?), or it may already have been fixed since. The real gaps found here are listed in Step 2 below — they are subtler than a blanket queryset leak.

---

## Step 0 — Identity & ownership model

- **Owner is the one and only user table.** `AUTH_USER_MODEL = 'owners.Owner'` (`config/settings.py:185`). `Owner` (`apps/owners/models.py:7`) is a full `AbstractBaseUser`, keyed by UUID, with `email`/`phone_number` login.
- **There is no separate Student model.** The Flutter app's "students" authenticate against and are represented by rows in the *same* `owners` table as hostel owners (`Booking.student` and `Wishlist.user` are both `ForeignKey(settings.AUTH_USER_MODEL, ...)`, confirmed in `apps/bookings/models.py:35` and `:80`). `Owner.ROLE_CHOICES` currently only defines `'owner'` — there is no `'student'` choice, and nothing in the codebase branches on `role` at all (grepped; only reference is the field's own default). In practice: the same identity (`request.user`) can simultaneously be "an owner" (if they have `Hostel` rows via the `owner` FK) and "a student" (if they have `Booking`/`Wishlist` rows via the `student`/`user` FK) — these are two independent relationships hanging off the *same* row, not two separate tables.
- **Consequence for the design:** there is no need for a contextvar or middleware to resolve "current tenant" vs. "current user" — both scopes resolve to the same `request.user` already provided by DRF's standard auth on every request. The only thing that varies is *which relation path* a given view filters on (`hostel__owner=request.user` for the owner's-eye view of a resource, vs. `student=request.user` for the same person's-eye view of their own bookings). This significantly simplifies Step 3: the "current identity" resolution problem the task brief anticipated is already solved by DRF; what's missing is just a second, parallel `OWNER_LOOKUP`-style declaration for the user-scope case.
- **Hostel ↔ Owner cardinality:** `Hostel.owner` is a plain `ForeignKey` (`apps/hostels/models.py:19`), not `OneToOneField`. So **one owner can own many hostels**, but **one hostel has exactly one owner** — there is no join table or second FK anywhere for a co-manager/staff-per-hostel concept. I grepped for `co_owner`, `manager`, `staff_member`, `HostelStaff` etc. — none exist. `Owner.is_staff` / `is_superuser` are the standard Django auth flags (used only by `create_superowner` management command for Django-admin access), not a "hostel manager" role.
- **How an owner-facing view currently establishes "this user may act on hostel X":** every one of them ultimately does `<relation-path>__owner=request.user` (or the equivalent object-level `obj.hostel.owner == request.user`) — i.e. literal identity comparison against `Hostel.owner_id`, no separate tenant/org ID. This confirms the tenant identifier **is** the `Owner`/User ID directly — there is no separate Organization/Owner-group model to introduce.
- **Platform-admin bypass:** no distinct "platform staff" role exists yet beyond Django's built-in `is_staff`/`is_superuser` (used today only for Django admin and the `createsuperowner` command, not for any API-level cross-tenant bypass). Recommend introducing the explicit bypass as `is_superuser`-gated (Django admin already uses this concept) rather than inventing a new flag, unless you'd rather keep the two concerns (Django-admin access vs. API cross-tenant support access) separate — **flagging as an open question below**.
- **Student identity confirmed:** there is no separate "Student profile" model — resources key directly off `request.user` (the `Owner` row), exactly as they do for the owner side. Same identity, different relation.

---

## Step 1 — Model-to-scope map

| Model | App | Scope | Relation path to owner / user | Notes |
|---|---|---|---|---|
| `Hostel` | hostels | Tenant | `owner` (direct FK) | `OWNER_LOOKUP` declared but **not used** — `HostelViewSet` hand-rolls `Hostel.objects.filter(owner=request.user)` instead of the mixin. Equivalent today, but a duplicate implementation. |
| `Room` | rooms | Tenant | `hostel__owner` | Correctly wired via `TenantScopedQuerysetMixin`. List/retrieve are intentionally public (nested under `/hostels/<hostel_id>/rooms/`, so always additionally filtered to that one hostel — confirmed not a leak). |
| `Bed` | rooms | Tenant | `room__hostel__owner` | `OWNER_LOOKUP` declared; **no view currently exists for Bed at all** (only touched internally during the payment flow via `booking.room`, already scoped through the student's own booking). Scoping is inherited "for free" today but should still be classified for when a Bed admin view is eventually built. |
| `Booking` | bookings | **Both** | Tenant: `hostel__owner`. User: `student` (direct FK). | `BookingViewSet` currently implements **only** the tenant/owner side. There is no student-facing "my bookings" list/detail endpoint at all yet (see Step 2). |
| `Wishlist` | bookings (model), dashboard (views) | User | `user` (direct FK) | No `TenantScopedModel`-equivalent base yet for user scope — `dashboard/views.py` hand-rolls `filter(user=request.user)` correctly but ad hoc. |
| `Resident` | residents | Tenant | `hostel__owner` | Correctly wired. |
| `Notice` | notices | Tenant | **Declared as `posted_by`**, should be `hostel__owner` | See finding below — works today only because of the 1-owner-per-hostel, 1-login-per-owner cardinality confirmed in Step 0; it's a latent inconsistency, not a live leak. |
| `Payment` | payments | **Both** | Tenant: `booking__hostel__owner`. User: `booking__student`. | Correctly wired for both sides via distinct views (`AdminPaymentListView` uses the mixin; student views hand-roll `booking__student=request.user`). |
| `PaymentAttempt` | payments | **Both** (transitively) | Tenant: `payment__booking__hostel__owner`. User: `payment__booking__student`. | Not directly exposed by any view today (only touched via `payment.attempts` off an already-scoped `Payment`) — correctly scoped today "for free," should still be classified. |
| `MediaItem` | media_uploads | Tenant | `hostel__owner` **or** `room__hostel__owner` (both FKs are independently nullable) | **Does not inherit `TenantScopedModel` at all.** Scoping is reimplemented inline 3x in `views.py`. This is the one model that needs a genuine base-class change, and it needs `OWNER_LOOKUP` to support two alternative paths (see Step 3). |
| `Owner` | owners | N/A (is the identity itself) | — | Not tenant- or user-scoped; it *is* the tenant/user. |
| `OTPRecord` | owners / otp_auth | Global/unscoped | — | Ephemeral, keyed by `identifier` (email/phone) before an account exists. Correctly has no owner concept. |
| Everything in `dashboard/views.py`'s "legacy" section (`DashboardStatsView`, `DashboardActivityView`) | dashboard | Tenant (intended) | `hostel__owner` (intended) | **Currently broken, not just unscoped** — see Step 2 finding; references fields (`Payment.hostel`, `Payment.amount_due`, `Payment.amount_paid`, `Payment.resident_name`) that don't exist on the current `Payment` model. Will 500 if called. |

---

## Step 2 — Access-point audit

Owner-facing (tenant scope):

| Endpoint | Scoping today | Verdict |
|---|---|---|
| `HostelViewSet` (list/retrieve/update/delete/create) | Manual `filter(owner=request.user)` + `IsOwner` object permission | Correct, but duplicates `OWNER_LOOKUP`/mixin instead of using it |
| `RoomViewSet` | `TenantScopedQuerysetMixin` (non-list actions) + always-present `hostel_id` URL filter + `IsOwner` | Correct (redundant IsOwner is harmless) |
| `BookingViewSet` list/retrieve/approve/reject/verify/mark_paid | `TenantScopedQuerysetMixin` + `get_tenant_scoped_object_or_404` | Correct for the owner side |
| `ResidentListView` / `ResidentCreateView` / `ResidentMarkVacatedView` | `TenantScopedQuerysetMixin` (list) / `TenantOwnershipValidationMixin` (create, validates the client-supplied `hostel` FK) / `get_tenant_scoped_object_or_404` (mark-vacated) | Correct |
| `NoticeListView` / `Create` / `Update` / `Delete` | `TenantScopedQuerysetMixin` keyed on `posted_by`, not `hostel__owner` | Functionally correct today (see Step 0 cardinality), but should be corrected to `hostel__owner` for consistency and to not silently break if co-management is ever added |
| `AdminPaymentListView` / `RefundView` | `TenantScopedQuerysetMixin` / `get_tenant_scoped_object_or_404` | Correct. `IsHostelOwnerOfPayment` permission class exists but is dead code (never attached to either view) — should be wired in as defense-in-depth, not left as decorative documentation |
| `MediaUploadView` / `MediaDetailView` / `MediaReorderView` | Inline `hostel.owner != request.user` / `room.hostel.owner != request.user` checks, duplicated 3x | Correct in effect, needs consolidating onto the shared mechanism |
| `DashboardStatsView` / `DashboardActivityView` | Manual `filter(hostel__owner=user)` etc., but against **fields that no longer exist** on `Payment` | **Broken** — will throw `FieldError`/500 today. Routed live at `/dashboard/stats/` and `/dashboard/activity/`. Needs a decision: fix to match current `Payment` schema, or delete if the Next.js admin panel dashboard doesn't call it (grep the frontend's API client before deciding — I have not touched frontend code). |

Student-facing (user scope):

| Endpoint | Scoping today | Verdict |
|---|---|---|
| `BookingViewSet.create` (public) | Auto-sets `student=request.user` if authenticated | Correct — no read exposure |
| `StudentDashboardStatsView` | Inline `filter(student=user)` / `Q(student__isnull=True, student_name__iexact=...)` legacy fallback | Correct, but the legacy name-match fallback is a soft spot: any authenticated user whose `display_name` happens to match a guest booking's `student_name` would see that booking's stats folded into their own. Low severity (stats aggregation only, not a detail view), but worth a note. |
| `WishlistView` (GET/POST) / `WishlistDetailView` (DELETE) | Inline `filter(user=request.user)` | Correct |
| **Missing entirely:** a "my bookings" list/detail endpoint (equivalent to `PaymentListView` for payments) | N/A | `BookingViewSet.get_queryset` always filters by `hostel__owner`, so a student calling `GET /bookings/` or `GET /bookings/<their own booking id>/` gets an **empty/404 result even for their own data** — this isn't a leak, it's a missing feature, but it's exactly the "student-facing views may have equivalent per-user leakage that hasn't been fully mapped" question the brief raised. Answer: no leak, but no access either — needs to be built (see implementation order). |
| `PaymentListView` / `PaymentStatusPollView` / `VerifyPaymentView` / `InitiateUpiIntentView` / `InitiateCardCheckoutView` / `CreateOrderView` | All filter by `booking__student=request.user` | Correct (independently audited in depth — see payments deep-dive below) |
| `WebhookView` | No user context (Razorpay-only); resolves target `Payment` from the HMAC-signed payload itself, not a client-trusted ID | Correct, well-designed |

**Payments deep-dive (delegated sub-audit, all 9 views read in full):** no exploitable cross-student or cross-owner leak found in `apps/payments/views.py`. One defense-in-depth gap: `IsPaymentOwner` and `IsHostelOwnerOfPayment` (`apps/payments/permissions.py`) are fully written and documented as protecting specific views but are **never actually attached** to any view's `permission_classes` — both views instead rely entirely on the queryset/helper filter being correct. This works today but leaves no safety net if someone later adds a plain `RetrieveAPIView`/`get_object()` path that bypasses the custom `get_queryset()`.

---

## Step 3 — Proposed enforcement mechanism

### File layout

Keep the existing `apps/core/` location (it's already exactly the right shape and everything already imports from it) rather than introducing a new `apps/core/tenancy/` package that would force every existing import to change for no behavioral reason. Reorganize it into a small package:

```
apps/core/
  tenancy/
    __init__.py
    models.py          # TenantScopedModel (existing, moved) + new UserScopedModel
    querysets.py        # TenantScopedQuerysetMixin (existing, moved) + new UserScopedQuerysetMixin
    utils.py            # get_tenant_scoped_object_or_404 (existing) + get_user_scoped_object_or_404 (new)
    serializers.py       # TenantOwnershipValidationMixin (existing) + UserOwnershipValidationMixin (new, for student-writable FKs)
    permissions.py       # NEW — consolidated object-level permission classes (replaces utils/permissions.py:IsOwner
                         #        and apps/payments/permissions.py, wired everywhere instead of left dead)
    checks.py            # existing OWNER_LOOKUP check, PLUS new "every concrete model in a scoped app must
                         #  declare its scope" check (see below)
  models.py              # re-exports from tenancy/ for backward compat during migration (see below)
  querysets.py           # re-exports
  utils.py               # re-exports
  serializers.py          # re-exports
```

`apps/core/models.py` etc. become thin `from apps.core.tenancy.models import *`-style re-export shims so every existing `from apps.core.models import TenantScopedModel` import across `hostels`, `rooms`, `bookings`, `residents`, `notices`, `payments` keeps working unchanged — only new code written in Phase 2 imports from `apps.core.tenancy.*` directly. This avoids a repo-wide mechanical import rewrite as a side effect of this change (lower risk, smaller diff, easier review) while still satisfying "one dedicated home, per-app files only import from it." `utils/permissions.py:IsOwner` gets deleted outright (not shimmed) since it's genuinely superseded, not just relocated — its two call sites (`hostels`, `rooms` views) get updated to the new consolidated permission class in the same Phase 2 pass that touches those apps.

### Core additions

1. **`UserScopedModel`** (mirrors `TenantScopedModel`): abstract base with `USER_LOOKUP: str = None`.
2. **`UserScopedQuerysetMixin`** (mirrors `TenantScopedQuerysetMixin`): filters `get_queryset()` by `{USER_LOOKUP: request.user}`. Explicitly checks `request.user and request.user.is_authenticated` first and returns `.none()` otherwise, rather than relying on an `AnonymousUser` instance simply never matching any row (that's the current *accidental* fail-closed behavior of `TenantScopedQuerysetMixin` — both mixins should make this explicit rather than incidental).
3. **`OWNER_LOOKUP`/`USER_LOOKUP` become string-or-tuple.** For `MediaItem`, a single dotted path can't express "via `hostel` OR via `room.hostel`" — the mixin/helper builds `Q(**{path: user})` for each entry in the tuple and OR-combines them. This is a small, generic extension, not special-cased just for MediaItem.
4. **Consolidated `apps/core/tenancy/permissions.py`**: one `IsTenantOwner` (replaces `IsOwner` + `IsHostelOwnerOfPayment`) and one `IsResourceUser` (replaces `IsPaymentOwner` and the inline student checks) object-permission class, each driving off the model's `OWNER_LOOKUP`/`USER_LOOKUP` the same way the querysets do, so there's exactly one place that knows how to walk these paths. Applied as `has_object_permission` defense-in-depth on every scoped detail/action view, in addition to (never instead of) queryset-level scoping.
5. **`get_scoped_object_or_404(model, pk, request, kind="tenant"|"user")`**: single helper replacing both `get_tenant_scoped_object_or_404` and the not-yet-existing user-scope equivalent, parameterized by which lookup attribute to use. Old name kept as a thin wrapper calling it with `kind="tenant"` for compatibility.
6. **Fail-closed default:** both querysets mixins and the object-permission classes deny/empty whenever `OWNER_LOOKUP`/`USER_LOOKUP` is missing (raises `ImproperlyConfigured` at request time, as today) or when `request.user` is unauthenticated (explicit `.none()`/`False`, not incidental). Nothing ever falls through to an unscoped `Model.objects.all()`.
7. **Explicit cross-tenant/platform-admin bypass — DEFERRED (see Open Questions resolution #3).** No platform-admin UI exists yet and building one is out of scope for this pass. Not implemented in Phase 2. The design still holds up without it: fail-closed means "no bypass" rather than "open access," which is the safer of the two states to ship. When a real support/staff workflow is scoped, revisit this as its own addition (`IsPlatformAdmin` + a `PlatformAdminQuerysetMixin`, deliberately opt-in per view, with access logging).
8. **System check upgrade (`apps/core/tenancy/checks.py`):** in addition to the existing "declared `TenantScopedModel` but no `OWNER_LOOKUP`" warning, add an **error-level** check that iterates `apps.get_models()` restricted to an explicit list of "business" app labels (`hostels`, `rooms`, `bookings`, `residents`, `notices`, `payments`, `media_uploads`, and future `reviews`) and fails startup if a concrete (non-abstract, non-proxy) model in one of those apps does not inherit `TenantScopedModel`, `UserScopedModel`, or an explicit `GlobalModel` marker (new no-op abstract base you add to `OTPRecord`, `PaymentAttempt`'s parent-level concerns, etc., meaning "yes, I looked at this, it's intentionally unscoped"). This is what actually prevents the bug class from returning — the existing check only catches a subset of misconfigurations of models that already opted in.

### Future note (no implementation needed now)

When Redis caching is introduced later, every cache key for tenant- or user-scoped data **must** embed the tenant/user identifier (e.g. `f"hostel:{owner_id}:dashboard-stats"` / `f"student:{user_id}:bookings"`), never a bare resource id alone — otherwise the cache becomes a fresh leak vector even after this fix. Flagging for whoever builds that layer; no action here.

---

## Step 4 — Review model gap

No `Review` app/model exists yet. When it's built, a review is naturally **dual-scope** like `Booking`/`Payment`: tenant-scoped for the owner's read-only view of reviews on their hostel (`OWNER_LOOKUP = "hostel__owner"`, read-only — owners should not be able to edit/delete another student's review) and user-scoped for the reviewing student's own write access (`USER_LOOKUP = "author"`, full CRUD on their own review only). Recommend it inherit both `TenantScopedModel` and `UserScopedModel` from day one and use `IsResourceUser` for the write paths, `TenantScopedQuerysetMixin` (read-only, no write mixin attached) for the owner's read path — following exactly the `Payment` pattern already proven in this codebase.

---

## Migration considerations

- **No new FK needed for `Hostel`, `Room`, `Bed`, `Booking`, `Resident`, `Payment`, `PaymentAttempt`, `Wishlist`** — all already have the relation path in the schema today; this is a pure code/behavior change (inheriting a new abstract base + `USER_LOOKUP` string adds no column, no migration).
- **`MediaItem`** needs to start inheriting `TenantScopedModel` — abstract base inheritance with no new fields still produces a no-op migration (Django will want to run `makemigrations` to record the new base in model state, but it won't alter any table). Will generate and share for review, not apply.
- **`Notice.OWNER_LOOKUP`** fix from `"posted_by"` to `"hostel__owner"` is a code-only change (no migration) — but since some historical `Notice` rows may have `hostel=NULL` (it's nullable), those rows would stop matching `hostel__owner` for anyone. Needs a data check before the switch: **query production for `Notice.objects.filter(hostel__isnull=True).count()`** — if non-zero, decide whether those are meant to be global notices (in which case keep them visible via a `Q(hostel__owner=request.user) | Q(hostel__isnull=True, posted_by=request.user)` combined lookup) or backfill `hostel` from context. This is a genuine open question, not just a code change — see below.
- **No production data backfill anticipated** for the other models since no new FK/column is introduced.

---

## Proposed implementation order

1. **`apps/core/tenancy/` package** — move/re-export existing mechanism, add `UserScopedModel` + `UserScopedQuerysetMixin` + consolidated permissions + upgraded system check. No behavior change to existing views yet; this step is pure infrastructure, verified by running the full existing test suite (should be 100% unaffected since it's additive/re-exported).
2. **`MediaItem`** — smallest real gap (one model, three views, all already correct in effect) — inherit `TenantScopedModel`, replace the 3 inline checks with the shared mixin/helper, add regression tests. Low risk, proves the new mechanism end-to-end.
3. **`Notice`** — fix `OWNER_LOOKUP`, resolve the nullable-`hostel` open question first (see above), add regression tests for the corrected scoping and the global-notice case if kept.
4. **`Hostel`, `Room`** — replace the manual `filter(owner=request.user)` / `IsOwner` with the consolidated mixin/permission class, so there's exactly one pattern in the codebase (currently these two are the only holdouts still using the old manual/duplicate style). Pure refactor, same behavior, tests prove it.
5. **`Booking`** student-facing surface — build the missing "my bookings" list/detail endpoints on `UserScopedQuerysetMixin`/`USER_LOOKUP="student"`, since this is genuinely new access (not a retrofit), and is the one gap the original brief's "student-facing leakage" concern maps onto.
6. **`Payment`/`PaymentAttempt`** — wire the already-written `IsPaymentOwner`/`IsHostelOwnerOfPayment` (or their consolidated replacements) into `AdminPaymentListView`/`RefundView`/student views as actual `permission_classes`, closing the defense-in-depth gap found in the sub-audit.
7. **`Wishlist`** — move `dashboard/views.py`'s inline `filter(user=request.user)` onto `UserScopedModel`/`UserScopedQuerysetMixin` for consistency.
8. **`DashboardStatsView` / `DashboardActivityView`** — separate decision needed before touching (see open questions) since these are currently broken independent of tenancy; not blocking the rest of this work.
9. **`Review`** — apply the pattern from Step 4 when that app is built (future work, not part of this task).

Each step gets its own regression tests (two tenants / two users, assert cross-access is blocked) and a full test-suite run before moving to the next, per your instructions.

---

## Open questions / things I'm not fully confident about

1. **The "confirmed `OwnerListView` leak"** named in the brief does not exist in the current code, and I found no trace of a prior audit anywhere in the repo.
2. **`Notice` rows with `hostel=NULL`:** are these real production data, or test/seed artifacts?
3. **Platform-admin bypass:** reuse `is_superuser`, or a distinct flag?
4. **`DashboardStatsView`/`DashboardActivityView`:** fix, delete, or leave for a separate ticket?
5. **`StudentDashboardStatsView`'s legacy name-match fallback:** tighten or leave as-is?

### Resolutions (from user, 2026-09-17)

1. **No specific repro exists** — the intent is systemic: "a mental fixed model for the entire system" so no hostel/object ever shows another hostel's data, regardless of whether a live incident is reproducible today. **Decision:** proceed against the real gaps found in Step 2 (`MediaItem` unscoped, `Notice` mislabeled lookup, `Hostel`/`Room` duplicate manual scoping, dead permission classes, missing student-facing booking endpoint) rather than a specific reported bug.
2. **Do it as I see fit.** **Decision:** use the combined-`Q()` fallback (`Q(hostel__owner=request.user) | Q(hostel__isnull=True, posted_by=request.user)`) rather than forcing `hostel` non-nullable — preserves current behavior for any existing null-hostel notices with no data risk, at the cost of one slightly less elegant queryset. Revisit if a later audit shows zero null-hostel rows in production.
3. **Skip entirely.** There is no platform-admin/superuser UI today (no cross-hostel listing, performance, or revenue view) and building one is a substantial net-new feature, not part of this fix. **Decision:** drop `IsPlatformAdmin`/`PlatformAdminQuerysetMixin` from Phase 2 scope. The fail-closed default (deny/empty when scope is missing or ambiguous) still applies with no bypass at all — safer than a half-built escalation path. Revisit when a real support/staff workflow is scoped as its own project.
4. **Fix from the backend side.** Confirmed: the admin-panel website partially uses `/dashboard/stats/` and `/dashboard/activity/`, and the Flutter app currently shows nothing there. **Decision:** fix the backend queries in this pass (Group 8 below) against the *current* `Payment`/`Booking` schema — `Payment.objects.filter(booking__hostel__owner=user)` instead of the nonexistent `hostel` field, revenue computed from `Payment.amount` (status=`SUCCESS`, online) plus `Booking.amount` (payment_mode=`offline`, status=`paid`), and `resident_name`/`amount_paid` references replaced with the real `Booking`/`Payment` fields. Frontend changes (if the mobile app needs new UI to consume this) are explicitly out of scope per the backend-only rule — flagging that gap in the final QA checklist rather than closing it myself.
5. **Best judgement: leave as-is.** Low severity, aggregate-display-only, predates this task, and removing it risks losing legacy guest-booking stats for existing bookings that were never linked to a `student` FK. Not touched in Phase 2; noted in the final report as a known soft spot.
