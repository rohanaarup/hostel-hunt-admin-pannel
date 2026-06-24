from django.contrib import admin
from .models import Booking

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('user_name', 'hostel', 'room_name', 'status', 'check_in_date', 'requested_at')
    list_filter = ('status', 'hostel')
    search_fields = ('user_name', 'user_email', 'user_phone', 'hostel__name')
    readonly_fields = ('id', 'requested_at', 'updated_at')
