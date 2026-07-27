import uuid
from django.db import models
from apps.hostels.models import Hostel
from apps.rooms.models import Room
from apps.bookings.models import Booking
from apps.core.models import TenantScopedModel

class Resident(TenantScopedModel):
    OWNER_LOOKUP = "hostel__owner"

    ID_PROOF_CHOICES = (
        ('aadhaar', 'Aadhaar'),
        ('passport', 'Passport'),
        ('driving_license', 'Driving License'),
        ('other', 'Other'),
    )
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('vacated', 'Vacated'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column='resident_id')
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='residents')
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, related_name='residents')
    
    bed_number = models.CharField(max_length=10, null=True, blank=True)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    
    id_proof_type = models.CharField(max_length=20, choices=ID_PROOF_CHOICES)
    id_proof_number = models.CharField(max_length=50)
    
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=15, blank=True)
    
    move_in_date = models.DateField()
    expected_move_out_date = models.DateField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    linked_booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True, related_name='linked_residents')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'residents'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.hostel.name} ({self.status})"
