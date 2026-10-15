"""
F4 Part 2: behaviour of the new payment code beyond the reproducing tests in test_f4_repro.py.
Razorpay itself is never called: the wrapper functions are patched.
"""
import json
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import Booking
from apps.core.sample_data import ensure_sample_catalog
from apps.owners.models import OTPRecord
from apps.payments import confirm as confirm_module
from apps.payments import test_f4_repro as repro
from apps.payments.models import Payment, PaymentAttempt, PaymentRefund, PaymentWebhookEvent
from apps.payments.services import razorpay_client
from apps.rooms.models import Bed, Room

VIEWS = repro.VIEWS


class Base(repro.PaymentCase):
    def lapse(self, bed_number=1):
        Bed.objects.filter(room=self.room, bed_number=bed_number).update(held_until=timezone.now() - timedelta(minutes=1))

    def refund(self, payment_id, amount=None, effect=None):
        payload = {} if amount is None else {'amount': str(amount)}
        kwargs = {'side_effect': effect} if effect else {'return_value': {'id': f'rfnd_{timezone.now().timestamp()}'}}
        with mock.patch(f'{VIEWS}.initiate_refund', **kwargs) as gateway:
            response = repro.api(self.owner).post(reverse('payment-refund', args=[payment_id]), payload, format='json')
        return response, gateway


class WebhookEventTests(Base):
    def test_the_same_event_id_is_processed_once(self):
        student, booking, payment_id, order_id = repro.start_order(self.room, 1, 'a@example.test')
        with mock.patch('apps.payments.views.confirm_payment', wraps=confirm_module.confirm_payment) as confirm:
            first = repro.webhook('payment.captured', order_id, 'pay_dup_1', self.paise, event_id='evt_dup_1')
            second = repro.webhook('payment.captured', order_id, 'pay_dup_1', self.paise, event_id='evt_dup_1')
        self.assertEqual(first.json()['status'], 'confirmed')
        self.assertEqual(second.json()['status'], 'duplicate')
        self.assertEqual(confirm.call_count, 1)
        self.assertEqual(PaymentWebhookEvent.objects.filter(event_id='evt_dup_1').count(), 1)

    def test_a_delivery_that_crashes_leaves_no_event_row_so_the_retry_is_processed(self):
        student, booking, payment_id, order_id = repro.start_order(self.room, 1, 'a@example.test')
        with mock.patch('apps.payments.views.confirm_payment', side_effect=RuntimeError('boom')):
            crashed = repro.webhook('payment.captured', order_id, 'pay_retry_1', self.paise, event_id='evt_retry_1')
        self.assertEqual(crashed.status_code, 500)
        self.assertFalse(PaymentWebhookEvent.objects.filter(event_id='evt_retry_1').exists())
        retry = repro.webhook('payment.captured', order_id, 'pay_retry_1', self.paise, event_id='evt_retry_1')
        self.assertEqual(retry.json()['status'], 'confirmed')

    def test_an_unknown_order_is_acknowledged(self):
        response = repro.webhook('payment.captured', 'order_unknown', 'pay_x', 100, event_id='evt_unknown_1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'unknown_order')


class FlaggedPaymentTests(Base):
    def test_a_wrong_amount_is_flagged_with_a_note(self):
        _, _, payment_id, order_id = repro.start_order(self.room, 1, 'a@example.test')
        repro.webhook('payment.captured', order_id, 'pay_short_1', 100)
        payment = Payment.objects.get(id=payment_id)
        self.assertTrue(payment.needs_review)
        self.assertIn('100', payment.review_note)

    def test_a_late_capture_is_flagged_and_keeps_the_razorpay_id_for_the_refund(self):
        first, first_booking, first_payment, first_order = repro.start_order(self.room, 1, 'a@example.test')
        self.lapse()
        call_command('expire_stale_holds', stdout=StringIO())
        second, _, second_payment, _ = repro.start_order(self.room, 1, 'b@example.test')
        repro.verify(second, second_payment, 'pay_second_1')

        with self.assertLogs('apps.payments', level='ERROR'):
            repro.webhook('payment.captured', first_order, 'pay_first_1', self.paise, event_id='evt_late_1')

        payment = Payment.objects.get(id=first_payment)
        self.assertTrue(payment.needs_review)
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertTrue(payment.attempts.filter(razorpay_payment_id='pay_first_1').exists())
        first_booking.refresh_from_db()
        self.assertNotEqual(first_booking.status, 'paid')

    def test_the_card_screen_tells_the_student_when_the_payment_cannot_be_honoured(self):
        first, _, first_payment, _ = repro.start_order(self.room, 1, 'a@example.test')
        self.lapse()
        call_command('expire_stale_holds', stdout=StringIO())
        second, _, second_payment, _ = repro.start_order(self.room, 1, 'b@example.test')
        repro.verify(second, second_payment, 'pay_second_1')
        response = repro.verify(first, first_payment, 'pay_first_1')
        self.assertEqual(response.status_code, 409)
        self.assertIn('refund', response.json()['error'].lower())

    def test_a_second_different_capture_for_a_paid_order_is_flagged_not_confirmed_twice(self):
        student, _, payment_id, order_id = repro.start_order(self.room, 1, 'a@example.test')
        repro.verify(student, payment_id, 'pay_one')
        repro.webhook('payment.captured', order_id, 'pay_two', self.paise, event_id='evt_two')
        payment = Payment.objects.get(id=payment_id)
        self.assertTrue(payment.needs_review)
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertEqual(payment.attempts.filter(status=PaymentAttempt.Status.SUCCESS).count(), 1)

    def test_a_booking_rejected_while_paying_is_flagged(self):
        student, booking, payment_id, _ = repro.start_order(self.room, 1, 'a@example.test')
        Booking.objects.filter(pk=booking.pk).update(status='rejected')
        with self.assertLogs('apps.payments', level='ERROR'):
            response = repro.verify(student, payment_id, 'pay_rejected_1')
        self.assertEqual(response.status_code, 409)
        self.assertTrue(Payment.objects.get(id=payment_id).needs_review)

    def test_verifying_twice_in_a_row_is_idempotent(self):
        student, _, payment_id, _ = repro.start_order(self.room, 1, 'a@example.test')
        self.assertEqual(repro.verify(student, payment_id, 'pay_once').status_code, 200)
        again = repro.verify(student, payment_id, 'pay_once')
        self.assertEqual(again.status_code, 200)
        self.assertEqual(PaymentAttempt.objects.filter(payment_id=payment_id, razorpay_payment_id='pay_once').count(), 1)


class AttemptReuseTests(Base):
    def test_tapping_pay_twice_makes_one_open_attempt(self):
        student, _, payment_id, _ = repro.start_order(self.room, 1, 'a@example.test')
        for _ in range(3):
            repro.api(student).post(reverse('payment-card-checkout'), {'payment_id': payment_id}, format='json')
        self.assertEqual(
            PaymentAttempt.objects.filter(payment_id=payment_id, status=PaymentAttempt.Status.INITIATED).count(), 1,
        )

    def test_starting_a_payment_after_the_hold_lapsed_is_refused(self):
        student, _, payment_id, _ = repro.start_order(self.room, 1, 'a@example.test')
        self.lapse()
        response = repro.api(student).post(reverse('payment-card-checkout'), {'payment_id': payment_id}, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Payment.objects.get(id=payment_id).status, Payment.Status.FAILED)


class RefundTests(Base):
    def paid(self, email='a@example.test'):
        student, _, payment_id, _ = repro.start_order(self.room, 1, email)
        self.assertEqual(repro.verify(student, payment_id, 'pay_refundable').status_code, 200)
        return payment_id

    def test_partial_then_rest_then_refused(self):
        payment_id = self.paid()
        first, _ = self.refund(payment_id, 1000)
        self.assertEqual(first.json()['status'], 'SUCCESS')
        payment = Payment.objects.get(id=payment_id)
        self.assertEqual(payment.refunded_amount, Decimal('1000.00'))

        rest, _ = self.refund(payment_id, 5500)
        self.assertEqual(rest.json()['status'], 'REFUNDED')
        third, gateway = self.refund(payment_id, 1)
        self.assertEqual(third.status_code, 409)
        gateway.assert_not_called()

    def test_more_than_is_left_is_refused_without_calling_the_gateway(self):
        payment_id = self.paid()
        self.refund(payment_id, 6000)
        response, gateway = self.refund(payment_id, 600)
        self.assertEqual(response.status_code, 409)
        gateway.assert_not_called()

    def test_zero_negative_and_nonsense_amounts_are_refused(self):
        payment_id = self.paid()
        for bad in ('0', '-5', 'abc', 'NaN'):
            response, gateway = self.refund(payment_id, bad)
            self.assertEqual(response.status_code, 400, bad)
            gateway.assert_not_called()

    def test_a_refusal_by_razorpay_releases_the_amount_so_it_can_be_retried(self):
        payment_id = self.paid()
        refused, _ = self.refund(payment_id, effect=razorpay_client.RefundRejected('no'))
        self.assertEqual(refused.status_code, 502)
        self.assertEqual(PaymentRefund.objects.get(payment_id=payment_id).status, PaymentRefund.Status.FAILED)
        retry, _ = self.refund(payment_id)
        self.assertEqual(retry.json()['status'], 'REFUNDED')

    def test_an_unknown_outcome_keeps_the_amount_reserved_and_flags_the_payment(self):
        payment_id = self.paid()
        unknown, _ = self.refund(payment_id, effect=TimeoutError('read timed out'))
        self.assertEqual(unknown.status_code, 502)
        self.assertEqual(PaymentRefund.objects.get(payment_id=payment_id).status, PaymentRefund.Status.RESERVED)
        self.assertTrue(Payment.objects.get(id=payment_id).needs_review)
        again, gateway = self.refund(payment_id)
        self.assertEqual(again.status_code, 409)
        gateway.assert_not_called()


class BedLifecycleTests(Base):
    def test_offline_mark_paid_is_refused_while_a_student_is_paying_for_that_bed(self):
        repro.start_order(self.room, 1, 'a@example.test')  # a live online hold on bed 1
        from django.contrib.auth import get_user_model
        student = get_user_model().objects.create_user(email='off@example.test', display_name='Off', password='pass12345')
        booking = Booking.objects.create(
            hostel=self.room.hostel, student=student, student_name='Off', room=self.room,
            bed_number='1', payment_mode='offline', status='confirmed',
        )
        response = repro.api(self.owner).patch(reverse('booking-mark-paid', args=[booking.id]))
        self.assertEqual(response.status_code, 409)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'confirmed')


class CleanupTests(Base):
    def test_cleanup_closes_lapsed_payments_and_purges_old_rows_but_keeps_fresh_ones(self):
        student, _, payment_id, _ = repro.start_order(self.room, 1, 'a@example.test')
        self.lapse()
        now = timezone.now()
        OTPRecord.objects.create(identifier='old@example.test', otp_code='x', purpose='signup', expires_at=now - timedelta(days=3))
        OTPRecord.objects.create(identifier='fresh@example.test', otp_code='x', purpose='signup', expires_at=now + timedelta(minutes=5))
        old = PaymentWebhookEvent.objects.create(event_id='evt_old')
        PaymentWebhookEvent.objects.filter(pk=old.pk).update(received_at=now - timedelta(days=45))
        PaymentWebhookEvent.objects.create(event_id='evt_new')

        out = StringIO()
        call_command('cleanup_expired', '--dry-run', stdout=out)
        self.assertEqual(Payment.objects.get(id=payment_id).status, Payment.Status.CREATED)
        self.assertEqual(OTPRecord.objects.count(), 2)

        call_command('cleanup_expired', stdout=out)
        call_command('cleanup_expired', stdout=out)  # safe to run twice
        self.assertEqual(Payment.objects.get(id=payment_id).status, Payment.Status.FAILED)
        self.assertEqual(list(OTPRecord.objects.values_list('identifier', flat=True)), ['fresh@example.test'])
        self.assertEqual(list(PaymentWebhookEvent.objects.values_list('event_id', flat=True)), ['evt_new'])

    def test_the_status_poll_closes_a_lapsed_payment_by_itself(self):
        student, _, payment_id, _ = repro.start_order(self.room, 1, 'a@example.test')
        self.lapse()
        repro.api(student).get(reverse('payment-status-poll', args=[payment_id]))
        self.assertEqual(Payment.objects.get(id=payment_id).status, Payment.Status.FAILED)
        self.assertIsNone(Bed.objects.get(room=self.room, bed_number=1).hold_payment_id)

    def test_a_new_student_can_book_a_bed_whose_old_hold_lapsed_without_any_cleanup(self):
        repro.start_order(self.room, 1, 'a@example.test')
        self.lapse()
        student, booking = repro.helpers.make_online_booking(self.room, 1, 'b@example.test')
        response = repro.helpers.create_order(student, booking)
        self.assertEqual(response.status_code, 201)
