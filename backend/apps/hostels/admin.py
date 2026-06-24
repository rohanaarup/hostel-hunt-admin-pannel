from django.contrib import admin
from .models import Hostel

@admin.register(Hostel)
class HostelAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'owner_name', 'gender_type', 'is_active', 'is_verified')
    list_filter = ('gender_type', 'is_active', 'is_verified', 'city')
    search_fields = ('name', 'owner_name', 'city', 'id')
    readonly_fields = ('id', 'created_at', 'updated_at')
