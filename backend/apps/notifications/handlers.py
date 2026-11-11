"""
apps/notifications/handlers.py
------------------------------
What happens to each kind of outbox event. process_outbox (engine.py) claims a batch, calls these OUTSIDE any database
transaction (an email is an HTTP call, rule S4), then records the result.

A handler returns None when the event is finished, or Defer(...) to try again later; it raises to fail (the engine retries
with exponential backoff and a limit). Every handler is idempotent: running the same event twice changes nothing the second
time, because each notice has a unique dedupe key and each reminder channel a unique NotificationLog row.

    stay.created               inbox notice for the student and for the owner
    rent.paid                  student: "Payment received" (or "Owner recorded your payment"); owner: "Payment received"
    stay.vacate_requested      inbox notice for the owner
    rent.reminder              the automatic ladder (7, 3, 1 days before, due day, 1, 3, 7 days after), in batches
    rent.reminder_manual       the owner's "Send reminder" button, in batches

Reminders go to the inbox and, when push exists (Part F is not built), to push; the email goes out on the due day and when
overdue only, highest severity first, never past EMAIL_DAILY_CAP a day. A user's preferences switch each channel off.
Nothing here logs a name, an email address or a phone number.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.core import mailer
from apps.payments.models import Payment
from apps.stays import billing
from apps.stays.dates import today_ist
from apps.stays.models import Due, Stay

from . import services, templates
from .models import Notification, NotificationLog

logger = logging.getLogger('hh.notifications')

EMAIL_RETRY_MINUTES = 15
OPEN_DUE = (Due.Status.SCHEDULED, Due.Status.PAYABLE)


class Defer:
    """Try this event again at `until`. `count_attempt` False means it is not a failure (quiet hours, the daily email cap)."""

    def __init__(self, until, count_attempt=False):
        self.until = until
        self.count_attempt = count_attempt


# ---------------------------------------------------------------------------------------------------- small notices

def create_notice(user, *, kind, category, title, body, dedupe_key, due=None, payload=None, now=None):
    """One inbox notice, once. Honours the user's inbox preference. Returns True when it was created."""
    if user is None or not services.channels_of(user).inbox:
        return False
    _, created = Notification.objects.get_or_create(
        dedupe_key=dedupe_key,
        defaults=dict(user=user, kind=kind, category=category, title=title, body=body, due=due, payload=payload or {},
                      channels_delivered=['in_app'], created_at=now or timezone.now()))
    if created:
        services.bump_unread(user.id)
    return created


def _stay(stay_id):
    return Stay.objects.select_related('hostel__owner__notification_preferences', 'room',
                                       'student__notification_preferences').filter(pk=stay_id).first()


def _labels(stay):
    from apps.stays.services import bed_label, room_label
    return room_label(stay.room), bed_label(stay.bed_number)


def handle_stay_created(event):
    stay = _stay(event.payload.get('stay_id'))
    if stay is None:
        return None
    payload = {'stay_id': str(stay.id)}
    title, body = templates.stay_created_student(stay.hostel.name)
    create_notice(stay.student, kind='stay_created', category='STAY', title=title, body=body, payload=payload,
                  dedupe_key=f'{event.dedupe_key}:student')
    room, bed = _labels(stay)
    title, body = templates.stay_created_owner(stay.hostel.name, room, bed)
    create_notice(stay.hostel.owner, kind='owner_stay_created', category='STAY', title=title, body=body, payload=payload,
                  dedupe_key=f'{event.dedupe_key}:owner')


def handle_rent_paid(event):
    due = Due.objects.select_related('stay__hostel__owner__notification_preferences', 'stay__room',
                                     'stay__student__notification_preferences').filter(pk=event.payload.get('due_id')).first()
    if due is None:
        return None
    stay = due.stay
    payment = Payment.objects.filter(pk=event.payload.get('payment_id')).first()
    source = event.payload.get('source') or (payment.source if payment else Payment.Source.ONLINE)
    payload = {'stay_id': str(stay.id), 'payment_id': event.payload.get('payment_id')}
    amount = payment.amount if payment else due.amount
    if source == Payment.Source.OFFLINE_OWNER:
        title, body = templates.owner_recorded(amount, payment.paid_via if payment else '', due.period_start, due.period_end)
        kind = 'owner_recorded'
    else:
        title, body = templates.payment_received(amount, due.period_start, due.period_end)
        kind = 'payment_received'
    create_notice(stay.student, kind=kind, category='RENT', title=title, body=body, due=due, payload=payload,
                  dedupe_key=f'{event.dedupe_key}:student')
    if source != Payment.Source.OFFLINE_OWNER:  # the owner who recorded rent by hand does not need to be told
        room, bed = _labels(stay)
        title, body = templates.rent_received_owner(amount, room, bed, due.period_start, due.period_end)
        create_notice(stay.hostel.owner, kind='owner_payment_received', category='RENT', title=title, body=body, due=due,
                      payload=payload, dedupe_key=f'{event.dedupe_key}:owner')


def handle_vacate_requested(event):
    stay = _stay(event.payload.get('stay_id'))
    if stay is None or stay.planned_move_out_date is None:
        return None
    room, bed = _labels(stay)
    title, body = templates.vacate_requested_owner(room, bed, stay.planned_move_out_date)
    create_notice(stay.hostel.owner, kind='owner_vacate_requested', category='STAY', title=title, body=body,
                  payload={'stay_id': str(stay.id)}, dedupe_key=f'{event.dedupe_key}:owner')


# ---------------------------------------------------------------------------------------------------------- reminders

def email_cap_left(now=None):
    """How many reminder emails may still go out today (IST) under EMAIL_DAILY_CAP."""
    cap = int(getattr(settings, 'EMAIL_DAILY_CAP', 80))
    sent = NotificationLog.objects.filter(channel='email', created_at__gte=services.ist_day_start(now)).count()
    return max(0, cap - sent)


def _next_morning(now):
    """08:00 IST tomorrow (the cap resets with the IST day)."""
    start = services.ist_day_start(now) + timedelta(days=1)
    _, end = services.quiet_hours()
    return start + timedelta(hours=end)


def reminder_batch(events):
    """Handle a batch of reminder events with a fixed number of queries (bulk read, bulk insert), then the few emails one by
    one. Returns {event.pk: None | Defer | Exception}."""
    now = timezone.now()
    today = today_ist(now)
    results = {}
    due_ids = [e.payload.get('due_id') for e in events if e.payload.get('due_id')]
    dues = {str(d.id): d for d in Due.objects.filter(pk__in=due_ids).select_related(
        'stay__hostel', 'stay__room', 'stay__student__notification_preferences')}
    sent = {(str(d), k, c, b) for d, k, c, b in NotificationLog.objects.filter(due_id__in=due_ids).values_list(
        'due_id', 'kind', 'channel', 'bucket')}

    notices, logs, emails = [], [], []
    users = set()
    for event in events:
        results[event.pk] = None
        due = dues.get(str(event.payload.get('due_id')))
        if due is None or due.status not in OPEN_DUE or not due.stay.is_current or due.stay.student_id is None:
            continue  # paid, waived, cancelled, ended or gone since it was queued: nothing to remind
        manual = event.topic == 'rent.reminder_manual'
        current = (due.due_date - today).days
        planned = event.payload.get('offset')
        if manual:
            offset, kind, bucket = current, 'manual_reminder', event.payload.get('bucket', '')
        else:
            kind, bucket = event.payload.get('kind', ''), ''
            if planned is None or planned > 0 and current != planned or planned <= 0 and current > 0:
                continue  # an upcoming step that is a day or more old is stale; the next step will come
            offset = planned if planned > 0 else current
        student = due.stay.student
        channels = services.channels_of(student)
        stay = due.stay
        title, body = templates.push_text(offset, due.amount, stay.hostel.name, due.due_date)
        key = (str(due.id), kind, 'in_app', bucket)
        if channels.inbox and key not in sent:
            notices.append(Notification(
                user=student, kind=kind, category='RENT', title=title, body=body, due=due,
                payload={'stay_id': str(stay.id), 'due_id': str(due.id)}, channels_delivered=['in_app'],
                dedupe_key=f'{event.dedupe_key}:in_app', created_at=now))
            logs.append(NotificationLog(due=due, kind=kind, channel='in_app', bucket=bucket, created_at=now))
            users.add(student.id)
        # push: Part F (Firebase) is not built, so there is no push channel to deliver through yet.
        wants_email = (templates.email_is_sent(offset) and channels.email and student.email
                       and (str(due.id), kind, 'email', bucket) not in sent)
        if wants_email:
            emails.append((event, due, kind, bucket, offset))

    if notices:
        Notification.objects.bulk_create(notices, ignore_conflicts=True)
    if logs:
        NotificationLog.objects.bulk_create(logs, ignore_conflicts=True)
    for user_id in users:
        services.bump_unread(user_id)

    if emails:
        cap_left = email_cap_left(now)
        provider_down = False
        for event, due, kind, bucket, offset in emails:
            if cap_left <= 0:
                results[event.pk] = Defer(_next_morning(now))
                continue
            if provider_down:
                results[event.pk] = Defer(now + timedelta(minutes=EMAIL_RETRY_MINUTES), count_attempt=True)
                continue
            stay = due.stay
            subject, text, html = templates.email_content(
                offset, amount=due.amount, hostel=stay.hostel.name, locality=stay.hostel.locality,
                name=stay.student.display_name, due_date=due.due_date, period_start=due.period_start,
                period_end=due.period_end, room_label=_labels(stay)[0], bed_label=_labels(stay)[1])
            try:
                mailer.send_email(stay.student.email, subject, text, html)
            except mailer.EmailError as exc:
                if exc.kind in (mailer.EmailError.TIMEOUT, mailer.EmailError.UNREACHABLE, mailer.EmailError.PROVIDER_DOWN):
                    provider_down = True  # a 429 and a provider outage both arrive as PROVIDER_DOWN: stop and try next run
                    results[event.pk] = Defer(now + timedelta(minutes=EMAIL_RETRY_MINUTES), count_attempt=True)
                else:
                    logger.error('reminder email not sent: event=%s kind=%s', event.pk, exc.kind)  # ids and a code only
                continue
            NotificationLog.objects.get_or_create(due=due, kind=kind, channel='email', bucket=bucket,
                                                  defaults={'created_at': now})
            cap_left -= 1
            notice = Notification.objects.filter(dedupe_key=f'{event.dedupe_key}:in_app').first()
            if notice is not None and 'email' not in notice.channels_delivered:
                notice.channels_delivered = notice.channels_delivered + ['email']
                notice.save(update_fields=['channels_delivered'])
    return results


# ------------------------------------------------------------------------------------------------------------ registry

HANDLERS = {
    'stay.created': handle_stay_created,
    'rent.paid': handle_rent_paid,
    'stay.vacate_requested': handle_vacate_requested,
}
BATCH_HANDLERS = {
    'rent.reminder': reminder_batch,
    'rent.reminder_manual': reminder_batch,
}
# Held back during quiet hours (21:00 to 08:00 IST): they would make a phone buzz or an email arrive.
QUIET_TOPICS = ('rent.reminder', 'rent.reminder_manual')
# Events other parts of the system write for later features; nothing to do for them yet.
IGNORED_TOPICS = ('rent.payment_voided',)
