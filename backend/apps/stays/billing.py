"""
The billing engine for stays: pure Python. No database, no Django, no other app, and no clock.

Every function takes the dates it needs as arguments (the caller passes `today`), so every result is reproducible and
testable. Amounts are Decimal rupees, never floats (a float is refused with TypeError).

Two billing rules (decision D1):

  ANNIVERSARY (the default). The join date is the anchor: joining on the 18th means paying on the 18th of each following
    month. due(n) = anchor + n months, with day = min(anchor day, last day of that month) (E9). Every due is computed
    from the anchor, never from the previous due: a 31 January anchor gives 28 February, 31 March, 30 April, 31 May,
    where chaining would drift to the 28th for ever.

  FIXED_DAY (rare, configured per hostel). Rent is due on a fixed day of the month, 1 to 28, or the LAST_DAY of the
    month. The first period starts on the join date and runs to the next fixed due day, under a first-period policy:
      FULL_MONTH  a whole month's rent is charged for that first (possibly short) period;
      PRORATE     only the part of the fixed period that is left is charged (see prorated_amount).

A Period covers `start` to `end` (both included) and is due on its first day: Due 1 of a booking is the period that
starts on the join date, Due 2 is the one that starts a month later. `next_due` is the first day of the following
period.

Everything about "how much is the first part-month" is in ONE function, prorated_amount. That rule is a proposal that
is still waiting for the founder's confirmation (docs/GAP_TRIAGE.md, FOUNDER_DEFERRED.md); if it changes, only that
function changes.
"""
import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext

ANNIVERSARY = 'ANNIVERSARY'
FIXED_DAY = 'FIXED_DAY'
BILLING_MODES = (ANNIVERSARY, FIXED_DAY)

PRORATE = 'PRORATE'
FULL_MONTH = 'FULL_MONTH'
FIRST_PERIOD_POLICIES = (PRORATE, FULL_MONTH)

LAST_DAY = 'LAST_DAY'  # the fixed due day "last day of the month"

# Due statuses. OVERDUE is derived when read (E8) and is never stored.
SCHEDULED, PAYABLE, OVERDUE = 'SCHEDULED', 'PAYABLE', 'OVERDUE'
PAID, WAIVED, CANCELLED = 'PAID', 'WAIVED', 'CANCELLED'
STORED_STATUSES = (SCHEDULED, PAYABLE, PAID, WAIVED, CANCELLED)
FINISHED_STATUSES = (PAID, WAIVED, CANCELLED)

_PAISA = Decimal('0.01')


@dataclass(frozen=True)
class Period:
    start: date
    end: date
    amount: Decimal
    next_due: date

    @property
    def due_date(self):
        """A period is due on its first day."""
        return self.start


# --------------------------------------------------------------------------------------------------- checks

def _check_date(value, name='date'):
    if not isinstance(value, date) or isinstance(value, datetime):
        raise TypeError(f'{name} must be a plain date (not a datetime or text)')
    return value


def _money(value):
    """Rent as an exact Decimal in whole paise. Floats are refused: they cannot hold rupees exactly."""
    if isinstance(value, (bool, float)):
        raise TypeError('an amount must be a Decimal, an int or a text number, never a float')
    amount = Decimal(value) if not isinstance(value, Decimal) else value
    if not amount.is_finite():
        raise ValueError('an amount must be a finite number')
    if amount < 0:
        raise ValueError('an amount cannot be negative')
    if amount != amount.quantize(_PAISA):
        raise ValueError('an amount must be in whole paise (two decimal places at most)')
    return amount.quantize(_PAISA)


def _check_fixed_day(day):
    if day == LAST_DAY and isinstance(day, str):
        return day
    if type(day) is int and 1 <= day <= 28:
        return day
    raise ValueError('the fixed due day must be a whole number from 1 to 28, or LAST_DAY')


def _check_mode(mode):
    if mode not in BILLING_MODES:
        raise ValueError(f'billing mode must be one of {BILLING_MODES}')
    return mode


# --------------------------------------------------------------------------------------------------- ANNIVERSARY

def last_day_of_month(year, month):
    return calendar.monthrange(year, month)[1]


def due_date(anchor, n):
    """anchor + n months, with day = min(anchor day, last day of that month). Computed from the anchor every time."""
    _check_date(anchor, 'anchor')
    if type(n) is not int:
        raise TypeError('n must be a whole number')
    if n < 0:
        raise ValueError('n cannot be negative')
    months = anchor.year * 12 + (anchor.month - 1) + n
    year, month = divmod(months, 12)
    month += 1
    return date(year, month, min(anchor.day, last_day_of_month(year, month)))


# --------------------------------------------------------------------------------------------------- FIXED_DAY

def _fixed_on(year, month, fixed_due_day):
    return date(year, month, last_day_of_month(year, month) if fixed_due_day == LAST_DAY else fixed_due_day)


def _step_month(year, month, by):
    months = year * 12 + (month - 1) + by
    year, month = divmod(months, 12)
    return year, month + 1


def fixed_day_due_dates(after, fixed_due_day, count):
    """The next `count` fixed due dates strictly AFTER `after`. A date that is itself a due day starts a new period,
    so the next due is a month later."""
    _check_date(after, 'after')
    _check_fixed_day(fixed_due_day)
    year, month = after.year, after.month
    if _fixed_on(year, month, fixed_due_day) <= after:
        year, month = _step_month(year, month, 1)
    dates = []
    for _ in range(count):
        dates.append(_fixed_on(year, month, fixed_due_day))
        year, month = _step_month(year, month, 1)
    return dates


def previous_fixed_due(on, fixed_due_day):
    """The latest fixed due date on or before `on`: the start of the fixed period that contains `on`."""
    _check_date(on, 'on')
    _check_fixed_day(fixed_due_day)
    candidate = _fixed_on(on.year, on.month, fixed_due_day)
    if candidate <= on:
        return candidate
    year, month = _step_month(on.year, on.month, -1)
    return _fixed_on(year, month, fixed_due_day)


def prorated_amount(rent, join_date, fixed_due_day):
    """THE proration rule, in one place (pending the founder's confirmation):

        rent x (days from the join date to the next fixed due day)
             / (days in the fixed period, previous fixed due day to next fixed due day, that contains the join date)

    rounded to the paisa, halves rounded up, with Decimal (never floats). Joining on a fixed due day is a whole period,
    so the result is the whole rent."""
    rent = _money(rent)
    _check_date(join_date, 'join_date')
    previous = previous_fixed_due(join_date, fixed_due_day)
    following = fixed_day_due_dates(join_date, fixed_due_day, 1)[0]
    days_left = (following - join_date).days
    days_in_period = (following - previous).days
    with localcontext() as context:
        context.prec = 50
        return (rent * days_left / days_in_period).quantize(_PAISA, rounding=ROUND_HALF_UP)


# --------------------------------------------------------------------------------------------------- periods

def first_period(join_date, mode, policy, rent, fixed_due_day):
    """The first period of a stay: what is charged and when the next one starts.

    ANNIVERSARY: a full period (policy and fixed day are ignored). FIXED_DAY: needs a fixed day and a policy;
    FULL_MONTH charges the whole rent, PRORATE charges prorated_amount."""
    _check_date(join_date, 'join_date')
    _check_mode(mode)
    rent = _money(rent)
    if mode == ANNIVERSARY:
        following = due_date(join_date, 1)
        amount = rent
    else:
        _check_fixed_day(fixed_due_day)
        if policy not in FIRST_PERIOD_POLICIES:
            raise ValueError(f'a FIXED_DAY stay needs a first-period policy: one of {FIRST_PERIOD_POLICIES}')
        following = fixed_day_due_dates(join_date, fixed_due_day, 1)[0]
        amount = rent if policy == FULL_MONTH else prorated_amount(rent, join_date, fixed_due_day)
    return Period(start=join_date, end=following - timedelta(days=1), amount=amount, next_due=following)


def build_periods(join_date, mode, policy, rent, fixed_due_day, count):
    """The first `count` periods of a stay, in order, with no gap and no overlap. The first is first_period; every
    later one is a whole month at the full rent. ANNIVERSARY periods come from the anchor, never from each other."""
    if type(count) is not int or count < 1:
        raise ValueError('count must be a whole number of at least 1')
    first = first_period(join_date, mode, policy, rent, fixed_due_day)
    rent = _money(rent)
    periods = [first]
    if mode == ANNIVERSARY:
        for index in range(1, count):
            start, following = due_date(join_date, index), due_date(join_date, index + 1)
            periods.append(Period(start, following - timedelta(days=1), rent, following))
    else:
        dues = fixed_day_due_dates(join_date, fixed_due_day, count)
        for index in range(1, count):
            start, following = dues[index - 1], dues[index]
            periods.append(Period(start, following - timedelta(days=1), rent, following))
    return periods


# --------------------------------------------------------------------------------------------------- payable and overdue

def _check_days(value, name):
    if type(value) is not int:
        raise TypeError(f'{name} must be a whole number of days')
    if value < 0:
        raise ValueError(f'{name} cannot be negative')
    return value


def payable_from(due, window_days):
    """The first day a due can be paid: `window_days` before its due date."""
    _check_date(due, 'due')
    return due - timedelta(days=_check_days(window_days, 'window_days'))


def is_payable(due, today, window_days):
    """True from `window_days` before the due date onwards; a late due is still payable."""
    _check_date(today, 'today')
    return today >= payable_from(due, window_days)


def is_overdue(due, today, grace_days):
    """True once today is later than the due date plus the grace days."""
    _check_date(due, 'due')
    _check_date(today, 'today')
    return today > due + timedelta(days=_check_days(grace_days, 'grace_days'))


def days_overdue(due, today, grace_days):
    """How many days past the end of the grace period (0 while not overdue)."""
    _check_date(due, 'due')
    _check_date(today, 'today')
    return max(0, (today - (due + timedelta(days=_check_days(grace_days, 'grace_days')))).days)


def days_until_due(due, today):
    """Days from today to the due date; negative after it."""
    _check_date(due, 'due')
    _check_date(today, 'today')
    return (due - today).days


def effective_status(stored_status, today, due, window_days, grace_days):
    """What a due really is on `today` (E8): finished dues keep their status; an open due is OVERDUE, PAYABLE or
    SCHEDULED by the dates. OVERDUE is never stored, so it is not an accepted stored status."""
    if stored_status not in STORED_STATUSES:
        raise ValueError(f'stored status must be one of {STORED_STATUSES} (overdue is worked out, never stored)')
    if stored_status in FINISHED_STATUSES:
        return stored_status
    if is_overdue(due, today, grace_days):
        return OVERDUE
    return PAYABLE if is_payable(due, today, window_days) else SCHEDULED
