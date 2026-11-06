from django.utils import timezone
from rest_framework import serializers

from .models import Stay
from .services import OFFLINE_METHODS


class VacateRequestSerializer(serializers.Serializer):
    """The 'Request to vacate' board: a planned move-out date and one of four reasons."""
    planned_move_out_date = serializers.DateField()
    reason = serializers.ChoiceField(choices=Stay.VacateReason.choices)


class StayLifecycleSerializer(serializers.ModelSerializer):
    """What the two lifecycle actions answer with. The full stay payload (billing summary and so on) is Phase 7."""

    class Meta:
        model = Stay
        fields = ['id', 'status', 'planned_move_out_date', 'vacate_reason', 'vacate_requested_at', 'ended_at']
        read_only_fields = fields


class StayErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    error = serializers.CharField()


class RecordPaymentSerializer(serializers.Serializer):
    """The AdminRecord board: when it was paid (date and time), how, and a reference note."""
    paid_at = serializers.DateTimeField()
    method = serializers.ChoiceField(choices=[(m, m) for m in OFFLINE_METHODS])
    reference_note = serializers.CharField(max_length=200)

    def validate_paid_at(self, value):
        if value > timezone.now():
            raise serializers.ValidationError('The payment time cannot be in the future.')
        return value


class VoidPaymentSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=200)


class RentPaymentRecordSerializer(serializers.Serializer):
    """What recording rent answers with: the receipt data the owner and, later, the student's receipt screen need."""
    payment_id = serializers.UUIDField()
    due_id = serializers.UUIDField()
    status = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    paid_at = serializers.DateTimeField()
    method = serializers.CharField()
    source = serializers.CharField()
    receipt_number = serializers.CharField()

