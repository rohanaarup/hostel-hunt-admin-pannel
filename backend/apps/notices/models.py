import uuid
from django.db import models
from django.conf import settings
from apps.hostels.models import Hostel
from apps.core.models import TenantScopedModel

class Notice(TenantScopedModel):
    OWNER_LOOKUP = "posted_by"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column='notice_id')
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, null=True, blank=True, related_name='notices')
    
    title = models.CharField(max_length=150)
    body = models.TextField()
    
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='posted_notices')
    posted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notices'
        ordering = ['-posted_at']

    def __str__(self):
        return self.title
