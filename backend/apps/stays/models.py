"""
Stays: the live tenancy created by a paid booking, its billing cycles, and the outbox.

  HostelBillingConfig  how one hostel bills (one row per hostel; no row means the defaults).
  Stay                 a student's tenancy in one bed, created from a paid booking (Phase 5).
  Due                  one billing cycle of a stay.
  OutboxEvent          work to do outside a request (reminders and the like); the table only, the consumer is Phase 8.

Tenancy (apps/core/tenancy): Stay and Due are visible to the hostel owner and to the student, so both inherit the two
scoped bases, like Booking and Payment. HostelBillingConfig is the owner's. OutboxEvent is internal and unscoped on
purpose (GlobalModel): nothing reads it through an API.

Nothing here talks to payments or bookings except by foreign key, and nothing here is reachable through an endpoint yet.
The arithmetic lives in apps/stays/billing.py (pure Python); these models only store its results.
"""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.bookings.models import Booking
from apps.core.tenancy.models import GlobalModel, TenantScopedModel, UserScopedModel
from apps.hostels.models import Hostel
from apps.residents.models import Resident
from apps.rooms.models import Room

from . import billing


class HostelBillingConfig(TenantScopedModel):
    """How a hostel bills its stays. A hostel with no row uses the defaults (effective_for); a change here never
    changes an existing stay, which keeps the snapshot it was created with (Stay.billing_snapshot)."""

    OWNER_LOOKUP = 'hostel__owner'

    class BillingMode(models.TextChoices):
        ANNIVERSARY = billing.ANNIVERSARY, 'Anniversary (due on the join day each month)'
        FIXED_DAY = billing.FIXED_DAY, 'Fixed day of the month'

    class FirstPeriodPolicy(models.TextChoices):
        PRORATE = billing.PRORATE, 'Prorate the first part-month'
        FULL_MONTH = billing.FULL_MONTH, 'Charge the first part-month as a whole month'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hostel = models.OneToOneField(Hostel, on_delete=models.CASCADE, related_name='billing_config')
    billing_mode = models.CharField(max_length=20, choices=BillingMode.choices, default=BillingMode.ANNIVERSARY)
    # FIXED_DAY only: a day 1 to 28, or the last day of the month (the flag). Exactly one of the two.
    fixed_due_day = models.PositiveSmallIntegerField(null=True, blank=True)
    fixed_due_last_day = models.BooleanField(default=False)
    # Default FULL_MONTH: PRORATE rests on a rule still waiting for the founder's confirmation (billing.prorated_amount).
    first_period_policy = models.CharField(max_length=20, choices=FirstPeriodPolicy.choices,
                                           default=FirstPeriodPolicy.FULL_MONTH)
    payable_window_days = models.PositiveSmallIntegerField(default=7, validators=[MaxValueValidator(60)])
    grace_days = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(30)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hostel_billing_configs'
        constraints = [
            models.CheckConstraint(
                condition=Q(fixed_due_day__isnull=True) | (Q(fixed_due_day__gte=1) & Q(fixed_due_day__lte=28)),
                name='hbc_fixed_day_1_to_28'),
            models.CheckConstraint(
                condition=(Q(billing_mode=billing.ANNIVERSARY) & Q(fixed_due_day__isnull=True) & Q(fixed_due_last_day=False))
                | (Q(billing_mode=billing.FIXED_DAY)
                   & ((Q(fixed_due_day__isnull=False) & Q(fixed_due_last_day=False))
                      | (Q(fixed_due_day__isnull=True) & Q(fixed_due_last_day=True)))),
                name='hbc_fixed_day_shape'),
            models.CheckConstraint(condition=Q(payable_window_days__lte=60), name='hbc_window_at_most_60'),
            models.CheckConstraint(condition=Q(grace_days__lte=30), name='hbc_grace_at_most_30'),
        ]

    def __str__(self):
        return f'Billing for hostel {self.hostel_id} ({self.billing_mode})'

    def clean(self):
        problems = {}
        if self.billing_mode == billing.FIXED_DAY:
            if self.fixed_due_day is None and not self.fixed_due_last_day:
                problems['fixed_due_day'] = 'A fixed-day hostel needs a due day from 1 to 28, or the last day of the month.'
            elif self.fixed_due_day is not None and self.fixed_due_last_day:
                problems['fixed_due_last_day'] = 'Choose a due day or the last day of the month, not both.'
            elif self.fixed_due_day is not None and not 1 <= self.fixed_due_day <= 28:
                problems['fixed_due_day'] = 'The due day must be from 1 to 28 (use "last day of the month" for the end).'
        elif self.fixed_due_day is not None or self.fixed_due_last_day:
            problems['billing_mode'] = 'A due day only applies to a fixed-day hostel.'
        if problems:
            raise ValidationError(problems)

    def fixed_day_spec(self):
        """What the billing engine wants: a day 1 to 28, the LAST_DAY marker, or None (ANNIVERSARY)."""
        if self.billing_mode != billing.FIXED_DAY:
            return None
        return billing.LAST_DAY if self.fixed_due_last_day else self.fixed_due_day

    def snapshot(self):
        """Plain data copied onto a stay when it is created, so later changes here never reach existing stays."""
        return {
            'billing_mode': self.billing_mode,
            'fixed_due_day': self.fixed_due_day,
            'fixed_due_last_day': self.fixed_due_last_day,
            'first_period_policy': self.first_period_policy,
            'payable_window_days': self.payable_window_days,
            'grace_days': self.grace_days,
        }

    @classmethod
    def effective_for(cls, hostel):
        """The hostel's config, or an UNSAVED one holding the defaults when it has none."""
        return cls.objects.filter(hostel=hostel).first() or cls(hostel=hostel)


class Stay(TenantScopedModel, UserScopedModel):
    """A student's tenancy. Created from a paid booking (Phase 5); one stay per booking.

    There is deliberately NO database rule limiting a student to one current stay: that rule (decision D2) is a
    booking-time check in a later phase, and a second paid booking must never be refused after the money is taken (E4),
    so such a stay is created and flagged needs_review instead."""

    OWNER_LOOKUP = 'hostel__owner'
    USER_LOOKUP = 'student'

    CURRENT_STATUSES = ('UPCOMING', 'ACTIVE', 'NOTICE')

    class Status(models.TextChoices):
        UPCOMING = 'UPCOMING', 'Upcoming'
        ACTIVE = 'ACTIVE', 'Active'
        NOTICE = 'NOTICE', 'On notice'
        ENDED = 'ENDED', 'Ended'
        CANCELLED = 'CANCELLED', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Optional, like Booking.student: a booking marked paid offline can have no account.
    student = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='stays')
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='stays')
    # The room and bed exactly as the booking has them (a room link and a bed number, no bed row).
    room = models.ForeignKey(Room, null=True, blank=True, on_delete=models.SET_NULL, related_name='stays')
    bed_number = models.CharField(max_length=20, null=True, blank=True)
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='stay')
    # E5: an optional automatic link to an existing Resident. Never created automatically.
    resident = models.ForeignKey(Resident, null=True, blank=True, on_delete=models.SET_NULL, related_name='stays')
    join_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPCOMING)
    # Copied when the stay is created: later price or billing changes never touch it.
    rent_amount = models.DecimalField(max_digits=10, decimal_places=2)
    billing_snapshot = models.JSONField(default=dict, blank=True)
    needs_review = models.BooleanField(default=False)
    vacate_requested_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'stays'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['student', 'status'], name='stays_student_status_idx')]

    def __str__(self):
        return f'Stay {self.pk} ({self.status})'

    @property
    def is_current(self):
        return self.status in self.CURRENT_STATUSES


class Due(TenantScopedModel, UserScopedModel):
    """One billing cycle of a stay. Overdue is never stored: it is worked out when read from the due date, today and the
    hostel's grace days (E8, billing.effective_status)."""

    OWNER_LOOKUP = 'stay__hostel__owner'
    USER_LOOKUP = 'stay__student'

    class Status(models.TextChoices):
        SCHEDULED = billing.SCHEDULED, 'Scheduled'
        PAYABLE = billing.PAYABLE, 'Payable'
        PAID = billing.PAID, 'Paid'
        WAIVED = billing.WAIVED, 'Waived'
        CANCELLED = billing.CANCELLED, 'Cancelled'

    class Kind(models.TextChoices):
        BOOKING_PERIOD = 'BOOKING_PERIOD', 'The period paid with the booking'
        RENT = 'RENT', 'Rent'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stay = models.ForeignKey(Stay, on_delete=models.CASCADE, related_name='dues')
    period_start = models.DateField()
    period_end = models.DateField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    paid_at = models.DateTimeField(null=True, blank=True)
    # By string, so this app does not import the payments app's models (no import cycle, no payment code touched).
    payment = models.ForeignKey('payments.Payment', null=True, blank=True, on_delete=models.SET_NULL, related_name='dues')
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.RENT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dues'
        ordering = ['due_date']
        constraints = [
            models.UniqueConstraint(fields=['stay', 'period_start'], name='due_unique_period_per_stay'),
            models.CheckConstraint(condition=Q(period_end__gte=F('period_start')), name='due_period_not_backwards'),
            models.CheckConstraint(condition=Q(amount__gte=0), name='due_amount_not_negative'),
        ]
        indexes = [
            models.Index(fields=['status', 'due_date'], name='dues_status_due_idx'),
            models.Index(fields=['stay', 'due_date'], name='dues_stay_due_idx'),
        ]

    def __str__(self):
        return f'Due {self.due_date} ({self.status})'


class OutboxEvent(GlobalModel):
    """Work to do outside a request (a reminder to send, a message to deliver). Written in the same transaction as the
    change that causes it; a job (Phase 8) reads PENDING rows whose next_attempt_at has come and marks them DONE or
    FAILED. dedupe_key is unique, so writing the same event twice is harmless.

    The payload holds ids and codes only: NO personal data (no names, emails or phone numbers), because payloads are
    logged and kept. Look the person up by id when the event is handled."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        DONE = 'DONE', 'Done'
        FAILED = 'FAILED', 'Failed'

    topic = models.CharField(max_length=100)
    payload = models.JSONField(default=dict, blank=True)
    dedupe_key = models.CharField(max_length=200, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'outbox_events'
        ordering = ['id']
        # The consumer's query: PENDING rows that are due, oldest first, in batches.
        indexes = [models.Index(fields=['status', 'next_attempt_at'], name='outbox_status_next_idx')]

    def __str__(self):
        return f'{self.topic} ({self.status})'
