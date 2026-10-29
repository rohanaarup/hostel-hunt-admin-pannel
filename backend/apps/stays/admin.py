from django.contrib import admin

from .models import Due, HostelBillingConfig, OutboxEvent, Stay


@admin.register(HostelBillingConfig)
class HostelBillingConfigAdmin(admin.ModelAdmin):
    list_display = ('hostel', 'billing_mode', 'fixed_due_day', 'fixed_due_last_day', 'first_period_policy',
                    'payable_window_days', 'grace_days')
    list_filter = ('billing_mode', 'first_period_policy')
    raw_id_fields = ('hostel',)


class DueInline(admin.TabularInline):
    model = Due
    extra = 0
    can_delete = False
    fields = ('due_date', 'period_start', 'period_end', 'amount', 'status', 'kind', 'paid_at')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Stay)
class StayAdmin(admin.ModelAdmin):
    """Stays are created by code from a paid booking, never typed in: the money and the billing snapshot are read-only."""
    list_display = ('id', 'hostel', 'join_date', 'status', 'rent_amount', 'needs_review', 'created_at')
    list_filter = ('status', 'needs_review', 'hostel')
    raw_id_fields = ('student', 'hostel', 'room', 'booking', 'resident')
    readonly_fields = ('rent_amount', 'billing_snapshot', 'created_at', 'updated_at')
    inlines = [DueInline]

    def has_add_permission(self, request):
        return False


@admin.register(Due)
class DueAdmin(admin.ModelAdmin):
    """A due's money and status are written by the payment code only; the admin shows them, it does not edit them."""
    list_display = ('id', 'stay', 'due_date', 'amount', 'status', 'kind')
    list_filter = ('status', 'kind')
    raw_id_fields = ('stay',)
    readonly_fields = ('amount', 'status', 'paid_at', 'payment', 'kind', 'created_at', 'updated_at')

    def has_add_permission(self, request):
        return False


@admin.register(OutboxEvent)
class OutboxEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'topic', 'status', 'attempts', 'next_attempt_at', 'processed_at')
    list_filter = ('status', 'topic')
    readonly_fields = ('topic', 'payload', 'dedupe_key', 'status', 'attempts', 'next_attempt_at', 'created_at',
                       'processed_at')

    def has_add_permission(self, request):
        return False
