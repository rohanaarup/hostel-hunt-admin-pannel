"""
apps/notifications/templates.py
-------------------------------
The words of the reminders and notices, in one place. The push wording and the email wording reproduce the approved boards
(docs/ui/text/PushPreview.txt and EmailPreview.txt) word for word; test_templates.py spells the expected strings out.

`offset` is the number of days from today to the due date: 7, 3, 1 before; 0 on the due day; -1, -3, -7 after (overdue).
The boards give wording for 7, 3 and 1 days before, the due day and 3 days overdue. The ladder also has 1 and 7 days overdue,
and a manual reminder can fall on any day: those use the same sentences with the number changed (listed in docs/ENGINE.md).

Placeholders: amount, hostel name, locality, student name, dates, room and bed. Nothing here reads the database.
"""
from html import escape

LADDER = (7, 3, 1, 0, -1, -3, -7)
KINDS = {7: 'before_7', 3: 'before_3', 1: 'before_1', 0: 'due_day', -1: 'overdue_1', -3: 'overdue_3', -7: 'overdue_7'}

APP_NAME = 'Hostel Hunt'


def kind_for(offset):
    """The ladder kind for a day offset, or None when the offset is not a ladder step."""
    return KINDS.get(offset)


def priority_for(offset):
    """Higher is more urgent: overdue first (the longer overdue the sooner), then the due day, then the nearest upcoming."""
    if offset < 0:
        return 100 + (-offset)
    if offset == 0:
        return 50
    return 10 + (8 - min(offset, 8))


def email_is_sent(offset):
    """Reminder emails go out on the due date and when rent is overdue only (inbox and push carry the earlier steps)."""
    return offset <= 0


def money(amount):
    from decimal import Decimal
    amount = Decimal(amount)
    whole = amount == amount.to_integral_value()
    return f'₹{amount:,.0f}' if whole else f'₹{amount:,.2f}'


def day(d):
    return f'{d.day} {d.strftime("%b")}'


def day_year(d):
    return f'{d.day} {d.strftime("%b %Y")}'


def days(n):
    return f'{n} day' if n == 1 else f'{n} days'


def push_text(offset, amount, hostel_name, due_date):
    """(title, body) of the push reminder; the same words fill the in-app notice."""
    m, due = money(amount), day(due_date)
    if offset > 1:
        if offset == 3:
            return 'Rent due in 3 days', f'Pay {m} by {due}. Tap to pay in the app.'
        return f'Rent due in {days(offset)}', f'{m} for {hostel_name} is due on {due}. You can pay now.'
    if offset == 1:
        return 'Rent due tomorrow', f'{m} is due tomorrow, {due}.'
    if offset == 0:
        return 'Rent is due today', f'Pay {m} now to stay on track.'
    return f'Rent is {days(-offset)} overdue', f'{m} was due on {due}. Please pay as soon as you can.'


def email_content(offset, *, amount, hostel, locality, name, due_date, period_start, period_end, room_label, bed_label):
    """(subject, text, html) of the reminder email for the due day (offset 0) or an overdue day (offset below 0)."""
    m = money(amount)
    where = f'{hostel} · {locality}' if locality else hostel
    if offset < 0:
        subject = f'Your rent of {m} is overdue'
        heading = 'Your rent is overdue'
        lead = (f'Hi {name}, your rent for {where} was due on {day(due_date)}. Please pay as soon as you can. '
                f'Paying on time keeps your stay record clear.')
    else:
        subject = f'Your rent of {m} is due today'
        heading = 'Your rent is due today'
        lead = f'Hi {name}, your rent for {where} is due today. Paying on time keeps your stay record clear.'
    rows = [
        ('Amount', m),
        ('Due date', day_year(due_date)),
        ('Rent period', f'{day(period_start)} – {day(period_end)} {period_end.year}'),
        ('Room and bed', f'{room_label}, {bed_label}'),
    ]
    button = 'Pay rent in the app'
    footer = ('You are receiving this because you have an active stay on Hostel Hunt. '
              'Reminder emails are sent on the due date and when rent is overdue.')

    text = '\n'.join([APP_NAME, '', heading, '', lead, ''] + [f'{k}: {v}' for k, v in rows] + ['', button, '', footer])
    row_html = ''.join(
        f'<tr><td style="padding:6px 0;color:#B3A59F">{escape(k)}</td><td style="padding:6px 0;text-align:right">{escape(v)}</td></tr>'
        for k, v in rows)
    html = (
        '<div style="font-family:IBM Plex Sans,Arial,sans-serif;background:#181514;color:#F4ECE8;padding:24px">'
        f'<div style="font-weight:600;color:#FF8A80">{escape(APP_NAME)}</div>'
        f'<h1 style="font-size:20px;margin:16px 0 8px">{escape(heading)}</h1>'
        f'<p style="margin:0 0 16px">{escape(lead)}</p>'
        f'<table style="width:100%;border-collapse:collapse">{row_html}</table>'
        f'<p style="margin:20px 0"><span style="background:#D32F2F;color:#fff;padding:10px 18px;border-radius:8px">{escape(button)}</span></p>'
        f'<p style="font-size:12px;color:#B3A59F">{escape(footer)}</p></div>'
    )
    return subject, text, html


# ---- inbox notices that are not reminders (the Inbox board) ----

OFFLINE_METHOD_WORDS = {'CASH': 'cash', 'BANK_TRANSFER': 'bank transfer', 'UPI_DIRECT': 'UPI direct'}


def payment_received(amount, period_start, period_end):
    return 'Payment received', f'{money(amount)} for {day(period_start)} – {day(period_end)} rent. Your receipt is ready.'


def owner_recorded(amount, method, period_start, period_end):
    word = OFFLINE_METHOD_WORDS.get(method, 'offline')
    return ('Owner recorded your payment',
            f'{money(amount)} {word} payment for {day(period_start)} – {day(period_end)} was recorded by the hostel owner.')


def stay_created_student(hostel_name):
    return 'You are booked in', f'Your stay at {hostel_name} is now active and locked to this hostel.'


def stay_created_owner(hostel_name, room_label, bed_label):
    return 'New stay started', f'{room_label}, {bed_label} at {hostel_name} now has a stay.'


def rent_received_owner(amount, room_label, bed_label, period_start, period_end):
    return ('Payment received',
            f'{money(amount)} rent for {room_label}, {bed_label} ({day(period_start)} – {day(period_end)}).')


def vacate_requested_owner(room_label, bed_label, move_out_date):
    return 'Request to vacate', f'The student in {room_label}, {bed_label} plans to move out on {day_year(move_out_date)}.'
