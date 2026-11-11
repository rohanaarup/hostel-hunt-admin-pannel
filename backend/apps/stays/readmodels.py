"""
apps/stays/readmodels.py
------------------------
The JSON the student boards need, built from stays whose rows are already loaded. Nothing here runs a query per row:
the views fetch the stay (select_related hostel and room) and its dues (prefetch, with the payment and its successful
attempt when a payment is shown) once, and these functions only arrange them. Shapes follow the approved boards in
docs/ui; docs/UI_DATA_MAP.md lists, field by field, which JSON field feeds which line of which board.

Dates in the payload are ISO dates (`2026-10-18`) or, for a moment in time, ISO datetimes in IST (`...+05:30`). Money is
a string of rupees (`"6000.00"`). A few `*_label` or `headline` strings carry the exact board wording that is composed from
several values, so the app does not have to repeat the wording rules.
"""
import calendar
import re
from datetime import date, timedelta
from decimal import Decimal

from . import billing, schedule
from .dates import to_ist, today_ist
from .models import Stay
from .notifications import unread_count
from .services import bed_label, room_label

KIND_LABEL = {'BOOKING_PERIOD': 'Booking', 'RENT': 'Rent'}
SERIES_STATES = ('on_time', 'late', 'upcoming')
METHODS = ('UPI', 'CARD', 'NETBANKING', 'CASH', 'BANK_TRANSFER', 'UPI_DIRECT', 'OTHER')
RECEIPT_READY_DAYS = 14
MONTH_RE = re.compile(r'^(\d{4})-(0[1-9]|1[0-2])$')
MAX_CALENDAR_MONTHS_AHEAD = 24


# ----------------------------------------------------------------------------------------------------------- wording

def day_label(d):
    return f'{d.day} {d.strftime("%b")}'


def day_year_label(d):
    return f'{d.day} {d.strftime("%b %Y")}'


def period_label(start, end):
    return f'{day_label(start)} – {day_label(end)}'


def ordinal(n):
    suffix = 'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f'{n}{suffix}'


def money(amount):
    amount = Decimal(amount)
    whole = amount == amount.to_integral_value()
    return f'₹{amount:,.0f}' if whole else f'₹{amount:,.2f}'


def plural(n, word):
    return f'{n} {word}' if n == 1 else f'{n} {word}s'


def ist_iso(moment):
    return to_ist(moment).isoformat() if moment else None


def iso(d):
    return d.isoformat() if d else None


def month_key(d):
    return d.strftime('%Y-%m')


# --------------------------------------------------------------------------------------------------- billing wording

def _snapshot(stay):
    return stay.billing_snapshot or {}


def _fixed_day_text(snapshot):
    if snapshot.get('fixed_due_last_day'):
        return 'last day'
    return ordinal(snapshot.get('fixed_due_day') or 1)


def rent_rule_text(stay):
    """'18th of every month' (ActiveStay, 'Rent is due')."""
    snapshot = _snapshot(stay)
    if snapshot.get('billing_mode') == billing.FIXED_DAY:
        return f'{_fixed_day_text(snapshot)} of every month'
    return f'{ordinal(stay.join_date.day)} of every month'


def billing_summary(stay, stored, today):
    """What StayCreated and StayCreatedFixed show, so those screens need no extra call."""
    snapshot = _snapshot(stay)
    mode = snapshot.get('billing_mode', billing.ANNIVERSARY)
    first = next((r for r in stored if r.kind == 'BOOKING_PERIOD'), None)
    periods = billing.build_periods(
        stay.join_date, mode, snapshot.get('first_period_policy', billing.FULL_MONTH), stay.rent_amount,
        schedule._fixed_spec(snapshot), 2)
    start = first.period_start if first else periods[0].start
    end = first.period_end if first else periods[0].end
    amount = first.amount if first else periods[0].amount
    next_due = periods[1].due_date if len(periods) > 1 else None
    days = (end - start).days + 1
    rent = money(stay.rent_amount)

    if mode == billing.FIXED_DAY:
        day_text = _fixed_day_text(snapshot)
        title = f'This hostel collects rent on the {day_text} of every month'
        if start.day == snapshot.get('fixed_due_day') and not snapshot.get('fixed_due_last_day') and amount == stay.rent_amount \
                and next_due and (next_due - start).days >= 28:
            text = (f'You joined on the {day_text}, so your first period is a full month. '
                    f'Each month\'s rent of {rent} is due on the {day_text}.')
        elif amount < stay.rent_amount:
            text = (f'Your first period is part of a month, so you paid {money(amount)} for {days} days. '
                    f'From {day_label(next_due)} the full {rent} is due on the {day_text}.')
        else:
            text = (f'Your first period is part of a month and is charged as a full month ({rent}). '
                    f'From {day_label(next_due)} the full {rent} is due on the {day_text}.')
    else:
        day_text = ordinal(stay.join_date.day)
        title = f'Rent is due on the {day_text} of every month'
        text = (f'You joined on the {day_text}, so each month\'s rent is due on the {day_text}. '
                f'Short months use their last day.')
    return {
        'mode': mode,
        'first_period_start': iso(start), 'first_period_end': iso(end), 'first_period_days': days,
        'first_period_amount': str(amount), 'next_due_date': iso(next_due),
        'rule_title': title, 'rule_text': text,
    }


# ------------------------------------------------------------------------------------------------------ due payloads

def due_item(row, today, grace=0):
    over = billing.days_overdue(row.due_date, today, grace) if row.status == billing.OVERDUE else 0
    return {
        'id': str(row.id) if row.id else None,
        'kind': row.kind, 'kind_label': KIND_LABEL.get(row.kind, 'Rent'),
        'label': f'{KIND_LABEL.get(row.kind, "Rent")}, {period_label(row.period_start, row.period_end)}',
        'period_start': iso(row.period_start), 'period_end': iso(row.period_end),
        'period_label': period_label(row.period_start, row.period_end),
        'due_date': iso(row.due_date), 'amount': str(row.amount),
        'status': row.status, 'stored_status': row.stored_status, 'payable': row.payable,
        'days_left': (row.due_date - today).days, 'days_overdue': over,
        'paid_at': ist_iso(row.paid_at), 'projected': row.projected,
    }


def next_due_block(row, today):
    if row is None:
        return None
    return {
        'due_id': str(row.id) if row.id else None, 'date': iso(row.due_date), 'amount': str(row.amount),
        'days_left': (row.due_date - today).days, 'status': row.status, 'payable': row.payable,
    }


# ---------------------------------------------------------------------------------------------- payment information

def _success_attempt(payment):
    if payment is None:
        return None
    for attempt in payment.attempts.all():  # prefetched, filtered to SUCCESS by the view
        if attempt.status == 'SUCCESS':
            return attempt
    return None


def method_of(payment):
    """UPI, CARD, NETBANKING, WALLET, OTHER, CASH, BANK_TRANSFER or UPI_DIRECT. Booking payments do not store it (G6-05), so
    it is read from the successful attempt."""
    if payment is None:
        return ''
    if payment.paid_via:
        return payment.paid_via
    attempt = _success_attempt(payment)
    if attempt is not None:
        from apps.payments.methods import paid_via_for
        return paid_via_for(attempt.method)
    return ''


def masked_transaction(payment):
    attempt = _success_attempt(payment)
    reference = getattr(attempt, 'razorpay_payment_id', None)
    return f'pay_••••{reference[-4:].upper()}' if reference else None


def masked_receipt_number(payment):
    return f'RCPT-••••{payment.receipt_number[-4:]}'


def payment_item(row, today, grace):
    item = due_item(row, today, grace)
    payment = row.payment if row.status == billing.PAID else None
    item.update({
        'due_id': item['id'],
        'payment_id': str(payment.id) if payment else None,
        'method': method_of(payment),
        'transaction': masked_transaction(payment) if payment else None,
        'receipt_number': payment.receipt_number if payment else None,
        'source': payment.source if payment else None,
        'recorded_by_owner': bool(payment and payment.source == 'OFFLINE_OWNER'),
    })
    return item


def receipt_payload(stay, row, payment):
    start, end = row.period_start, row.period_end
    return {
        'title': f'{start.strftime("%b %Y")} rent' if row.kind == 'RENT' else f'{start.strftime("%b %Y")} booking',
        'subtitle': f'Rent received · {period_label(start, end)} {end.year}',
        'amount': str(payment.amount),
        'receipt_number': masked_receipt_number(payment),
        'paid_at': ist_iso(payment.verified_at or row.paid_at),
        'method': method_of(payment),
        'transaction': masked_transaction(payment),
        'hostel_name': stay.hostel.name, 'locality': stay.hostel.locality,
        'room_label': room_label(stay.room), 'bed_label': bed_label(stay.bed_number),
        'paid_by': stay.student.display_name if stay.student_id else '',
        'rent_period': {'start': iso(start), 'end': iso(end), 'label': f'{period_label(start, end)} {end.year}'},
        'source': payment.source,
    }


# --------------------------------------------------------------------------------------------------- stay summaries

def stay_summary(stay, today, with_billing=True):
    stored, projected = schedule.all_rows(stay, today)
    next_row = schedule.next_unpaid(stored, projected) if stay.is_current else None
    until = schedule.paid_until(stored)
    data = {
        'id': str(stay.id),
        'hostel_name': stay.hostel.name, 'locality': stay.hostel.locality, 'city': stay.hostel.city,
        'room_label': room_label(stay.room), 'bed_label': bed_label(stay.bed_number),
        'joined_on': iso(stay.join_date), 'ended_on': iso(to_ist(stay.ended_at).date()) if stay.ended_at else None,
        'status': stay.status, 'openable': stay.is_current,
        'rent_amount': str(stay.rent_amount), 'rent_rule_text': rent_rule_text(stay),
        'next_due': next_due_block(next_row, today),
        'paid_until': iso(until),
        'pending_amount': None,  # reserved for the optional settlement add-on (BookingsSettle, decision D6)
    }
    if with_billing:
        data['billing_summary'] = billing_summary(stay, stored, today)
    return data, stored, projected


def stay_detail(stay, today, user):
    data, stored, projected = stay_summary(stay, today)
    data['unread_notices'] = unread_count(user)
    data['vacate'] = None
    if stay.vacate_requested_at:
        data['vacate'] = {
            'requested_at': ist_iso(stay.vacate_requested_at), 'planned_move_out_date': iso(stay.planned_move_out_date),
            'reason': stay.vacate_reason,
        }
    return data


def dues_payload(stay, today):
    stored, projected = schedule.all_rows(stay, today)
    _, grace = schedule.window_and_grace(stay)
    return [due_item(r, today, grace) for r in stored], [due_item(r, today, grace) for r in projected]


# ---------------------------------------------------------------------------------------------------------- analytics

def _months_between(join, today):
    months = (today.year - join.year) * 12 + (today.month - join.month)
    if today.day < join.day:
        months -= 1
    anchor_year, anchor_month = divmod(join.year * 12 + join.month - 1 + months, 12)
    last = date(anchor_year, anchor_month + 1, min(join.day, calendar.monthrange(anchor_year, anchor_month + 1)[1]))
    return months + (1 if (today - last).days >= 15 else 0)


def _month_shift(d, delta):
    index = d.year * 12 + d.month - 1 + delta
    return date(index // 12, index % 12 + 1, 1)


def _paid_late_days(row, grace):
    """Days late for a paid rent: the IST date of the payment against the due date plus grace. The booking payment is made
    when the booking is made, before the stay starts, so it always counts as on time."""
    if row.kind == 'BOOKING_PERIOD' or row.paid_at is None:
        return 0
    return max(0, (to_ist(row.paid_at).date() - (row.due_date + timedelta(days=grace))).days)


def analytics_payload(stay, today, range_key):
    stored, projected = schedule.all_rows(stay, today)
    _, grace = schedule.window_and_grace(stay)
    next_row = schedule.next_unpaid(stored, projected)
    considered = [r for r in stored + projected if next_row is None or r.due_date <= next_row.due_date]
    if next_row is None:
        considered = list(stored)
    end_month = considered[-1].due_date.replace(day=1) if considered else today.replace(day=1)
    window = {'6m': 6, '12m': 12}.get(range_key)
    start_month = _month_shift(end_month, -(window - 1)) if window else stay.join_date.replace(day=1)
    in_window = [r for r in considered if r.due_date.replace(day=1) >= start_month]

    paid = [r for r in in_window if r.status == billing.PAID]
    late = []
    for r in paid:
        days = _paid_late_days(r, grace)
        if days:
            late.append({'due_date': iso(r.due_date), 'days_late': days})
    methods = {m: 0 for m in METHODS}
    for r in paid:
        methods[method_of(r.payment) if method_of(r.payment) in methods else 'OTHER'] += 1

    buckets = {}
    for r in in_window:
        key = month_key(r.due_date)
        bucket = buckets.setdefault(key, {'month': key, 'label': r.due_date.strftime('%b'), 'amount': Decimal('0'),
                                          'states': []})
        if r.status == billing.PAID:
            bucket['amount'] += r.amount
            bucket['states'].append('late' if _paid_late_days(r, grace) else 'on_time')
        elif r.status in (billing.WAIVED, billing.CANCELLED):
            continue
        else:
            bucket['amount'] += r.amount
            bucket['states'].append('late' if r.status == billing.OVERDUE else 'upcoming')
    series = []
    for key in sorted(buckets):
        bucket = buckets[key]
        states = bucket.pop('states')
        if not states:
            continue
        bucket['state'] = 'late' if 'late' in states else ('upcoming' if 'upcoming' in states else 'on_time')
        bucket['amount'] = str(bucket['amount'])
        series.append(bucket)

    if len(late) == 1:
        late_label = f'1 paid {plural(late[0]["days_late"], "day")} late'
    elif late:
        late_label = f'{len(late)} paid late'
    else:
        late_label = 'All paid on time'

    upcoming = [r for r in stored + projected if r.is_open][:3]
    return {
        'range': range_key,
        'paid_so_far': str(sum((r.amount for r in paid), Decimal('0'))),
        'payments_count': len(paid),
        'on_time_count': len(paid) - len(late), 'late_count': len(late), 'late_payments': late, 'late_label': late_label,
        'stay_length_months': _months_between(stay.join_date, today), 'joined_on': iso(stay.join_date),
        'next_rent': ({'date': iso(next_row.due_date), 'amount': str(next_row.amount),
                       'days_left': (next_row.due_date - today).days} if next_row else None),
        'series': series, 'methods': methods,
        'next_dues': [{'due_id': str(r.id) if r.id else None, 'date': iso(r.due_date), 'amount': str(r.amount),
                       'status': r.status, 'projected': r.projected} for r in upcoming],
    }


# ----------------------------------------------------------------------------------------------------------- calendar

def parse_month(text, today):
    """(year, month) from 'YYYY-MM', or None when it is malformed or too far ahead."""
    match = MONTH_RE.match(text or '')
    if not match:
        return None
    year, month = int(match.group(1)), int(match.group(2))
    if (year * 12 + month) - (today.year * 12 + today.month) > MAX_CALENDAR_MONTHS_AHEAD:
        return None
    return year, month


def calendar_payload(stay, today, year, month):
    last_day = calendar.monthrange(year, month)[1]
    first, last = date(year, month, 1), date(year, month, last_day)
    stored, projected = schedule.all_rows(stay, today, horizon=3, until=last)
    rows = stored + projected
    days = []
    for number in range(1, last_day + 1):
        day = date(year, month, number)
        state, is_due, reminder = 'none', False, False
        for r in rows:
            if r.period_start <= day <= r.period_end:
                if r.status in (billing.PAID, billing.WAIVED):
                    state = 'covered'
                elif r.status in schedule.PAYABLE_NOW:
                    state = 'awaiting'
            if r.is_open:
                if r.due_date == day:
                    is_due = True
                if (r.due_date - day).days in (7, 3, 1):
                    reminder = True
        days.append({'date': iso(day), 'state': state, 'due': is_due, 'reminder': reminder, 'join': day == stay.join_date})
    upcoming = [{
        'due_id': str(r.id) if r.id else None, 'due_date': iso(r.due_date), 'period_start': iso(r.period_start),
        'period_end': iso(r.period_end), 'period_label': period_label(r.period_start, r.period_end),
        'amount': str(r.amount), 'status': r.status, 'projected': r.projected,
    } for r in rows if r.is_open][:3]
    return {
        'stay_id': str(stay.id), 'hostel_name': stay.hostel.name, 'locality': stay.hostel.locality, 'month': f'{year:04d}-{month:02d}',
        'join_date': iso(stay.join_date), 'days': days, 'upcoming': upcoming,
    }


# -------------------------------------------------------------------------------------------------------------- home

def _quick_actions(unread):
    return [
        {'key': 'pay_rent', 'label': 'Pay rent', 'badge': None},
        {'key': 'history', 'label': 'History', 'badge': None},
        {'key': 'calendar', 'label': 'Calendar', 'badge': None},
        {'key': 'notices', 'label': 'Notices', 'badge': unread},
        {'key': 'analytics', 'label': 'Analytics', 'badge': None},
        {'key': 'help', 'label': 'Help', 'badge': None},
    ]


def _days_phrase(days):
    if days == 0:
        return 'today'
    return f'in {plural(days, "day")}'


def _glance(stay, stored, projected, today, grace, next_row):
    paid = [r for r in stored if r.status == billing.PAID]
    on_time = sum(1 for r in paid if not _paid_late_days(r, grace))
    shown = [r for r in stored + projected if r.status in (billing.PAID, billing.WAIVED) or r.status in schedule.PAYABLE_NOW]
    months = []
    for r in shown[-5:]:
        if r.status == billing.PAID:
            state = 'late' if _paid_late_days(r, grace) else 'paid'
        elif r.status == billing.WAIVED:
            state = 'paid'
        else:
            state = 'overdue' if r.status == billing.OVERDUE else 'due'
        months.append({'month': month_key(r.due_date), 'label': r.due_date.strftime('%b'), 'state': state})
    if next_row is None:
        next_due = {'label': None, 'date': None}
    elif next_row.status == billing.OVERDUE:
        next_due = {'label': 'Overdue', 'date': iso(next_row.due_date)}
    else:
        next_due = {'label': day_label(next_row.due_date), 'date': iso(next_row.due_date)}
    return {
        'paid_so_far': str(sum((r.amount for r in paid), Decimal('0'))),
        'on_time': {'count': on_time, 'of': len(paid), 'label': f'{on_time} of {len(paid)}'},
        'next_due': next_due, 'months': months,
    }


def home_payload(stay, user, today):
    """The whole Home call. `stay` is the student's current stay (or None) with hostel, room and dues loaded."""
    unread = unread_count(user)
    if stay is None:
        return {
            'enabled': True, 'state': 'no_stay', 'stay': None, 'pill': None, 'due_card': None,
            'quick_actions': [], 'next_3_months': [],
            'attention': {'count': 0, 'items': []}, 'glance': None,
        }
    stored, projected = schedule.all_rows(stay, today)
    _, grace = schedule.window_and_grace(stay)
    next_row = schedule.next_unpaid(stored, projected)
    paid_rows = [r for r in stored if r.status == billing.PAID]
    last_paid = paid_rows[-1] if paid_rows else None
    room, bed = room_label(stay.room), bed_label(stay.bed_number)

    attention, pill, card = [], None, None
    if next_row is not None and next_row.status in schedule.PAYABLE_NOW:
        days = (next_row.due_date - today).days
        month_name = next_row.due_date.strftime('%B')
        if next_row.status == billing.OVERDUE:
            state = 'overdue'
            over = billing.days_overdue(next_row.due_date, today, grace)
            pill = {'kind': 'overdue', 'days': over, 'label': '!'}
            card = {
                'headline': f'{plural(over, "day")} overdue', 'subtitle': f'Rent overdue since {day_label(next_row.due_date)}',
                'cycle_label': None, 'note': 'Please pay as soon as you can',
            }
            attention.append({'kind': 'rent_overdue', 'title': f'{month_name} rent is overdue',
                              'subtitle': f'{money(next_row.amount)} · was due {day_label(next_row.due_date)}',
                              'amount': str(next_row.amount), 'due_id': str(next_row.id) if next_row.id else None,
                              'days': over})
        else:
            state = 'due_soon'
            pill = {'kind': 'days_left', 'days': days, 'label': f'{days}d'}
            covering = next((r for r in reversed(paid_rows) if r.period_start <= today), last_paid)
            card = {
                'headline': 'Due today' if days == 0 else f'{plural(days, "day")} left',
                'subtitle': f'Rent due {day_label(next_row.due_date)}',
                'cycle_label': (f'Cycle {period_label(covering.period_start, covering.period_end)}' if covering else None),
                'note': None,
            }
            attention.append({'kind': 'rent_due', 'title': f'Pay {month_name} rent',
                              'subtitle': f'{money(next_row.amount)} · due {day_label(next_row.due_date)}, {_days_phrase(days)}',
                              'amount': str(next_row.amount), 'due_id': str(next_row.id) if next_row.id else None,
                              'days': days})
        card.update({
            'kind': state, 'due_id': str(next_row.id) if next_row.id else None, 'payable': next_row.payable,
            'due_date': iso(next_row.due_date), 'amount': str(next_row.amount), 'next': None, 'receipt_payment_id': None,
        })
    else:
        state = 'all_paid'
        label_month = (last_paid.period_start if last_paid else stay.join_date).strftime('%b')
        card = {
            'kind': 'all_paid', 'headline': f'{label_month} rent paid', 'subtitle': "You're all paid up",
            'cycle_label': None, 'note': None, 'due_id': None, 'payable': False, 'due_date': None, 'amount': None,
            'next': (next_due_block(next_row, today) | {
                'text': f'Next rent {money(next_row.amount)} · {plural((next_row.due_date - today).days, "day")} to go'}
                if next_row else None),
            'receipt_payment_id': str(last_paid.payment.id) if last_paid and last_paid.payment else None,
        }

    # A receipt is ready for 14 days after a rent is paid.
    if paid_rows:
        newest = max((r for r in paid_rows if r.payment is not None and r.paid_at is not None),
                     key=lambda r: r.paid_at, default=None)
        if newest is not None and (today - to_ist(newest.paid_at).date()).days <= RECEIPT_READY_DAYS:
            attention.append({'kind': 'receipt_ready', 'title': f'{newest.period_start.strftime("%B")} receipt is ready',
                              'subtitle': 'Download or share it', 'amount': str(newest.amount),
                              'payment_id': str(newest.payment.id), 'due_id': str(newest.id)})
    card.update({'hostel_name': stay.hostel.name, 'locality': stay.hostel.locality, 'room_label': room, 'bed_label': bed, 'stay_id': str(stay.id)})

    strip = [{'month': month_key(r.due_date), 'label': r.due_date.strftime('%b'), 'due_date': iso(r.due_date),
              'amount': str(r.amount), 'status': r.status}
             for r in [x for x in stored + projected if x.is_open][:3]]
    return {
        'enabled': True, 'state': state,
        'stay': {'id': str(stay.id), 'hostel_name': stay.hostel.name, 'locality': stay.hostel.locality,
                 'status': stay.status, 'room_label': room,
                 'bed_label': bed, 'openable': stay.is_current},
        'pill': pill, 'due_card': card, 'quick_actions': _quick_actions(unread), 'next_3_months': strip,
        'attention': ({'count': len(attention), 'items': attention} if attention else
                      {'count': 0, 'items': [], 'empty_title': 'Nothing needs your attention',
                       'empty_text': 'We will remind you 7 days before your next rent.'}),
        'glance': _glance(stay, stored, projected, today, grace, next_row),
    }
