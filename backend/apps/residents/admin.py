from django.contrib import admin
from .models import Resident

@admin.register(Resident)
class ResidentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'hostel', 'room', 'status', 'move_in_date')
    list_filter = ('status', 'hostel')
    search_fields = ('name', 'phone', 'id_proof_number')
