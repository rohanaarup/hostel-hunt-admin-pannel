"""Test helpers for the Phase 8 tests (not a test module). Fictional names and example.test addresses only."""
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.bookings.models import Booking
from apps.core.sample_data import ensure_sample_catalog
from apps.rooms.models import Room
from apps.stays.models import Due, HostelBillingConfig, OutboxEvent, Stay

UTC = dt_timezone.utc
User = get_user_model()


def at(year, month, day, hour=0, minute=0):
    """A UTC moment. India time is UTC+5:30: 09:00 IST is 03:30 UTC; 21:00 IST is 15:30 UTC; 08:00 IST is 02:30 UTC."""
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def frozen(moment):
    return mock.patch('django.utils.timezone.now', return_value=moment)


def make_user(tag, email=True):
    kwargs = {'email': f'{tag}@example.test'} if email else {'email': None, 'phone_number': f'9{abs(hash(tag)) % 10**9:09d}'}
    return User.objects.create_user(display_name=tag.title(), password='pass12345', **kwargs)


class World:
    """The sample catalogue (an owner, hostels, rooms) and helpers to make stays and dues with exact dates."""

    def __init__(self):
        self.owner = ensure_sample_catalog()
        self.room = Room.objects.get(hostel__name='Seed Alpha Residency', room_name='Double')
        self.hostel = self.room.hostel
        self.rent = Decimal('6500.00')

    def stay(self, student=None, join=date(2026, 6, 18), status='ACTIVE', bed=1, tag=None):
        student = student or make_user(tag or f'student-{User.objects.count()}')
        booking = Booking.objects.create(
            hostel=self.hostel, student=student, student_name=student.display_name, room=self.room, bed_number=str(bed),
            payment_mode='offline', status='paid', check_in_date=join, marked_paid_at=at(2026, 6, 1))
        return Stay.objects.create(
            student=student, hostel=self.hostel, room=self.room, bed_number=str(bed), booking=booking, join_date=join,
            status=status, rent_amount=self.rent, billing_snapshot=HostelBillingConfig(hostel=self.hostel).snapshot())

    @staticmethod
    def due(stay, start, status='SCHEDULED', kind='RENT', amount=None):
        """A due whose period starts (and is due) on `start`; the period is 30 days."""
        return Due.objects.create(
            stay=stay, period_start=start, period_end=start + timedelta(days=29), due_date=start,
            amount=amount or stay.rent_amount, status=status, kind=kind)

    @staticmethod
    def event(topic, dedupe, payload=None, priority=0, status='PENDING', attempts=0, next_attempt_at=None):
        return OutboxEvent.objects.create(
            topic=topic, dedupe_key=dedupe, payload=payload or {}, priority=priority, status=status, attempts=attempts,
            next_attempt_at=next_attempt_at or at(2026, 1, 1))

    def reminder(self, due, kind, offset, priority=None):
        from apps.notifications import templates
        return self.event('rent.reminder', f'reminder-{due.id}-{kind}',
                          {'due_id': str(due.id), 'kind': kind, 'offset': offset},
                          priority=templates.priority_for(offset) if priority is None else priority)
