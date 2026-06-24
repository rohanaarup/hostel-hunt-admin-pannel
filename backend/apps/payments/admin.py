from django.contrib import admin
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('user_name', 'hostel', 'amount', 'status', 'method', 'paid_at')
    list_filter = ('status', 'method', 'hostel')
    search_fields = ('user_name', 'transaction_ref', 'hostel__name')
    readonly_fields = ('id', 'created_at')
