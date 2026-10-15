from django.conf import settings
from rest_framework import serializers
from .models import MediaItem

CLOUDINARY_HOST = 'https://res.cloudinary.com/'

class MediaItemSerializer(serializers.ModelSerializer):
    remote_url = serializers.CharField(read_only=True)
    
    class Meta:
        model = MediaItem
        fields = '__all__'
        read_only_fields = ('id', 'created_at')

    def validate_file_url(self, value):
        """Media addresses come from a browser upload to Cloudinary. Anything else (http, another host,
        another account's cloud when ours is configured) is refused, so the site never shows or links to
        an address the owner typed."""
        cloud = settings.CLOUDINARY_CLOUD_NAME
        required = f'{CLOUDINARY_HOST}{cloud}/' if cloud else CLOUDINARY_HOST
        if not value.startswith(required):
            raise serializers.ValidationError('Upload the file through the site; this address is not accepted.')
        return value
