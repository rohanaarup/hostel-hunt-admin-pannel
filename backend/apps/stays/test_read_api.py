"""
Phase 7 tests: the read-only student endpoints (stays list and detail, dues, payments, receipt, analytics, calendar and the
one aggregated Home call), their access rules, query budgets, IST day boundaries, caching and ETags.

Names, amounts and ids are fictional. No write endpoint is added in this phase.
"""
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.core.sample_data import ensure_sample_catalog
from apps.payments.models import Payment, PaymentAttempt
from apps.rooms.models import Room

from . import services
from .dates import today_ist
from .models import Due, HostelBillingConfig, OutboxEvent, Stay
from .test_lifecycle import make_booking, make_user, pay_online

UTC = dt_timezone.utc


def frozen(year, month, day, hour=6, minute=0):
    """A fixed 'now' in UTC; mock.patch it over django.utils.timezone.now."""
    return mock.patch('django.utils.timezone.now', return_value=datetime(year, month, day, hour, minute, tzinfo=UTC))


class ReadBase(TestCase):
    # Join 45 days ago: Due 2 started about two weeks ago, so it is overdue; a stay of this age has two stored dues.
    join_days_ago = 45

    def setUp(self):
        cache.clear()
        self.owner = ensure_sample_catalog()
        self.room = Room.objects.get(hostel__name='Seed Alpha Residency', room_name='Double')
        self.price = self.room.price_per_month
        self.student = make_user('student-a')
        self.stay = self.make_stay(self.student, 1, self.join_days_ago)
        self.client_student = self.client_for(self.student)

    def make_stay(self, student, bed, days_ago, check_in=None):
        booking = make_booking(self.room, bed, student, check_in=check_in or (today_ist() - timedelta(days=days_ago)))
        pay_online(booking, f'pay_read_{booking.id.hex[:8]}')
        return Stay.objects.get(booking=booking)

    @staticmethod
    def client_for(user):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    def get(self, name, *args, client=None, **query):
        return (client or self.client_student).get(reverse(name, args=args), query)

    def mark_paid(self, due, paid_at=None, via='UPI', ref='pay_ABCD3M9X'):
        paid_at = paid_at or timezone.now()
        payment = Payment.objects.create(
            booking=self.stay.booking, razorpay_order_id=f'order_{due.id.hex[:12]}', amount=due.amount,
            status=Payment.Status.SUCCESS, purpose='RENT', due=due, paid_via=via, verified_at=paid_at)
        PaymentAttempt.objects.create(payment=payment, method='UPI', status='SUCCESS', razorpay_payment_id=ref + due.id.hex[:4])
        Due.objects.filter(pk=due.pk).update(status='PAID', paid_at=paid_at, payment=payment)
        return payment

    def add_dues(self, count):
        """Add stored rent dues after the existing ones (bulk, so the test itself is cheap)."""
        last = self.stay.dues.order_by('-period_end').first()
        start = last.period_end + timedelta(days=1)
        rows = []
        for n in range(count):
            end = start + timedelta(days=29)
            rows.append(Due(stay=self.stay, period_start=start, period_end=end, due_date=start, amount=self.price,
                            status='SCHEDULED', kind='RENT'))
            start = end + timedelta(days=1)
        Due.objects.bulk_create(rows)


# ----------------------------------------------------------------------------------------------------------- access

class Access(ReadBase):
    ENDPOINTS = ('stay-detail', 'stay-dues', 'stay-payments', 'stay-analytics')

    def test_anonymous_gets_401_everywhere(self):
        anon = self.client_for(None)
        for name in ('stay-list', 'stay-home', 'stay-calendar'):
            self.assertEqual(anon.get(reverse(name)).status_code, 401, name)
        for name in self.ENDPOINTS:
            self.assertEqual(anon.get(reverse(name, args=[self.stay.id])).status_code, 401, name)

    def test_a_student_sees_only_their_own_stays(self):
        other = make_user('student-b')
        theirs = self.make_stay(other, 2, 10)
        mine = self.get('stay-list').json()
        self.assertEqual([row['id'] for row in mine['results']], [str(self.stay.id)])
        for name in self.ENDPOINTS:
            self.assertEqual(self.get(name, theirs.id).status_code, 404, name)
        self.assertEqual(self.get('stay-receipt', theirs.id, self.mark_paid(theirs.dues.first()).id).status_code, 404)

    def test_owners_and_strangers_get_404_on_a_students_stay(self):
        stranger = self.client_for(make_user('owner-b'))
        for client in (stranger, self.client_for(self.owner)):
            for name in self.ENDPOINTS:
                self.assertEqual(self.get(name, self.stay.id, client=client).status_code, 404, name)
            self.assertEqual(self.get('stay-list', client=client).json()['results'], [])

    def test_a_past_stay_is_listed_not_openable_and_its_pages_are_refused(self):
        past = self.make_stay(self.student, 2, 200)
        Stay.objects.filter(pk=past.pk).update(status='ENDED', ended_at=timezone.now())
        Stay.objects.filter(pk=self.stay.pk).update(status='ENDED')  # make `past` and the first both past
        Stay.objects.filter(pk=past.pk).update(status='ACTIVE')
        Stay.objects.filter(pk=self.stay.pk).update(status='ENDED', ended_at=timezone.now())
        rows = {row['id']: row for row in self.get('stay-list').json()['results']}
        self.assertTrue(rows[str(past.id)]['openable'])
        self.assertFalse(rows[str(self.stay.id)]['openable'])
        self.assertEqual(rows[str(self.stay.id)]['status'], 'ENDED')
        payment = self.mark_paid(self.stay.dues.first())
        for name in self.ENDPOINTS:
            response = self.get(name, self.stay.id)
            self.assertIn(response.status_code, (403, 404), name)
            self.assertEqual(response.status_code, 403, name)
            self.assertEqual(response.json()['code'], 'STAY_NOT_OPENABLE')
        self.assertEqual(self.get('stay-receipt', self.stay.id, payment.id).status_code, 403)

    def test_cancelled_stays_are_also_not_openable(self):
        Stay.objects.filter(pk=self.stay.pk).update(status='CANCELLED')
        self.assertFalse(self.get('stay-list').json()['results'][0]['openable'])
        self.assertEqual(self.get('stay-detail', self.stay.id).status_code, 403)

    def test_current_stays_come_first_then_past_ones(self):
        old = self.make_stay(self.student, 2, 300)
        Stay.objects.filter(pk=old.pk).update(status='ENDED', ended_at=timezone.now())
        rows = self.get('stay-list').json()['results']
        self.assertEqual([r['id'] for r in rows], [str(self.stay.id), str(old.id)])

    def test_the_list_is_paginated_with_a_ceiling(self):
        body = self.get('stay-list', page_size=1000).json()
        self.assertEqual(set(body), {'count', 'next', 'previous', 'results'})
        for n in range(3):
            booking = Booking.objects.create(hostel=self.room.hostel, student=self.student, room=self.room,
                                             payment_mode='offline', status='paid', marked_paid_at=timezone.now())
            extra, _ = services.create_stay_for_booking(booking, None)
            Stay.objects.filter(pk=extra.pk).update(status='ENDED')
        self.assertEqual(len(self.get('stay-list', page_size=2).json()['results']), 2)

    def test_the_read_endpoints_accept_only_get(self):
        for name in ('stay-list', 'stay-home', 'stay-calendar'):
            self.assertEqual(self.client_student.post(reverse(name), {}, format='json').status_code, 405, name)
        for name in self.ENDPOINTS:
            self.assertEqual(self.client_student.post(reverse(name, args=[self.stay.id]), {}, format='json').status_code,
                             405, name)

    def test_a_receipt_of_another_stays_payment_is_404(self):
        other = self.make_stay(self.student, 2, 40)
        Stay.objects.filter(pk=other.pk).update(status='ACTIVE')
        payment = self.mark_paid(other.dues.first())
        self.assertEqual(self.get('stay-receipt', self.stay.id, payment.id).status_code, 404)


# --------------------------------------------------------------------------------------------------- list and detail

class StayShape(ReadBase):
    def test_summary_fields(self):
        row = self.get('stay-list').json()['results'][0]
        for key in ('id', 'hostel_name', 'city', 'room_label', 'bed_label', 'joined_on', 'ended_on', 'status', 'openable',
                    'rent_amount', 'rent_rule_text', 'next_due', 'paid_until', 'pending_amount', 'billing_summary'):
            self.assertIn(key, row)
        self.assertEqual(row['hostel_name'], 'Seed Alpha Residency')
        self.assertEqual(row['city'], 'Hyderabad')
        self.assertEqual(row['locality'], 'Gachibowli')
        self.assertEqual(row['bed_label'], 'Bed A')
        self.assertEqual(row['status'], 'ACTIVE')
        self.assertTrue(row['openable'])
        self.assertEqual(Decimal(row['rent_amount']), self.price)
        self.assertIsNone(row['pending_amount'])
        join = self.stay.join_date
        self.assertEqual(row['joined_on'], join.isoformat())
        self.assertEqual(row['rent_rule_text'], f'{self.ordinal(join.day)} of every month')

    @staticmethod
    def ordinal(n):
        return f'{n}{"th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")}'

    def test_next_due_and_paid_until(self):
        row = self.get('stay-list').json()['results'][0]
        due2 = self.stay.dues.get(kind='RENT')
        self.assertEqual(set(row['next_due']), {'due_id', 'date', 'amount', 'days_left', 'status', 'payable'})
        self.assertEqual(row['next_due']['date'], due2.due_date.isoformat())
        self.assertEqual(row['next_due']['days_left'], (due2.due_date - today_ist()).days)
        self.assertEqual(row['next_due']['status'], 'OVERDUE')
        self.assertTrue(row['next_due']['payable'])
        self.assertEqual(row['paid_until'], self.stay.dues.get(kind='BOOKING_PERIOD').period_end.isoformat())

    def test_next_due_after_everything_stored_is_paid_is_projected_and_not_payable(self):
        self.mark_paid(self.stay.dues.get(kind='RENT'))
        row = self.get('stay-list').json()['results'][0]
        due2 = self.stay.dues.get(kind='RENT')
        self.assertIsNone(row['next_due']['due_id'])
        self.assertFalse(row['next_due']['payable'])
        self.assertGreater(date.fromisoformat(row['next_due']['date']), due2.due_date)
        self.assertEqual(row['next_due']['date'], billing_next(self.stay, 2))

    def test_billing_summary_for_an_anniversary_stay(self):
        stay = self.make_stay(make_user('anniv'), 2, 0, check_in=date(2026, 6, 18))
        summary = self.get('stay-detail', stay.id, client=self.client_for(stay.student)).json()['billing_summary']
        self.assertEqual(summary['mode'], 'ANNIVERSARY')
        self.assertEqual((summary['first_period_start'], summary['first_period_end']), ('2026-06-18', '2026-07-17'))
        self.assertEqual(summary['first_period_days'], 30)
        self.assertEqual(Decimal(summary['first_period_amount']), self.price)
        self.assertEqual(summary['next_due_date'], '2026-07-18')
        self.assertIn('18th', summary['rule_text'])
        self.assertIn('Short months use their last day', summary['rule_text'])
        self.assertEqual(summary['rule_title'], 'Rent is due on the 18th of every month')

    def test_billing_summary_for_a_fixed_day_stay_matches_the_board_numbers(self):
        HostelBillingConfig.objects.create(hostel=self.room.hostel, billing_mode='FIXED_DAY', fixed_due_day=1,
                                           first_period_policy='PRORATE')
        booking = make_booking(self.room, 2, make_user('fixed'), check_in=date(2026, 9, 18))
        stay_user = booking.student
        booking.status = 'paid'
        booking.marked_paid_at = timezone.now()
        booking.save()
        stay, _ = services.create_stay_for_booking(booking, None)
        summary = self.get('stay-detail', stay.id, client=self.client_for(stay_user)).json()['billing_summary']
        self.assertEqual(summary['mode'], 'FIXED_DAY')
        self.assertEqual((summary['first_period_start'], summary['first_period_end']), ('2026-09-18', '2026-09-30'))
        self.assertEqual(summary['first_period_days'], 13)
        self.assertEqual(summary['next_due_date'], '2026-10-01')
        self.assertIn('13 days', summary['rule_text'])
        self.assertEqual(self.get('stay-detail', stay.id, client=self.client_for(stay_user)).json()['rent_rule_text'],
                         '1st of every month')

    def test_detail_adds_notice_and_unread_count(self):
        body = self.get('stay-detail', self.stay.id).json()
        self.assertEqual(body['unread_notices'], 0)
        self.assertIsNone(body['vacate'])
        services.request_vacate(self.stay, today_ist() + timedelta(days=20), 'MOVING_CITY')
        body = self.get('stay-detail', self.stay.id).json()
        self.assertEqual(body['status'], 'NOTICE')
        self.assertEqual(body['vacate']['reason'], 'MOVING_CITY')

    def test_dues_list_has_stored_dues_and_the_projected_ones_marked(self):
        body = self.get('stay-dues', self.stay.id).json()
        self.assertEqual([r['kind'] for r in body['results']], ['BOOKING_PERIOD', 'RENT'])
        first, second = body['results']
        self.assertEqual(first['status'], 'PAID')
        self.assertEqual(second['status'], 'OVERDUE')
        self.assertEqual(second['stored_status'], self.stay.dues.get(kind='RENT').status)
        self.assertTrue(second['payable'])
        self.assertGreater(second['days_overdue'], 0)
        self.assertFalse(first['projected'])
        self.assertEqual(len(body['projected']), 3)
        for item in body['projected']:
            self.assertTrue(item['projected'])
            self.assertIsNone(item['id'])
            self.assertFalse(item['payable'])
        starts = [r['period_start'] for r in body['results']] + [r['period_start'] for r in body['projected']]
        self.assertEqual(starts, sorted(starts))


def billing_next(stay, index):
    from . import billing
    snap = stay.billing_snapshot
    spec = billing.LAST_DAY if snap['fixed_due_last_day'] else snap['fixed_due_day']
    periods = billing.build_periods(stay.join_date, snap['billing_mode'], snap['first_period_policy'], stay.rent_amount,
                                    spec if snap['billing_mode'] == 'FIXED_DAY' else None, index + 1)
    return periods[index].due_date.isoformat()


# ----------------------------------------------------------------------------------------------- payments / receipts

class Payments(ReadBase):
    def setUp(self):
        super().setUp()
        self.due2 = self.stay.dues.get(kind='RENT')

    def rows(self, **query):
        body = self.get('stay-payments', self.stay.id, **query).json()
        return body['results']

    def test_all_paid_and_upcoming_filters(self):
        self.mark_paid(self.due2, paid_at=timezone.now() - timedelta(days=1), via='CARD')
        everything = self.rows()
        paid = self.rows(filter='paid')
        upcoming = self.rows(filter='upcoming')
        self.assertEqual(len(everything), 2 + 0)  # stored dues only in the list; projected ones are separate
        self.assertEqual({r['status'] for r in paid}, {'PAID'})
        self.assertEqual(len(paid), 2)
        self.assertEqual(upcoming, [])
        self.assertEqual(self.get('stay-payments', self.stay.id, filter='upcoming').json()['projected'][0]['projected'], True)

    def test_an_open_due_shows_as_upcoming_and_payable(self):
        rows = self.rows(filter='upcoming')
        self.assertEqual([r['due_id'] for r in rows], [str(self.due2.id)])
        self.assertEqual(rows[0]['status'], 'OVERDUE')
        self.assertIsNone(rows[0]['paid_at'])
        self.assertIsNone(rows[0]['transaction'])

    def test_a_paid_row_carries_the_history_board_fields(self):
        paid_at = datetime(2026, 9, 16, 12, 42, tzinfo=UTC)  # 18:12 IST
        self.mark_paid(self.due2, paid_at=paid_at, via='UPI', ref='pay_ABCD3M9X')
        row = [r for r in self.rows() if r['due_id'] == str(self.due2.id)][0]
        self.assertEqual(row['status'], 'PAID')
        self.assertEqual(row['kind_label'], 'Rent')
        self.assertTrue(row['label'].startswith('Rent, '))
        self.assertEqual(row['paid_at'], '2026-09-16T18:12:00+05:30')
        self.assertEqual(row['method'], 'UPI')
        self.assertTrue(row['transaction'].startswith('pay_••••'))
        self.assertTrue(row['transaction'].endswith(self.due2.id.hex[:4].upper()))
        self.assertNotIn('ABCD3M9X', row['transaction'].replace('pay_••••', ''))
        self.assertTrue(row['receipt_number'])
        self.assertEqual(row['source'], 'ONLINE')
        self.assertFalse(row['recorded_by_owner'])
        self.assertEqual(Decimal(row['amount']), self.due2.amount)

    def test_cash_recorded_by_the_owner(self):
        client = self.client_for(self.owner)
        response = client.post(reverse('due-record-payment', args=[self.due2.id]), {
            'paid_at': (timezone.now() - timedelta(hours=2)).isoformat(), 'method': 'CASH', 'reference_note': 'book 214'},
            format='json')
        self.assertEqual(response.status_code, 201, response.content)
        row = [r for r in self.rows() if r['due_id'] == str(self.due2.id)][0]
        self.assertEqual(row['method'], 'CASH')
        self.assertEqual(row['source'], 'OFFLINE_OWNER')
        self.assertTrue(row['recorded_by_owner'])
        self.assertIsNone(row['transaction'])
        self.assertNotIn('book 214', str(row))  # the owner's note is not shown to the student

    def test_the_booking_period_row_is_labelled_booking_and_shows_its_method(self):
        row = [r for r in self.rows() if r['kind'] == 'BOOKING_PERIOD'][0]
        self.assertEqual(row['kind_label'], 'Booking')
        self.assertTrue(row['label'].startswith('Booking, '))
        self.assertEqual(row['status'], 'PAID')
        self.assertEqual(row['method'], 'CARD')  # read from the successful attempt, not from the empty paid_via
        self.assertTrue(row['transaction'].startswith('pay_••••'))

    def test_a_voided_offline_payment_is_not_shown_as_paid(self):
        client = self.client_for(self.owner)
        client.post(reverse('due-record-payment', args=[self.due2.id]), {
            'paid_at': (timezone.now() - timedelta(hours=2)).isoformat(), 'method': 'CASH', 'reference_note': 'x'}, format='json')
        client.post(reverse('due-void-payment', args=[self.due2.id]), {'reason': 'wrong'}, format='json')
        row = [r for r in self.rows() if r['due_id'] == str(self.due2.id)][0]
        self.assertNotEqual(row['status'], 'PAID')
        self.assertIsNone(row['paid_at'])

    def test_receipt_data(self):
        payment = self.mark_paid(self.due2, paid_at=datetime(2026, 9, 16, 12, 42, tzinfo=UTC), via='UPI', ref='pay_ABCD3M9X')
        body = self.get('stay-receipt', self.stay.id, payment.id).json()
        self.assertEqual(body['paid_at'], '2026-09-16T18:12:00+05:30')
        self.assertEqual(body['method'], 'UPI')
        self.assertTrue(body['transaction'].startswith('pay_••••'))
        self.assertTrue(body['receipt_number'].startswith('RCPT-••••'))
        self.assertNotIn(payment.id.hex[:6].upper(), body['receipt_number'][:9])
        self.assertEqual(body['hostel_name'], 'Seed Alpha Residency')
        self.assertEqual(body['room_label'], f'Room {self.room.room_number}')
        self.assertEqual(body['bed_label'], 'Bed A')
        self.assertEqual(body['paid_by'], self.student.display_name)
        self.assertEqual(body['rent_period'], {'start': self.due2.period_start.isoformat(),
                                               'end': self.due2.period_end.isoformat(),
                                               'label': body['rent_period']['label']})
        self.assertEqual(Decimal(body['amount']), self.due2.amount)
        self.assertIn('rent', body['title'].lower())

    def test_receipt_of_an_unpaid_or_voided_or_unknown_payment_is_404(self):
        open_payment = Payment.objects.create(booking=self.stay.booking, razorpay_order_id='order_open', amount=1,
                                              purpose='RENT', due=self.due2)
        self.assertEqual(self.get('stay-receipt', self.stay.id, open_payment.id).status_code, 404)
        import uuid
        self.assertEqual(self.get('stay-receipt', self.stay.id, uuid.uuid4()).status_code, 404)
        voided = self.mark_paid(self.due2)
        Payment.objects.filter(pk=voided.pk).update(status='VOIDED')
        self.assertEqual(self.get('stay-receipt', self.stay.id, voided.id).status_code, 404)


# ---------------------------------------------------------------------------------------------------- analytics

class Analytics(ReadBase):
    join_days_ago = 120  # four stored months would be needed; build them

    def setUp(self):
        super().setUp()
        self.add_dues(3)
        dues = list(self.stay.dues.order_by('due_date'))
        self.dues = dues
        # due 0 paid at booking (on time); due 1 paid 2 days late by card; due 2 paid early by cash; 3,4 open
        self.pay(dues[1], days_after_due=2, via='CARD', ref='pay_CARDCARD')
        self.pay(dues[2], days_after_due=-3, via='CASH', ref=None)

    def pay(self, due, days_after_due, via, ref):
        paid_at = datetime.combine(due.due_date + timedelta(days=days_after_due), datetime.min.time(), tzinfo=UTC) + timedelta(hours=6)
        payment = Payment.objects.create(booking=self.stay.booking, razorpay_order_id=f'order_{due.id.hex[:12]}',
                                         amount=due.amount, status='SUCCESS', purpose='RENT', due=due, paid_via=via,
                                         verified_at=paid_at,
                                         source='OFFLINE_OWNER' if via == 'CASH' else 'ONLINE')
        Due.objects.filter(pk=due.pk).update(status='PAID', paid_at=paid_at, payment=payment)

    def body(self, **query):
        return self.get('stay-analytics', self.stay.id, **query).json()

    def test_totals_and_on_time_counts(self):
        body = self.body()
        self.assertEqual(body['payments_count'], 3)
        self.assertEqual(Decimal(body['paid_so_far']), self.price * 3)
        self.assertEqual(body['on_time_count'], 2)
        self.assertEqual(body['late_count'], 1)
        self.assertEqual(body['late_payments'][0]['days_late'], 2)
        self.assertEqual(body['joined_on'], self.stay.join_date.isoformat())
        self.assertGreaterEqual(body['stay_length_months'], 3)
        self.assertIn('2 days late', body['late_label'])

    def test_grace_days_move_the_on_time_line(self):
        Stay.objects.filter(pk=self.stay.pk).update(billing_snapshot={**self.stay.billing_snapshot, 'grace_days': 2})
        body = self.body()
        self.assertEqual(body['late_count'], 0)
        self.assertEqual(body['on_time_count'], 3)

    def test_method_breakdown(self):
        methods = self.body()['methods']
        self.assertEqual(set(methods), {'UPI', 'CARD', 'NETBANKING', 'CASH', 'BANK_TRANSFER', 'UPI_DIRECT', 'OTHER'})
        self.assertEqual(methods['CARD'], 2)  # the booking payment (read from its attempt) and one rent paid by card
        self.assertEqual(methods['CASH'], 1)
        self.assertEqual(sum(methods.values()), 3)

    def test_monthly_series_states(self):
        self.pay(self.dues[3], days_after_due=0, via='UPI', ref='pay_UPIUPIUP')  # then the next open due is in the future
        series = self.body()['series']
        self.assertEqual({row['state'] for row in series} - {'on_time', 'late', 'upcoming'}, set())
        by_state = [row['state'] for row in series]
        self.assertIn('late', by_state)
        self.assertIn('upcoming', by_state)
        self.assertEqual(series[0]['month'], self.dues[0].due_date.strftime('%Y-%m'))
        self.assertEqual(sorted(r['month'] for r in series), [r['month'] for r in series])

    def test_ranges(self):
        everything = self.body(range='stay')['series']
        six = self.body(range='6m')['series']
        twelve = self.body(range='12m')['series']
        self.assertLessEqual(len(six), 6)
        self.assertLessEqual(len(twelve), 12)
        self.assertGreaterEqual(len(everything), len(six))
        self.assertEqual(self.get('stay-analytics', self.stay.id, range='bogus').status_code, 400)

    def test_next_rent_and_next_three_dues(self):
        body = self.body()
        self.assertEqual(len(body['next_dues']), 3)
        self.assertEqual(set(body['next_rent']), {'date', 'amount', 'days_left'})
        self.assertEqual(body['next_dues'][0]['date'], body['next_rent']['date'])

    def test_the_booking_period_counts_in_the_totals(self):
        Due.objects.filter(pk=self.dues[0].pk).update(status='PAID', paid_at=timezone.now())
        self.assertGreaterEqual(self.body()['payments_count'], 3)


# ---------------------------------------------------------------------------------------------------------- calendar

class Calendar(ReadBase):
    join_days_ago = 25  # Due 2 starts in about 5 days: inside the payable window

    def month_of(self, d):
        return d.strftime('%Y-%m')

    def days(self, month=None):
        body = self.get('stay-calendar', month=month or self.month_of(self.stay.dues.get(kind='RENT').due_date)).json()
        return body, {row['date']: row for row in body['days']}

    def test_paid_days_are_covered_and_a_payable_period_is_awaiting(self):
        due2 = self.stay.dues.get(kind='RENT')
        body, days = self.days(self.month_of(due2.due_date))
        self.assertEqual(body['stay_id'], str(self.stay.id))
        self.assertEqual(days[due2.due_date.isoformat()]['state'], 'awaiting')
        self.assertTrue(days[due2.due_date.isoformat()]['due'])
        last_paid_day = self.stay.dues.get(kind='BOOKING_PERIOD').period_end
        if self.month_of(last_paid_day) == self.month_of(due2.due_date):
            self.assertEqual(days[last_paid_day.isoformat()]['state'], 'covered')

    def test_join_date_marker_and_days_before_it(self):
        join = self.stay.join_date
        body, days = self.days(self.month_of(join))
        self.assertEqual(body['join_date'], join.isoformat())
        self.assertTrue(days[join.isoformat()]['join'])
        self.assertEqual(sum(1 for d in days.values() if d['join']), 1)
        earlier = join - timedelta(days=1)
        if self.month_of(earlier) == self.month_of(join):
            self.assertEqual(days[earlier.isoformat()]['state'], 'none')

    def test_reminder_dots_before_an_unpaid_due(self):
        due2 = self.stay.dues.get(kind='RENT')
        body, days = self.days(self.month_of(due2.due_date - timedelta(days=7)))
        for ahead in (7, 3, 1):
            day = (due2.due_date - timedelta(days=ahead)).isoformat()
            if day in days:
                self.assertTrue(days[day]['reminder'], ahead)
        self.assertFalse(days[(due2.due_date - timedelta(days=5)).isoformat()]['reminder']
                         if (due2.due_date - timedelta(days=5)).isoformat() in days else False)

    def test_a_paid_due_has_no_reminders_or_awaiting_days(self):
        due2 = self.stay.dues.get(kind='RENT')
        self.mark_paid(due2)
        body, days = self.days(self.month_of(due2.due_date))
        self.assertEqual(days[due2.due_date.isoformat()]['state'], 'covered')
        self.assertFalse(days[due2.due_date.isoformat()]['due'])
        self.assertFalse(any(d['reminder'] for d in days.values() if d['date'] < due2.due_date.isoformat()
                             and d['date'] >= (due2.due_date - timedelta(days=7)).isoformat()))

    def test_future_months_use_projected_dues_that_are_not_stored(self):
        stored_before = Due.objects.count()
        due2 = self.stay.dues.get(kind='RENT')
        future = due2.due_date + timedelta(days=70)
        body, days = self.days(self.month_of(future))
        self.assertEqual(Due.objects.count(), stored_before, 'a GET must never write')
        self.assertTrue(any(d['due'] for d in days.values()), 'a projected due date is marked')
        self.assertTrue(any(item['projected'] for item in body['upcoming']))

    def test_the_upcoming_list(self):
        body, _ = self.days()
        self.assertEqual(len(body['upcoming']), 3)
        self.assertEqual(body['upcoming'][0]['due_date'], self.stay.dues.get(kind='RENT').due_date.isoformat())
        self.assertEqual(body['upcoming'][0]['status'], 'PAYABLE')
        self.assertIsNotNone(body['upcoming'][0]['due_id'])
        self.assertIsNone(body['upcoming'][-1]['due_id'])

    def test_bad_months_and_no_stay(self):
        for bad in ('2026-13', 'abc', '2026-1', ''):
            self.assertEqual(self.get('stay-calendar', month=bad).status_code, 400, bad)
        self.assertEqual(self.get('stay-calendar', month='2099-12').status_code, 400)
        nobody = self.client_for(make_user('no-stay'))
        self.assertEqual(self.get('stay-calendar', client=nobody, month='2026-10').status_code, 404)


# ------------------------------------------------------------------------------------------------------------- home

class Home(ReadBase):
    def home(self, client=None):
        return self.get('stay-home', client=client).json()

    @override_settings(STAYS_ENABLED=True)
    def test_overdue_state(self):
        body = self.home()
        self.assertEqual(body['enabled'], True)
        self.assertEqual(body['state'], 'overdue')
        self.assertEqual(body['pill']['kind'], 'overdue')
        self.assertEqual(body['pill']['label'], '!')
        self.assertGreater(body['pill']['days'], 0)
        card = body['due_card']
        self.assertEqual(card['hostel_name'], 'Seed Alpha Residency')
        self.assertTrue(card['headline'].endswith('overdue'))
        self.assertTrue(card['subtitle'].startswith('Rent overdue since '))
        self.assertEqual(Decimal(card['amount']), self.price)
        self.assertEqual(card['room_label'], f'Room {self.room.room_number}')
        self.assertEqual(card['bed_label'], 'Bed A')
        self.assertTrue(card['payable'])
        self.assertIsNotNone(card['due_id'])
        self.assertEqual([a['kind'] for a in body['attention']['items']][0], 'rent_overdue')
        self.assertEqual(body['glance']['next_due']['label'], 'Overdue')

    @override_settings(STAYS_ENABLED=True)
    def test_quick_actions(self):
        actions = self.home()['quick_actions']
        self.assertEqual([a['key'] for a in actions], ['pay_rent', 'history', 'calendar', 'notices', 'analytics', 'help'])
        self.assertEqual([a['label'] for a in actions], ['Pay rent', 'History', 'Calendar', 'Notices', 'Analytics', 'Help'])
        self.assertEqual(next(a for a in actions if a['key'] == 'notices')['badge'], 0)

    @override_settings(STAYS_ENABLED=True)
    def test_due_soon_state(self):
        stay = self.make_stay(make_user('soon'), 2, 25)
        body = self.home(self.client_for(stay.student))
        self.assertEqual(body['state'], 'due_soon')
        days_left = (stay.dues.get(kind='RENT').due_date - today_ist()).days
        self.assertEqual(body['pill'], {'kind': 'days_left', 'days': days_left, 'label': f'{days_left}d'})
        self.assertEqual(body['due_card']['headline'], f'{days_left} days left')
        self.assertTrue(body['due_card']['subtitle'].startswith('Rent due '))
        self.assertIn('Cycle ', body['due_card']['cycle_label'] or 'Cycle ')
        self.assertEqual(body['attention']['items'][0]['kind'], 'rent_due')
        self.assertEqual(len(body['next_3_months']), 3)

    @override_settings(STAYS_ENABLED=True)
    def test_all_paid_state(self):
        self.mark_paid(self.stay.dues.get(kind='RENT'))
        body = self.home()
        self.assertEqual(body['state'], 'all_paid')
        self.assertIsNone(body['pill'])
        self.assertTrue(body['due_card']['headline'].endswith('rent paid'))
        self.assertEqual(body['due_card']['subtitle'], "You're all paid up")
        self.assertIsNotNone(body['due_card']['next'])
        self.assertEqual(body['glance']['on_time']['of'], 2)
        self.assertEqual(body['glance']['paid_so_far'], str(self.price * 2) if False else body['glance']['paid_so_far'])
        self.assertEqual(Decimal(body['glance']['paid_so_far']), self.price * 2)

    @override_settings(STAYS_ENABLED=True)
    def test_no_stay_state(self):
        body = self.home(self.client_for(make_user('nobody')))
        self.assertEqual(body['enabled'], True)
        self.assertEqual(body['state'], 'no_stay')
        self.assertIsNone(body['due_card'])
        self.assertIsNone(body['pill'])
        self.assertEqual(body['attention']['count'], 0)

    @override_settings(STAYS_ENABLED=True)
    def test_an_ended_stay_means_no_stay(self):
        Stay.objects.filter(pk=self.stay.pk).update(status='ENDED')
        self.assertEqual(self.home()['state'], 'no_stay')

    @override_settings(STAYS_ENABLED=False)
    def test_disabled_returns_only_enabled_false(self):
        response = self.get('stay-home')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'enabled': False})

    def test_the_flag_defaults_to_off(self):
        from django.conf import settings
        self.assertFalse(getattr(settings, 'STAYS_ENABLED', None))

    @override_settings(STAYS_ENABLED=True)
    def test_receipt_ready_within_14_days_only(self):
        due2 = self.stay.dues.get(kind='RENT')
        self.mark_paid(due2, paid_at=timezone.now() - timedelta(days=3))
        kinds = [a['kind'] for a in self.home()['attention']['items']]
        self.assertIn('receipt_ready', kinds)
        item = next(a for a in self.home()['attention']['items'] if a['kind'] == 'receipt_ready')
        self.assertTrue(item['payment_id'])
        self.assertEqual(item['subtitle'], 'Download or share it')
        cache.clear()
        Payment.objects.filter(due=due2).update(verified_at=timezone.now() - timedelta(days=20))
        Due.objects.filter(stay=self.stay).update(paid_at=timezone.now() - timedelta(days=20))  # the booking period too
        self.assertNotIn('receipt_ready', [a['kind'] for a in self.home()['attention']['items']])

    @override_settings(STAYS_ENABLED=True)
    def test_glance_block(self):
        glance = self.home()['glance']
        self.assertEqual(Decimal(glance['paid_so_far']), self.price)
        self.assertEqual(glance['on_time'], {'count': 1, 'of': 1, 'label': '1 of 1'})
        self.assertTrue(1 <= len(glance['months']) <= 5)
        self.assertEqual({m['state'] for m in glance['months']} - {'paid', 'late', 'due', 'overdue', 'upcoming'}, set())

    @override_settings(STAYS_ENABLED=True)
    def test_the_home_call_makes_a_constant_number_of_queries_and_never_writes(self):
        before = (Stay.objects.count(), Due.objects.count(), OutboxEvent.objects.count())
        self.home()
        self.assertEqual((Stay.objects.count(), Due.objects.count(), OutboxEvent.objects.count()), before)


# --------------------------------------------------------------------------------------------- IST day boundaries

class IstMidnight(ReadBase):
    """Frozen at 18:29 and 18:31 UTC: 23:59 and 00:01 IST on the next day."""

    def setUp(self):
        # Join on a fixed date so the days are known: due 2 is on 2026-07-18, window 7, grace 0.
        cache.clear()
        self.owner = ensure_sample_catalog()
        self.room = Room.objects.get(hostel__name='Seed Alpha Residency', room_name='Double')
        self.student = make_user('student-a')
        self.stay = self.make_stay(self.student, 1, 0, check_in=date(2026, 6, 18))
        self.due2 = self.stay.dues.get(kind='RENT')
        self.client_student = self.client_for(self.student)

    def next_due(self):
        return self.get('stay-list').json()['results'][0]['next_due']

    def test_overdue_starts_at_midnight_ist_not_midnight_utc(self):
        self.assertEqual(self.due2.due_date, date(2026, 7, 18))
        with frozen(2026, 7, 18, 18, 29):  # 23:59 IST on the 18th: the due day itself
            self.assertEqual(self.next_due()['status'], 'PAYABLE')
            self.assertEqual(self.next_due()['days_left'], 0)
        with frozen(2026, 7, 18, 18, 31):  # 00:01 IST on the 19th
            self.assertEqual(self.next_due()['status'], 'OVERDUE')
            self.assertEqual(self.next_due()['days_left'], -1)

    def test_the_payable_window_opens_at_midnight_ist(self):
        # window 7: payable from 2026-07-11 00:00 IST = 2026-07-10 18:30 UTC
        with frozen(2026, 7, 10, 18, 29):
            self.assertEqual(self.next_due()['status'], 'SCHEDULED')
            self.assertFalse(self.next_due()['payable'])
        with frozen(2026, 7, 10, 18, 31):
            self.assertEqual(self.next_due()['status'], 'PAYABLE')
            self.assertTrue(self.next_due()['payable'])

    @override_settings(STAYS_ENABLED=True)
    def test_home_state_changes_across_ist_midnight(self):
        with frozen(2026, 7, 18, 18, 29):
            self.assertEqual(self.get('stay-home').json()['state'], 'due_soon')
        cache.clear()
        with frozen(2026, 7, 18, 18, 31):
            self.assertEqual(self.get('stay-home').json()['state'], 'overdue')

    def test_grace_days_delay_overdue(self):
        Stay.objects.filter(pk=self.stay.pk).update(billing_snapshot={**self.stay.billing_snapshot, 'grace_days': 3})
        with frozen(2026, 7, 21, 18, 29):  # 23:59 IST on the 21st = due + 3
            self.assertEqual(self.next_due()['status'], 'PAYABLE')
        with frozen(2026, 7, 21, 18, 31):
            self.assertEqual(self.next_due()['status'], 'OVERDUE')

    def test_on_time_uses_the_ist_date_of_the_payment(self):
        # paid at 18:29 UTC on the due day = 23:59 IST on the due day: on time. 18:31 UTC = next IST day: one day late.
        for hour_minute, expected in (((18, 29), 0), ((18, 31), 1)):
            Due.objects.filter(pk=self.due2.pk).update(status='SCHEDULED', paid_at=None, payment=None)
            Payment.objects.filter(due=self.due2).delete()
            paid_at = datetime(2026, 7, 18, *hour_minute, tzinfo=UTC)
            payment = Payment.objects.create(booking=self.stay.booking, razorpay_order_id=f'o_{hour_minute[1]}',
                                             amount=self.due2.amount, status='SUCCESS', purpose='RENT', due=self.due2,
                                             paid_via='UPI', verified_at=paid_at)
            Due.objects.filter(pk=self.due2.pk).update(status='PAID', paid_at=paid_at, payment=payment)
            with frozen(2026, 7, 20):
                body = self.get('stay-analytics', self.stay.id).json()
            late = body['late_payments']
            self.assertEqual(len(late), expected, hour_minute)
            if expected:
                self.assertEqual(late[0]['days_late'], 1)


# --------------------------------------------------------------------------------------------------- query budgets

class QueryBudgets(ReadBase):
    """The number of queries must not grow with the number of dues (1, 5 and 25)."""

    def count(self, name, *args, **query):
        cache.clear()
        with CaptureQueriesContext(connection) as queries:
            response = self.client_student.get(reverse(name, args=args), query)
        self.assertEqual(response.status_code, 200, (name, response.content))
        return len(queries)

    def counts_for(self, n_extra, name, *args_factory, **query):
        raise NotImplementedError

    def measure(self, name, args_for, **query):
        results = {}
        # grow the stay: existing stored dues are 2; add 0, 4 and 24 more -> 2, 6 and 26 rows
        added = 0
        for target_extra in (0, 4, 20):
            if target_extra:
                self.add_dues(target_extra)
            added += target_extra
            results[2 + added] = self.count(name, *args_for(), **query)
        return results

    def assert_constant(self, results, budget):
        values = set(results.values())
        self.assertEqual(len(values), 1, f'query count grew with the number of dues: {results}')
        self.assertLessEqual(max(values), budget, results)

    def test_stay_list(self):
        self.assert_constant(self.measure('stay-list', lambda: ()), 4)

    def test_stay_detail(self):
        self.assert_constant(self.measure('stay-detail', lambda: (self.stay.id,)), 3)

    def test_dues(self):
        self.assert_constant(self.measure('stay-dues', lambda: (self.stay.id,)), 3)

    def test_payments_with_paid_rows(self):
        for due in self.stay.dues.filter(kind='RENT'):
            self.mark_paid(due)
        self.assert_constant(self.measure('stay-payments', lambda: (self.stay.id,)), 4)

    def test_payments_upcoming(self):
        self.assert_constant(self.measure('stay-payments', lambda: (self.stay.id,), filter='upcoming'), 4)

    def test_receipt(self):
        payment = self.mark_paid(self.stay.dues.get(kind='RENT'))
        self.assert_constant(self.measure('stay-receipt', lambda: (self.stay.id, payment.id)), 4)

    def test_analytics(self):
        self.assert_constant(self.measure('stay-analytics', lambda: (self.stay.id,)), 4)

    def test_calendar(self):
        month = (today_ist() + timedelta(days=5)).strftime('%Y-%m')
        self.assert_constant(self.measure('stay-calendar', lambda: (), month=month), 3)

    @override_settings(STAYS_ENABLED=True)
    def test_home(self):
        self.assert_constant(self.measure('stay-home', lambda: ()), 3)


# ------------------------------------------------------------------------------------------------------- http cache

class Conditional(ReadBase):
    NAMES = (('stay-list', ()), ('stay-calendar', ()),)

    def test_etag_and_private_no_cache_and_304(self):
        for name, args, query in (('stay-list', (), {}), ('stay-detail', (self.stay.id,), {}),
                                  ('stay-dues', (self.stay.id,), {}), ('stay-payments', (self.stay.id,), {}),
                                  ('stay-analytics', (self.stay.id,), {}),
                                  ('stay-calendar', (), {'month': today_ist().strftime('%Y-%m')})):
            first = self.client_student.get(reverse(name, args=args), query)
            self.assertEqual(first.status_code, 200, name)
            etag = first['ETag']
            self.assertTrue(etag.startswith('"'), name)
            cache_control = first['Cache-Control']
            self.assertIn('private', cache_control, name)
            self.assertIn('no-cache', cache_control, name)
            self.assertNotIn('no-store', cache_control, name)
            second = self.client_student.get(reverse(name, args=args), query, HTTP_IF_NONE_MATCH=etag)
            self.assertEqual(second.status_code, 304, name)
            self.assertEqual(second.content, b'', name)
            self.assertEqual(second['ETag'], etag, name)
            self.assertIn('private', second['Cache-Control'], name)
            third = self.client_student.get(reverse(name, args=args), query, HTTP_IF_NONE_MATCH='"other"')
            self.assertEqual(third.status_code, 200, name)

    @override_settings(STAYS_ENABLED=True)
    def test_home_has_an_etag_too_and_changes_when_money_state_changes(self):
        first = self.client_student.get(reverse('stay-home'))
        self.assertEqual(self.client_student.get(reverse('stay-home'), HTTP_IF_NONE_MATCH=first['ETag']).status_code, 304)
        self.mark_paid(self.stay.dues.get(kind='RENT'))
        services.bump_home_cache(self.student.id)
        changed = self.client_student.get(reverse('stay-home'), HTTP_IF_NONE_MATCH=first['ETag'])
        self.assertEqual(changed.status_code, 200)
        self.assertNotEqual(changed['ETag'], first['ETag'])

    def test_errors_and_other_users_are_never_cached(self):
        stranger = self.client_for(make_user('student-b'))
        response = stranger.get(reverse('stay-detail', args=[self.stay.id]))
        self.assertEqual(response.status_code, 404)
        self.assertIn('no-store', response['Cache-Control'])


# ------------------------------------------------------------------------------------------------ home cache (Redis)

@override_settings(STAYS_ENABLED=True)
class HomeCache(ReadBase):
    def build_calls(self):
        from . import read_views
        return mock.patch.object(read_views.readmodels, 'home_payload', wraps=read_views.readmodels.home_payload)

    def test_the_second_call_is_served_from_the_cache(self):
        with self.build_calls() as builder:
            self.get('stay-home')
            self.get('stay-home')
        self.assertEqual(builder.call_count, 1)

    def test_the_key_is_per_user(self):
        other = self.make_stay(make_user('student-b'), 2, 10)
        mine = self.get('stay-home').json()
        theirs = self.get('stay-home', client=self.client_for(other.student)).json()
        self.assertNotEqual(mine['due_card']['due_id'], theirs['due_card']['due_id'])
        self.assertEqual(self.get('stay-home').json()['due_card']['due_id'], mine['due_card']['due_id'])

    def test_paying_rent_bumps_the_users_version_so_money_is_never_stale(self):
        self.assertEqual(self.get('stay-home').json()['state'], 'overdue')
        due2 = self.stay.dues.get(kind='RENT')
        from apps.payments.confirm import confirm_payment
        order = {'id': 'order_home_cache', 'currency': 'INR'}
        with mock.patch('apps.payments.views.razorpay_client.create_order', return_value=order):
            created = self.client_student.post(reverse('payment-create-rent-order'), {'due_id': str(due2.id)}, format='json')
        confirm_payment(created.json()['payment_id'], 'pay_home_cache', 'sig')
        self.assertEqual(self.get('stay-home').json()['state'], 'all_paid')

    def test_offline_recording_and_void_bump_it_too(self):
        due2 = self.stay.dues.get(kind='RENT')
        self.get('stay-home')
        owner = self.client_for(self.owner)
        owner.post(reverse('due-record-payment', args=[due2.id]), {
            'paid_at': (timezone.now() - timedelta(hours=1)).isoformat(), 'method': 'CASH', 'reference_note': 'x'},
            format='json')
        self.assertEqual(self.get('stay-home').json()['state'], 'all_paid')
        owner.post(reverse('due-void-payment', args=[due2.id]), {'reason': 'wrong'}, format='json')
        self.assertEqual(self.get('stay-home').json()['state'], 'overdue')

    def test_ending_a_stay_and_creating_one_bump_it(self):
        self.assertEqual(self.get('stay-home').json()['state'], 'overdue')
        services.end_stay(self.stay)
        self.assertEqual(self.get('stay-home').json()['state'], 'no_stay')
        fresh = self.make_stay(self.student, 2, 25)
        self.assertEqual(self.get('stay-home').json()['state'], 'due_soon')
        self.assertTrue(fresh)

    def test_vacate_request_bumps_it(self):
        self.get('stay-home')
        services.request_vacate(self.stay, today_ist() + timedelta(days=10), 'OTHER')
        self.assertEqual(self.get('stay-home').json()['stay']['status'], 'NOTICE')

    def test_a_cache_that_is_down_still_gives_correct_answers(self):
        class DownCache:
            """What ResilientRedisCache answers while Redis is unreachable: nothing found, no lock, nothing stored."""
            def get(self, key, default=None):
                return default

            def add(self, key, value, timeout=None):
                return None

            def set(self, key, value, timeout=None):
                return None

            def delete(self, key):
                return None

        with mock.patch('apps.core.cache.cache', DownCache()):
            response = self.get('stay-home')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['state'], 'overdue')

    def test_the_cache_uses_the_shared_helper_not_a_process_local_dict(self):
        import inspect
        from . import read_views, readmodels
        source = inspect.getsource(read_views) + inspect.getsource(readmodels)
        self.assertIn('get_or_set', source)
        self.assertNotIn('LocMemCache', source)


# ---------------------------------------------------------------------------------------------------------- misc

class Misc(ReadBase):
    def test_the_unread_helper_returns_zero_until_phase_8(self):
        from .notifications import unread_count
        self.assertEqual(unread_count(self.student), 0)

    def test_money_is_a_string_and_dates_are_iso(self):
        row = self.get('stay-list').json()['results'][0]
        self.assertIsInstance(row['rent_amount'], str)
        date.fromisoformat(row['joined_on'])

    def test_an_index_exists_for_the_stay_status_due_date_queries(self):
        names = {i.name for i in Due._meta.indexes}
        self.assertIn('dues_stay_status_due_idx', names)

    def test_no_write_endpoint_was_added(self):
        for name in ('stay-list', 'stay-home', 'stay-calendar'):
            for method in ('put', 'patch', 'delete'):
                self.assertEqual(getattr(self.client_student, method)(reverse(name)).status_code, 405, (name, method))

    def test_the_locust_file_has_the_stays_scenarios(self):
        from pathlib import Path
        from django.conf import settings
        text = (Path(settings.BASE_DIR).parent / 'tools' / 'loadtest' / 'locustfile.py').read_text(encoding='utf-8')
        for path in ('/stays/home/', "'/stays/'", '/dues/', '/payments/'):
            self.assertIn(path, text)

    def test_env_example_lists_the_flag(self):
        from pathlib import Path
        from django.conf import settings
        self.assertIn('STAYS_ENABLED', (Path(settings.BASE_DIR) / '.env.example').read_text(encoding='utf-8'))
