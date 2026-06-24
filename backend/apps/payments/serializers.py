from rest_framework import serializers
from .models import Payment

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ('id', 'created_at')
        extra_kwargs = {
            'id': {'source': 'payment_id'}
        }

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Rename id to payment_id
        ret['payment_id'] = ret.pop('id')
        ret['booking_id'] = ret.pop('booking')
        ret['hostel_id'] = ret.pop('hostel')
        return ret
