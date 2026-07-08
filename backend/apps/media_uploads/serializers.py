from rest_framework import serializers
from .models import MediaItem

class MediaItemSerializer(serializers.ModelSerializer):
    remote_url = serializers.ReadOnlyField()
    
    class Meta:
        model = MediaItem
        fields = '__all__'
        read_only_fields = ('id', 'created_at')
