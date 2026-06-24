from django.contrib import admin
from .models import Room

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_name', 'hostel', 'sharing_type', 'capacity', 'price_per_month', 'is_active')
    list_filter = ('sharing_type', 'is_active', 'is_ac', 'has_attached_bathroom')
    search_fields = ('room_name', 'hostel__name')
    readonly_fields = ('id', 'created_at', 'updated_at')
