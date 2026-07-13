import uuid
from django.db import models
from apps.hostels.models import Hostel
from apps.rooms.models import Room

STATUS_CHOICES = (
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('cancelled', 'Cancelled'),
    ('checked_in', 'Checked In'),
    ('checked_out', 'Checked Out'),
)

class Booking(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column='booking_id')
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='bookings')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='bookings')
    
    # Store snapshot of room name to keep historical data intact
    room_name = models.CharField(max_length=100)
    
    # External User fields (from Flutter app)
    floor_number = models.CharField(max_length=50, null=True, blank=True)
    room_number = models.CharField(max_length=50, null=True, blank=True)
    bed_number = models.CharField(max_length=50, null=True, blank=True)
    
    user_id = models.CharField(max_length=255)
    user_name = models.CharField(max_length=255)
    user_email = models.EmailField()
    user_phone = models.CharField(max_length=20)
    user_profile_photo = models.URLField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    check_in_date = models.DateField()
    check_out_date = models.DateField(null=True, blank=True)
    
    notes = models.TextField(null=True, blank=True)
    
    requested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bookings'
        ordering = ['-requested_at']

    def __str__(self):
        return f"{self.user_name} - {self.room_name} ({self.status})"
