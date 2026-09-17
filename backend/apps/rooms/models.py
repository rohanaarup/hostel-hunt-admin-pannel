import uuid
from django.db import models
from apps.hostels.models import Hostel
from apps.core.models import TenantScopedModel

SHARING_CHOICES = (
    ('single', 'Single'),
    ('double', 'Double'),
    ('triple', 'Triple'),
    ('quad', 'Quad'),
    ('dormitory', 'Dormitory'),
)

class Room(TenantScopedModel):
    OWNER_LOOKUP = "hostel__owner"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column='room_id')
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='rooms')
    
    floor_number = models.PositiveIntegerField(default=1)
    room_number = models.CharField(max_length=20, default='')
    room_name = models.CharField(max_length=100)
    
    sharing_type = models.CharField(max_length=20, choices=SHARING_CHOICES)
    capacity = models.PositiveIntegerField()
    bed_count = models.PositiveIntegerField(default=1)
    price_per_month = models.DecimalField(max_digits=10, decimal_places=2)
    available_beds = models.PositiveIntegerField()
    
    has_attached_bathroom = models.BooleanField(default=False)
    is_ac = models.BooleanField(default=False)
    
    description = models.TextField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'rooms'
        ordering = ['room_name']

    def __str__(self):
        return f"{self.room_name} - {self.hostel.name}"


# ─────────────────────────────────────────────────────────────────────────────
# Bed
# ─────────────────────────────────────────────────────────────────────────────

class Bed(TenantScopedModel):
    """
    Represents a single bed slot within a Room.

    Role in the payment pipeline:
      - CreateOrderView calls Bed.objects.select_for_update() to atomically lock
        the bed row before placing a Razorpay order.
      - held_until is set to now() + 15 minutes while payment is in-flight.
      - VerifyPaymentView / WebhookView clears held_until and sets is_available=False
        once payment is captured.
      - expire_stale_holds management command clears held_until for timed-out orders.

    NOTE: Bed rows are expected to be seeded when a Room is created (bed_count beds
    per room). The Flutter UI currently renders beds dynamically from Room.bed_count;
    the Bed model brings that concept into the DB for safe concurrent locking.
    """

    OWNER_LOOKUP = "room__hostel__owner"

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_column='bed_id'
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name='beds',
    )
    bed_number = models.PositiveIntegerField(
        help_text="1-indexed bed number within the room (e.g. 1, 2, 3).",
    )
    is_available = models.BooleanField(
        default=True,
        db_index=True,
        help_text="False once a payment is confirmed for this bed.",
    )
    held_until = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Set while payment is in-flight; cleared on capture or expiry.",
    )

    class Meta:
        db_table = 'beds'
        ordering = ['room', 'bed_number']
        unique_together = [('room', 'bed_number')]

    def __str__(self):
        return f"Bed {self.bed_number} — {self.room}"
