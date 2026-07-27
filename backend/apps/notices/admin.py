from django.contrib import admin
from .models import Notice

@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'hostel', 'is_active', 'posted_at', 'expires_at')
    list_filter = ('is_active', 'hostel')
    search_fields = ('title', 'body')
