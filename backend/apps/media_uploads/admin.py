from django.contrib import admin
from .models import MediaItem

@admin.register(MediaItem)
class MediaItemAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'category', 'hostel', 'room', 'created_at')
    list_filter = ('category',)
    search_fields = ('file_name', 'hostel__name', 'room__room_name')
    readonly_fields = ('id', 'created_at')
