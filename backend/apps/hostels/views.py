from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Hostel
from .serializers import HostelSerializer
from utils.permissions import IsOwner

class HostelViewSet(viewsets.ModelViewSet):
    serializer_class = HostelSerializer
    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        # Only return hostels owned by the current user
        return Hostel.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        # Auto-set the owner to the current user
        serializer.save(owner=self.request.user)
