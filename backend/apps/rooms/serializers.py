from rest_framework import serializers
from .models import Room

class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')
        extra_kwargs = {
            'id': {'source': 'room_id'}
        }

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Rename id to room_id
        ret['room_id'] = ret.pop('id')
        ret['hostel_id'] = ret.pop('hostel')
        return ret
