import uuid
from django.db import models
from django.conf import settings
import django.utils.timezone
from apps.hostels.models import Hostel
from apps.bookings.models import Booking
from apps.core.models import TenantScopedModel

class Payment(TenantScopedModel):
    OWNER_LOOKUP = "hostel__owner"

    MODE_CHOICES = (
        ('cash', 'Cash'),
        ('upi', 'UPI'),
        ('bank_transfer', 'Bank Transfer'),
    )
    STATUS_CHOICES = (
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('overdue', 'Overdue'),
        ('partial', 'Partial'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column='payment_id')
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, null=True, blank=True, related_name='payments')
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='payments')
    
    resident_name = models.CharField(max_length=100, default='')
    resident_phone = models.CharField(max_length=15, default='')
    
    amount_due = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    due_date = models.DateField(default=django.utils.timezone.now)
    paid_date = models.DateField(null=True, blank=True)
    
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='cash')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='payments_marked')
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.resident_name} - {self.amount_due} ({self.status})"
