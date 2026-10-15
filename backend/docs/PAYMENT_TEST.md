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
