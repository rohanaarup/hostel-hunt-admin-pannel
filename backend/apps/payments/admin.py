from django.contrib import admin
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'resident_name', 'hostel', 'amount_due', 'amount_paid', 'status', 'due_date')
    list_filter = ('status', 'mode', 'hostel')
    search_fields = ('resident_name', 'resident_phone')
