from rest_framework import serializers


class TenantOwnershipValidationMixin:
    """
    Mixin for create/update serializers whose model has a client-writable
    FK named `hostel`. Validates that the referenced hostel actually
    belongs to the requesting user. If `hostel` is None (nullable/global
    case), validation is skipped for that field.
    """
    hostel_field_name = "hostel"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        hostel = attrs.get(self.hostel_field_name)
        request = self.context.get("request")
        if hostel is not None and request is not None:
            if hostel.owner != request.user:
                raise serializers.ValidationError({
                    self.hostel_field_name: "You do not have permission to "
                                             "add data to this hostel."
                })
        return attrs
