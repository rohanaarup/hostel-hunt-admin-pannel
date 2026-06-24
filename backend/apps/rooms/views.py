from rest_framework import viewsets, permissions
from .models import Room
from .serializers import RoomSerializer
from utils.permissions import IsOwner

class RoomViewSet(viewsets.ModelViewSet):
    serializer_class = RoomSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        # We want to return rooms for a specific hostel. 
        # Usually this is nested: /api/v1/hostels/{hostel_id}/rooms/
        hostel_id = self.kwargs.get('hostel_id')
        if hostel_id:
            return Room.objects.filter(hostel_id=hostel_id, hostel__owner=self.request.user)
        # Fallback to all rooms owned by the user
        return Room.objects.filter(hostel__owner=self.request.user)

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
