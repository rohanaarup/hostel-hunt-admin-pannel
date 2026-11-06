# Hostel Hunt UI pack: Stay and Rent screens

These are the 25 approved boards for the Active Stay and Rent Manager. They are the source of truth for layout, wording and states. Place this whole folder at docs/ui in BOTH repos (the backend and admin repo, and the Flutter app repo), then commit it.

## Folders
- screens/*.png: each board at 2x. Student boards are 390 px wide, admin boards 1280 px (AdminRecord 640), EmailPreview 640.
- source/*.dc.html: the exact markup with real spacing, colours and sample data. Open in a browser. The text between double curly braces is filled by the board script.
- text/*.txt: every word on each board, for exact copy.

## Design tokens (dark HH theme used by the boards)
background #181514, surface #262120, raised surface #2B2423, border #3A3230, text #F4ECE8, muted text #B3A59F, accent #D32F2F (button), accent text #FF8A80, success #7FD6A8 on #1E3B2F, warning #F5C76A on #3B2E12. Font on the boards: IBM Plex Sans. In the app use the existing theme and fonts, and match these values; never hard-code colours.

## Board index

| Board | Group | Built in phase | Fed by | Notes |
|---|---|---|---|---|
| HomeDue (Home: rent due soon) | Student app | 10 | GET /stays/home/ (Phase 7); Unread notices badge (Phase 8) | Needs more than a state: a days-left pill, six quick actions (Pay rent, History, Calendar, Notices with badge, Analytics, Help), a next-3-months strip, an attention list that includes a receipt-ready item, and a stay-at-a-glance block with month dots. |
| HomeOverdue (Home: rent overdue) | Student app | 10 | GET /stays/home/ (Phase 7) | Same payload as above with state overdue; the pill shows an alert and the glance block says Overdue. |
| HomePaid (Home: all paid) | Student app | 10 | GET /stays/home/ (Phase 7) | State all_paid: next due is shown, the pay card is replaced by the paid summary. |
| HomeNoStay (Home: no active stay) | Student app | 10 | GET /stays/home/ (Phase 7) | State no_stay; the existing hostel list below is unchanged. |
| StayCreated (Stay created: anniversary hostel) | Student app | 10 | GET /stays/{id}/ billing_summary (Phase 7); Booking confirm flow (Phase 5 creates the stay) | Shows first rent period, next due and the rule text, so the stay payload carries a billing_summary block. |
| StayCreatedFixed (Stay created: fixed-day hostel) | Student app | 10 | GET /stays/{id}/ billing_summary (Phase 7) | Shows the prorated first period (13 days, 2,600 rupees) and the fixed due day. |
| Main (Bookings) | Student app | 10 | GET /stays/ (Phase 7) | Current stay card is tappable; past stays are greyed and not tappable; the server enforces it. |
| ActiveStay (Active stay) | Student app | 10 | GET /stays/{id}/ and /dues/ (Phase 7); POST /stays/{id}/vacate-request/ (Phase 5) | Needs city, rent rule text, next rent with days left, notification count. |
| PayRent (Pay rent) | Student app | 10 | GET /stays/{id}/dues/ (Phase 7); POST /payments/create-rent-order/ (Phase 6) | Has a Pay with choice (UPI or card and net banking), passed to Razorpay checkout as a preference. |
| PayPending (Confirming payment) | Student app | 10 | Existing payment status poll, made rent-aware (Phase 6) | Reuses PaymentScreen and PaymentStatusPoller. |
| PaymentDone (Rent paid) | Student app | 10 | Payment status + GET /stays/{id}/payments/ (Phase 7) | Shows method, masked transaction and the next rent due. |
| PayFailed (Payment failed) | Student app | 10 | Existing payment status poll (Phase 6) | Try again reuses the open attempt rules from create-rent-order. |
| History (Payment history) | Student app | 10 | GET /stays/{id}/payments/?filter=paid|upcoming (Phase 7) | Filters All, Paid, Upcoming; cash entries show Recorded by the hostel owner. |
| Receipt (Receipt) | Student app | 10 | GET /stays/{id}/receipts/{payment_id}/ (Phase 7) | Download and Share are generated on the phone from the receipt data; no server PDF. |
| Calendar (Payment calendar) | Student app | 10 | GET /stays/calendar/?month= (Phase 7) | Legend: covered or paid, awaiting rent, reminder; plus the upcoming rent list. |
| Inbox (Notifications) | Student app | 10 | GET /notifications/?category= (Phase 8) | Filters All, Rent, Stay; each item shows which channels delivered it; includes Owner recorded your payment. |
| Analytics (Stay analytics) | Student app | 10 | GET /stays/{id}/analytics/?range= (Phase 7) | Needs its own endpoint: ranges, on-time and late counts, monthly series, how you paid, next dues. |
| BookingBlocked (Booking blocked: one stay at a time) | Student app | 10 | 409 ACTIVE_STAY_EXISTS with current_stay (Phase 5) | The 409 must carry hostel, room and bed and rent paid until. |
| VacateRequest (Request to vacate) | Student app | 10 | POST /stays/{id}/vacate-request/ (Phase 5) | Needs a planned move-out date and a reason (four options). |
| BookingsSettle (Bookings: pending after stay ended (proposal)) | Needs your decision | 10 | Optional add-on after Phase 10 | A proposal, not in the 11 phases. Past stay with an unpaid last partial month that can be paid. Needs decision D6; an optional add-on prompt is on the page. |
| PushPreview (Push reminders (reminder ladder)) | Backend templates | 8 | Outbox consumer, Part F (Phase 8) | Five wordings: 7 days before, 3 days before, 1 day before, due day, 3 days overdue. |
| EmailPreview (Email reminder) | Backend templates | 8 | Outbox consumer and email (Phase 8) | Sent on the due date and when overdue only. |
| AdminBilling (Admin: billing and rent) | Admin panel | 9 | GET and PUT /hostels/{id}/billing/, POST /stays/billing/preview/ (Phases 9, 4) | Rule choice, due day, first part-month policy, payable window, grace, preview for four sample join dates. |
| AdminDues (Admin: stays and dues) | Admin panel | 9 | GET /stays/admin/ with totals (Phase 9); POST /stays/dues/{id}/send-reminder/ (Phase 8) | Four totals, tab counts, and row actions: Record payment, Send reminder, View, Receipt. |
| AdminRecord (Admin: record offline payment) | Admin panel | 9 | POST /stays/dues/{id}/record-payment/ and /void-payment/ (Phase 6) | Paid on date and time, method (Cash, Bank transfer, UPI direct), reference note; can be voided later. |

## Rules
1. A board shows what the user must see. If the backend cannot supply a field a board shows, report it as a gap; do not drop the field and do not change the board.
2. BookingsSettle is a proposal and is NOT built unless the founder approves decision D6.
3. Boards use sample data (Sample PG, Student A, amounts such as 6,000 rupees). Real data comes from the API.
4. Student names, emails and transaction ids on boards are placeholders or masked; never log or store them in tests.
