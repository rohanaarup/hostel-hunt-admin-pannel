from rest_framework import viewsets, permissions
from .models import Room
from .serializers import RoomSerializer
from utils.permissions import IsOwner
from apps.core.querysets import TenantScopedQuerysetMixin

class RoomViewSet(TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    serializer_class = RoomSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    queryset = Room.objects.all()

    def get_queryset(self):
        # TenantScopedQuerysetMixin restricts to rooms owned by request.user.
        # Additionally filter by hostel_id when coming from a nested route.
        qs = super().get_queryset()
        hostel_id = self.kwargs.get('hostel_id')
        if hostel_id:
            qs = qs.filter(hostel_id=hostel_id)
        return qs

    def perform_create(self, serializer):
        # The hostel is passed in the payload, but we could also extract it from URL.
        # We need to verify the user owns the hostel they are adding a room to.
        # This is handled mostly by validation, but we can double check here or in serializer.
        hostel = serializer.validated_data.get('hostel')
        if hostel and hostel.owner == self.request.user:
            serializer.save()
        else:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not own this hostel.")
