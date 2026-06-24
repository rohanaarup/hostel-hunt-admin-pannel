import uuid
from django.db import models
from apps.hostels.models import Hostel

SHARING_CHOICES = (
    ('single', 'Single'),
    ('double', 'Double'),
    ('triple', 'Triple'),
    ('quad', 'Quad'),
    ('dormitory', 'Dormitory'),
)

class Room(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column='room_id')
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='rooms')
    room_name = models.CharField(max_length=100)
    
    sharing_type = models.CharField(max_length=20, choices=SHARING_CHOICES)
    capacity = models.PositiveIntegerField()
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
