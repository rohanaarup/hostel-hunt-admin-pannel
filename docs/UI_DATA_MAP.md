# UI data map: which endpoint and field feeds each line of each student board

**Status:** Phase 7 (read APIs). Source of truth for layout and wording: `docs/ui` (read `docs/ui/README.md` first). This file says,
for every field a board shows, where the data comes from. A field with no source is a **GAP**: it is listed, never dropped,
and the board is never changed. "Pending" means a later phase supplies it.

**Conventions.** All endpoints are under `/api/v1`, student scope, GET only, `ETag` plus `Cache-Control: private, no-cache` (send
`If-None-Match`, get a bodiless 304). Dates are ISO (`2026-10-18`); a moment in time is an ISO datetime in IST (`2026-09-16T18:12:00+05:30`).
Money is a string of rupees. "App formats" means the app turns the ISO value into the board's wording (`18 Oct`, `Oct 2026`). `HOME` is
`GET /stays/home/`; `STAY` is `GET /stays/{id}/` (or one row of `GET /stays/`).

Wording the server composes (because it joins several values) is marked **text**. Where a board has wording for one case only and the
server must produce the others, the extra wording is ours and is listed in section 4.

## 1. Student boards

### HomeDue, HomeOverdue, HomePaid (Home, `HOME`)

| Board line | Source |
|---|---|
| "4d" pill (due soon) | `HOME.pill` `{kind: days_left, days: 4, label: "4d"}` |
| "!" pill (overdue) | `HOME.pill` `{kind: overdue, days, label: "!"}` |
| no pill (all paid) | `HOME.pill` is `null` |
| Quick actions: Pay rent, History, Calendar, Notices, Analytics, Help | `HOME.quick_actions[]` `{key, label, badge}` (keys `pay_rent history calendar notices analytics help`) |
| Notices badge "1" | `HOME.quick_actions[notices].badge` (unread count; **0 until Phase 8**, helper `apps/stays/notifications.py`) |
| "SAMPLE PG · DILSUKHNAGAR" | `HOME.due_card.hostel_name` and `HOME.due_card.locality` |
| "4 days left" / "3 days overdue" | `HOME.due_card.headline` (**text**) |
| "Rent due 18 Oct" / "Rent overdue since 18 Oct" | `HOME.due_card.subtitle` (**text**) |
| "Oct rent paid" (all paid) | `HOME.due_card.headline` (**text**) |
| "You're all paid up" | `HOME.due_card.subtitle` |
| "₹6,000" | `HOME.due_card.amount` |
| "Cycle 18 Sep – 17 Oct" | `HOME.due_card.cycle_label` (**text**; `null` when overdue) |
| "Please pay as soon as you can" | `HOME.due_card.note` (**text**) |
| "Room 204, Bed B" | `HOME.due_card.room_label`, `HOME.due_card.bed_label` |
| "Pay now" button | `HOME.due_card.due_id` (feed it to `POST /payments/create-rent-order/`); `HOME.due_card.payable` says whether it may be tapped |
| "Details" button | `HOME.stay.id` then `STAY` |
| All paid: "18 Nov" and "Next rent ₹6,000 · 35 days to go" | `HOME.due_card.next` `{date, amount, days_left, text}` (`text` is **text**) |
| All paid: "View receipt" | `HOME.due_card.receipt_payment_id` then `GET /stays/{id}/receipts/{payment_id}/` |
| "NEXT 3 MONTHS" strip | `HOME.next_3_months[]` `{month, label, due_date, amount, status}` (the next three dues, stored or projected) |
| "Payment calendar" link | opens `GET /stays/calendar/?month=` |
| "Needs your attention" and its count "2" | `HOME.attention.count`, `HOME.attention.items[]` |
| "Pay October rent" / "₹6,000 · due 18 Oct, in 4 days" | item `kind: rent_due`: `title`, `subtitle` (**text**), `amount`, `due_id`, `days` |
| "October rent is overdue" / "₹6,000 · was due 18 Oct" | item `kind: rent_overdue`: `title`, `subtitle` (**text**), `amount`, `due_id`, `days` |
| "September receipt is ready" / "Download or share it" | item `kind: receipt_ready` (latest paid receipt within 14 days): `title`, `subtitle`, `payment_id`, `due_id` |
| "Nothing needs your attention" / "We will remind you 7 days before your next rent." | `HOME.attention.empty_title`, `empty_text` (present when `count` is 0) |
| Glance: "Paid so far ₹24,000" | `HOME.glance.paid_so_far` |
| Glance: "On time 3 of 4" | `HOME.glance.on_time.label` (`count`, `of`) |
| Glance: "Next due 18 Oct" / "Overdue" | `HOME.glance.next_due.label` (`date`) |
| Glance: month dots Jun to Oct | `HOME.glance.months[]` `{month, label, state}` (state `paid late due overdue upcoming`; the last five) |
| "Analytics" link | opens `GET /stays/{id}/analytics/` |
| "YOUR LOCATION Dilsukhnagar", "FIND YOUR SPACE", "Near Dilsukhnagar", search, filters, hostel cards, "Contact for price" | **unchanged existing screen**: the hostels endpoints (`/hostels/`, `/cities/`), not the stay feature |
| Dismiss (x) on "Needs your attention" | app-side only (not stored) |
| Which of the three states | `HOME.state` (`due_soon overdue all_paid no_stay`); feature off: `{"enabled": false}` only |

### HomeNoStay (`HOME`, state `no_stay`)

| Board line | Source |
|---|---|
| "Book a bed to start your stay", "After your first payment, ..." | static wording in the app; shown when `HOME.state == "no_stay"` (`quick_actions`, `due_card`, `glance` are empty or `null`) |
| Hostel list below | existing hostels endpoints |

### StayCreated, StayCreatedFixed (`STAY.billing_summary`)

| Board line | Source |
|---|---|
| "You are booked in", "Your stay is now active and locked to this hostel." | static wording |
| Hostel "Sample PG · Dilsukhnagar" | `STAY.hostel_name`, `STAY.locality` |
| Room and bed | `STAY.room_label`, `STAY.bed_label` |
| Joining "18 Jun 2026" | `STAY.joined_on` (app formats) |
| First rent covers "18 Jun – 17 Jul" / "18 – 30 Sep (13 days, ₹2,600)" | `STAY.billing_summary.first_period_start`, `first_period_end`, `first_period_days`, `first_period_amount` (app composes the dash range and the "(13 days, ₹2,600)" tail) |
| Next rent due | `STAY.billing_summary.next_due_date` |
| "Rent is due on the 18th of every month" / "This hostel collects rent on the 1st of every month" | `STAY.billing_summary.rule_title` (**text**) |
| "You joined on the 18th, so each month's rent is due on the 18th. Short months use their last day." / "Your first period is part of a month, so you paid ₹2,600 for 13 days. From 1 Oct the full ₹6,000 is due on the 1st." | `STAY.billing_summary.rule_text` (**text**) |
| "WHAT HAPPENS NEXT" three rows | static wording |
| "Go to my stay", "Back to home" | navigation |
| (the stay id to open) | the booking confirm flow returns the new stay through `GET /stays/` (current first); there is **no stay id in the verify or order reply** (see G7-02) |

### Main (Bookings tab, `GET /stays/`)

| Board line | Source |
|---|---|
| "CURRENT STAY" card, "Sample PG · Dilsukhnagar" | `results[0]` where `openable` is true: `hostel_name`, `locality` |
| "Room 204, Bed B · Joined 18 Jun 2026" | `room_label`, `bed_label`, `joined_on` |
| "Active" chip | `status` |
| "Next rent, due 18 Oct 2026" and "In 4 days" | `next_due.date`, `next_due.days_left` |
| "₹6,000" | `next_due.amount` |
| "Pay this month's rent" | `next_due.due_id` and `next_due.payable` |
| "Payment history" | opens `GET /stays/{id}/payments/` |
| "PAST STAYS", "Sample PG · Kondapur", "12 Jan – 30 Apr 2026", "Ended" | rows where `openable` is false: `hostel_name`, `locality`, `joined_on`, `ended_on`, `status` |
| "Past stays are kept for your records and can't be opened." | static; the server enforces it (past stay pages answer 403 `STAY_NOT_OPENABLE`) |

### ActiveStay (`STAY`)

| Board line | Source |
|---|---|
| "Sample PG · Dilsukhnagar", "Hyderabad" | `hostel_name`, `locality`, `city` |
| "Active" | `status` (`NOTICE` shows as the notice state) |
| Room and bed | `room_label`, `bed_label` |
| Joined | `joined_on` |
| Monthly rent | `rent_amount` |
| "Rent is due 18th of every month" | `rent_rule_text` |
| NEXT RENT "18 Oct 2026", "Due in 4 days. You can pay now." | `next_due.date`, `next_due.days_left`, `next_due.payable` (app words the sentence) |
| "₹6,000" and "Pay this month's rent" | `next_due.amount`, `next_due.due_id` |
| "Payment history", "Payment calendar" | `GET /stays/{id}/payments/`, `GET /stays/calendar/` |
| "Notifications 1" | `STAY.unread_notices` (0 until Phase 8) |
| "Request to vacate" | `POST /stays/{id}/vacate-request/` (Phase 5); after it, `STAY.vacate` `{requested_at, planned_move_out_date, reason}` |

### PayRent (`GET /stays/{id}/dues/` and `POST /payments/create-rent-order/`)

| Board line | Source |
|---|---|
| "Sample PG · Dilsukhnagar, Room 204 Bed B" | `STAY.hostel_name`, `locality`, `room_label`, `bed_label` |
| "Rent for 18 Oct – 17 Nov 2026" | due `period_start`, `period_end` (or `period_label`) |
| "₹6,000" | due `amount` |
| "Due date 18 Oct 2026" | due `due_date` |
| "Status Payable now" | due `status` (`PAYABLE` or `OVERDUE`; app maps the wording) |
| "PAY WITH UPI / Card or net banking", "Pay ₹6,000" | app-side choice passed to Razorpay checkout; the order comes from `POST /payments/create-rent-order/` `{due_id}` (Phase 6) |

### PayPending, PayFailed (`GET /payments/status/{payment_id}/`)

| Board line | Source |
|---|---|
| "Confirming your payment" / "Payment was not completed", "Not paid" | `status` (`CREATED PENDING SUCCESS FAILED`) |
| Amount | the `amount` the app got from `create-rent-order` (the poll does not repeat it) |
| "For Rent, 18 Oct – 17 Nov" / "Rent for 18 Oct – 17 Nov" | `purpose` and `due_id` from the poll, the period from the due the app already holds |
| "Try again" | `POST /payments/create-rent-order/` again (reuses the open order, or makes a new one after a failure) |
| "Check payment history" | `GET /stays/{id}/payments/` |

### PaymentDone (`GET /stays/{id}/payments/`, `STAY`)

| Board line | Source |
|---|---|
| "Your payment for 18 Oct – 17 Nov 2026 is recorded" | the paid row `period_start`, `period_end` |
| Amount | row `amount` |
| "Date and time 14 Oct 2026, 10:42 AM" | row `paid_at` (IST; app formats) |
| "Method UPI" | row `method` (`UPI CARD NETBANKING WALLET OTHER CASH BANK_TRANSFER UPI_DIRECT`) |
| "Transaction pay_••••7Q2K" | row `transaction` (masked) |
| "Next rent due 18 Nov 2026" | `STAY.next_due.date` (refetch the stay) |
| "View payment history", "Back to bookings" | navigation |

### History (`GET /stays/{id}/payments/?filter=paid|upcoming`)

| Board line | Source |
|---|---|
| "Sample PG · Dilsukhnagar · Room 204, Bed B" | `STAY` |
| Filters All, Paid, Upcoming | the `filter` query (`all` default) |
| "Rent, 18 Oct – 17 Nov" / "Booking, 18 Jun – 17 Jul" | row `label` (**text**), `kind`, `kind_label` |
| "₹6,000" | row `amount` |
| "Due 18 Oct 2026" and "Payable" | row `due_date`, `status` |
| "16 Sep 2026, 6:12 PM · UPI" and "Paid" | row `paid_at`, `method`, `status` |
| "Transaction pay_••••3M9X" | row `transaction` (null for cash) |
| "Recorded by the hostel owner" (cash) | row `recorded_by_owner` (true when `source` is `OFFLINE_OWNER`); the owner's own reference note is **not** sent to the student |
| Not-yet-created future rents | `projected[]` on every page (marked `projected: true`, no `id`, cannot be paid until the cron creates them in Phase 8) |

### Receipt (`GET /stays/{id}/receipts/{payment_id}/`)

| Board line | Source |
|---|---|
| "Sep 2026 rent", "Rent received · 18 Sep – 17 Oct 2026" | `title`, `subtitle` (**text**) |
| "₹6,000" | `amount` |
| "Receipt no. RCPT-••••3M9X" | `receipt_number` (masked) |
| "Paid on 16 Sep 2026, 6:12 PM" | `paid_at` |
| Method, Transaction | `method`, `transaction` (masked) |
| "Sample PG · Dilsukhnagar" | `hostel_name`, `locality` |
| "Room 204, Bed B" | `room_label`, `bed_label` |
| "Paid by [Student name]" | `paid_by` (the student's display name) |
| "Rent period 18 Sep – 17 Oct 2026" | `rent_period` `{start, end, label}` |
| Download, Share | generated on the phone from this data (no server PDF) |

### Calendar (`GET /stays/calendar/?month=YYYY-MM`)

| Board line | Source |
|---|---|
| "Sample PG · Dilsukhnagar", "October 2026" | `hostel_name`, `locality`, `month` |
| Each day cell | `days[]` `{date, state: covered \| awaiting \| none, due, reminder, join}` |
| Green "Covered, paid" | `state: covered` |
| Yellow "Awaiting rent" | `state: awaiting` |
| Red dot "Reminder" | `reminder: true` (7, 3 and 1 days before an unpaid due) |
| "DUE" label | `due: true` |
| Join date marker | `join: true` and `join_date` |
| "UPCOMING RENT" rows: "18 Oct 2026", "18 Oct – 17 Nov", "₹6,000", "Payable" / "Scheduled" | `upcoming[]` `{due_date, period_start, period_end, period_label, amount, status, due_id, projected}` (three) |

### Analytics (`GET /stays/{id}/analytics/?range=stay|6m|12m`)

| Board line | Source |
|---|---|
| Range tabs This stay, 6 months, 12 months | `range` query |
| "Paid so far ₹30,000" and "5 payments" | `paid_so_far`, `payments_count` |
| "On time 4 of 5" | `on_time_count` of `payments_count` |
| "1 paid 2 days late" | `late_label` (**text**), `late_payments[]` `{due_date, days_late}` |
| "Next rent 18 Nov, ₹6,000 · 35 days" | `next_rent` `{date, amount, days_left}` |
| "Stay length 4 months", "Joined 18 Jun 2026" | `stay_length_months`, `joined_on` |
| "RENT PAID BY MONTH" bars | `series[]` `{month, label, amount, state: on_time \| late \| upcoming}` |
| "HOW YOU PAID": "UPI · 3", "Card · 1", "Cash, owner recorded · 1" | `methods` counts (`UPI CARD NETBANKING CASH BANK_TRANSFER UPI_DIRECT OTHER`); app words "Cash, owner recorded" |
| "NEXT DUES" three rows | `next_dues[]` `{date, amount, status, due_id, projected}` |

### BookingBlocked (409 `ACTIVE_STAY_EXISTS` on `POST /bookings/`, Phase 5)

| Board line | Source |
|---|---|
| "You are staying at Sample PG · Dilsukhnagar" | `current_stay.hostel_name`, `current_stay.locality` |
| "Room 204, Bed B" | `current_stay.room_label`, `current_stay.bed_label` |
| "Rent paid until 17 Nov 2026" | `current_stay.paid_until` |
| "Go to my stay" | `current_stay.id` |
| "Request to vacate" | `POST /stays/{id}/vacate-request/` |
| The hostel header "Garuda boys hostel, hyderabad, Telangana" (the one being booked) | the existing hostel screen the student came from |

### VacateRequest (`POST /stays/{id}/vacate-request/`, Phase 5)

| Board line | Source |
|---|---|
| "Sample PG · Dilsukhnagar" | `STAY.hostel_name`, `locality` |
| "PLANNED MOVE-OUT DATE" options (30 Nov, 31 Dec, 31 Jan) | generated in the app; sent as `planned_move_out_date` |
| "REASON": Course completed, Moving city, Found another place, Other | fixed list of codes `COURSE_COMPLETED MOVING_CITY FOUND_ANOTHER_PLACE OTHER`, sent as `reason` |
| "Request sent to your owner" | the 200 reply; then `STAY.status == NOTICE` |

## 2. Pending: Phase 8 (notifications) and Phase 9 (owner screens)

| Board | Field | Source | Phase |
|---|---|---|---|
| Inbox | the list, filters All, Rent, Stay, "which channels delivered it", "Owner recorded your payment" | `GET /notifications/?category=` | 8 (pending) |
| Home, ActiveStay | notices badge (real count) | `apps/stays/notifications.unread_count` (returns 0 now) | 8 (pending) |
| PushPreview | five reminder wordings (7, 3, 1 days before, due day, 3 days overdue) | outbox consumer templates | 8 (pending) |
| EmailPreview | email wording on the due date and when overdue | outbox consumer and email | 8 (pending) |
| AdminBilling | rule, due day, first part-month policy, window, grace, preview | `GET` and `PUT /hostels/{id}/billing/`, `POST /stays/billing/preview/` | 9 (pending) |
| AdminDues | four totals, tab counts, row actions (Send reminder) | `GET /stays/admin/`, `POST /stays/dues/{id}/send-reminder/` | 9 (pending; Record payment already exists, Phase 6) |
| AdminRecord | the form | `POST /stays/dues/{id}/record-payment/` | done in Phase 6; the owner list that links to it is 9 |
| BookingsSettle (proposal) | pending amount of an ended stay | `pending_amount` is reserved and `null` | not built (decision D6) |

## 3. GAPS

| # | Board and field | What is missing | Impact |
|---|---|---|---|
| G7-01 | Home, Calendar, History, Analytics: rents beyond the stored ones | Only Due 1 and Due 2 are stored until Phase 8's cron creates the next ones. Later rents are **projected** on read (marked `projected: true`, no `id`). A projected due has no row, so "Pay now" cannot start for it: after the student pays Due 2 there is nothing to pay until the cron creates the next due (the Home card then shows the next rent with `payable: false`). | Moderate. Phase 8 must create dues ahead of their window. |
| G7-02 | StayCreated, StayCreatedFixed: the new stay's id | The booking verify and order replies carry no stay id. The app finds the new stay with `GET /stays/` (current stay first). | Low. A later phase may add `stay_id` to the paid confirmation. |
| G7-03 | Home "NEXT 3 MONTHS" strip | The board shows three cells with no visible text; the payload gives `label`, `due_date`, `amount`, `status` for each. The exact content of a cell is for the app to choose. | Low. |
| G7-04 | PayPending and PayFailed: amount and period | The status poll does not return them; the app keeps them from `create-rent-order` and the due it opened. | Low. |
| G7-05 | Analytics "On time" for the booking payment | The booking payment is made at booking time, before the stay starts, so it always counts as on time. | Low; stated here so the "3 of 4" counts are not a surprise. |
| G7-06 | Method on booking payments | `Payment.paid_via` is empty for booking payments (G6-05); the read API reads the method from the successful attempt. A booking paid offline with no payment record shows an empty method and counts as OTHER. | Low. |

## 4. Wording the server composes that the boards show for one case only

The boards give the exact words for one situation; the server writes the others in the same voice. If the founder prefers other
words, they live in `apps/stays/readmodels.py` (`billing_summary`, `home_payload`, `analytics_payload`):

- FIXED_DAY with FULL_MONTH (the default policy): "Your first period is part of a month and is charged as a full month (₹6,000). From 1 Oct the full ₹6,000 is due on the 1st." (The board only shows the prorated case.)
- FIXED_DAY and joining exactly on the due day: "You joined on the 1st, so your first period is a full month. Each month's rent of ₹6,000 is due on the 1st."
- "Due today" when 0 days are left; "1 day left" / "1 day overdue" in the singular; "today" in the attention line.
- Analytics: "All paid on time" when nothing is late; "N paid late" when more than one is.
- Home all-paid with no rent paid yet: the month is taken from the join date.
