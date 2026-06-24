from rest_framework import serializers
from .models import Booking

class BookingSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    
    class Meta:
        model = Booking
        fields = '__all__'
        read_only_fields = ('id', 'requested_at', 'updated_at')
        extra_kwargs = {
            'id': {'source': 'booking_id'}
        }

    def get_user(self, obj):
        return {
            'user_id': obj.user_id,
            'name': obj.user_name,
            'email': obj.user_email,
            'phone': obj.user_phone,
            'profile_photo_url': obj.user_profile_photo
        }

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Rename id to booking_id
        ret['booking_id'] = ret.pop('id')
        ret['hostel_id'] = ret.pop('hostel')
        ret['room_id'] = ret.pop('room')
        
        # Remove flat user fields from response since we nest them under 'user'
        ret.pop('user_name', None)
        ret.pop('user_email', None)
        ret.pop('user_phone', None)
        ret.pop('user_profile_photo', None)
        
        return ret
