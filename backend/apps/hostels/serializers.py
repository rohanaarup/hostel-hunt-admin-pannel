from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from apps.core.images import LIST_WIDTH, sized_image_url
from apps.core.tenancy.querysets import tenant_scope_q
from .locations import resolve_city, resolve_localities
from .models import City, Hostel, Locality
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
            'gender_type', 'is_active', 'is_verified', 'amenities',
            'cover_image', 'price_from', 'price_to',
            'room_count', 'bed_count',
            'created_at', 'updated_at',
        ]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_cover_image(self, obj):
        return sized_image_url(getattr(obj, 'cover_image', None), LIST_WIDTH)

    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_price_from(self, obj):
        return getattr(obj, 'price_from', None)

    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_price_to(self, obj):
        return getattr(obj, 'price_to', None)

    @extend_schema_field(serializers.IntegerField())
    def get_room_count(self, obj):
        return getattr(obj, 'room_count', None) or 0

    @extend_schema_field(serializers.IntegerField())
    def get_bed_count(self, obj):
        return getattr(obj, 'bed_count', None) or 0

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['hostel_id'] = ret.pop('id')
        return ret

# What a hostel save may send for a room. Anything else is refused with a 400 instead of crashing the save.
ROOM_WRITABLE = {f.name for f in Room._meta.concrete_fields} - {'id', 'hostel', 'created_at', 'updated_at'}
ROOM_DRAFT_KEYS = {'_draft_id', 'photos', 'room_id', 'id'}  # sent by the admin wizard, never stored on the room


class HostelSerializer(serializers.ModelSerializer):
    rooms = RoomSerializer(many=True, read_only=True)
    media = MediaItemSerializer(many=True, read_only=True)
    
    rooms_data = serializers.ListField(child=serializers.DictField(), write_only=True, required=False)
    media_ids = serializers.ListField(child=serializers.UUIDField(), write_only=True, required=False)
    # Preferred way to set the place: ids from GET /cities/ and /cities/{slug}/localities/.
    city_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    locality_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Hostel
        fields = '__all__'
        read_only_fields = ('id', 'owner', 'created_at', 'updated_at', 'is_verified', 'city_ref', 'locality_ref')
        # The text fields stay accepted (legacy clients); with city_id / locality_id they are filled in.
        extra_kwargs = {
            'city': {'required': False}, 'locality': {'required': False}, 'state': {'required': False},
        }

    def validate_rooms_data(self, rows):
        for number, row in enumerate(rows, start=1):
            unknown = sorted(set(row) - ROOM_WRITABLE - ROOM_DRAFT_KEYS)
            if unknown:
                raise serializers.ValidationError(f"Room {number} has fields that cannot be saved: {', '.join(unknown)}.")
        return rows

    @staticmethod
    def _room_values(row):
        values = {key: value for key, value in row.items() if key not in ROOM_DRAFT_KEYS}
        if 'sharing_type' in values and not values['sharing_type']:
            values.pop('sharing_type')
        return values

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Rename id to hostel_id
        ret['hostel_id'] = ret.pop('id')
        # Map owner to owner_id
        ret['owner_id'] = ret.pop('owner')
        ret['city_id'] = ret.pop('city_ref')
        ret['locality_id'] = ret.pop('locality_ref')
        return ret

    def validate(self, attrs):
        attrs = super().validate(attrs)
        city = locality = None
        city_given = locality_given = False

        if attrs.get('city_id'):
            city_given = True
            city = City.objects.filter(pk=attrs['city_id'], is_active=True).first()
            if city is None:
                raise serializers.ValidationError({'city_id': 'Unknown or inactive city.'})
        elif (attrs.get('city') or '').strip():
            city_given = True
            city = resolve_city(attrs['city'])
        elif 'city_id' in attrs or 'city' in attrs:
            city_given = True

        if attrs.get('locality_id'):
            locality_given = True
            locality = Locality.objects.select_related('city').filter(pk=attrs['locality_id'], is_active=True).first()
            if locality is None:
                raise serializers.ValidationError({'locality_id': 'Unknown or inactive locality.'})
            if city is not None and locality.city_id != city.pk:
                raise serializers.ValidationError({'locality_id': f'{locality.name} is not in {city.name}.'})
            if city is None and not city_given:
                city, city_given = locality.city, True
        elif (attrs.get('locality') or '').strip():
            locality_given = True
            matches = resolve_localities(attrs['locality'], city) if city is not None else []
            locality = matches[0] if matches else None
        elif 'locality_id' in attrs or 'locality' in attrs:
            locality_given = True
        attrs.pop('city_id', None)
        attrs.pop('locality_id', None)

        if city_given:
            attrs['city_ref'] = city
            if city is not None:
                attrs['city'] = city.name
                if not (attrs.get('state') or '').strip():
                    attrs['state'] = city.state
        if locality_given:
            attrs['locality_ref'] = locality
            if locality is not None:
                attrs['locality'] = locality.name

        if self.instance is None:  # creating: the place is still required, as before
            for field in ('city', 'locality', 'state'):
                if not (attrs.get(field) or '').strip():
                    raise serializers.ValidationError({field: 'This field is required.'})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """The hostel, all its rooms (one INSERT) and its media links are saved together or not at all."""
        rooms_data = validated_data.pop('rooms_data', [])
        media_ids = validated_data.pop('media_ids', [])

        hostel = super().create(validated_data)

        rooms = [Room(hostel=hostel, **self._room_values(row)) for row in rooms_data]
        if rooms:
            Room.objects.bulk_create(rooms)

        if media_ids:
            self._link_media(hostel, media_ids)

        return hostel

    def _link_media(self, hostel, media_ids):
        """Attach uploaded media to the hostel, but only media the signed-in owner may link: media that
        nobody has claimed yet (uploaded before the hostel existed) or that is already on one of their
        own hostels. Someone else's media is skipped, never moved."""
        user = self.context['request'].user
        allowed = Q(hostel__isnull=True, room__isnull=True) | tenant_scope_q(MediaItem, user)
        MediaItem.objects.filter(allowed, id__in=media_ids).update(hostel=hostel)

    @transaction.atomic
    def update(self, instance, validated_data):
        """One transaction. A room left out of the list is deleted only if nothing refers to it; a room that has
        bookings is deactivated instead (it disappears from the public hostel but keeps its bookings and beds).
        Sending a deactivated room again reactivates it."""
        rooms_data = validated_data.pop('rooms_data', None)
        media_ids = validated_data.pop('media_ids', None)

        hostel = super().update(instance, validated_data)

        if rooms_data is not None:
            existing = {str(r.id): r for r in Room.objects.filter(hostel=hostel)}
            kept_ids, new_rooms, changed, fields = set(), [], [], {'is_active', 'updated_at'}
            now = timezone.now()

            for row in rooms_data:
                room_id = row.get('room_id') or row.get('id')
                values = self._room_values(row)
                values.setdefault('is_active', True)
                room = existing.get(str(room_id)) if room_id else None
                if room is not None:
                    for name, value in values.items():
                        setattr(room, name, value)
                    room.updated_at = now
                    fields.update(values)
                    changed.append(room)
                    kept_ids.add(str(room.id))
                else:
                    new_rooms.append(Room(hostel=hostel, **values))

            if changed:
                Room.objects.bulk_update(changed, sorted(fields))  # one UPDATE for every changed room
            if new_rooms:
                kept_ids.update(str(room.id) for room in Room.objects.bulk_create(new_rooms))

            left_out = Room.objects.filter(hostel=hostel).exclude(id__in=kept_ids)
            with_bookings = list(left_out.filter(bookings__isnull=False).values_list('id', flat=True).distinct())
            if with_bookings:
                Room.objects.filter(id__in=with_bookings).update(is_active=False)
            left_out.exclude(id__in=with_bookings).delete()

        if media_ids is not None:
            # Only link new ones; do not aggressively delete media missing from the list
            # unless we explicitly want to. For safety, let's just update the ones passed.
            self._link_media(hostel, media_ids)

        return hostel
