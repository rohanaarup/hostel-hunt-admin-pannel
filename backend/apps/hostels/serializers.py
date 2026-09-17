from rest_framework import serializers
from .models import Hostel
from apps.rooms.serializers import RoomSerializer
from apps.media_uploads.serializers import MediaItemSerializer
from apps.rooms.models import Room
from apps.media_uploads.models import MediaItem


class HostelListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for the public hostel LIST endpoint.

    HostelSerializer/PublicHostelSerializer nest the full `rooms` and
    `media` arrays (every field of every room/media row) on every hostel,
    which is fine for a single detail view but expensive across a whole
    list. This serializer instead exposes: a starting/ending price range,
    a single cover image URL, and room/bed counts — all populated via
    queryset-level annotations (see HostelViewSet.get_queryset) rather
    than per-instance queries, so listing N hostels stays a fixed number
    of queries regardless of N.
    """
    cover_image = serializers.SerializerMethodField()
    price_from = serializers.SerializerMethodField()
    price_to = serializers.SerializerMethodField()
    room_count = serializers.SerializerMethodField()
    bed_count = serializers.SerializerMethodField()

    class Meta:
        model = Hostel
        fields = [
            'id', 'name', 'locality', 'address', 'city', 'state',
            'gender_type', 'is_active', 'is_verified',
            'cover_image', 'price_from', 'price_to',
            'room_count', 'bed_count',
            'created_at', 'updated_at',
        ]

    def get_cover_image(self, obj):
        return getattr(obj, 'cover_image', None)

    def get_price_from(self, obj):
        return getattr(obj, 'price_from', None)

    def get_price_to(self, obj):
        return getattr(obj, 'price_to', None)

    def get_room_count(self, obj):
        return getattr(obj, 'room_count', None) or 0

    def get_bed_count(self, obj):
        return getattr(obj, 'bed_count', None) or 0

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['hostel_id'] = ret.pop('id')
        return ret

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
