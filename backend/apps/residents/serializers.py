from rest_framework import serializers
from .models import Resident
from apps.core.serializers import TenantOwnershipValidationMixin

class ResidentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resident
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')

class ResidentCreateSerializer(TenantOwnershipValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = Resident
        exclude = ('status', 'created_at', 'updated_at')
