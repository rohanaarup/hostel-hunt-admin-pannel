from rest_framework import serializers
from .models import Hostel
from apps.rooms.serializers import RoomSerializer
from apps.media_uploads.serializers import MediaItemSerializer
from apps.rooms.models import Room
from apps.media_uploads.models import MediaItem

class HostelSerializer(serializers.ModelSerializer):
    rooms = RoomSerializer(many=True, read_only=True)
    media = MediaItemSerializer(many=True, read_only=True)
    
    rooms_data = serializers.ListField(child=serializers.DictField(), write_only=True, required=False)
    media_ids = serializers.ListField(child=serializers.UUIDField(), write_only=True, required=False)

    class Meta:
        model = Hostel
        fields = '__all__'
        read_only_fields = ('id', 'owner', 'created_at', 'updated_at', 'is_verified')

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Rename id to hostel_id
        ret['hostel_id'] = ret.pop('id')
        # Map owner to owner_id
        ret['owner_id'] = ret.pop('owner')
        return ret

    def create(self, validated_data):
        rooms_data = validated_data.pop('rooms_data', [])
        media_ids = validated_data.pop('media_ids', [])
        
        hostel = super().create(validated_data)
        
        for room_data in rooms_data:
            # Pop frontend-only draft id if present
            room_data.pop('_draft_id', None)
            room_data.pop('photos', None)
            room_data.pop('room_id', None)
            room_data.pop('id', None)
            if 'sharing_type' in room_data and not room_data['sharing_type']:
                room_data.pop('sharing_type')
            Room.objects.create(hostel=hostel, **room_data)
            
        if media_ids:
            MediaItem.objects.filter(id__in=media_ids).update(hostel=hostel)
            
        return hostel

    def update(self, instance, validated_data):
        rooms_data = validated_data.pop('rooms_data', None)
        media_ids = validated_data.pop('media_ids', None)
        
        hostel = super().update(instance, validated_data)
        
        if rooms_data is not None:
            existing_room_ids = [str(r.id) for r in instance.rooms.all()]
            incoming_ids = []
            
            for room_data in rooms_data:
                room_data.pop('_draft_id', None)
                room_data.pop('photos', None)
                room_id = room_data.pop('room_id', None) or room_data.pop('id', None)
                
                if 'sharing_type' in room_data and not room_data['sharing_type']:
                    room_data.pop('sharing_type')
                
                if room_id and str(room_id) in existing_room_ids:
                    Room.objects.filter(id=room_id).update(**room_data)
                    incoming_ids.append(str(room_id))
                else:
                    new_room = Room.objects.create(hostel=hostel, **room_data)
                    incoming_ids.append(str(new_room.id))
                    
            Room.objects.filter(hostel=hostel).exclude(id__in=incoming_ids).delete()
            
        if media_ids is not None:
            # Only link new ones; do not aggressively delete media missing from the list 
            # unless we explicitly want to. For safety, let's just update the ones passed.
            MediaItem.objects.filter(id__in=media_ids).update(hostel=hostel)
            
        return hostel
