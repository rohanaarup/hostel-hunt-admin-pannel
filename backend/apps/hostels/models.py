import uuid
from django.db import models
from django.conf import settings



GENDER_CHOICES = (
    ('boys', 'Boys'),
    ('girls', 'Girls'),
    ('co_living', 'Co-Living'),
)

class Hostel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column='hostel_id')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hostels')
    name = models.CharField(max_length=255)
    owner_name = models.CharField(max_length=255)
    contact_number = models.CharField(max_length=20)
    email = models.EmailField()
    
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=20)
    landmark = models.CharField(max_length=255, null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    google_maps_url = models.URLField(max_length=500, null=True, blank=True)
    
    gender_type = models.CharField(max_length=20, choices=GENDER_CHOICES)
    total_floors = models.PositiveIntegerField(default=1)
    total_rooms = models.PositiveIntegerField(default=0)
    total_beds = models.PositiveIntegerField(default=0)
    occupancy_types = models.JSONField(default=list) # List of strings e.g. ['single', 'double']
    
    description = models.TextField(null=True, blank=True)
    rules = models.TextField(null=True, blank=True)
    check_in_policy = models.CharField(max_length=255, null=True, blank=True)
    check_out_policy = models.CharField(max_length=255, null=True, blank=True)
    
    amenities = models.JSONField(default=list)
    
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hostels'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.city})"
