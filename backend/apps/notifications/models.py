"""
Notifications (Phase 8): what a user sees in the inbox, which reminder was already sent through which channel, each user's
channel preferences, and a record of when each scheduled job last ran.

  Notification            one inbox item for one user (a student reminder, a receipt notice, an owner payment notice).
  NotificationLog         "this reminder was sent through this channel for this due". Unique on (due, kind, channel, bucket),
                          so a second run, a retry or a second worker can never send the same reminder twice. Internal.
  NotificationPreference  per user: inbox, push, email (all default true).
  JobRun                  one run of a scheduled command (stays_daily, process_outbox): when, how it ended, counts, a checkpoint
                          to resume from. Internal; the ops status page reads it.

Tenancy: Notification and NotificationPreference belong to one user (UserScopedModel, USER_LOOKUP = user), so the existing
IsResourceUser permission and the user-scoped helpers apply. NotificationLog and JobRun are internal and read by no API
except the admin-only ops status (GlobalModel). Nothing here stores an email address or a phone number.
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.tenancy.models import GlobalModel, UserScopedModel


class Notification(UserScopedModel):
    USER_LOOKUP = 'user'

    class Category(models.TextChoices):
        RENT = 'RENT', 'Rent'
        STAY = 'STAY', 'Stay'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    # before_7, before_3, before_1, due_day, overdue_1, overdue_3, overdue_7, manual_reminder, payment_received,
    # owner_recorded, stay_created, owner_payment_received, owner_stay_created, owner_vacate_requested
    kind = models.CharField(max_length=40)
    category = models.CharField(max_length=10, choices=Category.choices)
    title = models.CharField(max_length=120)
    body = models.CharField(max_length=300)
    due = models.ForeignKey('stays.Due', null=True, blank=True, on_delete=models.SET_NULL, related_name='notifications')
    # Ids only (stay_id, payment_id): what the app needs to open the right screen. Never a name, email or phone number.
    payload = models.JSONField(default=dict, blank=True)
    # The channels that really delivered it: 'in_app', 'push', 'email'.
    channels_delivered = models.JSONField(default=list, blank=True)
    # Makes creating the same notice twice harmless (the outbox event key plus the audience).
    dedupe_key = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            # The unread count (user, read_at is null) and the newest-first list.
            models.Index(fields=['user', 'read_at', 'created_at'], name='notif_user_read_created_idx'),
            models.Index(fields=['user', 'category', 'created_at'], name='notif_user_cat_created_idx'),
            models.Index(fields=['created_at'], name='notif_created_idx'),  # the 90-day purge
        ]

    def __str__(self):
        return f'{self.kind} for user {self.user_id}'


class NotificationLog(GlobalModel):
    id = models.BigAutoField(primary_key=True)
    due = models.ForeignKey('stays.Due', on_delete=models.CASCADE, related_name='notification_logs')
    kind = models.CharField(max_length=40)
    channel = models.CharField(max_length=10)  # in_app, push, email, or request (a manual reminder asked for)
    # Empty for the automatic ladder. A manual reminder uses the IST date, so an owner can send one per due per day.
    bucket = models.CharField(max_length=10, blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'notification_logs'
        constraints = [
            models.UniqueConstraint(fields=['due', 'kind', 'channel', 'bucket'], name='notification_log_once'),
        ]
        indexes = [
            models.Index(fields=['channel', 'created_at'], name='notiflog_channel_created_idx'),  # the daily email cap
        ]

    def __str__(self):
        return f'{self.kind}/{self.channel} for due {self.due_id}'


class NotificationPreference(UserScopedModel):
    USER_LOOKUP = 'user'

    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_preferences')
    inbox = models.BooleanField(default=True)
    push = models.BooleanField(default=True)
    email = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_preferences'

    def __str__(self):
        return f'Preferences of user {self.user_id}'


class JobRun(GlobalModel):
    class Status(models.TextChoices):
        RUNNING = 'RUNNING', 'Running'
        OK = 'OK', 'Finished'
        FAILED = 'FAILED', 'Failed'

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=60)
    run_day = models.DateField(help_text='The IST date the run belongs to (a resumed run continues the same day).')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    # Where to resume (the last stay id handled) and what was done: counts only, no personal data.
    checkpoint = models.CharField(max_length=64, blank=True, default='')
    counts = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'job_runs'
        ordering = ['-started_at']
        indexes = [models.Index(fields=['name', 'started_at'], name='jobrun_name_started_idx')]

    def __str__(self):
        return f'{self.name} {self.status} {self.started_at:%Y-%m-%d %H:%M}'
