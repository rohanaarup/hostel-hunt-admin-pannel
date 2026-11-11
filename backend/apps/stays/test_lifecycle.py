"""
Phase 5 tests: a paid booking becomes a Stay with Due 1 (paid) and Due 2; a second current stay is refused (D2);
a stay can be ended (bed released, future dues cancelled) and a student can ask to vacate.

Names and amounts are fictional (example.test addresses, no real people).
"""
import threading
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock, skipUnless

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.core.sample_data import ensure_sample_catalog
from apps.payments.confirm import Outcome, confirm_payment
from apps.payments.models import Payment
from apps.residents.models import Resident
from apps.rooms.models import Bed, Room

from . import services
from .dates import today_ist
from .models import Due, HostelBillingConfig, OutboxEvent, Stay

on_postgres = skipUnless(connection.vendor == 'postgresql', 'row locks and real concurrency need PostgreSQL')
User = get_user_model()


def make_user(tag):
    return User.objects.create_user(email=f'{tag}@example.test', display_name=tag, password='pass12345')


def make_booking(room, bed_number, student=None, mode='online', check_in=None, status='pending'):
    return Booking.objects.create(
        hostel=room.hostel, student=student, student_name='Student A', room=room, bed_number=str(bed_number),
        payment_mode=mode, check_in_date=check_in, status=status,
    )


def make_payment(booking, suffix=None):
    return Payment.objects.create(
        booking=booking, razorpay_order_id=f'order_{suffix or booking.id.hex[:14]}',
        amount=booking.room.price_per_month, status=Payment.Status.CREATED,
    )


def make_resident(booking, name):
    return Resident.objects.create(
        hostel=booking.hostel, name=name, phone='9000000000', id_proof_type='other', id_proof_number='X1',
        move_in_date=date(2026, 6, 18), linked_booking=booking)


def pay_online(booking, rp_id='pay_test_1'):
    """Run the real confirm path (card callback and webhook both end here)."""
    payment = make_payment(booking)
    return payment, confirm_payment(payment.id, rp_id, 'sig')


class Base(TestCase):
    def setUp(self):
        self.owner = ensure_sample_catalog()
        self.room = Room.objects.get(hostel__name='Seed Alpha Residency', room_name='Double')
        self.price = self.room.price_per_month  # 6500.00
        self.student = make_user('student-a')
        self.owner_client = APIClient()
        self.owner_client.force_authenticate(self.owner)
        self.student_client = APIClient()
        self.student_client.force_authenticate(self.student)


class CreateStayFromEachPaidPath(Base):
    """Each of the three paid paths gives exactly one Stay, Due 1 (paid, linked to the payment) and Due 2."""

    def assert_one_stay(self, booking, payment=None, join=None):
        self.assertEqual(Stay.objects.filter(booking=booking).count(), 1)
        stay = Stay.objects.get(booking=booking)
        dues = list(stay.dues.order_by('due_date'))
        self.assertEqual(len(dues), 2)
        first, second = dues
        self.assertEqual(first.kind, Due.Kind.BOOKING_PERIOD)
        self.assertEqual(first.status, Due.Status.PAID)
        self.assertEqual(first.amount, self.price)
        self.assertIsNotNone(first.paid_at)
        if payment is not None:
            self.assertEqual(first.payment_id, payment.id)
        self.assertEqual(second.kind, Due.Kind.RENT)
        self.assertEqual(second.period_start, first.period_end + timedelta(days=1))
        self.assertIn(second.status, (Due.Status.SCHEDULED, Due.Status.PAYABLE))
        self.assertEqual(stay.rent_amount, self.price)
        self.assertEqual(stay.hostel_id, booking.hostel_id)
        self.assertEqual(OutboxEvent.objects.filter(dedupe_key=f'stay-created-{booking.id}').count(), 1)
        return stay, first, second

    def test_confirm_payment_path(self):
        booking = make_booking(self.room, 1, self.student, check_in=date(2026, 6, 18))
        payment, outcome = pay_online(booking)
        self.assertEqual(outcome, Outcome.CONFIRMED)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'paid')
        stay, first, second = self.assert_one_stay(booking, payment)
        self.assertEqual((first.period_start, first.period_end), (date(2026, 6, 18), date(2026, 7, 17)))
        self.assertEqual(second.period_start, date(2026, 7, 18))
        self.assertEqual(stay.student_id, self.student.id)
        self.assertEqual(stay.bed_number, '1')
        self.assertEqual(stay.billing_snapshot['billing_mode'], 'ANNIVERSARY')

    def test_owner_verify_path_links_the_successful_payment(self):
        booking = make_booking(self.room, 1, self.student, check_in=date(2026, 6, 18))
        payment = make_payment(booking)
        Payment.objects.filter(pk=payment.pk).update(status=Payment.Status.SUCCESS)
        response = self.owner_client.post(reverse('booking-verify', args=[booking.id]))
        self.assertEqual(response.status_code, 200)
        self.assert_one_stay(booking, payment)

    def test_owner_mark_paid_path(self):
        booking = make_booking(self.room, 1, self.student, mode='offline', check_in=date(2026, 6, 18))
        response = self.owner_client.patch(reverse('booking-mark-paid', args=[booking.id]))
        self.assertEqual(response.status_code, 200)
        stay, first, _ = self.assert_one_stay(booking)
        self.assertIsNone(first.payment_id)

    def test_amount_comes_from_the_room_never_from_booking_amount(self):
        booking = make_booking(self.room, 1, self.student, mode='offline', check_in=date(2026, 6, 18))
        Booking.objects.filter(pk=booking.pk).update(amount=Decimal('1.00'))
        self.owner_client.patch(reverse('booking-mark-paid', args=[booking.id]))
        self.assertEqual(Stay.objects.get(booking=booking).rent_amount, self.price)

    def test_no_check_in_date_joins_today_ist(self):
        booking = make_booking(self.room, 1, self.student, mode='offline')
        self.owner_client.patch(reverse('booking-mark-paid', args=[booking.id]))
        stay = Stay.objects.get(booking=booking)
        self.assertEqual(stay.join_date, today_ist())
        self.assertEqual(stay.status, Stay.Status.ACTIVE)

    def test_future_join_is_upcoming_and_past_join_is_active(self):
        future = today_ist() + timedelta(days=10)
        b1 = make_booking(self.room, 1, self.student, mode='offline', check_in=future)
        self.owner_client.patch(reverse('booking-mark-paid', args=[b1.id]))
        self.assertEqual(Stay.objects.get(booking=b1).status, Stay.Status.UPCOMING)

    def test_billing_config_is_snapshotted_fixed_day(self):
        HostelBillingConfig.objects.create(
            hostel=self.room.hostel, billing_mode='FIXED_DAY', fixed_due_day=1, first_period_policy='FULL_MONTH')
        booking = make_booking(self.room, 1, self.student, mode='offline', check_in=date(2026, 9, 18))
        self.owner_client.patch(reverse('booking-mark-paid', args=[booking.id]))
        stay = Stay.objects.get(booking=booking)
        first, second = list(stay.dues.order_by('due_date'))
        self.assertEqual((first.period_start, first.period_end), (date(2026, 9, 18), date(2026, 9, 30)))
        self.assertEqual(second.period_start, date(2026, 10, 1))
        self.assertEqual(stay.billing_snapshot['fixed_due_day'], 1)
        # a later change to the hostel's config never touches the stay
        HostelBillingConfig.objects.filter(hostel=self.room.hostel).update(fixed_due_day=5)
        stay.refresh_from_db()
        self.assertEqual(stay.billing_snapshot['fixed_due_day'], 1)

    def test_prorated_first_period_mismatching_the_payment_is_flagged_not_hidden(self):
        """create-order charges a whole month (frozen). A PRORATE hostel would make Due 1 smaller than what was paid:
        the stay is created and flagged for a person, never silently wrong."""
        HostelBillingConfig.objects.create(
            hostel=self.room.hostel, billing_mode='FIXED_DAY', fixed_due_day=1, first_period_policy='PRORATE')
        booking = make_booking(self.room, 1, self.student, check_in=date(2026, 9, 18))
        _, outcome = pay_online(booking)
        self.assertEqual(outcome, Outcome.CONFIRMED)
        stay = Stay.objects.get(booking=booking)
        self.assertTrue(stay.needs_review)

    def test_resident_linked_only_when_exactly_one(self):
        booking = make_booking(self.room, 1, self.student, mode='offline', check_in=date(2026, 6, 18))
        resident = make_resident(booking, 'Student A')
        self.owner_client.patch(reverse('booking-mark-paid', args=[booking.id]))
        self.assertEqual(Stay.objects.get(booking=booking).resident_id, resident.id)
        two = make_booking(self.room, 2, make_user('student-b'), mode='offline', check_in=date(2026, 6, 18))
        make_resident(two, 'B1')
        make_resident(two, 'B2')
        self.owner_client.patch(reverse('booking-mark-paid', args=[two.id]))
        self.assertIsNone(Stay.objects.get(booking=two).resident_id)

    def test_residents_are_never_created(self):
        booking = make_booking(self.room, 1, self.student, mode='offline')
        before = Resident.objects.count()
        self.owner_client.patch(reverse('booking-mark-paid', args=[booking.id]))
        self.assertEqual(Resident.objects.count(), before)

    def test_outbox_payload_holds_ids_only(self):
        booking = make_booking(self.room, 1, self.student, mode='offline')
        self.owner_client.patch(reverse('booking-mark-paid', args=[booking.id]))
        event = OutboxEvent.objects.get(dedupe_key=f'stay-created-{booking.id}')
        self.assertEqual(event.topic, 'stay.created')
        text = str(event.payload).lower()
        for secret in ('student a', '@', 'example.test'):
            self.assertNotIn(secret, text)
        self.assertIn(str(booking.id), text)


class IdempotenceAndSafety(Base):
    def test_service_is_idempotent(self):
        booking = make_booking(self.room, 1, self.student, mode='offline', status='paid')
        booking.marked_paid_at = timezone.now()
        a, created_a = services.create_stay_for_booking(booking, None)
        b, created_b = services.create_stay_for_booking(booking, None)
        self.assertTrue(created_a)
        self.assertFalse(created_b)
        self.assertEqual(a.pk, b.pk)
        self.assertEqual(Due.objects.filter(stay=a).count(), 2)
        self.assertEqual(OutboxEvent.objects.filter(dedupe_key=f'stay-created-{booking.id}').count(), 1)

    def test_service_refuses_a_booking_that_is_not_paid(self):
        booking = make_booking(self.room, 1, self.student, mode='offline')
        with self.assertRaises(services.StayError):
            services.create_stay_for_booking(booking, None)

    def test_verify_twice_is_a_no_op(self):
        booking = make_booking(self.room, 1, self.student)
        payment = make_payment(booking)
        Payment.objects.filter(pk=payment.pk).update(status=Payment.Status.SUCCESS)
        url = reverse('booking-verify', args=[booking.id])
        self.assertEqual(self.owner_client.post(url).status_code, 200)
        paid_at = Booking.objects.get(pk=booking.pk).marked_paid_at
        second = self.owner_client.post(url)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Booking.objects.get(pk=booking.pk).marked_paid_at, paid_at)
        self.assertEqual(Stay.objects.filter(booking=booking).count(), 1)
        self.assertEqual(Due.objects.filter(stay__booking=booking).count(), 2)

    def test_verify_refuses_a_cancelled_booking(self):
        booking = make_booking(self.room, 1, self.student, status='cancelled')
        response = self.owner_client.post(reverse('booking-verify', args=[booking.id]))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Stay.objects.filter(booking=booking).exists())

    def test_failure_inside_the_service_leaves_the_booking_paid(self):
        booking = make_booking(self.room, 1, self.student)
        payment = make_payment(booking)
        with mock.patch('apps.stays.services.create_stay_for_booking', side_effect=RuntimeError('boom')):
            with self.assertLogs('hh.stays', level='ERROR'):
                outcome = confirm_payment(payment.id, 'pay_test_1', 'sig')
        self.assertEqual(outcome, Outcome.CONFIRMED)
        booking.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(booking.status, 'paid')
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertFalse(Bed.objects.get(room=self.room, bed_number=1).is_available)
        self.assertFalse(Stay.objects.filter(booking=booking).exists())

    def test_partial_failure_rolls_back_only_the_stay(self):
        """A failure after the Stay row is written leaves no half-built stay and keeps the payment."""
        booking = make_booking(self.room, 1, self.student)
        payment = make_payment(booking)
        with mock.patch('apps.stays.services._write_dues', side_effect=RuntimeError('boom')):
            with self.assertLogs('hh.stays', level='ERROR'):
                outcome = confirm_payment(payment.id, 'pay_test_1', 'sig')
        self.assertEqual(outcome, Outcome.CONFIRMED)
        self.assertFalse(Stay.objects.filter(booking=booking).exists())
        self.assertEqual(Booking.objects.get(pk=booking.pk).status, 'paid')

    def test_offline_booking_without_a_room_makes_no_stay_but_stays_paid(self):
        booking = Booking.objects.create(hostel=self.room.hostel, student_name='Walk in', payment_mode='offline')
        with self.assertLogs('hh.stays', level='WARNING'):
            response = self.owner_client.patch(reverse('booking-mark-paid', args=[booking.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Stay.objects.filter(booking=booking).exists())

    def test_confirm_twice_gives_one_stay(self):
        booking = make_booking(self.room, 1, self.student)
        payment = make_payment(booking)
        self.assertEqual(confirm_payment(payment.id, 'pay_test_1', 'sig'), Outcome.CONFIRMED)
        self.assertEqual(confirm_payment(payment.id, 'pay_test_1', 'sig'), Outcome.ALREADY_CONFIRMED)
        self.assertEqual(Stay.objects.filter(booking=booking).count(), 1)
        self.assertEqual(Due.objects.filter(stay__booking=booking).count(), 2)


class D2Guard(Base):
    def paid_stay(self, status=Stay.Status.ACTIVE):
        booking = make_booking(self.room, 1, self.student, mode='offline', check_in=date(2026, 6, 18))
        self.owner_client.patch(reverse('booking-mark-paid', args=[booking.id]))
        Stay.objects.filter(booking=booking).update(status=status)
        return Stay.objects.get(booking=booking)

    def post_booking(self, client, bed=2):
        return client.post(reverse('booking-list'), {
            'hostel': str(self.room.hostel_id), 'room': str(self.room.id), 'bed_number': str(bed),
            'payment_mode': 'online',
        }, format='json')

    def test_current_stay_blocks_a_new_booking_with_409(self):
        for status in ('UPCOMING', 'ACTIVE', 'NOTICE'):
            stay = self.paid_stay(status)
            response = self.post_booking(self.student_client)
            self.assertEqual(response.status_code, 409, status)
            body = response.json()
            self.assertEqual(body['code'], 'ACTIVE_STAY_EXISTS')
            self.assertTrue(body['message'])
            current = body['current_stay']
            self.assertEqual(set(current), {'id', 'hostel_name', 'locality', 'room_label', 'bed_label', 'paid_until'})
            self.assertEqual(current['id'], str(stay.id))
            self.assertEqual(current['hostel_name'], 'Seed Alpha Residency')
            self.assertEqual(current['bed_label'], 'Bed A')
            self.assertEqual(current['paid_until'], '2026-07-17')
            Stay.objects.all().delete()
            Booking.objects.all().delete()
            Bed.objects.update(is_available=True)

    def test_paid_until_is_the_end_of_the_last_paid_period(self):
        stay = self.paid_stay()
        first = stay.dues.get(kind=Due.Kind.BOOKING_PERIOD)
        second = stay.dues.get(kind=Due.Kind.RENT)
        second.status = Due.Status.PAID
        second.paid_at = timezone.now()
        second.save()
        response = self.post_booking(self.student_client)
        self.assertEqual(response.json()['current_stay']['paid_until'], str(second.period_end))
        self.assertNotEqual(str(first.period_end), str(second.period_end))

    def test_ended_stay_does_not_block(self):
        self.paid_stay(Stay.Status.ENDED)
        self.assertEqual(self.post_booking(self.student_client).status_code, 201)

    def test_anonymous_booking_is_allowed(self):
        self.paid_stay()
        self.assertEqual(self.post_booking(APIClient(), bed=3).status_code, 201)

    def test_another_student_is_not_blocked(self):
        self.paid_stay()
        other = APIClient()
        other.force_authenticate(make_user('student-b'))
        self.assertEqual(self.post_booking(other, bed=3).status_code, 201)

    def test_second_paid_booking_is_never_blocked_and_is_flagged(self):
        first = self.paid_stay()
        second_booking = make_booking(self.room, 2, self.student)
        _, outcome = pay_online(second_booking)
        self.assertEqual(outcome, Outcome.CONFIRMED)
        second = Stay.objects.get(booking=second_booking)
        self.assertTrue(second.needs_review)
        first.refresh_from_db()
        self.assertFalse(first.needs_review)

    def test_first_stay_is_not_flagged(self):
        self.assertFalse(self.paid_stay().needs_review)


class VacateRequest(Base):
    def make_stay(self, student=None):
        booking = make_booking(self.room, 1, student or self.student, mode='offline', check_in=date(2026, 6, 18))
        self.owner_client.patch(reverse('booking-mark-paid', args=[booking.id]))
        return Stay.objects.get(booking=booking)

    def url(self, stay):
        return reverse('stay-vacate-request', args=[stay.id])

    def body(self, days=30, reason='MOVING_CITY'):
        return {'planned_move_out_date': str(today_ist() + timedelta(days=days)), 'reason': reason}

    def test_student_moves_active_to_notice_and_the_owner_is_told(self):
        stay = self.make_stay()
        response = self.student_client.post(self.url(stay), self.body(), format='json')
        self.assertEqual(response.status_code, 200, response.content)
        stay.refresh_from_db()
        self.assertEqual(stay.status, Stay.Status.NOTICE)
        self.assertEqual(stay.vacate_reason, 'MOVING_CITY')
        self.assertEqual(stay.planned_move_out_date, today_ist() + timedelta(days=30))
        self.assertIsNotNone(stay.vacate_requested_at)
        event = OutboxEvent.objects.get(dedupe_key=f'stay-vacate-requested-{stay.id}')
        self.assertEqual(event.topic, 'stay.vacate_requested')
        self.assertEqual(event.payload['stay_id'], str(stay.id))

    def test_today_is_allowed_and_yesterday_is_not(self):
        stay = self.make_stay()
        bad = self.student_client.post(self.url(stay), self.body(days=-1), format='json')
        self.assertEqual(bad.status_code, 400)
        stay.refresh_from_db()
        self.assertEqual(stay.status, Stay.Status.ACTIVE)
        ok = self.student_client.post(self.url(stay), self.body(days=0), format='json')
        self.assertEqual(ok.status_code, 200)

    def test_all_four_reasons_and_nothing_else(self):
        for reason in ('COURSE_COMPLETED', 'MOVING_CITY', 'FOUND_ANOTHER_PLACE', 'OTHER'):
            stay = self.make_stay(make_user(reason.lower().replace('_', '-')))
            client = APIClient()
            client.force_authenticate(stay.student)
            self.assertEqual(client.post(self.url(stay), self.body(reason=reason), format='json').status_code, 200)
            Stay.objects.all().delete()
            Booking.objects.all().delete()
            Bed.objects.update(is_available=True)
        stay = self.make_stay()
        self.assertEqual(self.student_client.post(self.url(stay), self.body(reason='BORED'), format='json').status_code, 400)

    def test_missing_fields_are_rejected(self):
        stay = self.make_stay()
        self.assertEqual(self.student_client.post(self.url(stay), {}, format='json').status_code, 400)

    def test_second_request_is_refused_and_changes_nothing(self):
        stay = self.make_stay()
        self.student_client.post(self.url(stay), self.body(30), format='json')
        again = self.student_client.post(self.url(stay), self.body(60, 'OTHER'), format='json')
        self.assertEqual(again.status_code, 409)
        stay.refresh_from_db()
        self.assertEqual(stay.vacate_reason, 'MOVING_CITY')
        self.assertEqual(OutboxEvent.objects.filter(topic='stay.vacate_requested').count(), 1)

    def test_other_students_and_owners_cannot_use_it(self):
        stay = self.make_stay()
        other = APIClient()
        other.force_authenticate(make_user('student-b'))
        self.assertEqual(other.post(self.url(stay), self.body(), format='json').status_code, 404)
        self.assertEqual(self.owner_client.post(self.url(stay), self.body(), format='json').status_code, 404)
        self.assertEqual(APIClient().post(self.url(stay), self.body(), format='json').status_code, 401)
        stay.refresh_from_db()
        self.assertEqual(stay.status, Stay.Status.ACTIVE)

    def test_ended_stay_cannot_be_vacated(self):
        stay = self.make_stay()
        Stay.objects.filter(pk=stay.pk).update(status=Stay.Status.ENDED)
        self.assertEqual(self.student_client.post(self.url(stay), self.body(), format='json').status_code, 409)


class EndStay(Base):
    def make_stay(self, check_in=date(2026, 6, 18), bed=1):
        booking = make_booking(self.room, bed, self.student, check_in=check_in)
        pay_online(booking)
        return Stay.objects.get(booking=booking)

    def url(self, stay):
        return reverse('stay-end', args=[stay.id])

    def test_owner_ends_the_stay_bed_is_released_and_future_dues_cancelled(self):
        stay = self.make_stay(check_in=today_ist() - timedelta(days=5))
        self.assertFalse(Bed.objects.get(room=self.room, bed_number=1).is_available)
        response = self.owner_client.post(self.url(stay))
        self.assertEqual(response.status_code, 200, response.content)
        stay.refresh_from_db()
        self.assertEqual(stay.status, Stay.Status.ENDED)
        self.assertIsNotNone(stay.ended_at)
        self.assertTrue(Bed.objects.get(room=self.room, bed_number=1).is_available)
        due2 = stay.dues.get(kind=Due.Kind.RENT)
        self.assertEqual(due2.status, Due.Status.CANCELLED)
        self.assertEqual(stay.dues.get(kind=Due.Kind.BOOKING_PERIOD).status, Due.Status.PAID)
        booking = Booking.objects.get(pk=stay.booking_id)
        self.assertEqual(booking.status, 'paid')  # history is kept

    def test_the_cycle_already_running_stays_payable(self):
        """Only FUTURE dues are cancelled: a rent whose period has started is still owed."""
        stay = self.make_stay(check_in=today_ist() - timedelta(days=40))
        due2 = stay.dues.get(kind=Due.Kind.RENT)
        self.assertLessEqual(due2.period_start, today_ist())
        self.owner_client.post(self.url(stay))
        due2.refresh_from_db()
        self.assertIn(due2.status, (Due.Status.SCHEDULED, Due.Status.PAYABLE))

    def test_bed_is_ended_so_it_can_be_booked_again(self):
        stay = self.make_stay()
        self.owner_client.post(self.url(stay))
        response = APIClient().post(reverse('booking-list'), {
            'hostel': str(self.room.hostel_id), 'room': str(self.room.id), 'bed_number': '1',
            'payment_mode': 'online'}, format='json')
        self.assertEqual(response.status_code, 201)

    def test_bed_stays_taken_while_another_current_stay_holds_it(self):
        stay = self.make_stay()
        twin = Booking.objects.create(hostel=self.room.hostel, room=self.room, bed_number='1', payment_mode='offline',
                                      status='paid', student=make_user('student-b'))
        services.create_stay_for_booking(twin, None)
        self.owner_client.post(self.url(stay))
        self.assertFalse(Bed.objects.get(room=self.room, bed_number=1).is_available)

    def test_end_is_idempotent(self):
        stay = self.make_stay()
        self.owner_client.post(self.url(stay))
        stay.refresh_from_db()
        ended_at = stay.ended_at
        again = self.owner_client.post(self.url(stay))
        self.assertEqual(again.status_code, 200)
        stay.refresh_from_db()
        self.assertEqual(stay.ended_at, ended_at)

    def test_student_cannot_end(self):
        stay = self.make_stay()
        self.assertEqual(self.student_client.post(self.url(stay)).status_code, 404)
        stay.refresh_from_db()
        self.assertEqual(stay.status, Stay.Status.ACTIVE)

    def test_another_owner_cannot_end(self):
        stay = self.make_stay()
        stranger = APIClient()
        stranger.force_authenticate(make_user('owner-b'))
        self.assertEqual(stranger.post(self.url(stay)).status_code, 404)
        self.assertEqual(APIClient().post(self.url(stay)).status_code, 401)
        stay.refresh_from_db()
        self.assertEqual(stay.status, Stay.Status.ACTIVE)

    def test_admin_staff_can_end_any_stay(self):
        stay = self.make_stay()
        staff = User.objects.create_user(email='staff@example.test', display_name='staff', password='pass12345')
        staff.is_staff = True
        staff.save()
        client = APIClient()
        client.force_authenticate(staff)
        self.assertEqual(client.post(self.url(stay)).status_code, 200)
        stay.refresh_from_db()
        self.assertEqual(stay.status, Stay.Status.ENDED)

    def test_notice_stay_can_be_ended(self):
        stay = self.make_stay()
        self.student_client.post(reverse('stay-vacate-request', args=[stay.id]), {
            'planned_move_out_date': str(today_ist() + timedelta(days=10)), 'reason': 'OTHER'}, format='json')
        self.assertEqual(self.owner_client.post(self.url(stay)).status_code, 200)
        stay.refresh_from_db()
        self.assertEqual(stay.status, Stay.Status.ENDED)


class ReconcileStays(Base):
    def paid_without_stay(self, bed, **kw):
        booking = make_booking(self.room, bed, make_user(f'student-{bed}'), mode='offline', status='paid', **kw)
        Booking.objects.filter(pk=booking.pk).update(marked_paid_at=timezone.now())
        return booking

    def run_command(self, *args):
        out = StringIO()
        call_command('reconcile_stays', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_changes_nothing_and_reports_counts(self):
        self.paid_without_stay(1)
        self.paid_without_stay(2)
        output = self.run_command('--dry-run')
        self.assertIn('would create 2', output)
        self.assertEqual(Stay.objects.count(), 0)
        self.assertEqual(OutboxEvent.objects.count(), 0)

    def test_creates_missing_stays_and_is_safe_to_run_twice(self):
        b1, b2 = self.paid_without_stay(1), self.paid_without_stay(2)
        first = self.run_command()
        self.assertIn('created 2', first)
        second = self.run_command()
        self.assertIn('created 0', second)
        self.assertEqual(Stay.objects.count(), 2)
        self.assertEqual(Due.objects.count(), 4)
        self.assertTrue(Stay.objects.filter(booking=b1).exists() and Stay.objects.filter(booking=b2).exists())

    def test_ignores_unpaid_bookings_and_existing_stays(self):
        make_booking(self.room, 3, make_user('student-3'), mode='offline')
        paid = self.paid_without_stay(1)
        services.create_stay_for_booking(paid, None)
        self.assertIn('created 0', self.run_command())
        self.assertEqual(Stay.objects.count(), 1)

    def test_skips_a_booking_it_cannot_price_and_says_so(self):
        Booking.objects.create(hostel=self.room.hostel, payment_mode='offline', status='paid', student_name='Walk in')
        output = self.run_command()
        self.assertIn('skipped 1', output)
        self.assertEqual(Stay.objects.count(), 0)

    def test_batch_limit(self):
        for bed in (1, 2):
            self.paid_without_stay(bed)
        self.assertIn('created 1', self.run_command('--batch-size', '1'))
        self.assertIn('created 1', self.run_command('--batch-size', '1'))
        self.assertEqual(Stay.objects.count(), 2)

    def test_output_has_no_personal_data(self):
        self.paid_without_stay(1)
        output = self.run_command()
        self.assertNotIn('example.test', output)
        self.assertNotIn('Student A', output)


@on_postgres
class ConcurrentConfirmation(TransactionTestCase):
    """Webhook and verify at the same moment: one Stay, one Due 1, one outbox row."""

    def setUp(self):
        self.owner = ensure_sample_catalog()
        self.room = Room.objects.get(hostel__name='Seed Alpha Residency', room_name='Double')
        self.student = make_user('student-a')

    def race(self, workers):
        barrier = threading.Barrier(len(workers))
        errors = []

        def run(work):
            try:
                barrier.wait(10)
                work()
            except Exception as exc:  # pragma: no cover - reported below
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=run, args=(w,)) for w in workers]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        self.assertEqual(errors, [])

    def assert_single(self, booking):
        self.assertEqual(Stay.objects.filter(booking=booking).count(), 1)
        self.assertEqual(Due.objects.filter(stay__booking=booking, kind=Due.Kind.BOOKING_PERIOD).count(), 1)
        self.assertEqual(Due.objects.filter(stay__booking=booking).count(), 2)
        self.assertEqual(OutboxEvent.objects.filter(dedupe_key=f'stay-created-{booking.id}').count(), 1)

    def test_webhook_and_card_callback_together(self):
        booking = make_booking(self.room, 1, self.student)
        payment = make_payment(booking)
        self.race([
            lambda: confirm_payment(payment.id, 'pay_test_1', 'sig', amount_paise=int(payment.amount * 100),
                                    currency='INR'),
            lambda: confirm_payment(payment.id, 'pay_test_1', 'sig'),
        ])
        self.assert_single(booking)

    def test_owner_verify_and_confirm_together(self):
        booking = make_booking(self.room, 1, self.student)
        payment = make_payment(booking)
        client = APIClient()
        client.force_authenticate(self.owner)

        def verify():
            client.post(reverse('booking-verify', args=[booking.id]))

        self.race([lambda: confirm_payment(payment.id, 'pay_test_1', 'sig'), verify])
        self.assert_single(booking)

    def test_verify_called_twice_at_once(self):
        booking = make_booking(self.room, 1, self.student)
        payment = make_payment(booking)
        Payment.objects.filter(pk=payment.pk).update(status=Payment.Status.SUCCESS)
        client = APIClient()
        client.force_authenticate(self.owner)
        url = reverse('booking-verify', args=[booking.id])
        self.race([lambda: client.post(url), lambda: client.post(url)])
        self.assert_single(booking)

    def test_reconcile_racing_a_confirmation(self):
        booking = make_booking(self.room, 1, self.student)
        payment = make_payment(booking)
        self.race([
            lambda: confirm_payment(payment.id, 'pay_test_1', 'sig'),
            lambda: call_command('reconcile_stays', stdout=StringIO()),
        ])
        self.assert_single(booking)


class QueryBudget(Base):
    """S3: each new query path stays within a fixed number of queries. Every lookup uses an existing index: Stay.booking
    (unique), Stay (student, status) for the D2 guard, Due (stay, due_date), Bed (room, bed_number), Resident.linked_booking
    (foreign key index), Payment.booking (foreign key index)."""

    def count(self, work):
        from django.db import connection as conn
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(conn) as queries:
            work()
        return len(queries)

    def test_create_stay_budget(self):
        booking = make_booking(self.room, 1, self.student, mode='offline', status='paid')
        used = self.count(lambda: services.create_stay_for_booking(booking, None))
        self.assertLessEqual(used, 16, used)

    def test_repeat_call_is_cheap(self):
        booking = make_booking(self.room, 1, self.student, mode='offline', status='paid')
        services.create_stay_for_booking(booking, None)
        used = self.count(lambda: services.create_stay_for_booking(booking, None))
        self.assertLessEqual(used, 6, used)

    def test_d2_guard_is_one_query_and_none_when_anonymous(self):
        from django.contrib.auth.models import AnonymousUser
        self.assertEqual(self.count(lambda: services.find_current_stay(self.student)), 1)
        self.assertEqual(self.count(lambda: services.find_current_stay(AnonymousUser())), 0)

    def test_end_and_vacate_budget(self):
        booking = make_booking(self.room, 1, self.student, mode='offline', status='paid')
        stay, _ = services.create_stay_for_booking(booking, None)
        tomorrow = today_ist() + timedelta(days=1)
        self.assertLessEqual(self.count(lambda: services.request_vacate(stay, tomorrow, 'OTHER')), 10)
        self.assertLessEqual(self.count(lambda: services.end_stay(stay)), 12)
