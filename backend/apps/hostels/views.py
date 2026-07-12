from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Hostel
from .serializers import HostelSerializer
from utils.permissions import IsOwner


class PublicHostelSerializer(HostelSerializer):
    """Safe read-only serializer for unauthenticated public listing."""
    class Meta(HostelSerializer.Meta):
        # Explicitly list public-safe fields (exclude 'owner' UUID)
        fields = [
            'id', 'name', 'owner_name', 'contact_number', 'email',
            'address', 'city', 'state', 'pincode', 'landmark',
            'latitude', 'longitude', 'google_maps_url',
            'gender_type', 'total_floors', 'total_rooms', 'total_beds',
            'occupancy_types', 'description', 'rules',
            'check_in_policy', 'check_out_policy',
            'amenities', 'is_active', 'is_verified',
            'created_at', 'updated_at',
            'rooms', 'media',
        ]

    def to_representation(self, instance):
        # Skip parent's to_representation (which tries to pop 'owner')
        # Call grandparent directly
        from rest_framework import serializers
        ret = serializers.ModelSerializer.to_representation(self, instance)
        # Rename id → hostel_id to match Flutter model expectation
        if 'id' in ret:
            ret['hostel_id'] = ret.pop('id')
        return ret


class HostelViewSet(viewsets.ModelViewSet):
    serializer_class = HostelSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated(), IsOwner()]

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return PublicHostelSerializer
        return HostelSerializer

    def get_queryset(self):
        if self.action in ['list', 'retrieve']:
            qs = Hostel.objects.filter(is_active=True).prefetch_related('rooms', 'media')
            # Optional filter by gender_type query param
            gender = self.request.query_params.get('gender_type')
            if gender:
                qs = qs.filter(gender_type=gender)
            return qs
        # Only return hostels owned by the current user
        return Hostel.objects.filter(owner=self.request.user).prefetch_related('rooms', 'media')

    def perform_create(self, serializer):
        # Auto-set the owner to the current user
        serializer.save(owner=self.request.user)

