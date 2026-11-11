"""
apps/stays/schedule.py
----------------------
A stay's dues as the student sees them: the dues stored in the database, then the dues that will exist later but do not yet
(projected, never written by a read). Pure data work over a stay whose dues are already loaded (`prefetch_related('dues')`):
nothing in here runs a query, so the number of queries never depends on the number of dues.

Overdue and payable are worked out on read (E8) from today (IST), the stay's own `payable_window_days` and `grace_days`.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from . import billing

OPEN = (billing.SCHEDULED, billing.PAYABLE, billing.OVERDUE)
PAYABLE_NOW = (billing.PAYABLE, billing.OVERDUE)
MAX_PROJECTED_PERIODS = 240


@dataclass
class DueRow:
    id: Optional[object]
    kind: str
    period_start: date
    period_end: date
    due_date: date
    amount: Decimal
    stored_status: str
    status: str            # what it is today: SCHEDULED, PAYABLE, OVERDUE, PAID, WAIVED or CANCELLED
    paid_at: Optional[object]
    payment: Optional[object]
    projected: bool

    @property
    def is_open(self):
        return self.status in OPEN

    @property
    def payable(self):
        """A stored due that can be paid now. A projected due has no row yet, so it can never be paid."""
        return (not self.projected) and self.status in PAYABLE_NOW


def window_and_grace(stay):
    snapshot = stay.billing_snapshot or {}
    return int(snapshot.get('payable_window_days', 7)), int(snapshot.get('grace_days', 0))


def _fixed_spec(snapshot):
    if snapshot.get('billing_mode') != billing.FIXED_DAY:
        return None
    return billing.LAST_DAY if snapshot.get('fixed_due_last_day') else snapshot.get('fixed_due_day')


def stored_rows(stay, today):
    """Every stored due of the stay (prefetched), oldest period first, with its status worked out for `today`."""
    window, grace = window_and_grace(stay)
    rows = []
    for due in sorted(stay.dues.all(), key=lambda d: (d.period_start, d.due_date)):
        rows.append(DueRow(
            id=due.id, kind=due.kind, period_start=due.period_start, period_end=due.period_end, due_date=due.due_date,
            amount=due.amount, stored_status=due.status,
            status=billing.effective_status(due.status, today, due.due_date, window, grace),
            # the payment only when the caller loaded it (select_related); reading `due.payment` would run a query
            paid_at=due.paid_at, payment=due._state.fields_cache.get('payment'), projected=False,
        ))
    return rows


def projected_rows(stay, today, stored, *, horizon=3, until=None):
    """The dues after the last stored one: at least `horizon` of them, and further if `until` (a date) needs it.
    Computed from the stay's own copied billing settings, so they are the dues the cron will create later (Phase 8)."""
    if not stay.is_current:
        return []
    snapshot = stay.billing_snapshot or {}
    window, grace = window_and_grace(stay)
    last_end = stored[-1].period_end if stored else None
    count = max(len(stored) + horizon, 2)
    while True:
        periods = billing.build_periods(
            stay.join_date, snapshot.get('billing_mode', billing.ANNIVERSARY),
            snapshot.get('first_period_policy', billing.FULL_MONTH), stay.rent_amount, _fixed_spec(snapshot), count)
        ahead = [p for p in periods if last_end is None or p.start > last_end]
        enough = len(ahead) >= horizon and (until is None or ahead[-1].start > until)
        if enough or count >= MAX_PROJECTED_PERIODS:
            break
        count = min(MAX_PROJECTED_PERIODS, count * 2)
    rows = []
    for period in ahead:
        rows.append(DueRow(
            id=None, kind='RENT', period_start=period.start, period_end=period.end, due_date=period.due_date,
            amount=period.amount, stored_status=billing.SCHEDULED,
            status=billing.effective_status(billing.SCHEDULED, today, period.due_date, window, grace),
            paid_at=None, payment=None, projected=True,
        ))
    return rows


def all_rows(stay, today, *, horizon=3, until=None):
    stored = stored_rows(stay, today)
    return stored, projected_rows(stay, today, stored, horizon=horizon, until=until)


def next_open(rows):
    """The first due that is not finished: the one the student will pay next."""
    for row in rows:
        if row.is_open:
            return row
    return None


def next_unpaid(stored, projected):
    return next_open(stored) or next_open(projected)


def paid_until(stored):
    ends = [r.period_end for r in stored if r.status == billing.PAID]
    return max(ends) if ends else None
