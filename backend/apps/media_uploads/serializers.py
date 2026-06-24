from rest_framework import serializers
from .models import MediaItem

class MediaItemSerializer(serializers.ModelSerializer):
    remote_url = serializers.ReadOnlyField()
    
    class Meta:
        model = MediaItem
        fields = '__all__'
        read_only_fields = ('id', 'created_at')

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Ensure we return remote_url which frontend expects
        if 'file' in ret and not ret.get('remote_url'):
             ret['remote_url'] = ret['file']
        return ret
