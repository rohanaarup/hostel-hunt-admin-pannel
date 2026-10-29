"""
Phase 4, Part 2: the pure billing engine (apps/stays/billing.py). No database, no Django, no clock.

Rules under test (decision D1, E8, E9):
  * ANNIVERSARY (default): due(n) = anchor + n months, day = min(anchor day, last day of that month). Never chained.
  * FIXED_DAY: a fixed due day 1 to 28, or the last day of the month, with first_period_policy PRORATE or FULL_MONTH.
  * PRORATE (pending founder confirmation, kept in ONE function): rent x days from the join date to the next fixed due day
    / days in the fixed period (previous fixed due day to next fixed due day) that contains the join date, rounded to the
    paisa with ROUND_HALF_UP.
  * payable window and overdue helpers take today and grace days as arguments and never read the clock.
"""
import re
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

from apps.stays import billing
from apps.stays.billing import (
    ANNIVERSARY, FIXED_DAY, FULL_MONTH, LAST_DAY, PRORATE,
    build_periods, days_overdue, days_until_due, due_date, effective_status, first_period, fixed_day_due_dates,
    is_overdue, is_payable, last_day_of_month, payable_from, previous_fixed_due, prorated_amount,
)

D = date
RENT = Decimal('6500.00')


class DueDateTests(unittest.TestCase):
    def test_31_january_anchor_follows_the_end_of_each_month(self):
        anchor = D(2026, 1, 31)
        self.assertEqual(due_date(anchor, 1), D(2026, 2, 28))
        self.assertEqual(due_date(anchor, 2), D(2026, 3, 31))
        self.assertEqual(due_date(anchor, 3), D(2026, 4, 30))
        self.assertEqual(due_date(anchor, 4), D(2026, 5, 31))

    def test_31_january_in_a_leap_year_gives_29_february(self):
        self.assertEqual(due_date(D(2028, 1, 31), 1), D(2028, 2, 29))

    def test_18_september_anchor_is_the_18th_every_month(self):
        anchor = D(2026, 9, 18)
        self.assertEqual(due_date(anchor, 1), D(2026, 10, 18))
        self.assertEqual(due_date(anchor, 2), D(2026, 11, 18))
        self.assertEqual(due_date(anchor, 3), D(2026, 12, 18))
        self.assertEqual(due_date(anchor, 4), D(2027, 1, 18))  # across a year end

    def test_n_zero_is_the_anchor_and_twelve_is_a_year_later(self):
        self.assertEqual(due_date(D(2026, 9, 18), 0), D(2026, 9, 18))
        self.assertEqual(due_date(D(2026, 9, 18), 12), D(2027, 9, 18))

    def test_29_february_anchor_survives_non_leap_years_and_returns_in_leap_years(self):
        anchor = D(2028, 2, 29)
        self.assertEqual(due_date(anchor, 12), D(2029, 2, 28))
        self.assertEqual(due_date(anchor, 48), D(2032, 2, 29))

    def test_dues_are_never_chained_from_the_previous_due(self):
        """Chaining 31 Jan -> 28 Feb -> 28 Mar would drift. The third due must be 31 March."""
        anchor = D(2026, 1, 31)
        chained = due_date(due_date(anchor, 1), 1)
        self.assertEqual(chained, D(2026, 3, 28))  # what chaining would give
        self.assertEqual(due_date(anchor, 2), D(2026, 3, 31))  # what the rule gives

    def test_the_day_is_always_the_anchor_day_or_the_last_day_of_the_month(self):
        for anchor in (D(2026, 1, 29), D(2026, 1, 30), D(2026, 1, 31), D(2026, 5, 31), D(2028, 2, 29), D(2026, 9, 18)):
            for n in range(0, 49):
                result = due_date(anchor, n)
                self.assertEqual(result.day, min(anchor.day, last_day_of_month(result.year, result.month)), (anchor, n))

    def test_consecutive_dues_are_strictly_increasing(self):
        for anchor in (D(2026, 1, 31), D(2026, 9, 18), D(2028, 2, 29)):
            dues = [due_date(anchor, n) for n in range(0, 60)]
            self.assertEqual(dues, sorted(set(dues)))

    def test_a_negative_count_is_refused(self):
        with self.assertRaises(ValueError):
            due_date(D(2026, 9, 18), -1)

    def test_only_plain_dates_are_accepted(self):
        with self.assertRaises(TypeError):
            due_date(datetime(2026, 9, 18, 10, 0), 1)  # a datetime would hide a time-zone mistake
        with self.assertRaises(TypeError):
            due_date('2026-09-18', 1)

    def test_last_day_of_month(self):
        self.assertEqual([last_day_of_month(2026, m) for m in (1, 2, 4)], [31, 28, 30])
        self.assertEqual(last_day_of_month(2028, 2), 29)
        self.assertEqual(last_day_of_month(2100, 2), 28)  # 2100 is not a leap year


class FixedDayDueDateTests(unittest.TestCase):
    def test_the_next_dues_after_a_date_for_a_fixed_day(self):
        self.assertEqual(fixed_day_due_dates(D(2026, 9, 18), 5, 3), [D(2026, 10, 5), D(2026, 11, 5), D(2026, 12, 5)])

    def test_a_date_on_the_fixed_day_starts_the_next_period_not_this_one(self):
        self.assertEqual(fixed_day_due_dates(D(2026, 9, 5), 5, 2), [D(2026, 10, 5), D(2026, 11, 5)])

    def test_day_one_and_day_28(self):
        self.assertEqual(fixed_day_due_dates(D(2026, 9, 18), 1, 2), [D(2026, 10, 1), D(2026, 11, 1)])
        self.assertEqual(fixed_day_due_dates(D(2026, 1, 28), 28, 2), [D(2026, 2, 28), D(2026, 3, 28)])

    def test_the_last_day_of_the_month(self):
        self.assertEqual(fixed_day_due_dates(D(2026, 1, 15), LAST_DAY, 3), [D(2026, 1, 31), D(2026, 2, 28), D(2026, 3, 31)])
        self.assertEqual(fixed_day_due_dates(D(2028, 1, 31), LAST_DAY, 2), [D(2028, 2, 29), D(2028, 3, 31)])

    def test_across_a_year_end(self):
        self.assertEqual(fixed_day_due_dates(D(2026, 12, 20), 10, 2), [D(2027, 1, 10), D(2027, 2, 10)])

    def test_the_previous_fixed_due_is_on_or_before_the_date(self):
        self.assertEqual(previous_fixed_due(D(2026, 9, 18), 5), D(2026, 9, 5))
        self.assertEqual(previous_fixed_due(D(2026, 9, 5), 5), D(2026, 9, 5))
        self.assertEqual(previous_fixed_due(D(2026, 9, 4), 5), D(2026, 8, 5))
        self.assertEqual(previous_fixed_due(D(2026, 1, 2), 5), D(2025, 12, 5))
        self.assertEqual(previous_fixed_due(D(2026, 3, 1), LAST_DAY), D(2026, 2, 28))
        self.assertEqual(previous_fixed_due(D(2026, 3, 31), LAST_DAY), D(2026, 3, 31))

    def test_a_day_outside_1_to_28_is_refused(self):
        for bad in (0, 29, 30, 31, -1, None, 5.0, '5', True):
            with self.assertRaises(ValueError, msg=repr(bad)):
                fixed_day_due_dates(D(2026, 9, 18), bad, 1)


class ProratedAmountTests(unittest.TestCase):
    def test_a_join_part_way_through_a_period(self):
        # period 5 Sep to 5 Oct = 30 days; 18 Sep to 5 Oct = 17 days; 6500 x 17 / 30 = 3683.333...
        self.assertEqual(prorated_amount(RENT, D(2026, 9, 18), 5), Decimal('3683.33'))

    def test_joining_on_the_fixed_day_is_a_whole_period(self):
        self.assertEqual(prorated_amount(RENT, D(2026, 9, 5), 5), Decimal('6500.00'))

    def test_joining_the_day_before_the_fixed_day_is_one_day(self):
        # the period holding 4 Sep runs 5 Aug to 5 Sep = 31 days, so one day is 3100 / 31 = 100.00
        self.assertEqual(prorated_amount(Decimal('3100.00'), D(2026, 9, 4), 5), Decimal('100.00'))
        self.assertEqual(prorated_amount(Decimal('3000.00'), D(2026, 9, 4), 5), Decimal('96.77'))  # 3000 / 31

    def test_the_period_length_is_the_real_one(self):
        # 1 Oct to 1 Nov = 31 days; 20 Oct to 1 Nov = 12 days; 3100 x 12 / 31 = 1200.00
        self.assertEqual(prorated_amount(Decimal('3100'), D(2026, 10, 20), 1), Decimal('1200.00'))

    def test_the_last_day_of_the_month_option(self):
        # period 31 Jan to 28 Feb = 28 days; 10 Feb to 28 Feb = 18 days; 3100 x 18 / 28 = 1992.857... -> 1992.86
        self.assertEqual(prorated_amount(Decimal('3100'), D(2026, 2, 10), LAST_DAY), Decimal('1992.86'))

    def test_a_half_paisa_rounds_up_not_to_even(self):
        # 30-day period (5 Sep to 5 Oct), 3 days left: 0.05 x 3 / 30 = 0.005 exactly. HALF_UP gives 0.01 (HALF_EVEN would give 0.00).
        self.assertEqual(prorated_amount(Decimal('0.05'), D(2026, 10, 2), 5), Decimal('0.01'))

    def test_the_result_has_exactly_two_decimal_places(self):
        self.assertEqual(prorated_amount(RENT, D(2026, 9, 18), 5).as_tuple().exponent, -2)
        self.assertEqual(prorated_amount(6500, D(2026, 9, 5), 5).as_tuple().exponent, -2)

    def test_whole_rupee_and_text_rent_are_accepted_but_floats_are_not(self):
        self.assertEqual(prorated_amount(6500, D(2026, 9, 5), 5), Decimal('6500.00'))
        self.assertEqual(prorated_amount('6500.00', D(2026, 9, 5), 5), Decimal('6500.00'))
        with self.assertRaises(TypeError):
            prorated_amount(6500.0, D(2026, 9, 18), 5)

    def test_a_negative_rent_is_refused_and_zero_gives_zero(self):
        with self.assertRaises(ValueError):
            prorated_amount(Decimal('-1'), D(2026, 9, 18), 5)
        self.assertEqual(prorated_amount(Decimal('0'), D(2026, 9, 18), 5), Decimal('0.00'))

    def test_it_is_never_more_than_the_rent_and_never_zero_for_any_join_date(self):
        start = D(2026, 1, 1)
        for fixed in (1, 5, 15, 28, LAST_DAY):
            for offset in range(0, 400):
                amount = prorated_amount(RENT, start + timedelta(days=offset), fixed)
                self.assertTrue(Decimal('0') < amount <= RENT, (fixed, offset, amount))

    def test_the_formula_lives_in_exactly_one_function(self):
        source = Path(billing.__file__).read_text(encoding='utf-8')
        self.assertEqual(len(re.findall(r'ROUND_HALF_UP', source.replace('import ROUND_HALF_UP', ''))), 1)
        self.assertIn('def prorated_amount(', source)


class FirstPeriodTests(unittest.TestCase):
    def test_anniversary_is_a_full_first_period(self):
        period = first_period(D(2026, 9, 18), ANNIVERSARY, None, RENT, None)
        self.assertEqual(period.start, D(2026, 9, 18))
        self.assertEqual(period.end, D(2026, 10, 17))
        self.assertEqual(period.amount, RENT)
        self.assertEqual(period.next_due, D(2026, 10, 18))

    def test_anniversary_ignores_the_fixed_day_and_the_policy(self):
        plain = first_period(D(2026, 9, 18), ANNIVERSARY, None, RENT, None)
        self.assertEqual(first_period(D(2026, 9, 18), ANNIVERSARY, PRORATE, RENT, 5), plain)

    def test_anniversary_from_the_31st(self):
        period = first_period(D(2026, 1, 31), ANNIVERSARY, None, RENT, None)
        self.assertEqual((period.end, period.next_due), (D(2026, 2, 27), D(2026, 2, 28)))

    def test_fixed_day_full_month_charges_a_whole_month_and_the_next_due_is_the_fixed_day(self):
        period = first_period(D(2026, 9, 18), FIXED_DAY, FULL_MONTH, RENT, 5)
        self.assertEqual(period.amount, RENT)
        self.assertEqual(period.start, D(2026, 9, 18))
        self.assertEqual(period.next_due, D(2026, 10, 5))
        self.assertEqual(period.end, D(2026, 10, 4))

    def test_fixed_day_prorate_charges_part_of_a_month(self):
        period = first_period(D(2026, 9, 18), FIXED_DAY, PRORATE, RENT, 5)
        self.assertEqual(period.amount, Decimal('3683.33'))
        self.assertLess(period.amount, RENT)
        self.assertEqual(period.next_due, D(2026, 10, 5))

    def test_the_proration_goes_through_the_one_function(self):
        with mock.patch.object(billing, 'prorated_amount', return_value=Decimal('1.23')) as one_place:
            period = first_period(D(2026, 9, 18), FIXED_DAY, PRORATE, RENT, 5)
        one_place.assert_called_once_with(RENT, D(2026, 9, 18), 5)
        self.assertEqual(period.amount, Decimal('1.23'))
        with mock.patch.object(billing, 'prorated_amount') as unused:
            first_period(D(2026, 9, 18), FIXED_DAY, FULL_MONTH, RENT, 5)
            first_period(D(2026, 9, 18), ANNIVERSARY, None, RENT, None)
        unused.assert_not_called()

    def test_joining_on_the_fixed_day_is_a_whole_period_for_either_policy(self):
        for policy in (PRORATE, FULL_MONTH):
            period = first_period(D(2026, 9, 5), FIXED_DAY, policy, RENT, 5)
            self.assertEqual((period.amount, period.start, period.next_due), (RENT, D(2026, 9, 5), D(2026, 10, 5)), policy)

    def test_fixed_last_day_of_month(self):
        period = first_period(D(2026, 2, 10), FIXED_DAY, FULL_MONTH, Decimal('3100'), LAST_DAY)
        self.assertEqual((period.amount, period.next_due), (Decimal('3100.00'), D(2026, 2, 28)))

    def test_bad_input_is_refused(self):
        with self.assertRaises(ValueError):
            first_period(D(2026, 9, 18), FIXED_DAY, FULL_MONTH, RENT, None)   # a fixed day is required
        with self.assertRaises(ValueError):
            first_period(D(2026, 9, 18), FIXED_DAY, None, RENT, 5)            # a policy is required
        with self.assertRaises(ValueError):
            first_period(D(2026, 9, 18), 'WEEKLY', None, RENT, None)
        with self.assertRaises(ValueError):
            first_period(D(2026, 9, 18), FIXED_DAY, 'HALF', RENT, 5)
        with self.assertRaises(ValueError):
            first_period(D(2026, 9, 18), ANNIVERSARY, None, Decimal('-1'), None)
        with self.assertRaises(TypeError):
            first_period(D(2026, 9, 18), ANNIVERSARY, None, 6500.0, None)

    def test_the_amount_is_a_two_place_decimal(self):
        self.assertEqual(first_period(D(2026, 9, 18), ANNIVERSARY, None, 6500, None).amount.as_tuple().exponent, -2)


class BuildPeriodsTests(unittest.TestCase):
    def test_anniversary_periods_follow_the_anchor_without_chaining(self):
        periods = build_periods(D(2026, 1, 31), ANNIVERSARY, None, RENT, None, 4)
        self.assertEqual([p.start for p in periods], [D(2026, 1, 31), D(2026, 2, 28), D(2026, 3, 31), D(2026, 4, 30)])
        self.assertEqual([p.end for p in periods], [D(2026, 2, 27), D(2026, 3, 30), D(2026, 4, 29), D(2026, 5, 30)])
        self.assertEqual({p.amount for p in periods}, {RENT})

    def test_periods_do_not_overlap_and_leave_no_gap(self):
        for args in ((D(2026, 1, 31), ANNIVERSARY, None, None), (D(2026, 9, 18), FIXED_DAY, PRORATE, 5),
                     (D(2026, 9, 18), FIXED_DAY, FULL_MONTH, LAST_DAY)):
            periods = build_periods(args[0], args[1], args[2], RENT, args[3], 14)
            for previous, following in zip(periods, periods[1:]):
                self.assertEqual(previous.end + timedelta(days=1), following.start, args)
                self.assertEqual(previous.next_due, following.start, args)

    def test_fixed_day_with_prorate_starts_with_a_part_month_then_whole_months(self):
        periods = build_periods(D(2026, 9, 18), FIXED_DAY, PRORATE, RENT, 5, 3)
        self.assertEqual([p.start for p in periods], [D(2026, 9, 18), D(2026, 10, 5), D(2026, 11, 5)])
        self.assertEqual([p.amount for p in periods], [Decimal('3683.33'), RENT, RENT])

    def test_fixed_day_with_full_month_charges_whole_months_throughout(self):
        periods = build_periods(D(2026, 9, 18), FIXED_DAY, FULL_MONTH, RENT, 5, 3)
        self.assertEqual([p.amount for p in periods], [RENT, RENT, RENT])

    def test_the_first_two_periods_are_what_a_paid_booking_needs(self):
        first, second = build_periods(D(2026, 9, 18), ANNIVERSARY, None, RENT, None, 2)
        self.assertEqual(first.due_date, D(2026, 9, 18))   # Due 1: the booking period
        self.assertEqual(second.due_date, D(2026, 10, 18))  # Due 2: the first rent

    def test_a_period_is_due_on_its_first_day(self):
        for period in build_periods(D(2026, 9, 18), FIXED_DAY, PRORATE, RENT, 5, 4):
            self.assertEqual(period.due_date, period.start)

    def test_a_count_below_one_is_refused(self):
        with self.assertRaises(ValueError):
            build_periods(D(2026, 9, 18), ANNIVERSARY, None, RENT, None, 0)


class PayableAndOverdueTests(unittest.TestCase):
    DUE = D(2026, 10, 18)

    def test_the_payable_window_opens_the_chosen_number_of_days_before_the_due_date(self):
        self.assertEqual(payable_from(self.DUE, 7), D(2026, 10, 11))
        self.assertFalse(is_payable(self.DUE, D(2026, 10, 10), 7))
        self.assertTrue(is_payable(self.DUE, D(2026, 10, 11), 7))
        self.assertTrue(is_payable(self.DUE, self.DUE, 7))

    def test_a_late_due_is_still_payable(self):
        self.assertTrue(is_payable(self.DUE, D(2026, 11, 30), 7))

    def test_a_zero_day_window_opens_on_the_due_date(self):
        self.assertFalse(is_payable(self.DUE, D(2026, 10, 17), 0))
        self.assertTrue(is_payable(self.DUE, self.DUE, 0))

    def test_overdue_starts_the_day_after_the_due_date_when_there_is_no_grace(self):
        self.assertFalse(is_overdue(self.DUE, self.DUE, 0))
        self.assertTrue(is_overdue(self.DUE, D(2026, 10, 19), 0))
        self.assertEqual(days_overdue(self.DUE, D(2026, 10, 19), 0), 1)
        self.assertEqual(days_overdue(self.DUE, D(2026, 10, 25), 0), 7)

    def test_grace_days_delay_the_overdue_state(self):
        self.assertFalse(is_overdue(self.DUE, D(2026, 10, 21), 3))
        self.assertTrue(is_overdue(self.DUE, D(2026, 10, 22), 3))
        self.assertEqual(days_overdue(self.DUE, D(2026, 10, 22), 3), 1)
        self.assertEqual(days_overdue(self.DUE, D(2026, 10, 20), 3), 0)

    def test_days_until_due_is_negative_after_the_date(self):
        self.assertEqual(days_until_due(self.DUE, D(2026, 10, 15)), 3)
        self.assertEqual(days_until_due(self.DUE, self.DUE), 0)
        self.assertEqual(days_until_due(self.DUE, D(2026, 10, 20)), -2)

    def test_the_effective_status_is_worked_out_from_the_dates(self):
        args = (self.DUE, 7, 0)
        self.assertEqual(effective_status('SCHEDULED', D(2026, 10, 1), *args), 'SCHEDULED')
        self.assertEqual(effective_status('SCHEDULED', D(2026, 10, 11), *args), 'PAYABLE')
        self.assertEqual(effective_status('PAYABLE', D(2026, 10, 18), *args), 'PAYABLE')
        self.assertEqual(effective_status('PAYABLE', D(2026, 10, 19), *args), 'OVERDUE')
        self.assertEqual(effective_status('SCHEDULED', D(2026, 12, 1), *args), 'OVERDUE')

    def test_finished_dues_are_never_overdue(self):
        for stored in ('PAID', 'WAIVED', 'CANCELLED'):
            self.assertEqual(effective_status(stored, D(2027, 1, 1), self.DUE, 7, 0), stored)

    def test_an_unknown_stored_status_is_refused(self):
        with self.assertRaises(ValueError):
            effective_status('OVERDUE', D(2026, 10, 1), self.DUE, 7, 0)  # overdue is never stored (E8)

    def test_negative_windows_and_grace_are_refused(self):
        with self.assertRaises(ValueError):
            payable_from(self.DUE, -1)
        with self.assertRaises(ValueError):
            is_overdue(self.DUE, self.DUE, -1)

    def test_today_must_be_passed_in(self):
        with self.assertRaises(TypeError):
            is_payable(self.DUE, window_days=7)  # no today
        with self.assertRaises(TypeError):
            is_overdue(self.DUE, grace_days=0)
        with self.assertRaises(TypeError):
            effective_status('SCHEDULED', due=self.DUE, window_days=7, grace_days=0)  # everything but today

    def test_the_engine_never_reads_the_clock(self):
        source = Path(billing.__file__).read_text(encoding='utf-8')
        for forbidden in (r'\.today\(', r'\.now\(', r'\.utcnow\(', r'\bimport time\b', r'time\.time\(', r'timezone'):
            self.assertIsNone(re.search(forbidden, source), forbidden)

    def test_the_engine_imports_no_django_and_no_other_app(self):
        source = Path(billing.__file__).read_text(encoding='utf-8')
        self.assertNotRegex(source, r'(?m)^\s*(from|import)\s+(django|apps|rest_framework)')
