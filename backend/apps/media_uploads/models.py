import uuid
from django.db import models
from apps.hostels.models import Hostel
from apps.rooms.models import Room

CATEGORY_CHOICES = (
    ('hostel', 'Hostel'),
    ('room', 'Room'),
    ('common_area', 'Common Area'),
    ('video', 'Video'),
)

class MediaItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Optional relationships - media might be uploaded before attaching to a specific room
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='media', null=True, blank=True)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='media', null=True, blank=True)
    
    # The actual file
    file = models.FileField(upload_to='media_uploads/')
    
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    mime_type = models.CharField(max_length=100)
    file_name = models.CharField(max_length=255)
    
    # Allows reordering images on the frontend
    order_index = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'media_items'
        ordering = ['order_index', '-created_at']

    def __str__(self):
        return f"{self.category} - {self.file_name}"

    @property
    def remote_url(self):
        if self.file:
            return self.file.url
        return None
