from django.contrib import admin
from .models import OTPRecord

@admin.register(OTPRecord)
class OTPRecordAdmin(admin.ModelAdmin):
    list_display = ('identifier', 'purpose', 'is_used', 'created_at', 'expires_at')
    list_filter = ('is_used', 'purpose')
    search_fields = ('identifier',)
    ordering = ('-created_at',)