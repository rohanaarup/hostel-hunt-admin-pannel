from rest_framework import serializers
from .models import Hostel

class HostelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hostel
        fields = '__all__'
        read_only_fields = ('id', 'owner', 'created_at', 'updated_at', 'is_verified')
        extra_kwargs = {
            'id': {'source': 'hostel_id'}
        }

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Rename id to hostel_id
        ret['hostel_id'] = ret.pop('id')
        # Map owner to owner_id
        ret['owner_id'] = ret.pop('owner')
        return ret
