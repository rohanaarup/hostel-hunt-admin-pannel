"""
Phase 6 tests: a student pays a Due online (create-rent-order, confirm, webhook), an owner records rent paid offline and can
void that record. Booking payments must behave exactly as before.

Everything is fictional (example.test addresses, order_/pay_ ids made up here). No Razorpay call is real: the client is mocked.
"""
import threading
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock, skipUnless

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.core.sample_data import ensure_sample_catalog
from apps.payments import holds
from apps.payments.confirm import Outcome, confirm_payment
from apps.payments.models import Payment, PaymentAttempt
from apps.rooms.models import Bed, Room
from apps.stays import billing
from apps.stays.dates import today_ist
from apps.stays.models import Due, OutboxEvent, Stay
from apps.stays.test_lifecycle import make_booking, make_payment, make_user, pay_online

on_postgres = skipUnless(connection.vendor == 'postgresql', 'row locks and real concurrency need PostgreSQL')
User = get_user_model()

CREATE_ORDER = 'apps.payments.views.razorpay_client.create_order'
VERIFY_WEBHOOK = 'apps.payments.views.razorpay_client.verify_webhook_signature'


def fake_order(due=None):
    return {'id': f'order_rent_{timezone.now().timestamp():.6f}'.replace('.', '_'), 'currency': 'INR'}


class RentBase(TestCase):
    """A student with a paid booking, an ACTIVE stay, Due 1 paid and Due 2 open."""
    join_days_ago = 45  # Due 2 starts about two weeks ago: overdue, so payable

    def setUp(self):
        self.owner = ensure_sample_catalog()
        self.room = Room.objects.get(hostel__name='Seed Alpha Residency', room_name='Double')
        self.price = self.room.price_per_month
        self.student = make_user('student-a')
        self.booking = make_booking(self.room, 1, self.student, check_in=today_ist() - timedelta(days=self.join_days_ago))
        self.booking_payment, outcome = pay_online(self.booking, 'pay_booking_1')
        assert outcome == Outcome.CONFIRMED
        self.stay = Stay.objects.get(booking=self.booking)
        self.due = self.stay.dues.get(kind=Due.Kind.RENT)
        self.student_client = self.client_for(self.student)
        self.owner_client = self.client_for(self.owner)

    @staticmethod
    def client_for(user):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    def create_rent_order(self, due=None, client=None, **extra):
        due = due or self.due
        client = client or self.student_client
        order = {'id': f'order_{timezone.now().strftime("%H%M%S%f")}', 'currency': 'INR'}
        with mock.patch(CREATE_ORDER, return_value=order) as create:
            response = client.post(reverse('payment-create-rent-order'), {'due_id': str(due.id), **extra}, format='json')
        return response, create

    def rent_payment(self, due=None):
        """An open RENT payment for the due, created through the endpoint."""
        response, _ = self.create_rent_order(due)
        assert response.status_code in (200, 201), response.content
        return Payment.objects.get(pk=response.json()['payment_id'])

    def snapshot_booking_side(self):
        booking = Booking.objects.get(pk=self.booking.pk)
        bed = Bed.objects.get(room=self.room, bed_number=1)
        return (booking.status, booking.updated_at, bed.is_available, bed.held_until, bed.hold_payment_id,
                Stay.objects.count())


# ------------------------------------------------------------------------------------------------ create-rent-order

class CreateRentOrder(RentBase):
    def test_returns_the_same_shape_as_create_order(self):
        response, create = self.create_rent_order()
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(set(response.json()), {'payment_id', 'razorpay_order_id', 'amount', 'currency', 'razorpay_key_id'})
        self.assertEqual(response.json()['currency'], 'INR')
        self.assertEqual(Decimal(response.json()['amount']), self.due.amount)

    def test_the_payment_is_a_rent_payment_for_the_due(self):
        response, create = self.create_rent_order()
        payment = Payment.objects.get(pk=response.json()['payment_id'])
        self.assertEqual(payment.purpose, Payment.Purpose.RENT)
        self.assertEqual(payment.source, Payment.Source.ONLINE)
        self.assertEqual(payment.due_id, self.due.id)
        self.assertEqual(payment.booking_id, self.booking.id)
        self.assertEqual(payment.status, Payment.Status.CREATED)
        self.assertEqual(payment.amount, self.due.amount)
        self.assertIsInstance(payment.amount, Decimal)
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs['amount_paise'], int(self.due.amount * 100))
        self.assertEqual(kwargs['receipt_id'], str(self.due.id))

    def test_a_client_amount_is_ignored(self):
        response, create = self.create_rent_order(amount='1', amount_paise=100)
        self.assertEqual(Decimal(response.json()['amount']), self.due.amount)
        self.assertEqual(create.call_args.kwargs['amount_paise'], int(self.due.amount * 100))

    def test_a_repeat_call_reuses_the_open_order(self):
        first, create_one = self.create_rent_order()
        second, create_two = self.create_rent_order()
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()['payment_id'], second.json()['payment_id'])
        self.assertEqual(first.json()['razorpay_order_id'], second.json()['razorpay_order_id'])
        create_two.assert_not_called()
        self.assertEqual(Payment.objects.filter(due=self.due).count(), 1)

    def test_after_a_failed_payment_a_new_order_is_made(self):
        first = self.rent_payment()
        holds.fail_payment(first.id)
        second, create = self.create_rent_order()
        self.assertEqual(second.status_code, 201)
        self.assertNotEqual(second.json()['payment_id'], str(first.id))
        create.assert_called_once()

    def test_a_due_not_yet_payable_is_refused(self):
        far = Due.objects.create(
            stay=self.stay, period_start=today_ist() + timedelta(days=200), period_end=today_ist() + timedelta(days=229),
            due_date=today_ist() + timedelta(days=200), amount=self.price, status=Due.Status.SCHEDULED)
        response, create = self.create_rent_order(far)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['code'], 'DUE_NOT_PAYABLE')
        create.assert_not_called()

    def test_a_due_inside_the_window_is_payable(self):
        soon = Due.objects.create(
            stay=self.stay, period_start=today_ist() + timedelta(days=3), period_end=today_ist() + timedelta(days=32),
            due_date=today_ist() + timedelta(days=3), amount=self.price, status=Due.Status.SCHEDULED)
        self.assertEqual(self.create_rent_order(soon)[0].status_code, 201)

    def test_paid_waived_and_cancelled_dues_are_refused(self):
        for status in (Due.Status.PAID, Due.Status.WAIVED, Due.Status.CANCELLED):
            Due.objects.filter(pk=self.due.pk).update(status=status)
            response, create = self.create_rent_order()
            self.assertEqual(response.status_code, 409, status)
            self.assertEqual(response.json()['code'], f'DUE_{status}', status)
            create.assert_not_called()
        self.assertFalse(Payment.objects.filter(due=self.due).exists())

    def test_only_the_stays_student(self):
        stranger = self.client_for(make_user('student-b'))
        self.assertEqual(self.create_rent_order(client=stranger)[0].status_code, 404)
        self.assertEqual(self.create_rent_order(client=self.owner_client)[0].status_code, 404)
        self.assertEqual(self.create_rent_order(client=self.client_for(None))[0].status_code, 401)
        self.assertFalse(Payment.objects.filter(due=self.due).exists())

    def test_due_id_is_required(self):
        response = self.student_client.post(reverse('payment-create-rent-order'), {}, format='json')
        self.assertEqual(response.status_code, 400)
        response = self.student_client.post(reverse('payment-create-rent-order'), {'due_id': 'nope'}, format='json')
        self.assertEqual(response.status_code, 404)

    def test_a_gateway_failure_leaves_no_payment(self):
        with mock.patch(CREATE_ORDER, side_effect=RuntimeError('down')):
            response = self.student_client.post(
                reverse('payment-create-rent-order'), {'due_id': str(self.due.id)}, format='json')
        self.assertEqual(response.status_code, 502)
        self.assertFalse(Payment.objects.filter(due=self.due).exists())

    def test_no_bed_is_held_and_the_booking_is_untouched(self):
        before = self.snapshot_booking_side()
        self.create_rent_order()
        self.assertEqual(self.snapshot_booking_side(), before)

    def test_the_existing_payment_screen_endpoints_work_for_a_rent_payment(self):
        payment = self.rent_payment()
        poll = self.student_client.get(reverse('payment-status-poll', args=[payment.id]))
        self.assertEqual(poll.status_code, 200)
        self.assertEqual(poll.json()['status'], 'CREATED')
        self.assertEqual(poll.json()['purpose'], 'RENT')
        self.assertEqual(poll.json()['due_id'], str(self.due.id))
        with mock.patch('apps.payments.views.razorpay_client.get_card_checkout_session', return_value={'k': 'v'}):
            card = self.student_client.post(reverse('payment-card-checkout'), {'payment_id': str(payment.id)}, format='json')
        self.assertEqual(card.status_code, 200)

    def test_status_poll_of_a_booking_payment_says_booking(self):
        poll = self.student_client.get(reverse('payment-status-poll', args=[self.booking_payment.id]))
        self.assertEqual(poll.json()['purpose'], 'BOOKING')
        self.assertIsNone(poll.json()['due_id'])


# ----------------------------------------------------------------------------------------------- confirm_payment RENT

class ConfirmRent(RentBase):
    def test_confirming_pays_the_due_and_emits_one_event(self):
        payment = self.rent_payment()
        before = self.snapshot_booking_side()
        outcome = confirm_payment(payment.id, 'pay_rent_1', 'sig', amount_paise=int(payment.amount * 100), currency='INR',
                                  method=PaymentAttempt.Method.UPI)
        self.assertEqual(outcome, Outcome.CONFIRMED)
        payment.refresh_from_db()
        self.due.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertIsNotNone(payment.verified_at)
        self.assertEqual(payment.paid_via, 'UPI')
        self.assertEqual(self.due.status, Due.Status.PAID)
        self.assertIsNotNone(self.due.paid_at)
        self.assertEqual(self.due.payment_id, payment.id)
        events = OutboxEvent.objects.filter(topic='rent.paid')
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.get().dedupe_key, f'rent-paid-{payment.id}')
        payload = events.get().payload
        self.assertEqual(payload['due_id'], str(self.due.id))
        self.assertEqual(payload['payment_id'], str(payment.id))
        self.assertNotIn('@', str(payload))
        self.assertEqual(self.snapshot_booking_side(), before, 'a rent payment must not touch the booking, bed or stay count')

    def test_a_second_confirmation_changes_nothing(self):
        payment = self.rent_payment()
        confirm_payment(payment.id, 'pay_rent_1', 'sig')
        paid_at = Due.objects.get(pk=self.due.pk).paid_at
        self.assertEqual(confirm_payment(payment.id, 'pay_rent_1', 'sig'), Outcome.ALREADY_CONFIRMED)
        self.assertEqual(Due.objects.get(pk=self.due.pk).paid_at, paid_at)
        self.assertEqual(OutboxEvent.objects.filter(topic='rent.paid').count(), 1)
        self.assertEqual(payment.attempts.filter(status=PaymentAttempt.Status.SUCCESS).count(), 1)

    def test_wrong_amount_is_rejected_and_flagged(self):
        payment = self.rent_payment()
        outcome = confirm_payment(payment.id, 'pay_rent_1', 'sig', amount_paise=100, currency='INR')
        self.assertEqual(outcome, Outcome.AMOUNT_MISMATCH)
        payment.refresh_from_db()
        self.assertTrue(payment.needs_review)
        self.assertNotEqual(Due.objects.get(pk=self.due.pk).status, Due.Status.PAID)
        self.assertFalse(OutboxEvent.objects.filter(topic='rent.paid').exists())

    def test_a_cancelled_due_is_flagged_for_a_refund(self):
        payment = self.rent_payment()
        Due.objects.filter(pk=self.due.pk).update(status=Due.Status.CANCELLED)
        self.assertEqual(confirm_payment(payment.id, 'pay_rent_1', 'sig'), Outcome.FLAGGED)
        payment.refresh_from_db()
        self.assertTrue(payment.needs_review)
        self.assertEqual(Due.objects.get(pk=self.due.pk).status, Due.Status.CANCELLED)
        self.assertFalse(OutboxEvent.objects.filter(topic='rent.paid').exists())

    def test_a_due_already_paid_offline_flags_the_online_capture(self):
        payment = self.rent_payment()
        response = self.owner_client.post(reverse('due-record-payment', args=[self.due.id]), record_body())
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(confirm_payment(payment.id, 'pay_rent_1', 'sig'), Outcome.FLAGGED)
        payment.refresh_from_db()
        self.assertTrue(payment.needs_review)
        self.assertIn('already', payment.review_note.lower())
        due = Due.objects.get(pk=self.due.pk)
        self.assertEqual(due.status, Due.Status.PAID)
        self.assertNotEqual(due.payment_id, payment.id)

    def test_paid_via_comes_from_the_attempt_when_the_webhook_has_no_method(self):
        payment = self.rent_payment()
        PaymentAttempt.objects.create(payment=payment, method=PaymentAttempt.Method.UPI_GPAY)
        confirm_payment(payment.id, 'pay_rent_1', 'sig', method=PaymentAttempt.Method.CARD)
        payment.refresh_from_db()
        self.assertEqual(payment.paid_via, 'UPI')

    def test_a_late_capture_after_a_failed_payment_is_still_honoured(self):
        payment = self.rent_payment()
        holds.fail_payment(payment.id)
        self.assertEqual(confirm_payment(payment.id, 'pay_rent_1', 'sig'), Outcome.CONFIRMED)
        self.assertEqual(Due.objects.get(pk=self.due.pk).status, Due.Status.PAID)

    def test_a_booking_payment_is_confirmed_exactly_as_before(self):
        other = make_booking(self.room, 2, make_user('student-c'))
        payment, outcome = pay_online(other, 'pay_booking_2')
        self.assertEqual(outcome, Outcome.CONFIRMED)
        payment.refresh_from_db()
        self.assertEqual(payment.purpose, Payment.Purpose.BOOKING)
        self.assertEqual(Booking.objects.get(pk=other.pk).status, 'paid')
        self.assertFalse(Bed.objects.get(room=self.room, bed_number=2).is_available)
        self.assertEqual(Stay.objects.filter(booking=other).count(), 1)
        self.assertFalse(OutboxEvent.objects.filter(topic='rent.paid').exists())

    @on_postgres
    def test_lock_order_is_payment_then_due_and_never_bed_or_booking(self):
        payment = self.rent_payment()
        with CaptureQueriesContext(connection) as queries:
            confirm_payment(payment.id, 'pay_rent_1', 'sig')
        locks = []
        for q in queries.captured_queries:
            sql = q['sql']
            if 'FOR UPDATE' in sql:
                for name in ('"payments"', '"dues"', '"beds"', '"bookings"', '"payment_attempts"'):
                    if f'FROM {name}' in sql:
                        locks.append(name)
                        break
        self.assertIn('"payments"', locks)
        self.assertIn('"dues"', locks)
        self.assertLess(locks.index('"payments"'), locks.index('"dues"'))
        self.assertNotIn('"beds"', locks)
        self.assertNotIn('"bookings"', locks)


# ------------------------------------------------------------------------------------------------------------- holds

class RentHoldsAreSkipped(RentBase):
    def age(self, payment, minutes=30):
        Payment.objects.filter(pk=payment.pk).update(created_at=timezone.now() - timedelta(minutes=minutes))
        payment.refresh_from_db()

    def test_expire_if_lapsed_leaves_an_old_rent_payment_alone(self):
        payment = self.rent_payment()
        self.age(payment)
        self.assertFalse(holds.expire_if_lapsed(payment.id))
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.CREATED)

    def test_expire_stale_and_its_dry_run_skip_rent(self):
        payment = self.rent_payment()
        self.age(payment, 600)
        self.assertEqual(holds.expire_stale(dry_run=True)['payments_expired'], 0)
        self.assertEqual(holds.expire_stale()['payments_expired'], 0)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.CREATED)

    def test_the_cleanup_holds_step_skips_rent(self):
        payment = self.rent_payment()
        self.age(payment, 600)
        out = StringIO()
        call_command('cleanup_expired', stdout=out)
        self.assertIn("'payments_expired': 0", out.getvalue())
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.CREATED)
        out = StringIO()
        call_command('expire_stale_holds', stdout=out)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.CREATED)

    def test_the_status_poll_does_not_fail_an_old_rent_payment(self):
        payment = self.rent_payment()
        self.age(payment, 600)
        poll = self.student_client.get(reverse('payment-status-poll', args=[payment.id]))
        self.assertEqual(poll.json()['status'], 'CREATED')

    def test_initiate_card_checkout_does_not_expire_a_rent_payment(self):
        payment = self.rent_payment()
        self.age(payment, 600)
        with mock.patch('apps.payments.views.razorpay_client.get_card_checkout_session', return_value={'k': 'v'}):
            response = self.student_client.post(reverse('payment-card-checkout'), {'payment_id': str(payment.id)},
                                                format='json')
        self.assertEqual(response.status_code, 200)

    def test_booking_attempts_still_expire_as_before(self):
        other = make_booking(self.room, 2, make_user('student-c'))
        old = make_payment(other)
        Payment.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(minutes=30))
        self.assertTrue(holds.expire_if_lapsed(old.id))
        old.refresh_from_db()
        self.assertEqual(old.status, Payment.Status.FAILED)

    def test_the_failed_webhook_closes_a_rent_payment_and_touches_no_bed(self):
        payment = self.rent_payment()
        before = self.snapshot_booking_side()
        self.assertTrue(holds.fail_payment(payment.id))
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(self.snapshot_booking_side(), before)
        self.assertNotEqual(Due.objects.get(pk=self.due.pk).status, Due.Status.PAID)


# ------------------------------------------------------------------------------------------------------------ webhook

class RentWebhook(RentBase):
    def deliver(self, event, payment, entity_extra=None, event_id='evt_rent_1', amount_paise=None):
        entity = {'id': 'pay_rent_1', 'order_id': payment.razorpay_order_id,
                  'amount': amount_paise if amount_paise is not None else int(payment.amount * 100), 'currency': 'INR',
                  **(entity_extra or {})}
        body = {'event': event, 'payload': {'payment': {'entity': entity}}}
        with mock.patch(VERIFY_WEBHOOK, return_value=True):
            return APIClient().post(reverse('payment-webhook'), body, format='json', HTTP_X_RAZORPAY_EVENT_ID=event_id,
                                    HTTP_X_RAZORPAY_SIGNATURE='x')

    def test_captured_pays_the_due(self):
        payment = self.rent_payment()
        response = self.deliver('payment.captured', payment, {'method': 'upi'})
        self.assertEqual(response.json()['status'], 'confirmed')
        self.assertEqual(Due.objects.get(pk=self.due.pk).status, Due.Status.PAID)

    def test_a_duplicate_event_id_is_a_no_op(self):
        payment = self.rent_payment()
        self.assertEqual(self.deliver('payment.captured', payment).json()['status'], 'confirmed')
        paid_at = Due.objects.get(pk=self.due.pk).paid_at
        self.assertEqual(self.deliver('payment.captured', payment).json()['status'], 'duplicate')
        self.assertEqual(Due.objects.get(pk=self.due.pk).paid_at, paid_at)
        self.assertEqual(OutboxEvent.objects.filter(topic='rent.paid').count(), 1)

    def test_a_different_event_for_the_same_payment_is_already_confirmed(self):
        payment = self.rent_payment()
        self.deliver('payment.captured', payment)
        again = self.deliver('order.paid', payment, event_id='evt_rent_2')
        self.assertEqual(again.json()['status'], 'already_confirmed')
        self.assertEqual(OutboxEvent.objects.filter(topic='rent.paid').count(), 1)

    def test_amount_mismatch_is_rejected(self):
        payment = self.rent_payment()
        response = self.deliver('payment.captured', payment, amount_paise=100)
        self.assertEqual(response.json()['status'], 'amount_mismatch')
        self.assertNotEqual(Due.objects.get(pk=self.due.pk).status, Due.Status.PAID)

    def test_the_method_is_read_from_the_razorpay_entity(self):
        expected = {'upi': ('UPI', 'UPI'), 'card': ('CARD', 'CARD'), 'netbanking': ('NETBANKING', 'NETBANKING'),
                    'wallet': ('WALLET', 'WALLET'), 'emi': ('OTHER', 'OTHER'), 'paylater': ('OTHER', 'OTHER')}
        for index, (entity_method, (attempt_method, paid_via)) in enumerate(expected.items()):
            Due.objects.filter(pk=self.due.pk).update(status=Due.Status.PAYABLE, payment=None, paid_at=None)
            Payment.objects.filter(due=self.due).delete()
            payment = self.rent_payment()
            self.deliver('payment.captured', payment, {'method': entity_method, 'id': f'pay_m_{index}'},
                         event_id=f'evt_m_{index}')
            attempt = payment.attempts.get(status=PaymentAttempt.Status.SUCCESS)
            payment.refresh_from_db()
            self.assertEqual(attempt.method, attempt_method, entity_method)
            self.assertEqual(payment.paid_via, paid_via, entity_method)

    def test_a_booking_webhook_without_a_method_still_records_card(self):
        other = make_booking(self.room, 2, make_user('student-c'))
        payment = make_payment(other)
        self.deliver('payment.captured', payment, event_id='evt_b_1')
        self.assertEqual(payment.attempts.get().method, 'CARD')

    def test_a_booking_webhook_reads_the_method_too(self):
        other = make_booking(self.room, 2, make_user('student-c'))
        payment = make_payment(other)
        self.deliver('payment.captured', payment, {'method': 'netbanking'}, event_id='evt_b_2')
        self.assertEqual(payment.attempts.get().method, 'NETBANKING')

    def test_failed_event_closes_a_rent_payment(self):
        payment = self.rent_payment()
        response = self.deliver('payment.failed', payment)
        self.assertEqual(response.json()['status'], 'failed')
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)

    def test_the_card_callback_pays_the_due_through_the_same_function(self):
        payment = self.rent_payment()
        with mock.patch('apps.payments.views.razorpay_client.verify_payment_signature', return_value=True):
            response = self.student_client.post(reverse('payment-verify'), {
                'payment_id': str(payment.id), 'razorpay_payment_id': 'pay_rent_1', 'razorpay_signature': 'sig'},
                format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Due.objects.get(pk=self.due.pk).status, Due.Status.PAID)
        self.assertEqual(Payment.objects.get(pk=payment.pk).paid_via, 'CARD')


# ----------------------------------------------------------------------------------------------- offline recording

def record_body(minutes_ago=60, method='CASH', note='Received in person, receipt book no. 214', **extra):
    return {'paid_at': (timezone.now() - timedelta(minutes=minutes_ago)).isoformat(), 'method': method,
            'reference_note': note, **extra}


class RecordOffline(RentBase):
    def url(self, due=None):
        return reverse('due-record-payment', args=[(due or self.due).id])

    def test_owner_records_cash_rent(self):
        paid_at = timezone.now() - timedelta(hours=3)
        response = self.owner_client.post(self.url(), {
            'paid_at': paid_at.isoformat(), 'method': 'CASH', 'reference_note': 'Receipt book no. 214'}, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        self.due.refresh_from_db()
        self.assertEqual(self.due.status, Due.Status.PAID)
        self.assertEqual(self.due.paid_at, paid_at)
        payment = self.due.payment
        self.assertEqual(payment.purpose, Payment.Purpose.RENT)
        self.assertEqual(payment.source, Payment.Source.OFFLINE_OWNER)
        self.assertEqual(payment.recorded_by_id, self.owner.id)
        self.assertEqual(payment.paid_via, 'CASH')
        self.assertEqual(payment.reference_note, 'Receipt book no. 214')
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertEqual(payment.amount, self.due.amount)
        self.assertEqual(payment.due_id, self.due.id)
        self.assertEqual(payment.booking_id, self.booking.id)
        self.assertEqual(payment.verified_at, paid_at)
        self.assertTrue(payment.receipt_number)

    def test_the_same_event_row_as_the_online_path(self):
        self.owner_client.post(self.url(), record_body(), format='json')
        payment = Due.objects.get(pk=self.due.pk).payment
        event = OutboxEvent.objects.get(topic='rent.paid')
        self.assertEqual(event.dedupe_key, f'rent-paid-{payment.id}')
        self.assertEqual(event.payload['source'], 'OFFLINE_OWNER')
        self.assertNotIn('214', str(event.payload))  # the free-text note never goes to the outbox

    def test_all_three_methods_and_nothing_else(self):
        for index, method in enumerate(('CASH', 'BANK_TRANSFER', 'UPI_DIRECT')):
            due = Due.objects.create(
                stay=self.stay, period_start=date(2030, 1, 1) + timedelta(days=40 * index),
                period_end=date(2030, 1, 30) + timedelta(days=40 * index), due_date=date(2030, 1, 1) + timedelta(days=40 * index),
                amount=self.price, status=Due.Status.SCHEDULED)
            self.assertEqual(self.owner_client.post(self.url(due), record_body(method=method), format='json').status_code, 201)
            self.assertEqual(Due.objects.get(pk=due.pk).payment.paid_via, method)
        for bad in ('UPI', 'CARD', 'ONLINE', '', 'cash'):
            due = Due.objects.create(stay=self.stay, period_start=date(2031, 1, 1), period_end=date(2031, 1, 30),
                                     due_date=date(2031, 1, 1), amount=self.price, status=Due.Status.SCHEDULED)
            self.assertEqual(self.owner_client.post(self.url(due), record_body(method=bad), format='json').status_code,
                             400, bad)
            due.delete()

    def test_paid_at_must_not_be_in_the_future(self):
        future = (timezone.now() + timedelta(hours=2)).isoformat()
        response = self.owner_client.post(self.url(), {'paid_at': future, 'method': 'CASH', 'reference_note': 'x'},
                                          format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Payment.objects.filter(due=self.due, source='OFFLINE_OWNER').exists())

    def test_paid_at_is_required_and_a_note_is_required(self):
        self.assertEqual(self.owner_client.post(self.url(), {'method': 'CASH', 'reference_note': 'x'}, format='json')
                         .status_code, 400)
        self.assertEqual(self.owner_client.post(self.url(), record_body(note=''), format='json').status_code, 400)
        self.assertEqual(self.owner_client.post(self.url(), record_body(note='   '), format='json').status_code, 400)
        self.assertEqual(self.owner_client.post(self.url(), record_body(note='x' * 201), format='json').status_code, 400)

    def test_a_second_call_on_the_same_due_is_refused(self):
        self.assertEqual(self.owner_client.post(self.url(), record_body(), format='json').status_code, 201)
        second = self.owner_client.post(self.url(), record_body(method='BANK_TRANSFER'), format='json')
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.json()['code'], 'DUE_PAID')
        self.assertEqual(Payment.objects.filter(due=self.due, source='OFFLINE_OWNER').count(), 1)
        self.assertEqual(OutboxEvent.objects.filter(topic='rent.paid').count(), 1)

    def test_paid_waived_and_cancelled_dues_are_refused(self):
        for status in (Due.Status.PAID, Due.Status.WAIVED, Due.Status.CANCELLED):
            Due.objects.filter(pk=self.due.pk).update(status=status)
            response = self.owner_client.post(self.url(), record_body(), format='json')
            self.assertEqual(response.status_code, 409, status)
            self.assertEqual(response.json()['code'], f'DUE_{status}')

    def test_the_booking_period_due_cannot_be_recorded_again(self):
        due1 = self.stay.dues.get(kind=Due.Kind.BOOKING_PERIOD)
        self.assertEqual(self.owner_client.post(self.url(due1), record_body(), format='json').status_code, 409)

    def test_cross_tenant_and_student_access_is_denied(self):
        stranger = self.client_for(make_user('owner-b'))
        self.assertEqual(stranger.post(self.url(), record_body(), format='json').status_code, 404)
        self.assertEqual(self.student_client.post(self.url(), record_body(), format='json').status_code, 404)
        self.assertEqual(self.client_for(None).post(self.url(), record_body(), format='json').status_code, 401)
        self.assertEqual(Due.objects.get(pk=self.due.pk).status, self.due.status)

    def test_admin_staff_can_record(self):
        staff = User.objects.create_user(email='staff@example.test', display_name='staff', password='pass12345')
        staff.is_staff = True
        staff.save()
        self.assertEqual(self.client_for(staff).post(self.url(), record_body(), format='json').status_code, 201)
        self.assertEqual(Due.objects.get(pk=self.due.pk).payment.recorded_by_id, staff.id)

    def test_it_never_touches_the_booking_or_the_bed(self):
        before = self.snapshot_booking_side()
        self.owner_client.post(self.url(), record_body(), format='json')
        self.assertEqual(self.snapshot_booking_side(), before)

    def test_an_offline_payment_cannot_be_refunded_through_razorpay(self):
        self.owner_client.post(self.url(), record_body(), format='json')
        payment = Due.objects.get(pk=self.due.pk).payment
        response = self.owner_client.post(reverse('payment-refund', args=[payment.id]), {}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_the_response_has_the_receipt_data_the_board_needs(self):
        response = self.owner_client.post(self.url(), record_body(), format='json')
        body = response.json()
        for key in ('payment_id', 'due_id', 'status', 'amount', 'paid_at', 'method', 'source', 'receipt_number'):
            self.assertIn(key, body)
        self.assertEqual(body['source'], 'OFFLINE_OWNER')
        self.assertEqual(Decimal(body['amount']), self.due.amount)


# ------------------------------------------------------------------------------------------------------------- void

class VoidOffline(RentBase):
    def record(self, due=None):
        due = due or self.due
        response = self.owner_client.post(reverse('due-record-payment', args=[due.id]), record_body(), format='json')
        assert response.status_code == 201, response.content
        return Due.objects.get(pk=due.pk).payment

    def url(self, due=None):
        return reverse('due-void-payment', args=[(due or self.due).id])

    def test_owner_voids_an_offline_payment(self):
        payment = self.record()
        response = self.owner_client.post(self.url(), {'reason': 'Entered against the wrong student'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        payment.refresh_from_db()
        self.due.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.VOIDED)
        self.assertEqual(payment.voided_by_id, self.owner.id)
        self.assertIsNotNone(payment.voided_at)
        self.assertEqual(payment.void_reason, 'Entered against the wrong student')
        self.assertEqual(payment.due_id, self.due.id)  # the original row is kept
        self.assertEqual(payment.source, Payment.Source.OFFLINE_OWNER)
        self.assertIn(self.due.status, (Due.Status.PAYABLE, Due.Status.SCHEDULED))
        self.assertIsNone(self.due.paid_at)
        self.assertIsNone(self.due.payment_id)

    def test_it_is_audited_with_an_event_row(self):
        payment = self.record()
        self.owner_client.post(self.url(), {'reason': 'Typo in the amount'}, format='json')
        event = OutboxEvent.objects.get(topic='rent.payment_voided')
        self.assertEqual(event.dedupe_key, f'rent-voided-{payment.id}')
        self.assertEqual(event.payload['voided_by'], str(self.owner.id))
        self.assertEqual(event.payload['due_id'], str(self.due.id))
        self.assertNotIn('Typo', str(event.payload))  # free text stays on the payment row, not in the outbox

    def test_an_overdue_due_reads_overdue_again_by_date(self):
        self.record()
        self.owner_client.post(self.url(), {'reason': 'Wrong person'}, format='json')
        due = Due.objects.get(pk=self.due.pk)
        snap = self.stay.billing_snapshot
        self.assertEqual(billing.effective_status(due.status, today_ist(), due.due_date, snap['payable_window_days'],
                                                  snap['grace_days']), billing.OVERDUE)

    def test_the_due_can_be_paid_again_after_a_void(self):
        self.record()
        self.owner_client.post(self.url(), {'reason': 'Wrong person'}, format='json')
        again = self.owner_client.post(reverse('due-record-payment', args=[self.due.id]), record_body(), format='json')
        self.assertEqual(again.status_code, 201)
        self.assertEqual(Payment.objects.filter(due=self.due).count(), 2)
        self.assertEqual(Payment.objects.filter(due=self.due, status=Payment.Status.VOIDED).count(), 1)

    def test_a_reason_is_required(self):
        self.record()
        for body in ({}, {'reason': ''}, {'reason': '   '}, {'reason': 'x' * 201}):
            self.assertEqual(self.owner_client.post(self.url(), body, format='json').status_code, 400, body)
        self.assertEqual(Due.objects.get(pk=self.due.pk).status, Due.Status.PAID)

    def test_a_second_void_is_refused(self):
        self.record()
        self.assertEqual(self.owner_client.post(self.url(), {'reason': 'Typo'}, format='json').status_code, 200)
        second = self.owner_client.post(self.url(), {'reason': 'Typo again'}, format='json')
        self.assertEqual(second.status_code, 409)
        self.assertEqual(OutboxEvent.objects.filter(topic='rent.payment_voided').count(), 1)

    def test_an_online_payment_can_never_be_voided_here(self):
        payment = self.rent_payment()
        confirm_payment(payment.id, 'pay_rent_1', 'sig')
        response = self.owner_client.post(self.url(), {'reason': 'Please'}, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['code'], 'ONLINE_PAYMENT_NEEDS_REFUND')
        self.assertEqual(Due.objects.get(pk=self.due.pk).status, Due.Status.PAID)
        self.assertEqual(Payment.objects.get(pk=payment.pk).status, Payment.Status.SUCCESS)

    def test_the_booking_period_payment_cannot_be_voided(self):
        due1 = self.stay.dues.get(kind=Due.Kind.BOOKING_PERIOD)
        response = self.owner_client.post(self.url(due1), {'reason': 'Please'}, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Due.objects.get(pk=due1.pk).status, Due.Status.PAID)

    def test_an_unpaid_due_cannot_be_voided(self):
        response = self.owner_client.post(self.url(), {'reason': 'Please'}, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['code'], 'DUE_NOT_PAID')

    def test_cross_tenant_access_is_denied(self):
        self.record()
        stranger = self.client_for(make_user('owner-b'))
        self.assertEqual(stranger.post(self.url(), {'reason': 'x'}, format='json').status_code, 404)
        self.assertEqual(self.student_client.post(self.url(), {'reason': 'x'}, format='json').status_code, 404)
        self.assertEqual(self.client_for(None).post(self.url(), {'reason': 'x'}, format='json').status_code, 401)
        self.assertEqual(Due.objects.get(pk=self.due.pk).status, Due.Status.PAID)

    def test_admin_staff_can_void(self):
        self.record()
        staff = User.objects.create_user(email='staff@example.test', display_name='staff', password='pass12345')
        staff.is_staff = True
        staff.save()
        self.assertEqual(self.client_for(staff).post(self.url(), {'reason': 'Audit fix'}, format='json').status_code, 200)

    def test_a_voided_payment_is_not_revenue(self):
        payment = self.record()
        self.owner_client.post(self.url(), {'reason': 'Typo'}, format='json')
        self.assertFalse(Payment.objects.filter(pk=payment.pk, status=Payment.Status.SUCCESS).exists())


# ----------------------------------------------------------------------------------------------------- model and misc

class ModelAdditions(RentBase):
    def test_defaults_keep_every_old_row_a_booking_payment(self):
        payment = make_payment(make_booking(self.room, 2, make_user('student-c')))
        self.assertEqual(payment.purpose, Payment.Purpose.BOOKING)
        self.assertEqual(payment.source, Payment.Source.ONLINE)
        self.assertIsNone(payment.due_id)
        self.assertIsNone(payment.recorded_by_id)
        self.assertEqual(payment.reference_note, '')
        self.assertEqual(payment.paid_via, '')

    def test_receipt_number_is_derived_not_stored(self):
        payment = self.booking_payment
        self.assertNotIn('receipt_number', [f.name for f in Payment._meta.get_fields()])
        self.assertEqual(payment.receipt_number, Payment.objects.get(pk=payment.pk).receipt_number)
        other = make_payment(make_booking(self.room, 2, make_user('student-c')))
        self.assertNotEqual(payment.receipt_number, other.receipt_number)
        self.assertTrue(payment.receipt_number.startswith('HH-'))

    def test_payment_lists_say_which_kind_of_payment_each_row_is(self):
        payment = self.rent_payment()
        mine = self.student_client.get(reverse('payment-list')).json()
        rows = mine['results'] if isinstance(mine, dict) and 'results' in mine else mine
        by_id = {row['id']: row for row in rows}
        self.assertEqual(by_id[str(payment.id)]['purpose'], 'RENT')
        self.assertEqual(by_id[str(self.booking_payment.id)]['purpose'], 'BOOKING')
        admin_rows = self.owner_client.get(reverse('payment-admin-list')).json()
        admin_rows = admin_rows['results'] if isinstance(admin_rows, dict) and 'results' in admin_rows else admin_rows
        self.assertEqual({row['id']: row['purpose'] for row in admin_rows}[str(payment.id)], 'RENT')

    def test_the_django_admin_cannot_edit_the_new_payment_fields(self):
        from django.contrib import admin as django_admin
        readonly = django_admin.site._registry[Payment].readonly_fields
        for name in ('purpose', 'due', 'source', 'recorded_by', 'reference_note', 'paid_via', 'voided_at', 'voided_by',
                     'void_reason'):
            self.assertIn(name, readonly)

    def test_the_migration_is_additive_and_defaulted(self):
        from django.db.migrations.loader import MigrationLoader
        migration = MigrationLoader(connection).get_migration('payments', '0006_payment_rent_fields')
        names = {type(op).__name__ for op in migration.operations}
        self.assertLessEqual(names, {'AddField', 'AlterField'})
        for op in migration.operations:
            if type(op).__name__ == 'AddField' and not op.field.null:
                self.assertIsNotNone(op.field.db_default, op.name)  # the previous app version must still insert


# ------------------------------------------------------------------------------------------------------ concurrency

@on_postgres
class RentConcurrency(TransactionTestCase):
    def setUp(self):
        self.owner = ensure_sample_catalog()
        self.room = Room.objects.get(hostel__name='Seed Alpha Residency', room_name='Double')
        self.student = make_user('student-a')
        booking = make_booking(self.room, 1, self.student, check_in=today_ist() - timedelta(days=45))
        pay_online(booking, 'pay_booking_1')
        self.stay = Stay.objects.get(booking=booking)
        self.due = self.stay.dues.get(kind=Due.Kind.RENT)
        client = APIClient()
        client.force_authenticate(self.student)
        with mock.patch(CREATE_ORDER, return_value={'id': 'order_rent_race', 'currency': 'INR'}):
            response = client.post(reverse('payment-create-rent-order'), {'due_id': str(self.due.id)}, format='json')
        self.payment = Payment.objects.get(pk=response.json()['payment_id'])

    def race(self, workers):
        barrier = threading.Barrier(len(workers))
        errors = []

        def run(work):
            try:
                barrier.wait(10)
                work()
            except Exception as exc:  # pragma: no cover
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=run, args=(w,)) for w in workers]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        self.assertEqual(errors, [])

    def assert_paid_once(self):
        due = Due.objects.get(pk=self.due.pk)
        self.assertEqual(due.status, Due.Status.PAID)
        self.assertEqual(OutboxEvent.objects.filter(topic='rent.paid').count(), 1)
        self.assertEqual(Payment.objects.filter(due=self.due, status=Payment.Status.SUCCESS).count(), 1)

    def test_webhook_and_card_callback_pay_the_due_once(self):
        payment = self.payment
        body = {'event': 'payment.captured', 'payload': {'payment': {'entity': {
            'id': 'pay_rent_1', 'order_id': payment.razorpay_order_id, 'amount': int(payment.amount * 100),
            'currency': 'INR', 'method': 'upi'}}}}

        def webhook():
            with mock.patch(VERIFY_WEBHOOK, return_value=True):
                APIClient().post(reverse('payment-webhook'), body, format='json', HTTP_X_RAZORPAY_EVENT_ID='evt_race_1',
                                 HTTP_X_RAZORPAY_SIGNATURE='x')

        def verify():
            client = APIClient()
            client.force_authenticate(self.student)
            with mock.patch('apps.payments.views.razorpay_client.verify_payment_signature', return_value=True):
                client.post(reverse('payment-verify'), {'payment_id': str(payment.id), 'razorpay_payment_id': 'pay_rent_1',
                                                         'razorpay_signature': 'sig'}, format='json')

        self.race([webhook, verify])
        self.assert_paid_once()

    def test_two_confirmations_at_once(self):
        self.race([lambda: confirm_payment(self.payment.id, 'pay_rent_1', 'sig')] * 2)
        self.assert_paid_once()

    def test_two_offline_records_at_once_make_one_payment(self):
        client = APIClient()
        client.force_authenticate(self.owner)
        url = reverse('due-record-payment', args=[self.due.id])
        self.race([lambda: client.post(url, record_body(), format='json')] * 2)
        self.assertEqual(Payment.objects.filter(due=self.due, source='OFFLINE_OWNER').count(), 1)
        self.assertEqual(OutboxEvent.objects.filter(topic='rent.paid').count(), 1)

    def test_offline_record_racing_an_online_capture_pays_once(self):
        client = APIClient()
        client.force_authenticate(self.owner)
        url = reverse('due-record-payment', args=[self.due.id])
        self.race([lambda: client.post(url, record_body(), format='json'),
                   lambda: confirm_payment(self.payment.id, 'pay_rent_1', 'sig')])
        due = Due.objects.get(pk=self.due.pk)
        self.assertEqual(due.status, Due.Status.PAID)
        self.assertEqual(OutboxEvent.objects.filter(topic='rent.paid').count(), 1)
        # whichever lost is flagged (online) or refused (offline): never two paid records
        self.assertEqual(Payment.objects.filter(due=self.due, status=Payment.Status.SUCCESS).count(), 1)
