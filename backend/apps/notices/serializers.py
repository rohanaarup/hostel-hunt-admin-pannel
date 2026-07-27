from rest_framework import serializers
from .models import Notice
from apps.core.serializers import TenantOwnershipValidationMixin

class NoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notice
        fields = '__all__'
        read_only_fields = ('id', 'posted_by', 'posted_at', 'created_at', 'updated_at')

class NoticeCreateSerializer(TenantOwnershipValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = Notice
        exclude = ('posted_by', 'posted_at', 'created_at', 'updated_at')

class NoticeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notice
        fields = ('title', 'body', 'expires_at', 'is_active')
