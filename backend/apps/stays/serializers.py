from rest_framework import serializers

from .models import Stay


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
