"""
Phase 9 backend slice: billing config per hostel, the billing preview, the AdminDues list and totals, the dashboard counts.

Today is frozen at 14 Oct 2026 (11:30 IST). Names are fictional; amounts are rupees as Decimal.
"""
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.notifications.testkit import World, at, frozen, make_user
from apps.payments.models import Payment
from apps.rooms.models import Room

from . import services
from .models import Due, HostelBillingConfig, OutboxEvent, Stay

TODAY = date(2026, 10, 14)
NOW = at(2026, 10, 14, 6, 0)
GOLDEN = Path(settings.BASE_DIR) / 'apps' / 'stays' / 'test_data' / 'adminbilling_golden.json'


def client_for(user):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


class AdminBase(TestCase):
    def setUp(self):
        cache.clear()
        self.world = World()
        self.owner = self.world.owner
        self.hostel = self.world.hostel
        self.owner_client = client_for(self.owner)
        self.staff = make_user('staff')
        self.staff.is_staff = True
        self.staff.save()
        self.stranger = make_user('owner-b')  # a signed-in user who owns nothing
        self.student = make_user('student-a')


# ------------------------------------------------------------------------------------------------- billing config

class BillingConfig(AdminBase):
    def url(self, hostel=None):
        return reverse('hostel-billing', args=[(hostel or self.hostel).id])

    def put(self, body, client=None):
        return (client or self.owner_client).put(self.url(), body, format='json')

    def test_get_gives_the_defaults_for_a_hostel_with_no_row(self):
        body = self.owner_client.get(self.url()).json()
        self.assertEqual(body['billing_mode'], 'ANNIVERSARY')
        self.assertIsNone(body['fixed_due_day'])
        self.assertFalse(body['fixed_due_last_day'])
        self.assertIsNone(body['first_period_policy'])
        self.assertEqual((body['payable_window_days'], body['grace_days']), (7, 0))
        self.assertEqual(body['booking_payment_covers'], 'FIRST_PERIOD_RENT')
        self.assertFalse(HostelBillingConfig.objects.exists(), 'a GET never writes')

    def test_get_shows_the_monthly_rent_from_the_rooms(self):
        body = self.owner_client.get(self.url()).json()
        rents = list(Room.objects.filter(hostel=self.hostel, is_active=True).values_list('price_per_month', flat=True))
        self.assertEqual(Decimal(body['monthly_rent']['min']), min(rents))
        self.assertEqual(Decimal(body['monthly_rent']['max']), max(rents))

    def test_put_saves_a_fixed_day_rule(self):
        response = self.put({'billing_mode': 'FIXED_DAY', 'fixed_due_day': 5, 'first_period_policy': 'PRORATE',
                             'payable_window_days': 10, 'grace_days': 2})
        self.assertEqual(response.status_code, 200, response.content)
        row = HostelBillingConfig.objects.get(hostel=self.hostel)
        self.assertEqual((row.billing_mode, row.fixed_due_day, row.fixed_due_last_day, row.first_period_policy,
                          row.payable_window_days, row.grace_days), ('FIXED_DAY', 5, False, 'PRORATE', 10, 2))
        self.assertEqual(self.owner_client.get(self.url()).json()['fixed_due_day'], 5)

    def test_put_accepts_the_last_day_option(self):
        response = self.put({'billing_mode': 'FIXED_DAY', 'fixed_due_last_day': True, 'first_period_policy': 'FULL_MONTH'})
        self.assertEqual(response.status_code, 200, response.content)
        row = HostelBillingConfig.objects.get(hostel=self.hostel)
        self.assertEqual((row.fixed_due_day, row.fixed_due_last_day), (None, True))

    def test_put_updates_the_same_row_and_can_go_back_to_anniversary(self):
        self.put({'billing_mode': 'FIXED_DAY', 'fixed_due_day': 1, 'first_period_policy': 'PRORATE'})
        response = self.put({'billing_mode': 'ANNIVERSARY', 'payable_window_days': 3, 'grace_days': 1})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(HostelBillingConfig.objects.filter(hostel=self.hostel).count(), 1)
        body = self.owner_client.get(self.url()).json()
        self.assertEqual((body['billing_mode'], body['fixed_due_day'], body['first_period_policy']), ('ANNIVERSARY', None, None))
        self.assertEqual((body['payable_window_days'], body['grace_days']), (3, 1))

    def test_validation(self):
        good = {'billing_mode': 'FIXED_DAY', 'fixed_due_day': 1, 'first_period_policy': 'PRORATE'}
        bad = [
            {'billing_mode': 'WEEKLY'},
            {'billing_mode': 'FIXED_DAY', 'first_period_policy': 'PRORATE'},                                   # no day
            {**good, 'fixed_due_day': 0}, {**good, 'fixed_due_day': 29}, {**good, 'fixed_due_day': 'x'},
            {**good, 'fixed_due_last_day': True},                                                              # day and last day
            {'billing_mode': 'FIXED_DAY', 'fixed_due_day': 1},                                                 # no policy
            {**good, 'first_period_policy': 'HALF'},
            {**good, 'payable_window_days': 0}, {**good, 'payable_window_days': 16},
            {**good, 'grace_days': -1}, {**good, 'grace_days': 16},
            {'billing_mode': 'ANNIVERSARY', 'fixed_due_day': 5},                                               # a day on anniversary
            {'billing_mode': 'ANNIVERSARY', 'fixed_due_last_day': True},
            {},
        ]
        for body in bad:
            self.assertEqual(self.put(body).status_code, 400, body)
        self.assertFalse(HostelBillingConfig.objects.exists())

    def test_the_limits_are_inclusive(self):
        for window, grace in ((1, 0), (15, 15)):
            response = self.put({'billing_mode': 'ANNIVERSARY', 'payable_window_days': window, 'grace_days': grace})
            self.assertEqual(response.status_code, 200, (window, grace))
        for day in (1, 28):
            self.assertEqual(self.put({'billing_mode': 'FIXED_DAY', 'fixed_due_day': day,
                                       'first_period_policy': 'FULL_MONTH'}).status_code, 200, day)

    def test_who_may_use_it(self):
        self.assertEqual(client_for(None).get(self.url()).status_code, 401)
        self.assertEqual(client_for(None).put(self.url(), {}, format='json').status_code, 401)
        for user in (self.stranger, self.student):
            self.assertEqual(client_for(user).get(self.url()).status_code, 404)
            self.assertEqual(self.put({'billing_mode': 'ANNIVERSARY'}, client_for(user)).status_code, 404)
        self.assertEqual(client_for(self.staff).get(self.url()).status_code, 200)
        self.assertEqual(self.put({'billing_mode': 'ANNIVERSARY'}, client_for(self.staff)).status_code, 200)
        self.assertEqual(client_for(self.stranger).get(reverse('hostel-billing', args=['00000000-0000-0000-0000-000000000000'])).status_code, 404)

    def test_only_get_and_put(self):
        for method in ('post', 'patch', 'delete'):
            self.assertEqual(getattr(self.owner_client, method)(self.url()).status_code, 405, method)


class ChangingTheRuleNeverTouchesExistingStays(AdminBase):
    def test_existing_stays_keep_their_snapshot_and_new_ones_get_the_new_rule(self):
        student = make_user('first')
        booking = Booking.objects.create(hostel=self.hostel, student=student, student_name='First', room=self.world.room,
                                         bed_number='1', payment_mode='offline', status='paid', check_in_date=date(2026, 9, 18),
                                         marked_paid_at=NOW)
        with frozen(NOW):
            old, _ = services.create_stay_for_booking(booking, None)
        before = (dict(old.billing_snapshot), old.rent_amount, list(old.dues.values_list('period_start', 'period_end', 'amount')))
        summary_before = client_for(student).get(reverse('stay-detail', args=[old.id])).json()['billing_summary']
        response = self.owner_client.put(reverse('hostel-billing', args=[self.hostel.id]), {
            'billing_mode': 'FIXED_DAY', 'fixed_due_day': 1, 'first_period_policy': 'PRORATE', 'payable_window_days': 12,
            'grace_days': 5}, format='json')
        self.assertEqual(response.status_code, 200)

        old.refresh_from_db()
        after = (dict(old.billing_snapshot), old.rent_amount, list(old.dues.values_list('period_start', 'period_end', 'amount')))
        self.assertEqual(after, before)
        self.assertEqual(old.billing_snapshot['billing_mode'], 'ANNIVERSARY')
        self.assertEqual(client_for(student).get(reverse('stay-detail', args=[old.id])).json()['billing_summary'], summary_before)

        other = make_user('second')
        booking2 = Booking.objects.create(hostel=self.hostel, student=other, student_name='Second', room=self.world.room,
                                          bed_number='2', payment_mode='offline', status='paid', check_in_date=date(2026, 9, 18),
                                          marked_paid_at=NOW)
        with frozen(NOW):
            new, _ = services.create_stay_for_booking(booking2, None)
        self.assertEqual(new.billing_snapshot['billing_mode'], 'FIXED_DAY')
        self.assertEqual((new.billing_snapshot['payable_window_days'], new.billing_snapshot['grace_days']), (12, 5))

    def test_the_daily_job_still_uses_the_stay_snapshot(self):
        stay = self.world.stay(join=date(2026, 8, 18))
        self.world.due(stay, date(2026, 8, 18), status='PAID', kind='BOOKING_PERIOD')
        self.world.due(stay, date(2026, 9, 18), status='PAID')
        self.owner_client.put(reverse('hostel-billing', args=[self.hostel.id]), {
            'billing_mode': 'FIXED_DAY', 'fixed_due_day': 1, 'first_period_policy': 'FULL_MONTH'}, format='json')
        from django.core.management import call_command
        from io import StringIO
        with frozen(NOW):
            call_command('stays_daily', '--today', '2026-09-18', '--skip-reconcile', stdout=StringIO())
        newest = stay.dues.order_by('-period_start').first()
        self.assertEqual(newest.period_start, date(2026, 10, 18), 'still on the 18th: the stay keeps the rule it joined with')


# ----------------------------------------------------------------------------------------------------------- preview

class Preview(AdminBase):
    def preview(self, body, client=None):
        return (client or self.owner_client).post(reverse('billing-preview'), body, format='json')

    def case_body(self, case, rent=6000):
        join = date.fromisoformat({'18 Sep 2026': '2026-09-18', '31 Jan 2027': '2027-01-31', '1 Sep 2026': '2026-09-01',
                                   '5 Sep 2026': '2026-09-05'}[case['join']])
        body = {'billing_mode': case['mode'], 'join_date': join.isoformat(), 'monthly_rent': str(rent), 'count': 5}
        if case['mode'] == 'FIXED_DAY':
            body['first_period_policy'] = case['policy']
            if case['day'] == 'LAST_DAY':
                body['fixed_due_last_day'] = True
            else:
                body['fixed_due_day'] = case['day']
        return body

    def test_every_golden_case_of_the_board_script_matches_exactly(self):
        golden = json.loads(GOLDEN.read_text(encoding='utf-8'))
        self.assertEqual(len(golden['cases']), 44)
        for case in golden['cases']:
            response = self.preview(self.case_body(case, golden['rent']))
            self.assertEqual(response.status_code, 200, (case['mode'], case['day'], case['join'], response.content))
            result = response.json()['results'][0]
            rows = [{'label': r['label'], 'period': r['period'], 'due': r['due'], 'amount': r['amount']} for r in result['rows']]
            self.assertEqual(rows, case['rows'], (case['mode'], case['day'], case['policy'], case['join']))
            self.assertEqual(result['summary'], case['summary'], (case['mode'], case['day'], case['policy'], case['join']))

    def test_the_first_three_due_dates_and_amounts(self):
        result = self.preview({'billing_mode': 'ANNIVERSARY', 'join_date': '2026-09-18', 'monthly_rent': '6000'}).json()['results'][0]
        self.assertGreaterEqual(len(result['rows']), 3)
        first, second, third = result['rows'][:3]
        self.assertEqual((first['due_date'], second['due_date'], third['due_date']), ('2026-09-18', '2026-10-18', '2026-11-18'))
        self.assertEqual((first['kind'], second['kind']), ('BOOKING_PERIOD', 'RENT'))
        self.assertEqual(Decimal(first['amount_rupees']), Decimal('6000.00'))

    def test_the_prorated_first_rent_is_the_engines_number(self):
        from . import billing
        result = self.preview({'billing_mode': 'FIXED_DAY', 'fixed_due_day': 1, 'first_period_policy': 'PRORATE',
                               'join_date': '2026-09-18', 'monthly_rent': '6000'}).json()['results'][0]
        self.assertEqual(Decimal(result['rows'][0]['amount_rupees']), billing.prorated_amount(Decimal('6000'), date(2026, 9, 18), 1))
        self.assertEqual(result['rows'][0]['amount'], '₹2,600')

    def test_several_join_dates_in_one_call(self):
        body = self.preview({'billing_mode': 'ANNIVERSARY', 'monthly_rent': '6000',
                             'join_dates': ['2026-09-18', '2027-01-31', '2026-09-01', '2026-09-05']}).json()
        self.assertEqual([r['join_date'] for r in body['results']], ['2026-09-18', '2027-01-31', '2026-09-01', '2026-09-05'])
        self.assertEqual(body['results'][1]['rows'][1]['due_date'], '2027-02-28')  # the anchor is never chained

    def test_amounts_are_exact_decimals(self):
        result = self.preview({'billing_mode': 'ANNIVERSARY', 'join_date': '2026-09-18', 'monthly_rent': '6500.50'}).json()['results'][0]
        self.assertEqual(result['rows'][0]['amount_rupees'], '6500.50')
        self.assertEqual(result['rows'][0]['amount'], '₹6,500.50')

    def test_validation(self):
        good = {'billing_mode': 'ANNIVERSARY', 'join_date': '2026-09-18', 'monthly_rent': '6000'}
        bad = [{**good, 'billing_mode': 'X'}, {**good, 'join_date': 'soon'}, {**good, 'monthly_rent': '0'},
               {**good, 'monthly_rent': '-5'}, {**good, 'monthly_rent': 'abc'}, {**good, 'monthly_rent': '99999999'},
               {**good, 'count': 0}, {**good, 'count': 13},
               {'billing_mode': 'FIXED_DAY', 'join_date': '2026-09-18', 'monthly_rent': '6000', 'first_period_policy': 'PRORATE'},
               {'billing_mode': 'FIXED_DAY', 'join_date': '2026-09-18', 'monthly_rent': '6000', 'fixed_due_day': 5},
               {**good, 'join_dates': ['2026-09-18'] * 7}, {'billing_mode': 'ANNIVERSARY', 'monthly_rent': '6000'}]
        for body in bad:
            self.assertEqual(self.preview(body).status_code, 400, body)

    def test_it_writes_nothing(self):
        before = (HostelBillingConfig.objects.count(), Stay.objects.count(), Due.objects.count(), OutboxEvent.objects.count())
        self.preview({'billing_mode': 'FIXED_DAY', 'fixed_due_day': 1, 'first_period_policy': 'PRORATE',
                      'join_date': '2026-09-18', 'monthly_rent': '6000'})
        self.assertEqual((HostelBillingConfig.objects.count(), Stay.objects.count(), Due.objects.count(),
                          OutboxEvent.objects.count()), before)

    def test_who_may_call_it(self):
        body = {'billing_mode': 'ANNIVERSARY', 'join_date': '2026-09-18', 'monthly_rent': '6000'}
        self.assertEqual(self.preview(body, client_for(None)).status_code, 401)
        self.assertEqual(self.preview(body, client_for(self.stranger)).status_code, 403)
        self.assertEqual(self.preview(body, client_for(self.student)).status_code, 403)
        self.assertEqual(self.preview(body, client_for(self.staff)).status_code, 200)
        self.assertEqual(self.preview(body).status_code, 200)

    def test_the_admin_does_not_need_its_own_billing_maths(self):
        src = Path(settings.BASE_DIR).parent / 'hostel-hunt-admin-next' / 'src'
        offenders = []
        for path in src.rglob('*.ts*'):
            if path.name.endswith('.test.ts') or path.name.endswith('.test.tsx'):
                continue
            text = path.read_text(encoding='utf-8')
            if 'prorat' in text.lower() and 'Math.floor' in text:
                offenders.append(path.name)
        self.assertEqual(offenders, [])


# ------------------------------------------------------------------------------------------------- the dues list

class DuesFixture(AdminBase):
    """Six stays at 14 Oct: two overdue, two payable (also due this week), one scheduled, one paid."""

    def setUp(self):
        super().setUp()
        self.s = {}
        plan = [
            ('A', 12, 'SCHEDULED', 1), ('B', 13, 'SCHEDULED', 2), ('C', 18, 'SCHEDULED', 1), ('D', 19, 'SCHEDULED', 2),
            ('E', 32, 'SCHEDULED', 1),   # 15 Nov
        ]
        room2 = Room.objects.get(hostel__name='Seed Alpha Residency', room_name='Single AC')
        for index, (tag, day, status, bed) in enumerate(plan):
            stay = self.world.stay(make_user(f'stud-{tag.lower()}'), bed=bed)
            if index % 2:
                Stay.objects.filter(pk=stay.pk).update(room=room2)
            due_date = date(2026, 10, 1) + timedelta(days=day - 1) if day <= 31 else date(2026, 11, 1) + timedelta(days=day - 32)
            self.world.due(stay, due_date, status=status)
            self.s[tag] = stay
        paid = self.world.stay(make_user('stud-f'), bed=2)
        self.world.due(paid, date(2026, 10, 1), status='PAID')
        Due.objects.filter(stay=paid).update(paid_at=at(2026, 10, 5, 6, 0))
        self.world.due(paid, date(2026, 10, 31) + timedelta(days=5), status='SCHEDULED')  # 5 Nov
        self.s['F'] = paid


class DuesList(DuesFixture):
    def get(self, name='stays-admin', client=None, **query):
        with frozen(NOW):
            return (client or self.owner_client).get(reverse(name), query)

    def rows(self, **query):
        return self.get(**query).json()['results']

    def test_the_rows_match_the_board(self):
        by_name = {r['student_name']: r for r in self.rows()}
        self.assertEqual(len(by_name), 6)
        statuses = {name: row['status'] for name, row in by_name.items()}
        self.assertEqual(statuses['Stud-A'], 'OVERDUE')
        self.assertEqual(statuses['Stud-B'], 'OVERDUE')
        self.assertEqual(statuses['Stud-C'], 'PAYABLE')
        self.assertEqual(statuses['Stud-D'], 'PAYABLE')
        self.assertEqual(statuses['Stud-E'], 'SCHEDULED')
        self.assertEqual(statuses['Stud-F'], 'PAID')
        row = by_name['Stud-A']
        self.assertEqual(row['status_label'], 'Overdue')
        self.assertEqual(Decimal(row['rent_amount']), self.world.rent)
        self.assertEqual(row['next_due']['date'], '2026-10-12')
        self.assertEqual(row['next_due']['days_left'], -2)
        self.assertEqual(row['room_label'], f'Room {self.world.room.room_number}')
        self.assertEqual(row['bed_label'], 'Bed A')
        self.assertEqual(row['hostel_name'], 'Seed Alpha Residency')
        self.assertEqual(by_name['Stud-F']['next_due']['date'], '2026-11-05')

    def test_rows_are_ordered_by_next_due_date(self):
        dates = [r['next_due']['date'] for r in self.rows()]
        self.assertEqual(dates, sorted(dates))

    def test_the_action_by_status(self):
        by_name = {r['student_name']: r for r in self.rows()}
        self.assertEqual(by_name['Stud-A']['primary_action'], 'record_payment')
        self.assertEqual(by_name['Stud-C']['primary_action'], 'send_reminder')
        self.assertEqual(by_name['Stud-E']['primary_action'], 'view')
        self.assertEqual(by_name['Stud-F']['primary_action'], 'view', 'paid with no payment record: nothing to show a receipt of')
        self.assertEqual(by_name['Stud-A']['action_due_id'], str(self.s['A'].dues.get().id))
        self.assertEqual(by_name['Stud-A']['action_due']['period_start'], '2026-10-12')
        self.assertEqual(by_name['Stud-A']['action_due']['period_end'], '2026-11-10')
        self.assertEqual(by_name['Stud-A']['action_due']['period_label'], '12 Oct – 10 Nov')
        self.assertEqual(Decimal(by_name['Stud-A']['action_due']['amount']), self.world.rent)
        a = set(by_name['Stud-A']['allowed_actions'])
        self.assertTrue({'record_payment', 'send_reminder', 'view', 'end_stay'} <= a)
        self.assertNotIn('receipt', a)
        self.assertIn('record_payment', by_name['Stud-E']['allowed_actions'])
        self.assertNotIn('send_reminder', by_name['Stud-E']['allowed_actions'])
        self.assertNotIn('receipt', by_name['Stud-F']['allowed_actions'])

    def test_a_paid_row_offers_receipt_and_void_only_for_an_offline_record(self):
        paid_due = self.s['F'].dues.get(status='PAID')
        payment = Payment.objects.create(booking=self.s['F'].booking, razorpay_order_id='order_x', amount=paid_due.amount,
                                         status='SUCCESS', purpose='RENT', due=paid_due, source='ONLINE', paid_via='UPI',
                                         verified_at=at(2026, 10, 5))
        Due.objects.filter(pk=paid_due.pk).update(payment=payment)
        row = next(r for r in self.rows() if r['student_name'] == 'Stud-F')
        self.assertEqual(row['receipt_payment_id'], str(payment.id))
        self.assertEqual(row['primary_action'], 'receipt')
        self.assertEqual(row['last_payment']['receipt_number'], payment.receipt_number)
        self.assertEqual((row['last_payment']['method'], row['last_payment']['source']), ('UPI', 'ONLINE'))
        self.assertEqual(row['last_payment']['paid_at'], '2026-10-05T05:30:00+05:30')
        self.assertNotIn('void', row['allowed_actions'])
        Payment.objects.filter(pk=payment.pk).update(source='OFFLINE_OWNER')
        row = next(r for r in self.rows() if r['student_name'] == 'Stud-F')
        self.assertIn('void', row['allowed_actions'])
        self.assertEqual(row['void_due_id'], str(paid_due.id))

    def test_the_totals(self):
        totals = self.get().json()['totals']
        rent = self.world.rent
        self.assertEqual(totals['active_stays'], 6)
        self.assertEqual(Decimal(totals['overdue']['amount']), rent * 2)
        self.assertEqual(totals['overdue']['count'], 2)
        self.assertEqual(Decimal(totals['due_this_week']['amount']), rent * 2)
        self.assertEqual(totals['due_this_week']['count'], 2)
        self.assertEqual(Decimal(totals['collected_this_month']['amount']), rent)
        self.assertEqual((totals['collected_this_month']['stays_paid'], totals['collected_this_month']['stays_total']), (1, 6))

    def test_tab_counts_and_the_tab_filters(self):
        body = self.get().json()
        self.assertEqual(body['tab_counts'], {'all': 6, 'overdue': 2, 'due_this_week': 2, 'paid': 1})
        self.assertEqual(body['count'], 6)
        self.assertEqual({r['student_name'] for r in self.rows(overdue='true')}, {'Stud-A', 'Stud-B'})
        self.assertEqual({r['student_name'] for r in self.rows(due_this_week='true')}, {'Stud-C', 'Stud-D'})
        self.assertEqual({r['student_name'] for r in self.rows(paid='true')}, {'Stud-F'})
        self.assertEqual(self.get(overdue='true').json()['count'], 2)

    def test_the_overdue_shortcut(self):
        body = self.get('stays-admin-overdue').json()
        self.assertEqual({r['student_name'] for r in body['results']}, {'Stud-A', 'Stud-B'})
        self.assertEqual(body['count'], 2)
        self.assertEqual(self.get('stays-admin-overdue', client=client_for(self.stranger)).json()['results'], [])

    def test_grace_days_move_the_overdue_line(self):
        Stay.objects.filter(pk=self.s['A'].pk).update(billing_snapshot={**self.s['A'].billing_snapshot, 'grace_days': 5})
        by_name = {r['student_name']: r['status'] for r in self.rows()}
        self.assertEqual(by_name['Stud-A'], 'PAYABLE')
        self.assertEqual(self.get().json()['tab_counts']['overdue'], 1)

    def test_the_payable_window_moves_payable(self):
        by_name = {r['student_name']: r['status'] for r in self.rows()}
        self.assertEqual(by_name['Stud-E'], 'SCHEDULED')  # due 1 Nov is 18 days away
        Stay.objects.filter(pk=self.s['E'].pk).update(billing_snapshot={**self.s['E'].billing_snapshot, 'payable_window_days': 15})
        self.assertEqual({r['student_name']: r['status'] for r in self.rows()}['Stud-E'], 'SCHEDULED')
        Stay.objects.filter(pk=self.s['E'].pk).update(billing_snapshot={**self.s['E'].billing_snapshot, 'payable_window_days': 20})
        self.assertEqual({r['student_name']: r['status'] for r in self.rows()}['Stud-E'], 'PAYABLE')

    def test_needs_review_filter_and_flag(self):
        Stay.objects.filter(pk=self.s['C'].pk).update(needs_review=True)
        rows = self.rows(needs_review='true')
        self.assertEqual([r['student_name'] for r in rows], ['Stud-C'])
        self.assertTrue(rows[0]['needs_review'])
        self.assertFalse(next(r for r in self.rows() if r['student_name'] == 'Stud-A')['needs_review'])

    def test_status_and_hostel_filters(self):
        Stay.objects.filter(pk=self.s['E'].pk).update(status='NOTICE')
        self.assertEqual([r['student_name'] for r in self.rows(status='NOTICE')], ['Stud-E'])
        ended = self.world.stay(make_user('stud-z'), bed=2)
        Stay.objects.filter(pk=ended.pk).update(status='ENDED')
        self.assertNotIn('Stud-Z', [r['student_name'] for r in self.rows()], 'ended stays are not in the default view')
        self.assertEqual([r['student_name'] for r in self.rows(status='ENDED')], ['Stud-Z'])
        other_hostel = self.hostel.__class__.objects.exclude(pk=self.hostel.pk).filter(owner=self.owner).first()
        self.assertEqual(self.rows(hostel=str(other_hostel.id)), [])
        self.assertEqual(len(self.rows(hostel=str(self.hostel.id))), 6)
        self.assertEqual(self.get(hostel='not-a-uuid').status_code, 400)
        self.assertEqual(self.get(status='NOPE').status_code, 400)

    def test_the_hostel_selector_lists_the_owners_hostels(self):
        hostels = self.get().json()['hostels']
        self.assertEqual({h['name'] for h in hostels}, {'Seed Alpha Residency', 'Seed Beta Stay', 'Seed Gamma PG'})
        self.assertEqual(set(hostels[0]), {'id', 'name', 'locality'})

    def test_scope_owners_see_only_their_tenant_staff_see_all(self):
        self.assertEqual(self.get(client=client_for(self.stranger)).json()['results'], [])
        self.assertEqual(self.get(client=client_for(self.stranger)).json()['totals']['active_stays'], 0)
        self.assertEqual(len(self.get(client=client_for(self.staff)).json()['results']), 6)
        self.assertEqual(self.get(client=client_for(None)).status_code, 401)
        self.assertEqual(self.get(client=client_for(self.student)).json()['results'], [])

    def test_pagination_is_capped(self):
        body = self.get(page_size=2).json()
        self.assertEqual((body['count'], len(body['results'])), (6, 2))
        self.assertEqual(len(self.get(page_size=1000).json()['results']), 6)
        self.assertEqual(len(self.get(page=2, page_size=4).json()['results']), 2)
        self.assertEqual(body['totals']['active_stays'], 6, 'totals cover every row, not one page')

    def test_waived_and_cancelled_dues_are_not_overdue(self):
        Due.objects.filter(stay=self.s['A']).update(status='WAIVED')
        Due.objects.filter(stay=self.s['B']).update(status='CANCELLED')
        self.assertEqual(self.get().json()['tab_counts']['overdue'], 0)

    def test_query_count_does_not_grow_with_the_number_of_stays(self):
        def count():
            cache.clear()
            with frozen(NOW), CaptureQueriesContext(connection) as queries:
                self.owner_client.get(reverse('stays-admin'), {'page_size': 100})
            return len(queries)

        small = count()
        for n in range(30):
            stay = self.world.stay(make_user(f'extra-{n}'), bed=1 if n % 2 else 2)
            self.world.due(stay, date(2026, 10, 12), status='SCHEDULED')
            self.world.due(stay, date(2026, 11, 12), status='SCHEDULED')
        self.assertEqual(count(), small)
        self.assertLessEqual(small, 14)

    def test_the_list_is_read_only(self):
        for method in ('post', 'put', 'patch', 'delete'):
            self.assertEqual(getattr(self.owner_client, method)(reverse('stays-admin')).status_code, 405, method)

    def test_the_new_stay_indexes_exist(self):
        self.assertIn('dues_stay_status_due_idx', {i.name for i in Due._meta.indexes})


# ---------------------------------------------------------------------------------------------------------- dashboard

class DashboardCounts(DuesFixture):
    def stats(self, client=None):
        with frozen(NOW):
            return (client or self.owner_client).get(reverse('dashboard-stats')).json()['data']

    def test_overdue_and_due_this_week_counts(self):
        data = self.stats()
        self.assertEqual(data['overdue_rent_count'], 2)
        self.assertEqual(data['due_this_week_count'], 2)

    def test_another_owner_sees_zero_and_the_cache_is_per_tenant(self):
        self.stats()  # fills the owner's cached entry
        other = self.stats(client_for(self.stranger))
        self.assertEqual((other['overdue_rent_count'], other['due_this_week_count']), (0, 0))
        self.assertEqual(self.stats()['overdue_rent_count'], 2)

    def test_the_count_is_cached_briefly_through_the_shared_cache(self):
        self.stats()
        Due.objects.filter(stay=self.s['A']).update(status='PAID')
        self.assertEqual(self.stats()['overdue_rent_count'], 2, 'inside the short cache window the number does not move')
        cache.clear()
        self.assertEqual(self.stats()['overdue_rent_count'], 1)

    def test_the_stats_endpoint_keeps_its_old_fields(self):
        data = self.stats()
        for key in ('total_hostels', 'total_residents', 'revenue_collected', 'bookings_by_status'):
            self.assertIn(key, data)


# ----------------------------------------------------------------------------------------- payments and bookings views

class AdminListFields(AdminBase):
    def test_the_payment_list_shows_purpose_method_and_source_and_filters(self):
        stay = self.world.stay(make_user('p1'))
        due = self.world.due(stay, date(2026, 10, 1), status='PAID')
        rent = Payment.objects.create(booking=stay.booking, razorpay_order_id='o1', amount=1, status='SUCCESS', purpose='RENT',
                                      due=due, source='OFFLINE_OWNER', paid_via='CASH', verified_at=NOW)
        online = Payment.objects.create(booking=stay.booking, razorpay_order_id='o2', amount=1, status='SUCCESS',
                                        purpose='BOOKING', source='ONLINE')
        rows = {r['id']: r for r in self.owner_client.get(reverse('payment-admin-list')).json()['results']}
        self.assertEqual((rows[str(rent.id)]['purpose'], rows[str(rent.id)]['source'], rows[str(rent.id)]['paid_via']),
                         ('RENT', 'OFFLINE_OWNER', 'CASH'))
        self.assertEqual(rows[str(online.id)]['source'], 'ONLINE')
        self.assertIn('receipt_number', rows[str(rent.id)])
        for params, expected in (({'purpose': 'rent'}, {str(rent.id)}), ({'purpose': 'booking'}, {str(online.id)}),
                                 ({'source': 'offline_owner'}, {str(rent.id)}), ({'source': 'online'}, {str(online.id)})):
            got = {r['id'] for r in self.owner_client.get(reverse('payment-admin-list'), params).json()['results']}
            self.assertEqual(got, expected, params)

    def test_the_booking_list_shows_the_stay_badge_and_needs_review(self):
        stay = self.world.stay(make_user('p2'))
        Stay.objects.filter(pk=stay.pk).update(needs_review=True)
        lone = Booking.objects.create(hostel=self.hostel, student_name='No Stay', room=self.world.room, payment_mode='offline')
        rows = {r['id']: r for r in self.owner_client.get(reverse('booking-list')).json()['results']}
        with_stay = rows[str(stay.booking_id)]
        self.assertEqual((with_stay['stay_id'], with_stay['stay_status'], with_stay['stay_needs_review']),
                         (str(stay.id), 'ACTIVE', True))
        self.assertEqual((rows[str(lone.id)]['stay_id'], rows[str(lone.id)]['stay_status'], rows[str(lone.id)]['stay_needs_review']),
                         (None, None, False))

    def test_the_booking_list_costs_no_extra_query_per_row(self):
        for n in range(5):
            self.world.stay(make_user(f'b{n}'), bed=1 if n % 2 else 2)
        with CaptureQueriesContext(connection) as small:
            self.owner_client.get(reverse('booking-list'))
        for n in range(5, 15):
            self.world.stay(make_user(f'b{n}'), bed=1 if n % 2 else 2)
        with CaptureQueriesContext(connection) as large:
            self.owner_client.get(reverse('booking-list'))
        self.assertEqual(len(small), len(large))
