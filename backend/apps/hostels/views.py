from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Hostel
from .serializers import HostelSerializer
from utils.permissions import IsOwner

class HostelViewSet(viewsets.ModelViewSet):
    serializer_class = HostelSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated(), IsOwner()]

    def get_queryset(self):
        if self.action in ['list', 'retrieve']:
            return Hostel.objects.all().prefetch_related('rooms', 'media')
        # Only return hostels owned by the current user
        return Hostel.objects.filter(owner=self.request.user).prefetch_related('rooms', 'media')

    def perform_create(self, serializer):
        # Auto-set the owner to the current user
        serializer.save(owner=self.request.user)
