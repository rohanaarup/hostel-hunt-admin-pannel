"""
apps/stays/admin_queries.py
---------------------------
The owner and admin view of rent (the AdminDues board): which stays are overdue, due this week or paid, and the four totals.

The classification is done IN THE DATABASE, so a page of 25 rows and the tab counts of 5,000 stays cost the same handful of
queries. It is the same rule as the student read API (schedule.py / billing.effective_status), written as SQL against each
stay's own copied settings (`billing_snapshot`: payable_window_days and grace_days):

  open due     stored status SCHEDULED or PAYABLE (PAID, WAIVED and CANCELLED dues are finished)
  OVERDUE      an open due whose due date + grace days is before today                       (E8: derived, never stored)
  PAYABLE      an open due whose payable window has opened (due date - window days <= today)
  DUE THIS WEEK  an open due that is not overdue and falls within the next 7 days (today to today + 6)
  PAID         a paid due whose period covers today, and nothing payable or overdue
  SCHEDULED    everything else

A row's status is the worst of its dues: OVERDUE, else PAYABLE, else PAID, else SCHEDULED. All dates are IST (apps/stays/dates.py).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import (
    Count, DateField, Exists, ExpressionWrapper, F, IntegerField, OuterRef, Q, Subquery, Sum, Value,
)
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast, Coalesce

from apps.hostels.models import Hostel

from . import billing, readmodels, schedule
from .dates import ist_midnight_utc
from .models import Due, Stay

OPEN = (Due.Status.SCHEDULED, Due.Status.PAYABLE)
WEEK_DAYS = 6  # today to today + 6 is "this week"
ACTIVE = (Stay.Status.ACTIVE, Stay.Status.NOTICE)
STATUS_LABELS = {billing.OVERDUE: 'Overdue', billing.PAYABLE: 'Payable', billing.SCHEDULED: 'Scheduled', billing.PAID: 'Paid'}
PRIMARY_ACTION = {billing.OVERDUE: 'record_payment', billing.PAYABLE: 'send_reminder', billing.SCHEDULED: 'view',
                  billing.PAID: 'receipt'}


def _snapshot_int(key, default):
    return Coalesce(Cast(KeyTextTransform(key, 'stay__billing_snapshot'), IntegerField()), Value(default))


def open_dues():
    """Open dues with their own overdue line and payable-from date worked out from the stay's settings."""
    return (Due.objects.filter(status__in=OPEN)
            .annotate(_grace=_snapshot_int('grace_days', 0), _window=_snapshot_int('payable_window_days', 7))
            .annotate(overdue_line=ExpressionWrapper(F('due_date') + F('_grace'), output_field=DateField()),
                      payable_from=ExpressionWrapper(F('due_date') - F('_window'), output_field=DateField())))


def scoped_stays(user, hostel_id=None):
    """The stays this user may see: the owner's own hostels, or every stay for an admin (is_staff)."""
    queryset = Stay.objects.all() if user.is_staff else Stay.objects.filter(hostel__owner=user)
    return queryset.filter(hostel_id=hostel_id) if hostel_id else queryset


def classify(queryset, today):
    """Add the yes/no columns the tabs and filters use, plus the date of the next open due (for ordering)."""
    due_today = open_dues().filter(stay=OuterRef('pk'))
    return queryset.annotate(
        has_overdue=Exists(due_today.filter(overdue_line__lt=today)),
        has_payable=Exists(due_today.filter(payable_from__lte=today)),
        has_week=Exists(due_today.filter(overdue_line__gte=today, due_date__lte=today + timedelta(days=WEEK_DAYS))),
        covered=Exists(Due.objects.filter(stay=OuterRef('pk'), status=Due.Status.PAID, period_start__lte=today,
                                          period_end__gte=today)),
        next_open_date=Subquery(Due.objects.filter(stay=OuterRef('pk'), status__in=OPEN).order_by('due_date')
                                .values('due_date')[:1]),
    )


TAB_FILTERS = {
    'overdue': Q(has_overdue=True),
    'due_this_week': Q(has_week=True, has_overdue=False),
    'paid': Q(covered=True, has_payable=False),
}


def tab_counts(classified):
    counts = classified.order_by().aggregate(
        all=Count('pk'),
        overdue=Count('pk', filter=TAB_FILTERS['overdue']),
        due_this_week=Count('pk', filter=TAB_FILTERS['due_this_week']),
        paid=Count('pk', filter=TAB_FILTERS['paid']),
    )
    return {key: counts[key] for key in ('all', 'overdue', 'due_this_week', 'paid')}


def _scope_filter(user, hostel_id=None):
    filters = {} if user.is_staff else {'stay__hostel__owner': user}
    if hostel_id:
        filters['stay__hostel_id'] = hostel_id
    return filters


def _money_block(aggregate):
    return {'amount': str(aggregate['amount'] or Decimal('0.00')), 'count': aggregate['stays'] or 0}


def month_bounds(today):
    """The start of this IST month and of the next one, as UTC moments."""
    first = today.replace(day=1)
    following = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    return ist_midnight_utc(first), ist_midnight_utc(following)


def rent_counts(user, today):
    """The two numbers the owner dashboard shows: stays with overdue rent, and stays with rent due this week."""
    dues = open_dues().filter(stay__hostel__owner=user, stay__status__in=Stay.CURRENT_STATUSES)
    counts = dues.aggregate(  # ONE query for both numbers
        overdue=Count('stay_id', distinct=True, filter=Q(overdue_line__lt=today)),
        week=Count('stay_id', distinct=True, filter=Q(overdue_line__gte=today, due_date__lte=today + timedelta(days=WEEK_DAYS))))
    return {'overdue_rent_count': counts['overdue'] or 0, 'due_this_week_count': counts['week'] or 0}


def totals(user, today, hostel_id=None):
    """The four tiles of the AdminDues board."""
    scope = _scope_filter(user, hostel_id)
    active = scoped_stays(user, hostel_id).filter(status__in=ACTIVE).count()
    current = open_dues().filter(stay__status__in=Stay.CURRENT_STATUSES, **scope)
    overdue = current.filter(overdue_line__lt=today).aggregate(amount=Sum('amount'), stays=Count('stay_id', distinct=True))
    week = current.filter(overdue_line__gte=today, due_date__lte=today + timedelta(days=WEEK_DAYS)).aggregate(
        amount=Sum('amount'), stays=Count('stay_id', distinct=True))
    start, end = month_bounds(today)
    collected = Due.objects.filter(status=Due.Status.PAID, paid_at__gte=start, paid_at__lt=end, **scope).aggregate(
        amount=Sum('amount'), stays=Count('stay_id', distinct=True))
    return {
        'active_stays': active,
        'overdue': _money_block(overdue),
        'due_this_week': _money_block(week),
        'collected_this_month': {'amount': str(collected['amount'] or Decimal('0.00')),
                                 'stays_paid': collected['stays'] or 0, 'stays_total': active},
    }


def hostels_for(user):
    queryset = Hostel.objects.all() if user.is_staff else Hostel.objects.filter(owner=user)
    return [{'id': str(h.id), 'name': h.name, 'locality': h.locality}
            for h in queryset.order_by('name')[:100]]


# ------------------------------------------------------------------------------------------------------------- rows

def row_for(stay, today):
    """One table row. `stay` has its hostel, room, student and dues (with payment) loaded."""
    stored, projected = schedule.all_rows(stay, today, horizon=1)
    overdue = [r for r in stored if r.status == billing.OVERDUE]
    payable = [r for r in stored if r.status == billing.PAYABLE]
    covered = any(r.status == billing.PAID and r.period_start <= today <= r.period_end for r in stored)
    status = (billing.OVERDUE if overdue else billing.PAYABLE if payable
              else billing.PAID if covered else billing.SCHEDULED)
    open_rows = [r for r in stored if r.is_open]
    action_due = (overdue or payable or open_rows or [None])[0]
    next_row = schedule.next_unpaid(stored, projected) if stay.is_current else None

    paid_rows = [r for r in stored if r.status == billing.PAID and r.payment is not None and r.payment.status == 'SUCCESS']
    last_paid = max(paid_rows, key=lambda r: r.period_end, default=None)
    actions = ['view']
    if open_rows and stay.is_current:
        actions.append('record_payment')
    if (overdue or payable) and stay.is_current:
        actions.append('send_reminder')
    if last_paid is not None:
        actions.append('receipt')
    offline = last_paid is not None and last_paid.payment.source == 'OFFLINE_OWNER'
    if offline:
        actions.append('void')
    if stay.is_current:
        actions.append('end_stay')

    return {
        'id': str(stay.id), 'student_name': (stay.student.display_name if stay.student_id else stay.booking.student_name) or '',
        'hostel_id': str(stay.hostel_id), 'hostel_name': stay.hostel.name,
        'room_label': readmodels.room_label(stay.room), 'bed_label': readmodels.bed_label(stay.bed_number),
        'rent_amount': str(stay.rent_amount), 'join_date': readmodels.iso(stay.join_date),
        'stay_status': stay.status, 'needs_review': stay.needs_review,
        'status': status, 'status_label': STATUS_LABELS[status],
        'next_due': readmodels.next_due_block(next_row, today),
        # A paid row offers its receipt only when there is a payment to show; a booking marked paid by hand has none.
        'primary_action': 'view' if status == billing.PAID and last_paid is None else PRIMARY_ACTION[status],
        'allowed_actions': actions,
        'action_due_id': str(action_due.id) if action_due is not None else None,
        # The due a button acts on (Record payment shows its period and amount, fixed to the due).
        'action_due': ({
            'due_id': str(action_due.id), 'period_start': readmodels.iso(action_due.period_start),
            'period_end': readmodels.iso(action_due.period_end),
            'period_label': readmodels.period_label(action_due.period_start, action_due.period_end),
            'due_date': readmodels.iso(action_due.due_date), 'amount': str(action_due.amount),
        } if action_due is not None else None),
        'receipt_payment_id': str(last_paid.payment.id) if last_paid is not None else None,
        'void_due_id': str(last_paid.id) if offline else None,
        # What the Receipt button shows (the owner has no student receipt page): the last successful payment of the stay.
        'last_payment': ({
            'payment_id': str(last_paid.payment.id), 'receipt_number': last_paid.payment.receipt_number,
            'amount': str(last_paid.payment.amount),
            'paid_at': readmodels.ist_iso(last_paid.payment.verified_at or last_paid.paid_at),
            'method': last_paid.payment.paid_via or '', 'source': last_paid.payment.source,
        } if last_paid is not None else None),
    }
