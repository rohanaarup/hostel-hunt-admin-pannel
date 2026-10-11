"""
Bed locking tests.

SQLite ignores select_for_update(), so the original suite never proved the bed locks do anything.
The row-lock assertions below only run on PostgreSQL (CI runs the whole suite there); the
behavioural checks run everywhere.
"""
import threading
from datetime import timedelta
from io import StringIO
from unittest import mock, skipUnless

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import OperationalError, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.core.sample_data import ensure_sample_catalog
from apps.rooms.models import Bed, Room

on_postgres = skipUnless(connection.vendor == 'postgresql', 'row locks exist only on PostgreSQL')


def make_online_booking(room, bed_number, email):
    student = get_user_model().objects.create_user(email=email, display_name=email, password='pass12345')
    booking = Booking.objects.create(
        hostel=room.hostel, student=student, student_name=email, room=room,
        bed_number=str(bed_number), payment_mode='online',
    )
    return student, booking


def create_order(student, booking):
    client = APIClient()
    client.force_authenticate(user=student)
    order = {'id': f'order_{booking.id.hex[:12]}', 'currency': 'INR'}
    with mock.patch('apps.payments.views.razorpay_client.create_order', return_value=order):
        return client.post(reverse('payment-create-order'), {'booking_id': str(booking.id)}, format='json')


class CreateOrderBedHoldTests(TestCase):
    def setUp(self):
        ensure_sample_catalog()
        self.room = Room.objects.order_by('room_name').first()

    def test_first_order_holds_the_bed(self):
        student, booking = make_online_booking(self.room, 1, 'first@example.test')
        response = create_order(student, booking)
        self.assertEqual(response.status_code, 201)
        bed = Bed.objects.get(room=self.room, bed_number=1)
        self.assertGreater(bed.held_until, timezone.now())

    def test_second_student_cannot_take_a_held_bed(self):
        first, first_booking = make_online_booking(self.room, 1, 'first@example.test')
        second, second_booking = make_online_booking(self.room, 1, 'second@example.test')
        self.assertEqual(create_order(first, first_booking).status_code, 201)
        response = create_order(second, second_booking)
        self.assertEqual(response.status_code, 409)

    @on_postgres
    def test_create_order_locks_the_bed_row(self):
        student, booking = make_online_booking(self.room, 1, 'first@example.test')
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(create_order(student, booking).status_code, 201)
        locking = [q['sql'] for q in queries.captured_queries if 'FOR UPDATE' in q['sql'] and '"beds"' in q['sql']]
        self.assertTrue(locking, 'CreateOrderView must lock the bed row before holding it')


class ExpireStaleHoldsTests(TestCase):
    def setUp(self):
        ensure_sample_catalog()
        self.room = Room.objects.order_by('room_name').first()
        self.bed = Bed.objects.get(room=self.room, bed_number=1)
        self.bed.held_until = timezone.now() - timedelta(hours=1)
        self.bed.save(update_fields=['held_until'])

    def test_releases_an_expired_hold(self):
        call_command('expire_stale_holds', stdout=StringIO())
        self.bed.refresh_from_db()
        self.assertIsNone(self.bed.held_until)

    def test_dry_run_changes_nothing(self):
        call_command('expire_stale_holds', '--dry-run', stdout=StringIO())
        self.bed.refresh_from_db()
        self.assertIsNotNone(self.bed.held_until)

    @on_postgres
    def test_expire_takes_a_row_lock(self):
        with CaptureQueriesContext(connection) as queries:
            call_command('expire_stale_holds', stdout=StringIO())
        locking = [q['sql'] for q in queries.captured_queries if 'FOR UPDATE' in q['sql'] and '"beds"' in q['sql']]
        self.assertTrue(locking, 'expire_stale_holds must lock the bed row')


@on_postgres
class RowLockExclusionTests(TransactionTestCase):
    """Two real connections: while one holds the lock the other cannot take it."""

    def test_second_connection_cannot_lock_a_locked_bed(self):
        ensure_sample_catalog()
        bed = Bed.objects.first()
        locked, release = threading.Event(), threading.Event()

        def holder():
            try:
                with transaction.atomic():
                    Bed.objects.select_for_update().get(pk=bed.pk)
                    locked.set()
                    release.wait(15)
            finally:
                connection.close()

        thread = threading.Thread(target=holder)
        thread.start()
        try:
            self.assertTrue(locked.wait(15), 'the first connection never obtained the lock')
            with transaction.atomic():
                with self.assertRaises(OperationalError):
                    Bed.objects.select_for_update(nowait=True).get(pk=bed.pk)
        finally:
            release.set()
            thread.join(15)
