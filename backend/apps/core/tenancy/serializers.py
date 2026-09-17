from rest_framework import serializers


class TenantOwnershipValidationMixin:
    """
    Mixin for create/update serializers whose model has a client-writable
    FK named `hostel` (override `hostel_field_name` if it's named
    differently). Validates that the referenced hostel actually belongs
    to the requesting user. If the field is None (nullable/global case),
    validation is skipped for that field.
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


class UserOwnershipValidationMixin:
    """
    Mixin for create/update serializers whose model has a client-writable
    FK that must point back to the requesting user themself (e.g. a
    review's `hostel` is validated by TenantOwnershipValidationMixin's
    sibling concept doesn't apply here — this is for the rarer case where
    a client can supply a user-identifying FK directly and it must match
    request.user). Most user-scoped create paths instead set the FK to
    request.user server-side in perform_create() and never accept it from
    the client at all — prefer that pattern where possible; use this
    mixin only when the field must be client-writable for some reason.
    """
    user_field_name = "user"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        value = attrs.get(self.user_field_name)
        request = self.context.get("request")
        if value is not None and request is not None:
            if value != request.user:
                raise serializers.ValidationError({
                    self.user_field_name: "You do not have permission to "
                                           "act on behalf of another user."
                })
        return attrs
