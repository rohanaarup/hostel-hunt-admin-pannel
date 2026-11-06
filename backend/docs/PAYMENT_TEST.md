# Staging payment test (Razorpay TEST mode)

Money-flow changes are never tested for the first time on production. Do every step on STAGING with Razorpay
TEST keys. Names only below; never paste a key or secret into a chat or a file in the repository.

## Before you start
1. Staging has these environment variables: `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` (TEST mode keys, they start with `rzp_test_`), `RAZORPAY_WEBHOOK_SECRET`, an email provider (`EMAIL_API_PROVIDER`, `EMAIL_API_KEY`, `DEFAULT_FROM_EMAIL`) so a student can sign up with an email code, and `SENTRY_DSN` if you want errors reported.
2. In the Razorpay dashboard (TEST mode) add a webhook: URL `https://<staging host>/api/v1/payments/webhook/`, secret = the value you put in `RAZORPAY_WEBHOOK_SECRET`, events `payment.captured`, `order.paid`, `payment.failed`.
3. Staging has sample data (`python manage.py seed_staging`, staging only) or one hostel with a room and an owner login.
4. In the Django admin (`/admin/`) open Payments. You will use it to check the results.

## The test
Use the card test number Razorpay documents for test mode. UPI intent opens a real UPI app and may not work in test mode, so UPI is not part of this script.

| # | Do this | You should see |
|---|---|---|
| 1 | In the app sign up a student (email code), open a staging hostel, choose a bed in the Double room, pay online with the test card. | Booking shows paid. In `/admin/` the payment is SUCCESS, the booking is paid, `needs review` is not ticked. |
| 2 | Start another booking for a different bed. When the card form opens, tap Pay twice quickly, then finish with the test card. | One successful payment. No error screen. In `/admin/` the payment has ONE attempt row with status SUCCESS. |
| 3 | On your computer run the replay tool (below) with the payment from step 1, 2 times. | First delivery: `duplicate` or `already_confirmed`. Every repeat: `duplicate`. The payment is unchanged. |
| 4 | As the owner, refund Rs 1000 of a Rs 6500 payment (admin site or the refund endpoint). | Payment stays SUCCESS, `refunded amount` = 1000. |
| 5 | Refund the remaining Rs 5500. | Payment becomes REFUNDED. |
| 6 | Try to refund again. | Refused: "already refunded in full". Razorpay shows only two refunds. |
| 7 | Create a booking and open the card form but do NOT pay. Wait 16 minutes. Open the app's payment screen again (or poll `/api/v1/payments/status/<id>/`). | Status FAILED (the hold lapsed) even before the clean-up job ran. The bed can be booked by another student. |
| 8 | Run `python manage.py cleanup_expired --dry-run` where you have a shell, or wait for the cron job. | It prints counts and changes nothing in a dry run. |

Replay tool (Windows cmd, from the `backend` folder):

```
set RAZORPAY_WEBHOOK_SECRET=<TEST webhook secret>
python ops/replay_webhook.py --url https://<staging host>/api/v1/payments/webhook/ --order order_XXXX --payment pay_XXXX --amount-rupees 6500 --times 2
```

## What to do with a payment that needs review
Payments with `needs review` ticked are cases where money was captured but the system refused to confirm it
(late payment after the bed went to someone else, wrong amount, a duplicate capture, an unknown refund
outcome). Read the note, refund in the Razorpay dashboard, then untick nothing: the flag stays as the record.

## Rent scenarios (Phase 6)

Do these on STAGING with Razorpay TEST keys, after the booking script above passes. You need a student with an ACTIVE stay
(the booking in step 1 creates one) and a rent due that can be paid: a due is payable from 7 days before its date (the hostel's
payable window), and a late one is payable too. On a brand-new stay Due 2 is a month away, so for the test either wait, or ask
Claude to join the student a month earlier on the staging copy (a `check_in_date` about 25 days in the past gives a payable Due 2).

| # | Do this | You should see |
|---|---|---|
| R1 | In the app (or with `POST /api/v1/payments/create-rent-order/` and `{"due_id": "<id>"}`) start a rent payment, then pay with the test card. | The reply has the same five fields as create-order. After paying: the payment is SUCCESS with purpose RENT, the due is PAID with a paid time, **the booking is unchanged and the bed is not touched**, and `/admin/` shows one `rent.paid` outbox row. |
| R2 | Call create-rent-order again for the same due before paying. | HTTP 200 with the SAME payment id and order id (no second order in Razorpay). |
| R3 | With the replay tool (below) send `payment.captured` for the rent order, 2 times. | First delivery `confirmed` or `already_confirmed`; the repeat `duplicate`. The due stays paid once; still one `rent.paid` row. |
| R4 | Replay with a wrong amount (for example `--amount-rupees 100`) for another unpaid rent order. | `amount_mismatch`. The due stays unpaid and the payment is flagged `needs review`. |
| R5 | Start a rent payment, do not pay, wait over 15 minutes (the booking hold time), then pay or replay the capture. | It is CONFIRMED: a rent payment never expires like a bed hold. `cleanup_expired --dry-run` shows `payments_expired` 0 for it. |
| R6 | Pay a rent online in Razorpay, then as the owner call `POST /api/v1/stays/dues/<id>/record-payment/` for the SAME due. | Refused (409 `DUE_PAID`). If you record it first and the student then pays online, the online payment is flagged `needs review` for a refund. |
| R7 | As the owner record cash rent for a different due (paid time not in the future, a reference note). Then void it with a reason. | Recorded: due PAID, payment source OFFLINE_OWNER. Voided: the payment shows VOIDED, the due is open again, a second void is refused, and an online payment can never be voided (use the refund). |

Replay a rent order exactly like a booking order (the tool does not care which it is):

```
python ops/replay_webhook.py --url https://<staging host>/api/v1/payments/webhook/ --order order_XXXX --payment pay_XXXX --amount-rupees 6000 --times 2
```

**Result of the local rehearsal (Phase 6, scratch database, not staging):** see `KNOWN_GAPS.md` G6-01. Staging was paused, so R1 and the
real-card steps are not yet proven against Razorpay.
