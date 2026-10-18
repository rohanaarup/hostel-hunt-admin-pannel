"""
F4 Part 1: tests that REPRODUCE the payment findings (G13, G14). They assert the correct behaviour,
so every test here is expected to FAIL on the code as it stands today and to pass after F4 Part 2.

Nothing here talks to Razorpay: the SDK wrapper functions are patched. The concurrency tests use two
real database connections and only run on PostgreSQL (SQLite ignores row locks).
"""
import json
import threading
from datetime import timedelta
from io import StringIO
from unittest import mock, skipUnless

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.core.sample_data import ensure_sample_catalog
from apps.payments import test_locking as helpers
from apps.payments.models import Payment, PaymentAttempt
from apps.rooms.models import Bed, Room

on_postgres = skipUnless(connection.vendor == 'postgresql', 'row locks exist only on PostgreSQL')

VIEWS = 'apps.payments.views.razorpay_client'
SIGNATURE_OK = mock.patch(f'{VIEWS}.verify_payment_signature', return_value=True)


def api(user=None):
    client = APIClient()
    client.raise_request_exception = False  # a crash must show up as a 500, not as an exception
    if user is not None:
        client.force_authenticate(user=user)
    return client


def verify(student, payment_id, razorpay_payment_id='pay_test_0001'):
    with SIGNATURE_OK:
        return api(student).post(reverse('payment-verify'), {
            'payment_id': payment_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': 'sig',
        }, format='json')


def webhook(event, order_id, razorpay_payment_id, amount_paise, event_id=None):
    body = {'event': event, 'payload': {'payment': {'entity': {
        'id': razorpay_payment_id, 'order_id': order_id, 'amount': amount_paise, 'currency': 'INR',
    }}}}
    extra = {'HTTP_X_RAZORPAY_SIGNATURE': 'sig'}
    if event_id:
        extra['HTTP_X_RAZORPAY_EVENT_ID'] = event_id
    with mock.patch(f'{VIEWS}.verify_webhook_signature', return_value=True):
        return api().post(reverse('payment-webhook'), json.dumps(body), content_type='application/json', **extra)


def start_order(room, bed_number, email):
    student, booking = helpers.make_online_booking(room, bed_number, email)
    created = helpers.create_order(student, booking)
    assert created.status_code == 201, created.data
    return student, booking, created.data['payment_id'], created.data['razorpay_order_id']


class PaymentCase(TestCase):
    def setUp(self):
        cache.clear()  # per-address throttle counters live in process memory and must not leak between tests
        self.owner = ensure_sample_catalog()
        self.room = Room.objects.order_by('room_name').first()  # the Double room, 6500 INR a month
        self.paise = int(self.room.price_per_month * 100)


class DoubleTapTests(PaymentCase):
    """G13: a student who taps Pay twice has two INITIATED card attempts; verify then crashes after the money moved."""

    def test_two_card_checkouts_then_verify_does_not_return_500(self):
        student, booking, payment_id, _ = start_order(self.room, 1, 'a@example.test')
        for _ in range(2):  # the Pay button tapped twice
            api(student).post(reverse('payment-card-checkout'), {'payment_id': payment_id}, format='json')
        response = verify(student, payment_id)
        self.assertEqual(response.status_code, 200, 'a double tap on Pay must not turn a paid order into a 500')
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'paid')


class WebhookTests(PaymentCase):
    def test_replayed_capture_after_a_refund_does_not_resurrect_the_payment(self):
        student, booking, payment_id, order_id = start_order(self.room, 1, 'a@example.test')
        self.assertEqual(verify(student, payment_id, 'pay_replay_1').status_code, 200)
        with mock.patch(f'{VIEWS}.initiate_refund', return_value={'id': 'rfnd_1'}):
            refund = api(self.owner).post(reverse('payment-refund', args=[payment_id]), {}, format='json')
        self.assertEqual(refund.status_code, 200)

        replay = webhook('payment.captured', order_id, 'pay_replay_1', self.paise, event_id='evt_replay_1')

        self.assertEqual(replay.status_code, 200, 'a replayed webhook must be acknowledged, never a 500')
        self.assertEqual(Payment.objects.get(id=payment_id).status, Payment.Status.REFUNDED)

    def test_capture_for_the_wrong_amount_is_not_confirmed(self):
        student, booking, payment_id, order_id = start_order(self.room, 1, 'a@example.test')
        webhook('payment.captured', order_id, 'pay_short_1', 100)  # Rs 1 captured against a Rs 6500 order
        self.assertNotEqual(Payment.objects.get(id=payment_id).status, Payment.Status.SUCCESS)
        booking.refresh_from_db()
        self.assertNotEqual(booking.status, 'paid')

    def test_late_capture_on_an_expired_hold_never_gives_a_second_paid_booking_for_one_bed(self):
        first, first_booking, first_payment, first_order = start_order(self.room, 1, 'a@example.test')
        Bed.objects.filter(room=self.room, bed_number=1).update(held_until=timezone.now() - timedelta(hours=1))
        call_command('expire_stale_holds', stdout=StringIO())  # the schedule releases the first student's hold

        second, second_booking, second_payment, _ = start_order(self.room, 1, 'b@example.test')
        self.assertEqual(verify(second, second_payment, 'pay_second_1').status_code, 200)

        # the first student's money is captured after all, long after the hold lapsed
        webhook('payment.captured', first_order, 'pay_first_1', self.paise, event_id='evt_late_1')

        paid = Booking.objects.filter(room=self.room, bed_number='1', status='paid').count()
        self.assertEqual(paid, 1, 'two bookings are now paid for the same bed; the late one needs a manual refund')

    def test_payment_failed_event_for_an_old_order_does_not_release_a_new_holder(self):
        first, _, first_payment, first_order = start_order(self.room, 1, 'a@example.test')
        Bed.objects.filter(room=self.room, bed_number=1).update(held_until=timezone.now() - timedelta(hours=1))
        call_command('expire_stale_holds', stdout=StringIO())
        start_order(self.room, 1, 'b@example.test')  # a second student now holds the bed
        held_until = Bed.objects.get(room=self.room, bed_number=1).held_until
        self.assertIsNotNone(held_until)

        webhook('payment.failed', first_order, 'pay_first_1', self.paise, event_id='evt_fail_1')

        self.assertIsNotNone(Bed.objects.get(room=self.room, bed_number=1).held_until,
                             "the first order's failure released the second student's hold")


class RefundTests(PaymentCase):
    def paid(self):
        student, booking, payment_id, _ = start_order(self.room, 1, 'a@example.test')
        self.assertEqual(verify(student, payment_id, 'pay_refund_1').status_code, 200)
        return payment_id

    def test_a_partial_refund_does_not_mark_the_whole_payment_refunded(self):
        payment_id = self.paid()
        with mock.patch(f'{VIEWS}.initiate_refund', return_value={'id': 'rfnd_1'}):
            response = api(self.owner).post(reverse('payment-refund', args=[payment_id]), {'amount': '1000'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(Payment.objects.get(id=payment_id).status, Payment.Status.REFUNDED,
                            'Rs 1000 of Rs 6500 was refunded; the payment is not fully refunded')

    def test_status_poll_reports_an_expired_hold_without_waiting_for_the_schedule(self):
        student, _, payment_id, _ = start_order(self.room, 1, 'a@example.test')
        Bed.objects.filter(room=self.room, bed_number=1).update(held_until=timezone.now() - timedelta(minutes=1))
        response = api(student).get(reverse('payment-status-poll', args=[payment_id]))
        self.assertEqual(response.data['status'], Payment.Status.FAILED,
                         'a hold that has lapsed must read as expired even if the cleanup has not run yet')


class BedLifecycleTests(PaymentCase):
    """G13: bookings that do not go through Razorpay never touch the Bed row."""

    def test_marking_an_offline_booking_paid_takes_the_bed(self):
        student = get_user_model().objects.create_user(email='off@example.test', display_name='Off', password='pass12345')
        booking = Booking.objects.create(
            hostel=self.room.hostel, student=student, student_name='Off', room=self.room,
            bed_number='1', payment_mode='offline', status='confirmed',
        )
        response = api(self.owner).patch(reverse('booking-mark-paid', args=[booking.id]))
        self.assertEqual(response.status_code, 200)
        bed = Bed.objects.filter(room=self.room, bed_number=1).first()
        self.assertTrue(bed is not None and not bed.is_available, 'a bed that is paid for offline must stop being offered')

    def test_a_booking_for_a_bed_that_is_already_paid_is_refused(self):
        student, booking, payment_id, _ = start_order(self.room, 1, 'a@example.test')
        self.assertEqual(verify(student, payment_id, 'pay_taken_1').status_code, 200)
        response = api().post(reverse('booking-list'), {
            'hostel': str(self.room.hostel_id), 'room': str(self.room.id), 'bed_number': '1',
            'payment_mode': 'online', 'student_name': 'Late', 'student_phone': '9000000001',
        }, format='json')
        self.assertIn(response.status_code, (400, 409), 'the bed is taken; the booking must not be accepted')


@on_postgres
class ConcurrencyTests(TransactionTestCase):
    """Two requests for the same payment really at the same moment (both pass the 'already done?' check)."""

    ROUNDS = 6

    def setUp(self):
        cache.clear()
        self.owner = ensure_sample_catalog()
        self.room = Room.objects.order_by('room_name').first()
        self.paise = int(self.room.price_per_month * 100)

    @staticmethod
    def parallel(*calls):
        results = [None] * len(calls)

        def run(i, call):
            try:
                results[i] = call()
            except BaseException as exc:  # reported by the assertions below
                results[i] = exc
            finally:
                connection.close()

        threads = [threading.Thread(target=run, args=(i, c)) for i, c in enumerate(calls)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(60)
        return results

    @staticmethod
    def meet(barrier, value):
        def hook(*args, **kwargs):
            try:
                barrier.wait(5)  # both requests are inside, past their 'already paid?' check
            except threading.BrokenBarrierError:
                pass
            return value
        return hook

    def test_two_verifies_at_once_confirm_once_and_neither_fails(self):
        problems = []
        for n in range(self.ROUNDS):
            student, _, payment_id, _ = start_order(self.room, n + 1, f'v{n}@example.test')
            barrier = threading.Barrier(2)

            def call():
                return api(student).post(reverse('payment-verify'), {
                    'payment_id': payment_id, 'razorpay_payment_id': f'pay_par_{n}', 'razorpay_signature': 'sig',
                }, format='json').status_code

            with mock.patch(f'{VIEWS}.verify_payment_signature', side_effect=self.meet(barrier, True)):
                codes = self.parallel(call, call)
            confirmed = PaymentAttempt.objects.filter(payment_id=payment_id, status=PaymentAttempt.Status.SUCCESS).count()
            if codes != [200, 200] or confirmed != 1:
                problems.append((n, codes, confirmed))
        self.assertEqual(problems, [], 'rounds where verify answered with an error or confirmed twice')

    def test_verify_and_webhook_at_once_confirm_once_and_neither_fails(self):
        problems = []
        for n in range(self.ROUNDS):
            student, _, payment_id, order_id = start_order(self.room, n + 1, f'w{n}@example.test')
            barrier = threading.Barrier(2)

            def verify_call():
                return api(student).post(reverse('payment-verify'), {
                    'payment_id': payment_id, 'razorpay_payment_id': f'pay_mix_{n}', 'razorpay_signature': 'sig',
                }, format='json').status_code

            def webhook_call():
                body = {'event': 'payment.captured', 'payload': {'payment': {'entity': {
                    'id': f'pay_mix_{n}', 'order_id': order_id, 'amount': self.paise, 'currency': 'INR'}}}}
                return api().post(reverse('payment-webhook'), json.dumps(body), content_type='application/json',
                                  HTTP_X_RAZORPAY_SIGNATURE='sig').status_code

            with mock.patch(f'{VIEWS}.verify_payment_signature', side_effect=self.meet(barrier, True)), \
                 mock.patch(f'{VIEWS}.verify_webhook_signature', side_effect=self.meet(barrier, True)):
                codes = self.parallel(verify_call, webhook_call)
            confirmed = PaymentAttempt.objects.filter(payment_id=payment_id, status=PaymentAttempt.Status.SUCCESS).count()
            if codes != [200, 200] or confirmed != 1:
                problems.append((n, codes, confirmed))
        self.assertEqual(problems, [], 'rounds where verify or the webhook failed, or the payment confirmed twice')

    def test_two_refunds_at_once_call_razorpay_once(self):
        student, _, payment_id, _ = start_order(self.room, 1, 'r@example.test')
        self.assertEqual(verify(student, payment_id, 'pay_dbl_refund').status_code, 200)
        barrier = threading.Barrier(2)
        calls = []

        def razorpay_refund(**kwargs):
            calls.append(kwargs)
            try:
                barrier.wait(3)  # a correct implementation never lets the second request in here
            except threading.BrokenBarrierError:
                pass
            return {'id': f'rfnd_{len(calls)}'}

        def call():
            return api(self.owner).post(reverse('payment-refund', args=[payment_id]), {}, format='json').status_code

        with mock.patch(f'{VIEWS}.initiate_refund', side_effect=razorpay_refund):
            self.parallel(call, call)
        self.assertEqual(len(calls), 1, 'the same payment was refunded twice at the gateway')
