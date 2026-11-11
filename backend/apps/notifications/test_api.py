"""
Notification endpoints, the manual 'Send reminder', the unread-count cache, the purge steps and the admin status page.
"""
from datetime import date, timedelta
from io import StringIO
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse
from rest_framework.test import APIClient

from apps.stays.models import Due, OutboxEvent, Stay

from . import engine, services
from .models import JobRun, Notification, NotificationLog, NotificationPreference
from .testkit import World, at, frozen, make_user

DUE = date(2026, 10, 18)
NOW = at(2026, 10, 15, 6, 0)  # 11:30 IST on 15 Oct: 3 days before the due date, inside the 7-day window


def client_for(user):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


class ApiBase(TestCase):
    def setUp(self):
        cache.clear()
        self.world = World()
        self.student = make_user('student-a')
        self.stay = self.world.stay(self.student)
        self.due = self.world.due(self.stay, DUE, status='PAYABLE')
        self.client_student = client_for(self.student)
        self.client_owner = client_for(self.world.owner)

    def notice(self, user=None, kind='before_7', category='RENT', channels=('in_app',), when=None, **extra):
        defaults = dict(user=user or self.student, kind=kind, category=category, title=f'T {kind}', body='B',
                        channels_delivered=list(channels), dedupe_key=f'k-{Notification.objects.count()}-{kind}',
                        created_at=when or NOW)
        defaults.update(extra)
        return Notification.objects.create(**defaults)


class ListAndRead(ApiBase):
    def test_list_newest_first_with_channels(self):
        old = self.notice(kind='before_7', when=NOW - timedelta(days=5), channels=('push', 'in_app'))
        new = self.notice(kind='payment_received', when=NOW, due=self.due, payload={'payment_id': 'p1', 'stay_id': 's1'})
        body = self.client_student.get(reverse('notification-list')).json()
        self.assertEqual(set(body), {'count', 'next', 'previous', 'results'})
        self.assertEqual([r['id'] for r in body['results']], [str(new.id), str(old.id)])
        first, second = body['results']
        self.assertEqual(second['channels'], ['push', 'in_app'])
        self.assertEqual(second['channels_label'], 'Push, in-app')
        self.assertEqual(first['category'], 'rent')
        self.assertEqual(first['action'], {'type': 'receipt', 'payment_id': 'p1', 'stay_id': 's1'})
        self.assertIsNone(first['read_at'])
        self.assertTrue(first['created_at'].endswith('+05:30'))

    def test_a_reminder_item_opens_the_pay_screen_for_its_due(self):
        self.notice(kind='before_7', due=self.due)
        item = self.client_student.get(reverse('notification-list')).json()['results'][0]
        self.assertEqual(item['action'], {'type': 'pay', 'due_id': str(self.due.id)})
        self.assertEqual(item['due_id'], str(self.due.id))

    def test_the_category_filter_matches_the_inbox_board(self):
        self.notice(kind='before_7', category='RENT')
        self.notice(kind='stay_created', category='STAY')
        for name, expected in (('rent', ['before_7']), ('stay', ['stay_created'])):
            rows = self.client_student.get(reverse('notification-list'), {'category': name}).json()['results']
            self.assertEqual([r['kind'] for r in rows], expected)
        self.assertEqual(self.client_student.get(reverse('notification-list'), {'category': 'RENT'}).json()['count'], 1)
        self.assertEqual(self.client_student.get(reverse('notification-list'), {'category': 'x'}).status_code, 400)
        self.assertEqual(len(self.client_student.get(reverse('notification-list')).json()['results']), 2)

    def test_pagination_is_capped(self):
        for n in range(30):
            self.notice(kind='before_7', when=NOW - timedelta(minutes=n))
        body = self.client_student.get(reverse('notification-list')).json()
        self.assertEqual((body['count'], len(body['results'])), (30, 20))
        self.assertEqual(len(self.client_student.get(reverse('notification-list'), {'page_size': 1000}).json()['results']), 30)
        self.assertEqual(len(self.client_student.get(reverse('notification-list'), {'page': 2}).json()['results']), 10)

    def test_only_my_notifications(self):
        other = make_user('student-b')
        mine = self.notice()
        theirs = self.notice(user=other)
        ids = [r['id'] for r in self.client_student.get(reverse('notification-list')).json()['results']]
        self.assertEqual(ids, [str(mine.id)])
        self.assertEqual(self.client_student.post(reverse('notification-read', args=[theirs.id])).status_code, 404)
        theirs.refresh_from_db()
        self.assertIsNone(theirs.read_at)

    def test_anonymous_gets_401(self):
        anon = client_for(None)
        for name in ('notification-list', 'notification-unread-count', 'notification-preferences'):
            self.assertEqual(anon.get(reverse(name)).status_code, 401, name)
        self.assertEqual(anon.post(reverse('notification-read-all')).status_code, 401)
        self.assertEqual(anon.post(reverse('notification-read', args=[self.notice().id])).status_code, 401)

    def test_mark_read_and_read_all(self):
        a, b, c = self.notice(), self.notice(kind='due_day'), self.notice(kind='overdue_3')
        with frozen(NOW):
            response = self.client_student.post(reverse('notification-read', args=[a.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json()['read_at'])
        a.refresh_from_db()
        first_read = a.read_at
        with frozen(NOW + timedelta(hours=1)):
            self.client_student.post(reverse('notification-read', args=[a.id]))  # a second tap changes nothing
        a.refresh_from_db()
        self.assertEqual(a.read_at, first_read)
        updated = self.client_student.post(reverse('notification-read-all')).json()['updated']
        self.assertEqual(updated, 2)
        self.assertFalse(Notification.objects.filter(user=self.student, read_at__isnull=True).exists())

    def test_the_unread_index_exists(self):
        names = {i.name for i in Notification._meta.indexes}
        self.assertIn('notif_user_read_created_idx', names)


class UnreadCount(ApiBase):
    def count(self):
        return self.client_student.get(reverse('notification-unread-count')).json()['unread']

    def test_counts_unread_only(self):
        self.notice()
        self.notice(kind='due_day')
        self.notice(kind='x', read_at=NOW)
        self.assertEqual(self.count(), 2)

    def test_it_is_cached_per_user_and_costs_no_query_the_second_time(self):
        self.notice()
        self.assertEqual(self.count(), 1)
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.count(), 1)
        self.assertEqual(len(queries), 0)

    def test_it_is_cached_for_15_seconds(self):
        self.assertEqual(services.UNREAD_TTL_SECONDS, 15)

    def test_the_version_is_bumped_on_every_change(self):
        a = self.notice()
        self.assertEqual(self.count(), 1)
        services.bump_unread(self.student.id)  # what a handler does after creating a notice
        self.notice(kind='due_day')
        self.assertEqual(self.count(), 2)
        self.client_student.post(reverse('notification-read', args=[a.id]))
        self.assertEqual(self.count(), 1)
        self.client_student.post(reverse('notification-read-all'))
        self.assertEqual(self.count(), 0)

    def test_one_users_count_never_reaches_another(self):
        other = client_for(make_user('student-b'))
        self.notice()
        self.assertEqual(self.count(), 1)
        self.assertEqual(other.get(reverse('notification-unread-count')).json()['unread'], 0)

    def test_creating_a_notice_through_the_engine_refreshes_the_count_and_the_home_badge(self):
        self.assertEqual(self.count(), 0)
        self.world.event('stay.created', 'sc1', {'stay_id': str(self.stay.id)})
        with frozen(NOW):
            engine.process_batch(10)
        self.assertEqual(self.count(), 1)
        with override_settings(STAYS_ENABLED=True):
            home = self.client_student.get(reverse('stay-home')).json()
        badge = next(a for a in home['quick_actions'] if a['key'] == 'notices')['badge']
        self.assertEqual(badge, 1)

    def test_a_cache_that_is_down_still_counts(self):
        class DownCache:
            def get(self, key, default=None):
                return default

            def add(self, key, value, timeout=None):
                return None

            def set(self, key, value, timeout=None):
                return None

            def delete(self, key):
                return None

        self.notice()
        with mock.patch('apps.core.cache.cache', DownCache()):
            self.assertEqual(self.count(), 1)


class Preferences(ApiBase):
    def test_defaults_without_a_row_and_without_creating_one(self):
        self.assertEqual(self.client_student.get(reverse('notification-preferences')).json(),
                         {'inbox': True, 'push': True, 'email': True})
        self.assertFalse(NotificationPreference.objects.exists())

    def test_patch_changes_only_what_is_sent(self):
        response = self.client_student.patch(reverse('notification-preferences'), {'email': False}, format='json')
        self.assertEqual(response.json(), {'inbox': True, 'push': True, 'email': False})
        self.client_student.patch(reverse('notification-preferences'), {'push': False}, format='json')
        self.assertEqual(self.client_student.get(reverse('notification-preferences')).json(),
                         {'inbox': True, 'push': False, 'email': False})
        self.assertEqual(NotificationPreference.objects.filter(user=self.student).count(), 1)

    def test_a_bad_value_is_refused(self):
        self.assertEqual(self.client_student.patch(reverse('notification-preferences'), {'email': 'maybe'}, format='json')
                         .status_code, 400)

    def test_one_user_cannot_change_anothers(self):
        self.client_student.patch(reverse('notification-preferences'), {'inbox': False}, format='json')
        other = client_for(make_user('student-b'))
        self.assertEqual(other.get(reverse('notification-preferences')).json()['inbox'], True)


# ---------------------------------------------------------------------------------------------------- manual reminder

class ManualReminder(ApiBase):
    def url(self, due=None):
        return reverse('due-send-reminder', args=[(due or self.due).id])

    def send(self, client=None, due=None, moment=NOW):
        with frozen(moment):
            return (client or self.client_owner).post(self.url(due))

    def test_the_owner_queues_a_reminder_through_the_outbox(self):
        response = self.send()
        self.assertEqual(response.status_code, 202, response.content)
        event = OutboxEvent.objects.get(topic='rent.reminder_manual')
        self.assertEqual(event.payload, {'due_id': str(self.due.id), 'bucket': '2026-10-15'})
        self.assertEqual(event.dedupe_key, f'reminder-manual-{self.due.id}-2026-10-15')
        self.assertEqual(NotificationLog.objects.get(channel='request').bucket, '2026-10-15')
        self.assertFalse(Notification.objects.exists(), 'nothing is sent inside the request')

    def test_it_is_delivered_by_the_engine_and_honours_preferences(self):
        self.send()
        with frozen(NOW), mock.patch('apps.core.mailer.send_email') as send:
            engine.process_batch(10)
        notice = Notification.objects.get()
        self.assertEqual(notice.kind, 'manual_reminder')
        self.assertEqual(notice.title, 'Rent due in 3 days')
        self.assertEqual(notice.body, 'Pay ₹6,500 by 18 Oct. Tap to pay in the app.')
        send.assert_not_called()  # three days before: inbox and push only

    def test_it_honours_a_student_who_switched_the_inbox_off(self):
        NotificationPreference.objects.create(user=self.student, inbox=False)
        self.send()
        with frozen(NOW):
            engine.process_batch(10)
        self.assertFalse(Notification.objects.exists())

    def test_an_overdue_manual_reminder_also_emails(self):
        Due.objects.filter(pk=self.due.pk).update(status='SCHEDULED')
        moment = at(2026, 10, 21, 6, 0)
        self.send(moment=moment)
        with frozen(moment), mock.patch('apps.core.mailer.send_email') as send:
            engine.process_batch(10)
        send.assert_called_once()
        self.assertEqual(Notification.objects.get().title, 'Rent is 3 days overdue')

    def test_at_most_once_per_due_per_day(self):
        self.assertEqual(self.send().status_code, 202)
        second = self.send()
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()['code'], 'REMINDER_ALREADY_SENT')
        self.assertEqual(OutboxEvent.objects.filter(topic='rent.reminder_manual').count(), 1)
        self.assertEqual(self.send(moment=NOW + timedelta(days=1)).status_code, 202, 'the next day it is allowed again')
        other_due = self.world.due(self.stay, DUE + timedelta(days=2), status='PAYABLE')  # also inside its window
        self.assertEqual(self.send(due=other_due).status_code, 202, 'the limit is per due')

    def test_only_payable_or_overdue_dues(self):
        far = self.world.due(self.stay, DUE + timedelta(days=200))
        response = self.send(due=far)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['code'], 'DUE_NOT_REMINDABLE')
        for status in ('PAID', 'WAIVED', 'CANCELLED'):
            due = self.world.due(self.stay, DUE + timedelta(days=60 + {'PAID': 0, 'WAIVED': 40, 'CANCELLED': 80}[status]),
                                 status=status)
            self.assertEqual(self.send(due=due).status_code, 409, status)
        self.assertFalse(OutboxEvent.objects.exists())

    def test_an_ended_stay_cannot_be_reminded(self):
        Stay.objects.filter(pk=self.stay.pk).update(status='ENDED')
        self.assertEqual(self.send().json()['code'], 'STAY_NOT_CURRENT')

    def test_permission_boundaries(self):
        self.assertEqual(self.send(client=self.client_student).status_code, 404)
        self.assertEqual(self.send(client=client_for(make_user('owner-b'))).status_code, 404)
        self.assertEqual(self.send(client=client_for(None)).status_code, 401)
        staff = make_user('staff')
        staff.is_staff = True
        staff.save()
        self.assertEqual(self.send(client=client_for(staff)).status_code, 202)
        self.assertEqual(OutboxEvent.objects.count(), 1)

    def test_quiet_hours_hold_a_manual_reminder_until_the_morning(self):
        night = at(2026, 10, 15, 16, 30)  # 22:00 IST, the due is still payable
        self.send(moment=night)
        with frozen(night):
            self.assertEqual(engine.process_batch(10)['claimed'], 0)
        with frozen(at(2026, 10, 16, 2, 40)):
            engine.process_batch(10)
        self.assertEqual(Notification.objects.count(), 1)


# ------------------------------------------------------------------------------------------------------------- purge

class Purge(ApiBase):
    def test_cleanup_expired_purges_old_rows_in_isolated_steps_and_keeps_new_ones(self):
        old = at(2026, 1, 1)
        fresh = NOW
        Notification.objects.create(user=self.student, kind='a', category='RENT', title='t', body='b', dedupe_key='old',
                                    created_at=old)
        Notification.objects.create(user=self.student, kind='a', category='RENT', title='t', body='b', dedupe_key='new',
                                    created_at=fresh)
        NotificationLog.objects.create(due=self.due, kind='before_7', channel='in_app', created_at=old)
        NotificationLog.objects.create(due=self.due, kind='before_3', channel='in_app', created_at=fresh)
        OutboxEvent.objects.create(topic='x', dedupe_key='done-old', status='DONE', processed_at=old)
        OutboxEvent.objects.create(topic='x', dedupe_key='done-new', status='DONE', processed_at=fresh)
        OutboxEvent.objects.create(topic='x', dedupe_key='pending-old', status='PENDING')
        OutboxEvent.objects.create(topic='x', dedupe_key='failed-old', status='FAILED', processed_at=old)
        JobRun.objects.create(name='stays_daily', run_day=date(2026, 1, 1), started_at=old)
        JobRun.objects.create(name='stays_daily', run_day=date(2026, 10, 15), started_at=fresh)
        out = StringIO()
        with frozen(NOW + timedelta(hours=1)):
            call_command('cleanup_expired', stdout=out)
        text = out.getvalue()
        for step in ('outbox_done', 'notification_logs', 'notifications', 'job_runs'):
            self.assertIn(f'{step}: 1', text, step)
        self.assertEqual(list(Notification.objects.values_list('dedupe_key', flat=True)), ['new'])
        self.assertEqual(list(NotificationLog.objects.values_list('kind', flat=True)), ['before_3'])
        self.assertEqual(sorted(OutboxEvent.objects.values_list('dedupe_key', flat=True)),
                         ['done-new', 'failed-old', 'pending-old'])
        self.assertEqual(JobRun.objects.count(), 1)

    def test_dry_run_changes_nothing(self):
        old = at(2026, 1, 1)
        OutboxEvent.objects.create(topic='x', dedupe_key='done-old', status='DONE', processed_at=old)
        with frozen(NOW):
            out = StringIO()
            call_command('cleanup_expired', '--dry-run', stdout=out)
        self.assertIn('outbox_done: 1', out.getvalue())
        self.assertEqual(OutboxEvent.objects.count(), 1)


# -------------------------------------------------------------------------------------------------------- ops status

class OpsStatus(ApiBase):
    def test_admin_only(self):
        staff = make_user('staff')
        staff.is_staff = True
        staff.save()
        url = reverse('ops-status')
        self.assertEqual(client_for(None).get(url).status_code, 401)
        self.assertEqual(self.client_student.get(url).status_code, 403)
        self.assertEqual(self.client_owner.get(url).status_code, 403)
        self.assertEqual(client_for(staff).get(url).status_code, 200)

    def test_the_content_and_no_personal_data(self):
        staff = make_user('staff')
        staff.is_staff = True
        staff.save()
        self.world.event('stay.created', 'e1', {'stay_id': str(self.stay.id)})
        self.world.event('stay.created', 'e2', {'stay_id': str(self.stay.id)}, status='FAILED', attempts=8)
        JobRun.objects.create(name='stays_daily', run_day=date(2026, 10, 15), status='OK', started_at=NOW,
                              finished_at=NOW + timedelta(minutes=2))
        with frozen(NOW + timedelta(hours=1)):
            body = client_for(staff).get(reverse('ops-status')).json()
        self.assertEqual(body['outbox']['pending'], 1)
        self.assertEqual(body['outbox']['failed'], 1)
        self.assertIsInstance(body['outbox']['oldest_pending_age_seconds'], int)
        self.assertEqual(body['jobs']['stays_daily']['last_run_status'], 'OK')
        self.assertTrue(body['jobs']['stays_daily']['last_success_at'])
        self.assertIsNone(body['jobs']['process_outbox']['last_success_at'])
        self.assertIn(body['redis'], ('not_configured', 'reachable', 'unreachable'))
        text = str(body)
        self.assertNotIn('example.test', text)
        self.assertNotIn('student-a', text.lower())

    def test_an_empty_outbox(self):
        staff = make_user('staff')
        staff.is_staff = True
        staff.save()
        body = client_for(staff).get(reverse('ops-status')).json()
        self.assertEqual(body['outbox'], {'pending': 0, 'failed': 0, 'oldest_pending_age_seconds': None})
