# Admin click-through (Phase 9)

A walk-through you can repeat on STAGING with a test owner and a test student. Nothing here needs a real payment. If a step does not look
as described, write down the step number and what you saw; do not fix anything by hand.

**You need:** the staging admin site, an owner login, one hostel with a room that has a price, and at least one student with a paid stay
(book a bed as a student; mark the booking paid from Bookings if there is no online test payment). Staging must have `STAYS_ENABLED` on if
you also want to check the student side.

| # | Do this | You should see |
|---|---|---|
| 1 | Sign in as the owner. In the left menu click **Stays and rent**. | The page "Stays and dues" with four tiles (Collected this month, Due this week, Overdue, Active stays), the tabs All, Overdue, Due this week and Paid with counts, and a table. |
| 2 | Click **Billing rule**. | "Billing and rent". "Same day each month" is selected. The monthly rent is read-only. The preview table shows rows for 18 Sep 2026 with 5 items (Booking, Rent 1 to Rent 4). |
| 3 | Click the other join dates (31 Jan 2027, 1 Sep 2026, 5 Sep 2026). | The table changes. For 31 Jan 2027 the next due is 28 Feb 2027 (short months use their last day). |
| 4 | Choose **Fixed day of the month**, due day **1**, **Prorate the first period**. Pick 18 Sep 2026. | Booking 18 Sep to 30 Sep 2026, amount about 13 of 30 days of the rent (for rent 6,000: Rs 2,600), then Rent 1 from 1 Oct 2026. The sentence under the table says "First period is prorated: 13 of 30 days = Rs 2,600". |
| 5 | Type 29 in **Other day** and click **Save billing rule**. | A message under Other day: the due day must be a whole number from 1 to 28. Nothing is saved. |
| 6 | Set Other day back to 1 (or click the 1 button), set Payable window 10 and Grace 2, click **Save billing rule**. | "Billing rule saved. It applies to new stays only." Reload the page: the same choices are still there. |
| 7 | Click **View stays and dues**. Students who were already staying are unchanged. | The table shows the same stays and amounts as before. |
| 8 | Back on Edit details (left menu), open the **Billing** tab. | The same editor with the same saved rule and the same preview. |
| 9 | On **Stays and rent**, find a row with the status **Overdue** (make one by choosing a stay whose rent date has passed). Click **Record payment**. | The Record offline payment window: student, room and bed, the Rent period and Amount (not editable), Paid on, Time, three buttons (Cash, Bank transfer, UPI direct), a Reference note, and the sentence about "Recorded by owner" and "voided later". |
| 10 | Pick tomorrow's date and click **Save payment**. | The message "The payment time cannot be in the future." plus messages for the missing method and note. Nothing is saved. |
| 11 | Set today's date and a time in the past, choose **Cash**, write "Receipt book 214", click **Save payment**. | The window closes, "Payment recorded for ...", and the row moves out of Overdue (the totals change). |
| 12 | On the same row click **Void payment**, enter a reason, confirm. | The rent is unpaid again and the row is back under Overdue or Payable. A second void of the same payment is not possible. |
| 13 | On a **Payable** row click **Send reminder**. Click it again. | First: "Reminder queued for ...". Second: a message that a reminder was already sent today. (The student gets the notice from the next outbox run, and not between 21:00 and 08:00.) |
| 14 | On any row click **End stay**. | A question that says the bed is released and future rent that is not yet due is cancelled. Cancel leaves everything as it was. Confirm ends the stay and it leaves the list. |
| 15 | Open **Payments**. | Columns Type (Booking or Rent), Method and Source (Online or Offline). The two selects filter by type and source. The rent you recorded in step 11 shows as Rent, Cash, Offline. |
| 16 | Open **Bookings**. | A booking that became a stay shows a small "Stay active" badge; a stay flagged for review also shows "Needs review". |
| 17 | Sign in as a different owner (or a student). | Another owner sees none of the first owner's stays. A student cannot reach the billing endpoints (you will see an empty page or an error, never the other owner's data). |

**If a step fails:** note the step, the text on screen, and the time. Do not repeat step 11 or 12 more than once on the same rent.
