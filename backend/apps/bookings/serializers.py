from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import APIException
from apps.rooms.models import Bed
from apps.stays import services as stay_services
from .models import Booking


class ActiveStayExists(APIException):
    """409 for a signed-in student who already has a current stay (decision D2): the BookingBlocked board."""
    status_code = 409
    default_code = 'ACTIVE_STAY_EXISTS'


class BookingSerializer(serializers.ModelSerializer):
    """Full read serializer — enriches FKs with human-readable names."""
    hostel_name = serializers.CharField(source='hostel.name', read_only=True)
    room_display = serializers.SerializerMethodField()
    # The stay this paid booking became (Phase 9). Read from the row the view already loaded: no query per booking.
    stay_id = serializers.SerializerMethodField()
    stay_status = serializers.SerializerMethodField()
    stay_needs_review = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            'id',
            'hostel', 'hostel_name',
            'room', 'room_display',
            'room_name', 'floor_number', 'room_number', 'bed_number',
            'student_name', 'student_phone',
            'check_in_date', 'check_out_date',
            'payment_mode', 'status', 'amount',
            'notes',
            'marked_paid_by', 'marked_paid_at',
            'stay_id', 'stay_status', 'stay_needs_review',
            'created_at', 'updated_at',
        ]
        read_only_fields = ('id', 'created_at', 'updated_at', 'marked_paid_at', 'hostel_name', 'room_display')

    @staticmethod
    def _stay(obj):
        return obj._state.fields_cache.get('stay')  # loaded by select_related('stay'); never triggers a query

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_stay_id(self, obj):
        stay = self._stay(obj)
        return str(stay.id) if stay else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_stay_status(self, obj):
        stay = self._stay(obj)
        return stay.status if stay else None

    @extend_schema_field(serializers.BooleanField())
    def get_stay_needs_review(self, obj):
        stay = self._stay(obj)
        return bool(stay and stay.needs_review)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_room_display(self, obj):
        """Return room name from FK if linked, else fall back to denormalised field."""
        if obj.room:
            return obj.room.room_name
        return obj.room_name or None


class BookingCreateSerializer(serializers.ModelSerializer):
    """Write serializer used by the Flutter app to create a new booking."""

    class Meta:
        model = Booking
        fields = [
            'id',
            'hostel',
            'room',
            'room_name', 'floor_number', 'room_number', 'bed_number',
            'student_name', 'student_phone',
            'check_in_date',
            'payment_mode',
            'amount',
            'notes',
        ]
        extra_kwargs = {
            'room': {'required': False, 'allow_null': True},
            'room_name': {'required': False, 'allow_null': True},
            'floor_number': {'required': False, 'allow_null': True},
            'room_number': {'required': False, 'allow_null': True},
            'bed_number': {'required': False, 'allow_null': True},
            'student_name': {'required': False, 'default': ''},
            'student_phone': {'required': False, 'default': ''},
            'check_in_date': {'required': False, 'allow_null': True},
            'amount': {'required': False, 'allow_null': True},
            'notes': {'required': False, 'allow_null': True},
        }

    def validate(self, attrs):
        # D2/E3: one current stay per student. Only for a signed-in student; an anonymous booking is allowed, and a second
        # PAID booking is never refused after the money is taken (it makes a stay flagged needs_review instead).
        request = self.context.get('request')
        current = stay_services.find_current_stay(getattr(request, 'user', None))
        if current is not None:
            raise ActiveStayExists({
                'code': 'ACTIVE_STAY_EXISTS',
                'message': 'You already have a current stay. You can hold one stay at a time, so booking another '
                           'hostel opens after your current stay ends.',
                'current_stay': stay_services.current_stay_payload(current),
            })
        # A bed that is already paid for cannot be requested again. (Beds are locked when a payment starts;
        # this only keeps an obviously taken bed from reaching the owner as a new request.)
        room, number = attrs.get('room'), attrs.get('bed_number')
        if room is not None and number:
            try:
                number = int(number)
            except (TypeError, ValueError):
                return attrs
            if Bed.objects.filter(room=room, bed_number=number, is_available=False).exists():
                raise serializers.ValidationError({'bed_number': 'This bed is no longer available.'})
        return attrs

    def create(self, validated_data):
        validated_data['status'] = 'pending'
        # Auto-link the authenticated student user
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            user = request.user
            validated_data['student'] = user
            # The app sends the profile's name and phone, but a blank must not reach the owner.
            if not (validated_data.get('student_name') or '').strip():
                validated_data['student_name'] = user.display_name or ''
            if not (validated_data.get('student_phone') or '').strip():
                validated_data['student_phone'] = user.phone_number or ''
        return super().create(validated_data)
