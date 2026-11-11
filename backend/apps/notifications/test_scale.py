"""
Scale checks for the engine (Phase 8). Each has a small version that always runs and a full-size version that runs when
HH_SCALE_TESTS=1 (it takes minutes):

    set HH_SCALE_TESTS=1 & python manage.py test apps.notifications.test_scale

  (a) stays_daily over 20,000 synthetic stays: runtime, and memory that stays flat from the first batch to the last.
  (b) process_outbox draining 100,000 synthetic OutboxEvent rows through a fake sender: events per second.

The numbers are printed as `SCALE ...` lines so they can be pasted into docs/ENGINE.md. They are measured on whatever machine
runs them (the scratch Postgres on a laptop here); they are not a promise about Render.
"""
import os
import sys
import time
from datetime import date
from io import StringIO
from unittest import mock, skipUnless

from django.core.management import call_command
from django.test import TestCase, TransactionTestCase

from apps.bookings.models import Booking
from apps.stays.models import Due, OutboxEvent, Stay

from . import engine, handlers
from .models import JobRun
from .testkit import World, at, frozen

FULL = os.environ.get('HH_SCALE_TESTS') == '1'
DUE = date(2026, 10, 18)
SNAPSHOT = {'billing_mode': 'ANNIVERSARY', 'fixed_due_day': None, 'fixed_due_last_day': False,
            'first_period_policy': 'FULL_MONTH', 'payable_window_days': 7, 'grace_days': 0}


def rss_mb():
    """Resident memory of this process in MB (no psutil needed)."""
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD),
                        ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                        ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]

        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        kernel32, psapi = ctypes.WinDLL('kernel32'), ctypes.WinDLL('psapi')
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
        return counters.WorkingSetSize / 1e6
    with open('/proc/self/status') as status:
        for line in status:
            if line.startswith('VmRSS:'):
                return int(line.split()[1]) / 1024
    return 0.0


def make_stays(world, count):
    """`count` ACTIVE stays, each with one open due on DUE (no users: the daily job needs none). Returns nothing."""
    bookings = [Booking(hostel=world.hostel, room=world.room, status='paid', payment_mode='offline', bed_number='1',
                        marked_paid_at=at(2026, 6, 1)) for _ in range(count)]
    Booking.objects.bulk_create(bookings, batch_size=2000)
    stays = [Stay(hostel=world.hostel, room=world.room, bed_number='1', booking=b, join_date=date(2026, 6, 18),
                  status='ACTIVE', rent_amount=world.rent, billing_snapshot=SNAPSHOT) for b in bookings]
    Stay.objects.bulk_create(stays, batch_size=2000)
    Due.objects.bulk_create([Due(stay=s, period_start=DUE, period_end=date(2026, 11, 16), due_date=DUE,
                                 amount=world.rent, status='PAYABLE', kind='RENT') for s in stays], batch_size=2000)


def run_daily_with_memory_samples(batch_size=1000):
    samples = []
    original = JobRun.save

    def sampling_save(self, *args, **kwargs):
        if self.name == 'stays_daily':
            samples.append(rss_mb())
        return original(self, *args, **kwargs)

    out = StringIO()
    started = time.perf_counter()
    with mock.patch.object(JobRun, 'save', sampling_save), frozen(at(2026, 10, 18, 3, 30)):
        call_command('stays_daily', '--today', DUE.isoformat(), '--skip-reconcile', '--batch-size', str(batch_size), stdout=out)
    return time.perf_counter() - started, samples


class StaysDailyScale(TestCase):
    def check(self, count, batch_size):
        world = World()
        make_stays(world, count)
        seconds, samples = run_daily_with_memory_samples(batch_size)
        self.assertEqual(OutboxEvent.objects.filter(topic='rent.reminder').count(), count)
        growth = samples[-1] - samples[1] if len(samples) > 2 else 0
        print(f'SCALE stays_daily: {count} stays, batch {batch_size}: {seconds:.1f} s '
              f'({count / seconds:.0f} stays/s), memory after batch 1: {samples[0]:.0f} MB, after batch 2: {samples[1]:.0f} MB, '
              f'at the end: {samples[-1]:.0f} MB, growth from batch 2 to the end: {growth:+.0f} MB over {len(samples)} batches')
        # a second pass adds nothing
        run_daily_with_memory_samples(batch_size)
        self.assertEqual(OutboxEvent.objects.filter(topic='rent.reminder').count(), count)
        return growth

    def test_2000_stays(self):
        growth = self.check(2000, 500)
        self.assertLess(growth, 60, 'memory must not grow batch after batch')

    @skipUnless(FULL, 'set HH_SCALE_TESTS=1 for the 20,000-stay run')
    def test_20000_stays(self):
        growth = self.check(20000, 1000)
        self.assertLess(growth, 60, 'memory must not grow batch after batch')


class OutboxDrainScale(TransactionTestCase):
    def drain(self, count, batch_size):
        sent = {'n': 0}

        def fake_sender(event):
            sent['n'] += 1

        OutboxEvent.objects.bulk_create(
            [OutboxEvent(topic='test.fake', dedupe_key=f'scale-{n}', next_attempt_at=at(2026, 1, 1), priority=n % 100)
             for n in range(count)], batch_size=5000)
        started = time.perf_counter()
        with mock.patch.dict(handlers.HANDLERS, {'test.fake': fake_sender}), frozen(at(2026, 10, 18, 3, 30)):
            total = engine.run(batch_size)
        seconds = time.perf_counter() - started
        print(f'SCALE process_outbox: {count} events, batch {batch_size}: {seconds:.1f} s ({count / seconds:.0f} events/s), '
              f'{total["batches"]} batches')
        self.assertEqual(sent['n'], count, 'every event handled exactly once')
        self.assertEqual(OutboxEvent.objects.filter(status='DONE').count(), count)

    def test_5000_events(self):
        self.drain(5000, 500)

    def test_a_20000_event_backlog_drains_at_a_steady_rate(self):
        """Regression guard: claiming must not slow down as the backlog grows (it once sorted the whole backlog per batch)."""
        count = 20000
        OutboxEvent.objects.bulk_create(
            [OutboxEvent(topic='test.fake', dedupe_key=f'guard-{n}', next_attempt_at=at(2026, 1, 1), priority=n % 100)
             for n in range(count)], batch_size=5000)
        rates = []
        with mock.patch.dict(handlers.HANDLERS, {'test.fake': lambda event: None}), frozen(at(2026, 10, 18, 3, 30)):
            while True:
                started = time.perf_counter()
                counts = engine.process_batch(500)
                if not counts['claimed']:
                    break
                rates.append(counts['claimed'] / (time.perf_counter() - started))
        self.assertEqual(OutboxEvent.objects.filter(status='DONE').count(), count)
        first, last = sum(rates[:5]) / 5, sum(rates[-5:]) / 5
        self.assertGreater(last, first / 4, f'the last batches ({last:.0f}/s) are far slower than the first ({first:.0f}/s)')
        self.assertGreater(count / sum(500 / r for r in rates), 300, 'the drain must stay above 300 events a second')

    @skipUnless(FULL, 'set HH_SCALE_TESTS=1 for the 100,000-event run')
    def test_100000_events(self):
        self.drain(100000, 500)


class ReminderDrainScale(TransactionTestCase):
    """The real reminder handler (bulk reads and inserts), inbox only (the email part is capped by design)."""

    def drain(self, count):
        from apps.stays.dates import today_ist  # noqa: F401
        from .testkit import make_user
        world = World()
        make_stays(world, count)
        students = [make_user(f'rs{n}') for n in range(min(count, 50))]
        stays = list(Stay.objects.all()[:count])
        for index, stay in enumerate(stays):
            stay.student = students[index % len(students)]
        Stay.objects.bulk_update(stays, ['student'], batch_size=2000)
        with frozen(at(2026, 10, 11, 3, 30)):
            call_command('stays_daily', '--today', '2026-10-11', '--skip-reconcile', stdout=StringIO())
        started = time.perf_counter()
        with frozen(at(2026, 10, 11, 3, 40)):
            total = engine.run(500)
        seconds = time.perf_counter() - started
        from .models import Notification
        print(f'SCALE reminders through the real handler: {count} reminders: {seconds:.1f} s ({count / seconds:.0f} events/s)')
        self.assertEqual(total['done'], count)
        self.assertEqual(Notification.objects.count(), count)

    def test_1000_reminders(self):
        self.drain(1000)

    @skipUnless(FULL, 'set HH_SCALE_TESTS=1 for the 20,000-reminder run')
    def test_20000_reminders(self):
        self.drain(20000)
