from rest_framework import serializers
from .models import Payment
from apps.core.serializers import TenantOwnershipValidationMixin

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')

class PaymentCreateSerializer(TenantOwnershipValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = Payment
        exclude = ('status', 'marked_by', 'created_at', 'updated_at')
