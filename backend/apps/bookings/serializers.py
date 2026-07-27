from rest_framework import serializers
from .models import Booking


class BookingSerializer(serializers.ModelSerializer):
    """Full read serializer — enriches FKs with human-readable names."""
    hostel_name = serializers.CharField(source='hostel.name', read_only=True)
    room_display = serializers.SerializerMethodField()

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
            'created_at', 'updated_at',
        ]
        read_only_fields = ('id', 'created_at', 'updated_at', 'marked_paid_at', 'hostel_name', 'room_display')

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

    def create(self, validated_data):
        validated_data['status'] = 'pending'
        return super().create(validated_data)
