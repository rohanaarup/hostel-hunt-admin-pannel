import uuid
from django.db import models
from apps.hostels.models import Hostel
from apps.bookings.models import Booking

PAYMENT_STATUS_CHOICES = (
    ('pending', 'Pending'),
    ('completed', 'Completed'),
    ('failed', 'Failed'),
    ('refunded', 'Refunded'),
)

PAYMENT_METHOD_CHOICES = (
    ('upi', 'UPI'),
    ('card', 'Card'),
    ('bank_transfer', 'Bank Transfer'),
    ('cash', 'Cash'),
)

class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column='payment_id')
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='payments')
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='payments')
    
    # Store snapshot of names
    user_name = models.CharField(max_length=255)
    room_name = models.CharField(max_length=100)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    
    transaction_ref = models.CharField(max_length=100, null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user_name} - {self.amount} ({self.status})"
