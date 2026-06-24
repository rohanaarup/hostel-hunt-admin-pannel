from django.contrib import admin
from .models import Owner, OTPRecord

@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'email', 'phone_number', 'is_verified', 'is_active', 'created_at')
    list_filter = ('is_verified', 'is_active', 'role')
    search_fields = ('display_name', 'email', 'phone_number', 'id')
    readonly_fields = ('id', 'created_at', 'updated_at', 'password')

@admin.register(OTPRecord)
class OTPRecordAdmin(admin.ModelAdmin):
    list_display = ('identifier', 'purpose', 'is_used', 'expires_at', 'created_at')
    list_filter = ('purpose', 'is_used')
    search_fields = ('identifier',)
    readonly_fields = ('identifier', 'otp_code', 'purpose', 'is_used', 'expires_at', 'created_at')
