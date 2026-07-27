from django.contrib import admin
from .models import Booking

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'student_name', 'hostel', 'room', 'status', 'created_at')
    list_filter = ('status', 'payment_mode', 'hostel')
    search_fields = ('student_name', 'student_phone')
