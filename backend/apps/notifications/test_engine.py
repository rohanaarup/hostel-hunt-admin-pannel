"""
The outbox engine (process_outbox) and the reminder handlers, with time frozen.

Reference clock: 09:00 IST is 03:30 UTC. The rent in these tests is due on 18 Oct 2026, so 11 Oct 09:00 IST is 7 days before,
18 Oct 09:00 IST is the due day and 21 Oct 09:00 IST is 3 days overdue.
"""
import logging
import threading
from datetime import date, timedelta
from io import StringIO
from unittest import mock, skipUnless

from django.core.cache import cache
from django.core.management import call_command
from django.db import connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings

from apps.core import mailer
from apps.stays.models import Due, OutboxEvent, Stay

from . import engine, handlers, services, templates
from .models import JobRun, Notification, NotificationLog, NotificationPreference
from .testkit import World, at, frozen, make_user

on_postgres = skipUnless(connection.vendor == 'postgresql', 'row locks and real concurrency need PostgreSQL')

DUE = date(2026, 10, 18)
MORNING = lambda day: at(2026, 10, day, 3, 30)  # 09:00 IST   # noqa: E731


class EngineBase(TestCase):
    def setUp(self):
        cache.clear()
        self.world = World()
        self.student = make_user('student-a')
        self.stay = self.world.stay(self.student)
        self.due = self.world.due(self.stay, DUE)


# ------------------------------------------------------------------------------------------------- claiming and results

class Claiming(EngineBase):
    def test_a_stay_created_event_is_done_and_notifies_student_and_owner(self):
        event = self.world.event('stay.created', 'stay-created-1', {'stay_id': str(self.stay.id)})
        with frozen(MORNING(11)):
            counts = engine.process_batch(10)
        event.refresh_from_db()
        self.assertEqual(event.status, 'DONE')
        self.assertIsNotNone(event.processed_at)
        self.assertEqual(counts['done'], 1)
        student = Notification.objects.get(user=self.student)
        self.assertEqual((student.kind, student.category, student.title), ('stay_created', 'STAY', 'You are booked in'))
        owner = Notification.objects.get(user=self.world.owner)
        self.assertEqual(owner.kind, 'owner_stay_created')
        self.assertNotIn('@', student.body + owner.body)

    def test_handlers_are_idempotent_by_dedupe_key(self):
        event = self.world.event('stay.created', 'stay-created-1', {'stay_id': str(self.stay.id)})
        with frozen(MORNING(11)):
            engine.process_batch(10)
            OutboxEvent.objects.filter(pk=event.pk).update(status='PENDING', processed_at=None, attempts=0)
            engine.process_batch(10)
        self.assertEqual(Notification.objects.filter(user=self.student).count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.world.owner).count(), 1)

    def test_a_failing_handler_never_blocks_the_others(self):
        bad = self.world.event('rent.paid', 'rent-paid-bad', {'due_id': str(self.due.id)}, priority=5)
        good = self.world.event('stay.created', 'stay-created-1', {'stay_id': str(self.stay.id)})
        with mock.patch.dict(handlers.HANDLERS, {'rent.paid': mock.Mock(side_effect=RuntimeError('boom'))}):
            with self.assertLogs('hh.outbox', level='ERROR') as logged:
                with frozen(MORNING(11)):
                    counts = engine.process_batch(10)
        bad.refresh_from_db()
        good.refresh_from_db()
        self.assertEqual((bad.status, bad.attempts), ('FAILED', 1))
        self.assertEqual(good.status, 'DONE')
        self.assertEqual(counts['failed'], 1)
        self.assertEqual(counts['done'], 1)
        text = '\n'.join(logged.output)
        self.assertIn(str(bad.pk), text)
        self.assertIn('RuntimeError', text)
        self.assertNotIn('example.test', text)

    def test_failures_retry_with_exponential_backoff_and_a_limit(self):
        event = self.world.event('rent.paid', 'rent-paid-bad', {'due_id': str(self.due.id)})
        failing = mock.Mock(side_effect=RuntimeError('boom'))
        moment = MORNING(11)
        waits = []
        with mock.patch.dict(handlers.HANDLERS, {'rent.paid': failing}), self.assertLogs('hh.outbox', level='ERROR'):
            for _ in range(engine.max_attempts()):
                with frozen(moment):
                    engine.process_batch(10)
                event.refresh_from_db()
                waits.append(int((event.next_attempt_at - moment).total_seconds()))
                moment = event.next_attempt_at + timedelta(seconds=1)
        self.assertEqual(waits[:4], [60, 120, 240, 480])
        self.assertLessEqual(max(waits), 6 * 3600)
        self.assertEqual((event.status, event.attempts), ('FAILED', engine.max_attempts()))
        calls = failing.call_count
        with mock.patch.dict(handlers.HANDLERS, {'rent.paid': failing}), frozen(moment + timedelta(days=2)):
            engine.process_batch(10)
        self.assertEqual(failing.call_count, calls, 'an event past the limit is left for a person')

    def test_a_failed_event_is_not_retried_before_its_backoff_and_then_succeeds(self):
        event = self.world.event('stay.created', 'stay-created-1', {'stay_id': str(self.stay.id)})
        flaky = mock.Mock(side_effect=[RuntimeError('once'), None])
        with mock.patch.dict(handlers.HANDLERS, {'stay.created': flaky}), self.assertLogs('hh.outbox', level='ERROR'):
            with frozen(MORNING(11)):
                engine.process_batch(10)
            with frozen(MORNING(11) + timedelta(seconds=30)):
                self.assertEqual(engine.process_batch(10)['claimed'], 0)
            with frozen(MORNING(11) + timedelta(seconds=61)):
                self.assertEqual(engine.process_batch(10)['done'], 1)
        event.refresh_from_db()
        self.assertEqual(event.status, 'DONE')

    def test_the_most_urgent_event_goes_first_then_the_oldest(self):
        low = self.world.event('stay.created', 'low', {'stay_id': str(self.stay.id)}, priority=1)
        high = self.world.event('stay.created', 'high', {'stay_id': str(self.stay.id)}, priority=90)
        mid = self.world.event('stay.created', 'mid', {'stay_id': str(self.stay.id)}, priority=50)
        order = []
        with mock.patch.dict(handlers.HANDLERS, {'stay.created': lambda e: order.append(e.dedupe_key)}):
            with frozen(MORNING(11)):
                engine.process_batch(1)
                engine.process_batch(1)
                engine.process_batch(1)
        self.assertEqual(order, ['high', 'mid', 'low'])

    def test_batch_size_is_honoured_and_run_drains_everything(self):
        for n in range(5):
            self.world.event('stay.created', f'e{n}', {'stay_id': str(self.stay.id)})
        with frozen(MORNING(11)):
            self.assertEqual(engine.process_batch(2)['claimed'], 2)
            total = engine.run(2)
        self.assertEqual(total['claimed'], 3)
        self.assertEqual(OutboxEvent.objects.filter(status='DONE').count(), 5)

    def test_max_batches_stops_early(self):
        for n in range(6):
            self.world.event('stay.created', f'e{n}', {'stay_id': str(self.stay.id)})
        with frozen(MORNING(11)):
            total = engine.run(2, max_batches=2)
        self.assertEqual((total['batches'], total['claimed']), (2, 4))

    def test_a_claim_is_leased_so_a_crashed_worker_leaves_rows_that_come_back(self):
        event = self.world.event('stay.created', 'e1', {'stay_id': str(self.stay.id)})
        with frozen(MORNING(11)):
            claimed = engine.claim(10, MORNING(11))  # claimed, then "the worker died"
            self.assertEqual(len(claimed), 1)
            self.assertEqual(engine.claim(10, MORNING(11)), [])
        with frozen(MORNING(11) + timedelta(minutes=engine.LEASE_MINUTES + 1)):
            self.assertEqual(len(engine.claim(10, MORNING(11) + timedelta(minutes=engine.LEASE_MINUTES + 1))), 1)
        event.refresh_from_db()
        self.assertEqual(event.attempts, 2)

    def test_an_unknown_topic_is_marked_done_with_a_warning(self):
        event = self.world.event('something.new', 'x1')
        with self.assertLogs('hh.outbox', level='WARNING'), frozen(MORNING(11)):
            engine.process_batch(10)
        event.refresh_from_db()
        self.assertEqual(event.status, 'DONE')

    def test_loop_mode_sleeps_between_looks_and_stops_at_max_seconds(self):
        sleeps = []
        clock = iter([0.0, 0.0, 0.5, 1.0, 1.6, 2.2, 3.0, 9.0, 9.0, 9.0])
        with mock.patch('apps.notifications.engine.time.sleep', side_effect=sleeps.append), \
                mock.patch('apps.notifications.engine.time.monotonic', side_effect=lambda: next(clock)), frozen(MORNING(11)):
            total = engine.run(10, loop=True, sleep=7.0, max_seconds=2)
        self.assertEqual(total['claimed'], 0)
        self.assertTrue(sleeps and set(sleeps) == {7.0})


# ------------------------------------------------------------------------------------------------------ the command

class Command(EngineBase):
    def run_command(self, *args):
        out = StringIO()
        call_command('process_outbox', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_counts_and_changes_nothing(self):
        event = self.world.event('stay.created', 'e1', {'stay_id': str(self.stay.id)})
        with frozen(MORNING(11)):
            output = self.run_command('--dry-run')
        self.assertIn('1 due now', output)
        event.refresh_from_db()
        self.assertEqual((event.status, event.attempts), ('PENDING', 0))
        self.assertEqual(JobRun.objects.count(), 0)

    def test_a_run_is_recorded_and_prints_counts_only(self):
        self.world.event('stay.created', 'e1', {'stay_id': str(self.stay.id)})
        with frozen(MORNING(11)):
            output = self.run_command('--batch-size', '10')
        self.assertIn('claimed 1', output)
        self.assertIn('done 1', output)
        run = JobRun.objects.get(name='process_outbox')
        self.assertEqual(run.status, 'OK')
        self.assertEqual(run.counts['done'], 1)
        self.assertNotIn('example.test', output)

    def test_it_rejects_a_silly_batch_size(self):
        from django.core.management.base import CommandError
        for bad in ('0', '1001'):
            with self.assertRaises(CommandError):
                self.run_command('--batch-size', bad)

    def test_it_runs_twice_safely(self):
        self.world.event('stay.created', 'e1', {'stay_id': str(self.stay.id)})
        with frozen(MORNING(11)):
            self.run_command()
            self.assertIn('claimed 0', self.run_command())
        self.assertEqual(Notification.objects.count(), 2)


@on_postgres
class SkipLocked(TransactionTestCase):
    """A second worker never waits for rows another worker holds: SKIP LOCKED."""

    def test_rows_locked_by_another_worker_are_skipped(self):
        world = World()
        student = make_user('student-a')
        stay = world.stay(student)
        events = [world.event('stay.created', f'e{n}', {'stay_id': str(stay.id)}, priority=10 - n) for n in range(4)]
        locked, release = threading.Event(), threading.Event()

        def other_worker():
            try:
                with transaction.atomic():
                    list(OutboxEvent.objects.select_for_update().filter(pk__in=[events[0].pk, events[1].pk]))
                    locked.set()
                    release.wait(15)
            finally:
                connection.close()

        thread = threading.Thread(target=other_worker)
        thread.start()
        try:
            self.assertTrue(locked.wait(15))
            with frozen(MORNING(11)):
                claimed = engine.claim(10, MORNING(11))
            self.assertEqual({e.dedupe_key for e in claimed}, {'e2', 'e3'})
        finally:
            release.set()
            thread.join(15)

    def test_the_claim_takes_a_row_lock(self):
        from django.test.utils import CaptureQueriesContext
        World().event('stay.created', 'e1')
        with CaptureQueriesContext(connection) as queries, frozen(MORNING(11)):
            engine.claim(10, MORNING(11))
        sql = ' '.join(q['sql'] for q in queries.captured_queries)
        self.assertIn('FOR UPDATE SKIP LOCKED', sql)


# --------------------------------------------------------------------------------------------------------- quiet hours

class QuietHours(EngineBase):
    def test_the_window(self):
        for moment, quiet in ((at(2026, 10, 11, 15, 29), False),   # 20:59 IST
                              (at(2026, 10, 11, 15, 30), True),    # 21:00 IST
                              (at(2026, 10, 11, 20, 0), True),     # 01:30 IST
                              (at(2026, 10, 12, 2, 29), True),     # 07:59 IST
                              (at(2026, 10, 12, 2, 30), False)):   # 08:00 IST
            self.assertEqual(services.in_quiet_hours(moment), quiet, moment)

    def test_the_next_window_opens_at_eight_ist(self):
        self.assertEqual(services.next_window_start(at(2026, 10, 11, 16, 0)), at(2026, 10, 12, 2, 30))   # 21:30 IST
        self.assertEqual(services.next_window_start(at(2026, 10, 12, 0, 0)), at(2026, 10, 12, 2, 30))    # 05:30 IST
        self.assertEqual(services.next_window_start(at(2026, 10, 12, 5, 0)), at(2026, 10, 12, 5, 0))     # 10:30 IST

    def test_reminders_wait_for_the_morning_but_other_events_do_not(self):
        reminder = self.world.reminder(self.due, 'before_7', 7)
        notice = self.world.event('stay.created', 'e1', {'stay_id': str(self.stay.id)})
        night = at(2026, 10, 11, 17, 0)  # 22:30 IST
        with frozen(night):
            counts = engine.process_batch(10)
        reminder.refresh_from_db()
        notice.refresh_from_db()
        self.assertEqual((reminder.status, reminder.attempts), ('PENDING', 0))
        self.assertEqual(notice.status, 'DONE')
        self.assertEqual(counts['claimed'], 1)
        self.assertFalse(Notification.objects.filter(kind='before_7').exists())
        with frozen(at(2026, 10, 12, 2, 31)):  # 08:01 IST: the window is open again (the reminder is 6 days before now)
            engine.process_batch(10)
        reminder.refresh_from_db()
        self.assertEqual(reminder.status, 'DONE')

    def test_manual_reminders_also_wait(self):
        event = self.world.event('rent.reminder_manual', 'm1', {'due_id': str(self.due.id), 'bucket': '2026-10-11'})
        with frozen(at(2026, 10, 11, 16, 0)):
            self.assertEqual(engine.process_batch(10)['claimed'], 0)
        event.refresh_from_db()
        self.assertEqual(event.status, 'PENDING')


# -------------------------------------------------------------------------------------------------- reminder wording

class ReminderMessages(EngineBase):
    EXPECTED = {
        7: ('before_7', 'Rent due in 7 days', '₹6,500 for Seed Alpha Residency is due on 18 Oct. You can pay now.'),
        3: ('before_3', 'Rent due in 3 days', 'Pay ₹6,500 by 18 Oct. Tap to pay in the app.'),
        1: ('before_1', 'Rent due tomorrow', '₹6,500 is due tomorrow, 18 Oct.'),
        0: ('due_day', 'Rent is due today', 'Pay ₹6,500 now to stay on track.'),
        -3: ('overdue_3', 'Rent is 3 days overdue', '₹6,500 was due on 18 Oct. Please pay as soon as you can.'),
    }

    def test_each_ladder_step_reaches_the_inbox_with_the_board_wording(self):
        for offset, (kind, title, body) in self.EXPECTED.items():
            event = self.world.reminder(self.due, kind, offset)
            with frozen(MORNING(18 - offset)), mock.patch('apps.core.mailer.send_email'):
                engine.process_batch(10)
            notice = Notification.objects.get(user=self.student, kind=kind)
            self.assertEqual((notice.title, notice.body), (title, body), kind)
            self.assertEqual(notice.category, 'RENT')
            self.assertEqual(notice.due_id, self.due.id)
            event.refresh_from_db()
            self.assertEqual(event.status, 'DONE', kind)

    def test_the_inbox_item_reports_its_channels(self):
        self.world.reminder(self.due, 'before_7', 7)
        with frozen(MORNING(11)):
            engine.process_batch(10)
        self.assertEqual(Notification.objects.get().channels_delivered, ['in_app'])
        self.assertEqual(NotificationLog.objects.get().channel, 'in_app')

    def test_a_second_run_yields_zero_duplicates(self):
        event = self.world.reminder(self.due, 'before_7', 7)
        with frozen(MORNING(11)):
            engine.process_batch(10)
            OutboxEvent.objects.filter(pk=event.pk).update(status='PENDING', processed_at=None, attempts=0)
            engine.process_batch(10)
            # the same reminder under a different event key is still caught by the unique log row
            self.world.event('rent.reminder', 'another-key', {'due_id': str(self.due.id), 'kind': 'before_7', 'offset': 7})
            engine.process_batch(10)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(NotificationLog.objects.count(), 1)

    def test_the_log_row_is_unique_per_due_kind_channel(self):
        from django.db import IntegrityError
        NotificationLog.objects.create(due=self.due, kind='before_7', channel='in_app')
        with self.assertRaises(IntegrityError), transaction.atomic():
            NotificationLog.objects.create(due=self.due, kind='before_7', channel='in_app')
        NotificationLog.objects.create(due=self.due, kind='before_7', channel='email')
        NotificationLog.objects.create(due=self.due, kind='manual_reminder', channel='in_app', bucket='2026-10-11')
        NotificationLog.objects.create(due=self.due, kind='manual_reminder', channel='in_app', bucket='2026-10-12')

    def test_nothing_is_sent_for_a_due_that_is_no_longer_open(self):
        for status in ('PAID', 'WAIVED', 'CANCELLED'):
            Due.objects.filter(pk=self.due.pk).update(status=status)
            self.world.event('rent.reminder', f'r-{status}', {'due_id': str(self.due.id), 'kind': 'before_7', 'offset': 7})
            with frozen(MORNING(11)):
                engine.process_batch(10)
        self.assertFalse(Notification.objects.exists())

    def test_nothing_is_sent_for_an_ended_stay(self):
        Stay.objects.filter(pk=self.stay.pk).update(status='ENDED')
        self.world.reminder(self.due, 'before_7', 7)
        with frozen(MORNING(11)):
            engine.process_batch(10)
        self.assertFalse(Notification.objects.exists())

    def test_a_stale_upcoming_step_is_skipped_but_an_overdue_one_uses_todays_wording(self):
        self.world.reminder(self.due, 'before_7', 7)
        with frozen(MORNING(13)):  # two days late: "due in 7 days" would be wrong now
            engine.process_batch(10)
        self.assertFalse(Notification.objects.exists())
        self.world.reminder(self.due, 'overdue_1', -1)
        with frozen(MORNING(21)), mock.patch('apps.core.mailer.send_email'):  # delivered 3 days late: worded for today
            engine.process_batch(10)
        self.assertEqual(Notification.objects.get().title, 'Rent is 3 days overdue')


# -------------------------------------------------------------------------------------------------------- preferences

class Preferences(EngineBase):
    def run_due_day(self):
        self.world.reminder(self.due, 'due_day', 0)
        with frozen(MORNING(18)), mock.patch('apps.core.mailer.send_email') as send:
            engine.process_batch(10)
        return send

    def test_defaults_are_all_on(self):
        send = self.run_due_day()
        self.assertEqual(Notification.objects.count(), 1)
        send.assert_called_once()

    def test_inbox_off_creates_no_notice_but_the_email_still_goes(self):
        NotificationPreference.objects.create(user=self.student, inbox=False)
        send = self.run_due_day()
        self.assertEqual(Notification.objects.count(), 0)
        send.assert_called_once()

    def test_email_off_sends_no_email_but_the_notice_is_created(self):
        NotificationPreference.objects.create(user=self.student, email=False)
        send = self.run_due_day()
        self.assertEqual(Notification.objects.count(), 1)
        send.assert_not_called()

    def test_push_off_changes_nothing_while_push_does_not_exist(self):
        NotificationPreference.objects.create(user=self.student, push=False)
        send = self.run_due_day()
        self.assertEqual(Notification.objects.count(), 1)
        send.assert_called_once()

    def test_all_off_sends_nothing_and_the_event_still_finishes(self):
        NotificationPreference.objects.create(user=self.student, inbox=False, push=False, email=False)
        send = self.run_due_day()
        self.assertEqual(Notification.objects.count(), 0)
        send.assert_not_called()
        self.assertEqual(OutboxEvent.objects.get().status, 'DONE')

    def test_a_student_with_no_email_address_gets_no_email(self):
        phone_only = make_user('phone-only', email=False)
        stay = self.world.stay(phone_only, bed=2)
        due = self.world.due(stay, DUE)
        self.world.reminder(due, 'due_day', 0)
        with frozen(MORNING(18)), mock.patch('apps.core.mailer.send_email') as send:
            engine.process_batch(10)
        send.assert_not_called()
        self.assertEqual(Notification.objects.filter(user=phone_only).count(), 1)


# ------------------------------------------------------------------------------------------------------------- email

class Email(EngineBase):
    def many(self, offsets):
        """One due per offset, each on its own stay, with a reminder queued; returns the events."""
        events = []
        for index, offset in enumerate(offsets):
            stay = self.world.stay(make_user(f'cap-{index}'), bed=1 if index % 2 == 0 else 2)
            due = self.world.due(stay, DUE)
            kind = templates.kind_for(offset)
            events.append(self.world.reminder(due, kind, offset))
        return events

    def test_the_due_day_email_has_the_board_subject_and_content(self):
        self.world.reminder(self.due, 'due_day', 0)
        with frozen(MORNING(18)), mock.patch('apps.core.mailer.send_email') as send:
            engine.process_batch(10)
        to, subject, text, html = send.call_args.args
        self.assertEqual(to, 'student-a@example.test')
        self.assertEqual(subject, 'Your rent of ₹6,500 is due today')
        self.assertIn('Hi Student-A, your rent for Seed Alpha Residency · Gachibowli is due today.', text)
        self.assertEqual(NotificationLog.objects.filter(channel='email').count(), 1)
        self.assertEqual(sorted(Notification.objects.get().channels_delivered), ['email', 'in_app'])

    def test_upcoming_steps_send_no_email(self):
        for offset in (7, 3, 1):
            self.world.reminder(self.due, templates.kind_for(offset), offset)
            with frozen(MORNING(18 - offset)), mock.patch('apps.core.mailer.send_email') as send:
                engine.process_batch(10)
            send.assert_not_called()

    def test_overdue_steps_do_send_an_email(self):
        for offset in (-1, -3, -7):
            Due.objects.filter(pk=self.due.pk).update(status='SCHEDULED')
            self.world.reminder(self.due, templates.kind_for(offset), offset)
            with frozen(MORNING(18 - offset)), mock.patch('apps.core.mailer.send_email') as send:
                engine.process_batch(10)
            send.assert_called_once()
            self.assertIn('is overdue', send.call_args.args[1])

    @override_settings(EMAIL_DAILY_CAP=2)
    def test_the_daily_cap_sends_the_most_severe_first_and_defers_the_rest(self):
        due_day, overdue_7, overdue_3 = self.many([0, -7, -3])
        sent = []
        with frozen(MORNING(25)), mock.patch('apps.core.mailer.send_email', side_effect=lambda *a: sent.append(a[1])):
            engine.process_batch(10)
        self.assertEqual(len(sent), 2)
        due_day.refresh_from_db()
        overdue_7.refresh_from_db()
        overdue_3.refresh_from_db()
        self.assertEqual((overdue_7.status, overdue_3.status), ('DONE', 'DONE'))
        self.assertEqual(due_day.status, 'PENDING')
        self.assertEqual(due_day.attempts, 0, 'waiting for the cap is not a failure')
        self.assertEqual(due_day.next_attempt_at, at(2026, 10, 26, 2, 30))  # 08:00 IST the next day
        self.assertEqual(NotificationLog.objects.filter(channel='email').count(), 2)
        self.assertEqual(Notification.objects.count(), 3, 'the inbox is not capped')

    @override_settings(EMAIL_DAILY_CAP=1)
    def test_the_cap_counts_the_ist_day_and_resets_tomorrow(self):
        first, second = self.many([-3, -3])
        with frozen(MORNING(25)), mock.patch('apps.core.mailer.send_email') as send:
            engine.process_batch(10)
            self.assertEqual(send.call_count, 1)
        with frozen(at(2026, 10, 26, 3, 30)), mock.patch('apps.core.mailer.send_email') as send:
            # tomorrow the deferred one is wanted again, but its overdue step is stale and uses today's wording
            engine.process_batch(10)
            self.assertEqual(send.call_count, 1)

    def test_a_provider_outage_defers_to_the_next_run_and_stops_trying(self):
        events = self.many([-3, -3, -3])
        with frozen(MORNING(25)), mock.patch('apps.core.mailer.send_email',
                                              side_effect=mailer.EmailError(mailer.EmailError.PROVIDER_DOWN)) as send:
            counts = engine.process_batch(10)
        self.assertEqual(send.call_count, 1, 'after an outage the rest of the batch is not tried')
        for event in events:
            event.refresh_from_db()
            self.assertEqual(event.status, 'PENDING')
            self.assertEqual(event.next_attempt_at, MORNING(25) + timedelta(minutes=handlers.EMAIL_RETRY_MINUTES))
        self.assertEqual(counts['deferred'], 3)
        self.assertEqual(Notification.objects.count(), 3)
        self.assertEqual(NotificationLog.objects.filter(channel='email').count(), 0)
        with frozen(MORNING(25) + timedelta(minutes=16)), mock.patch('apps.core.mailer.send_email') as send:
            engine.process_batch(10)
        self.assertEqual(send.call_count, 3)
        self.assertEqual(NotificationLog.objects.filter(channel='in_app').count(), 3, 'the inbox part was not repeated')

    def test_other_email_errors_are_logged_without_personal_data_and_do_not_block(self):
        events = self.many([-3, -3])
        error = mailer.EmailError(mailer.EmailError.REJECTED)
        with frozen(MORNING(25)), mock.patch('apps.core.mailer.send_email', side_effect=error), \
                self.assertLogs('hh.notifications', level='ERROR') as logged:
            engine.process_batch(10)
        text = '\n'.join(logged.output)
        self.assertIn('rejected', text)
        self.assertNotIn('example.test', text)
        self.assertNotIn('Cap-0', text)
        for event in events:
            event.refresh_from_db()
            self.assertEqual(event.status, 'DONE')
        self.assertEqual(NotificationLog.objects.filter(channel='email').count(), 0)

    def test_the_email_is_never_sent_twice_for_one_due_and_step(self):
        event = self.world.reminder(self.due, 'due_day', 0)
        with frozen(MORNING(18)), mock.patch('apps.core.mailer.send_email') as send:
            engine.process_batch(10)
            OutboxEvent.objects.filter(pk=event.pk).update(status='PENDING', processed_at=None, attempts=0)
            engine.process_batch(10)
        send.assert_called_once()

    def test_the_engine_has_no_raw_http_library(self):
        import inspect
        from . import engine as engine_module, handlers as handlers_module, services as services_module
        for module in (engine_module, handlers_module, services_module):
            source = inspect.getsource(module)
            for banned in ('import requests', 'urllib', 'httpx', 'http.client'):
                self.assertNotIn(banned, source, (module.__name__, banned))


class NoTransactionAroundTheHttpCall(TransactionTestCase):
    """Rule S4: the email goes out while no database transaction is open."""

    def test_the_http_call_is_made_outside_a_database_transaction(self):
        world = World()
        stay = world.stay(make_user('student-a'))
        due = world.due(stay, DUE)
        world.reminder(due, 'due_day', 0)
        seen = []
        with frozen(MORNING(18)), mock.patch('apps.core.mailer.send_email',
                                              side_effect=lambda *a: seen.append(connection.in_atomic_block)):
            engine.process_batch(10)
        self.assertEqual(seen, [False])
