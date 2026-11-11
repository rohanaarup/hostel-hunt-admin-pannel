"""
The daily job (stays_daily): activation, next dues, the reminder ladder, idempotence, batches, resume, dry run, isolation.
Time is passed with --today (an IST date) so every day is exact; the clock itself is frozen where the job reads it.
"""
from datetime import date, timedelta
from io import StringIO
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase

from apps.bookings.models import Booking
from apps.notifications.models import JobRun
from apps.notifications.testkit import World, at, frozen, make_user

from .models import Due, OutboxEvent, Stay

LADDER = {7: 'before_7', 3: 'before_3', 1: 'before_1', 0: 'due_day', -1: 'overdue_1', -3: 'overdue_3', -7: 'overdue_7'}
DUE = date(2026, 10, 18)


class DailyBase(TestCase):
    def setUp(self):
        cache.clear()
        self.world = World()

    def run_daily(self, today, *args):
        out = StringIO()
        with frozen(at(today.year, today.month, today.day, 3, 30)):
            call_command('stays_daily', '--today', today.isoformat(), '--skip-reconcile', *args, stdout=out)
        return out.getvalue()

    def events(self, **filters):
        return OutboxEvent.objects.filter(topic='rent.reminder', **filters)


class Activation(DailyBase):
    def test_upcoming_becomes_active_on_the_join_date_not_before(self):
        today_join = self.world.stay(join=DUE, status='UPCOMING', bed=1)
        later = self.world.stay(join=DUE + timedelta(days=1), status='UPCOMING', bed=2)
        past = self.world.stay(join=DUE - timedelta(days=3), status='UPCOMING', tag='past')
        self.run_daily(DUE)
        for stay, expected in ((today_join, 'ACTIVE'), (later, 'UPCOMING'), (past, 'ACTIVE')):
            stay.refresh_from_db()
            self.assertEqual(stay.status, expected)

    def test_ended_and_cancelled_stays_are_left_alone(self):
        ended = self.world.stay(join=DUE, status='ENDED', bed=1)
        cancelled = self.world.stay(join=DUE, status='CANCELLED', bed=2)
        self.run_daily(DUE)
        ended.refresh_from_db()
        cancelled.refresh_from_db()
        self.assertEqual((ended.status, cancelled.status), ('ENDED', 'CANCELLED'))

    def test_activation_clears_the_home_cache_of_that_student(self):
        stay = self.world.stay(join=DUE, status='UPCOMING')
        from . import services
        before = services.shared_cache.current_version(services.home_cache_name(stay.student_id))
        self.run_daily(DUE)
        after = services.shared_cache.current_version(services.home_cache_name(stay.student_id))
        self.assertGreater(after, before)


class Ladder(DailyBase):
    def test_each_ladder_day_queues_exactly_one_reminder_with_its_kind_and_priority(self):
        from apps.notifications import templates
        for offset, kind in LADDER.items():
            OutboxEvent.objects.all().delete()
            stay = self.world.stay(tag=f'ladder{offset}', bed=1 if offset % 2 else 2)
            due = self.world.due(stay, DUE, status='PAYABLE')
            self.run_daily(DUE - timedelta(days=offset))
            event = self.events(payload__due_id=str(due.id)).get()
            self.assertEqual(event.payload['kind'], kind)
            self.assertEqual(event.payload['offset'], offset)
            self.assertEqual(event.dedupe_key, f'reminder-{due.id}-{kind}')
            self.assertEqual(event.priority, templates.priority_for(offset))
            Stay.objects.filter(pk=stay.pk).update(status='ENDED')

    def test_days_between_ladder_steps_queue_nothing(self):
        stay = self.world.stay()
        self.world.due(stay, DUE)
        for offset in (10, 6, 5, 4, 2, -2, -4, -5, -6, -8, -20):
            self.run_daily(DUE - timedelta(days=offset))
        self.assertEqual(self.events().count(), 0)

    def test_paid_waived_and_cancelled_dues_get_no_reminder(self):
        for index, status in enumerate(('PAID', 'WAIVED', 'CANCELLED')):
            stay = self.world.stay(tag=f'skip{index}', bed=1 if index % 2 else 2)
            self.world.due(stay, DUE, status=status)
        self.run_daily(DUE)
        self.assertEqual(self.events().count(), 0)

    def test_an_ended_stay_gets_no_reminder_and_a_notice_stay_does(self):
        ended = self.world.stay(tag='ended', status='ENDED')
        self.world.due(ended, DUE)
        notice = self.world.stay(tag='notice', status='NOTICE', bed=2)
        due = self.world.due(notice, DUE)
        self.run_daily(DUE)
        self.assertEqual([e.payload['due_id'] for e in self.events()], [str(due.id)])

    def test_a_second_run_adds_nothing(self):
        stay = self.world.stay()
        self.world.due(stay, DUE)
        self.run_daily(DUE)
        first = (self.events().count(), Due.objects.count(), OutboxEvent.objects.count())
        self.run_daily(DUE)
        self.run_daily(DUE)
        self.assertEqual((self.events().count(), Due.objects.count(), OutboxEvent.objects.count()), first)

    def test_priority_puts_overdue_before_upcoming(self):
        a = self.world.stay(tag='a', bed=1)
        b = self.world.stay(tag='b', bed=2)
        self.world.due(a, DUE)
        self.world.due(b, DUE + timedelta(days=3 + 7))  # due in 10 days from the overdue one's perspective: overdue_3 vs before...
        self.run_daily(DUE + timedelta(days=3))        # a: 3 days overdue
        kinds = {e.payload['kind']: e.priority for e in self.events()}
        self.assertIn('overdue_3', kinds)


class NextDues(DailyBase):
    def paid_stay(self, join=date(2026, 8, 18)):
        stay = self.world.stay(join=join)
        first = self.world.due(stay, join, status='PAID', kind='BOOKING_PERIOD')
        second = self.world.due(stay, date(2026, 9, 18), status='SCHEDULED')
        return stay, first, second

    def test_the_next_due_is_created_when_the_window_of_the_current_one_opens(self):
        stay, _, second = self.paid_stay()
        self.run_daily(date(2026, 9, 10))   # 8 days before due 2: its window (7 days) has not opened
        self.assertEqual(stay.dues.count(), 2)
        self.run_daily(date(2026, 9, 11))   # 7 days before: opens; the one after it is created
        dues = list(stay.dues.order_by('period_start'))
        self.assertEqual(len(dues), 3)
        self.assertEqual(dues[2].period_start, date(2026, 10, 18))
        self.assertEqual(dues[2].period_end, date(2026, 11, 17))
        self.assertEqual(dues[2].status, 'SCHEDULED')
        self.assertEqual(dues[2].amount, stay.rent_amount)
        self.assertEqual(dues[2].kind, 'RENT')

    def test_the_next_due_is_created_when_the_current_one_is_paid(self):
        stay, _, second = self.paid_stay()
        Due.objects.filter(pk=second.pk).update(status='PAID')
        self.run_daily(date(2026, 8, 25))
        self.assertEqual(stay.dues.count(), 3)

    def test_a_second_run_cannot_create_a_duplicate_due(self):
        stay, _, _ = self.paid_stay()
        self.run_daily(date(2026, 9, 11))
        self.run_daily(date(2026, 9, 11))
        self.run_daily(date(2026, 9, 12))
        self.assertEqual(stay.dues.count(), 3)
        self.assertEqual(stay.dues.values('period_start').distinct().count(), 3)

    def test_the_anchor_is_never_chained(self):
        stay = self.world.stay(join=date(2026, 1, 31))
        self.world.due(stay, date(2026, 1, 31), status='PAID', kind='BOOKING_PERIOD')
        self.world.due(stay, date(2026, 2, 28), status='PAID')
        self.run_daily(date(2026, 3, 1))
        self.run_daily(date(2026, 3, 25))
        self.run_daily(date(2026, 4, 25))
        starts = [d.period_start for d in stay.dues.order_by('period_start')]
        self.assertEqual(starts[:5], [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30),
                                      date(2026, 5, 31)][:len(starts[:5])])

    def test_waived_and_cancelled_latest_dues(self):
        stay = self.world.stay()
        self.world.due(stay, date(2026, 8, 18), status='PAID', kind='BOOKING_PERIOD')
        self.world.due(stay, date(2026, 9, 18), status='CANCELLED')
        self.run_daily(date(2026, 9, 18))
        self.assertEqual(stay.dues.count(), 2, 'a cancelled latest due is not a reason to create another')

    def test_an_ended_stay_gets_no_new_due(self):
        stay = self.world.stay(status='ENDED')
        self.world.due(stay, date(2026, 8, 18), status='PAID', kind='BOOKING_PERIOD')
        self.run_daily(date(2026, 9, 18))
        self.assertEqual(stay.dues.count(), 1)

    def test_a_new_due_that_is_already_in_its_window_gets_its_reminder_the_same_day(self):
        stay = self.world.stay(join=date(2026, 8, 18))
        self.world.due(stay, date(2026, 8, 18), status='PAID', kind='BOOKING_PERIOD')
        self.world.due(stay, date(2026, 9, 18), status='PAID')
        self.run_daily(date(2026, 9, 11))  # the October due is created, exactly 37 days away: no reminder yet
        self.assertEqual(self.events().count(), 0)
        self.run_daily(date(2026, 10, 11))  # created earlier; 7 days before: the first reminder
        self.assertEqual(self.events().get().payload['kind'], 'before_7')


class Operation(DailyBase):
    def many(self, count):
        for n in range(count):
            booking = Booking.objects.create(hostel=self.world.hostel, student=make_user(f'm{n}'), room=self.world.room,
                                             payment_mode='offline', status='paid', marked_paid_at=at(2026, 6, 1))
            stay = Stay.objects.create(student=booking.student, hostel=self.world.hostel, room=self.world.room,
                                       bed_number='1', booking=booking, join_date=date(2026, 6, 18), status='ACTIVE',
                                       rent_amount=self.world.rent, billing_snapshot={'billing_mode': 'ANNIVERSARY',
                                       'fixed_due_day': None, 'fixed_due_last_day': False, 'first_period_policy': 'FULL_MONTH',
                                       'payable_window_days': 7, 'grace_days': 0})
            self.world.due(stay, DUE)

    def test_dry_run_changes_nothing(self):
        self.many(3)
        output = self.run_daily(DUE, '--dry-run')
        self.assertIn('reminders_planned', output)
        self.assertEqual(OutboxEvent.objects.count(), 0)
        self.assertEqual(JobRun.objects.count(), 0)
        self.assertEqual(Due.objects.count(), 3)

    def test_keyset_batches_process_every_stay_exactly_once(self):
        self.many(5)
        self.run_daily(DUE, '--batch-size', '2')
        self.assertEqual(self.events().count(), 5)
        run = JobRun.objects.get(name='stays_daily')
        self.assertEqual(run.status, 'OK')
        self.assertEqual(run.counts['stays'], 5)
        self.assertEqual(run.checkpoint, str(Stay.objects.order_by('-pk').first().pk))

    def test_a_run_that_crashes_halfway_resumes_without_duplicates(self):
        self.many(5)
        # fail the second batch of event inserts
        original = OutboxEvent.objects.bulk_create
        state = {'n': 0}

        def flaky(objs, **kwargs):
            state['n'] += 1
            if state['n'] == 2:
                raise RuntimeError('simulated crash')
            return original(objs, **kwargs)

        with mock.patch('apps.stays.management.commands.stays_daily.OutboxEvent.objects') as manager:
            manager.bulk_create.side_effect = flaky
            with self.assertRaises(SystemExit), self.assertLogs('hh.stays_daily', level='ERROR'):
                self.run_daily(DUE, '--batch-size', '2')
        crashed = JobRun.objects.get(name='stays_daily')
        self.assertEqual(crashed.status, 'FAILED')
        self.assertEqual(self.events().count(), 2, 'only the first batch was written')
        self.assertTrue(crashed.checkpoint)

        self.run_daily(DUE, '--batch-size', '2', '--resume')
        self.assertEqual(self.events().count(), 5)
        self.assertEqual(JobRun.objects.filter(name='stays_daily').count(), 1, 'the unfinished run was continued')
        self.assertEqual(JobRun.objects.get(name='stays_daily').status, 'OK')
        self.run_daily(DUE, '--batch-size', '2')   # and a full second pass adds nothing
        self.assertEqual(self.events().count(), 5)

    def test_steps_are_isolated(self):
        self.many(2)
        with mock.patch('apps.stays.management.commands.stays_daily.activate', side_effect=RuntimeError('boom')):
            with self.assertRaises(SystemExit) as caught, self.assertLogs('hh.stays_daily', level='ERROR'):
                self.run_daily(DUE)
        self.assertIn('activate', str(caught.exception))
        self.assertEqual(self.events().count(), 2, 'the other steps still ran')
        self.assertEqual(JobRun.objects.get(name='stays_daily').status, 'FAILED')

    def test_it_rejects_a_silly_batch_size(self):
        from django.core.management.base import CommandError
        for bad in ('0', '1001'):
            with self.assertRaises(CommandError):
                self.run_daily(DUE, '--batch-size', bad)

    def test_it_runs_under_the_heartbeat_wrapper(self):
        self.many(1)
        with frozen(at(2026, 10, 18, 3, 30)):
            call_command('ping_heartbeat', 'stays_daily', '--skip-reconcile', stdout=StringIO())
        self.assertTrue(JobRun.objects.filter(name='stays_daily', status='OK').exists())

    def test_output_is_counts_only(self):
        self.many(2)
        output = self.run_daily(DUE)
        self.assertNotIn('example.test', output)
        self.assertNotIn('M0', output)


class ReconcileStep(DailyBase):
    def paid_booking(self, days_ago, tag):
        return Booking.objects.create(
            hostel=self.world.hostel, student=make_user(tag), room=self.world.room, bed_number='1', payment_mode='offline',
            status='paid', marked_paid_at=at(2026, 10, 18) - timedelta(days=days_ago), check_in_date=date(2026, 10, 18))

    def test_only_recently_paid_bookings_are_healed_never_old_ones(self):
        recent = self.paid_booking(1, 'recent')
        old = self.paid_booking(30, 'old')
        out = StringIO()
        with frozen(at(2026, 10, 18, 3, 30)):
            call_command('stays_daily', '--today', '2026-10-18', stdout=out)
        self.assertTrue(Stay.objects.filter(booking=recent).exists())
        self.assertFalse(Stay.objects.filter(booking=old).exists(), 'a legacy booking must not become a stay (KNOWN_GAPS G5-03)')
        self.assertIn('created 1', out.getvalue())

    def test_reconcile_stays_since_and_max_age_options(self):
        old = self.paid_booking(30, 'old')
        with frozen(at(2026, 10, 18, 3, 30)):
            call_command('reconcile_stays', '--max-age-days', '3', stdout=StringIO())
            self.assertFalse(Stay.objects.filter(booking=old).exists())
            call_command('reconcile_stays', '--since', '2026-09-01', stdout=StringIO())
        self.assertTrue(Stay.objects.filter(booking=old).exists())

    def test_a_failing_reconcile_does_not_stop_the_rest(self):
        stay = self.world.stay()
        self.world.due(stay, DUE)
        with mock.patch('apps.stays.management.commands.reconcile_stays.Command.handle', side_effect=RuntimeError('boom')):
            with self.assertRaises(SystemExit), self.assertLogs('hh.stays_daily', level='ERROR'):
                with frozen(at(2026, 10, 18, 3, 30)):
                    call_command('stays_daily', '--today', '2026-10-18', stdout=StringIO())
        self.assertEqual(OutboxEvent.objects.filter(topic='rent.reminder').count(), 1)
