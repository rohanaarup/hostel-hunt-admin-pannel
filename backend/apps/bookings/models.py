import uuid
from django.db import models
from django.conf import settings
import django.utils.timezone
from apps.hostels.models import Hostel
from apps.rooms.models import Room
from apps.core.models import TenantScopedModel

class Booking(TenantScopedModel):
    OWNER_LOOKUP = "hostel__owner"

    PAYMENT_MODE_CHOICES = (
        ('offline', 'Offline'),
        ('online', 'Online'),
    )
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column='booking_id')
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='bookings')
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings')

    # Denormalised room info sent by the Flutter app (room FK may be null)
    room_name = models.CharField(max_length=100, null=True, blank=True)
    floor_number = models.CharField(max_length=20, null=True, blank=True)
    room_number = models.CharField(max_length=20, null=True, blank=True)
    bed_number = models.CharField(max_length=20, null=True, blank=True)

    # Guest info
    student_name = models.CharField(max_length=100, default='', blank=True)
    student_phone = models.CharField(max_length=15, default='', blank=True)

    # Dates
    check_in_date = models.DateField(null=True, blank=True)
    check_out_date = models.DateField(null=True, blank=True)

    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, default='offline')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    notes = models.TextField(null=True, blank=True)

    marked_paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='bookings_marked_paid'
    )
    marked_paid_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(default=django.utils.timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bookings'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.student_name or 'Guest'} - {self.hostel.name} ({self.status})"
