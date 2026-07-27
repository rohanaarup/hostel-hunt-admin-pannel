from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.utils import timezone
from .models import Resident
from .serializers import ResidentSerializer, ResidentCreateSerializer
from apps.core.querysets import TenantScopedQuerysetMixin
from apps.core.utils import get_tenant_scoped_object_or_404

class ResidentListView(TenantScopedQuerysetMixin, generics.ListAPIView):
    serializer_class = ResidentSerializer
    permission_classes = [IsAuthenticated]
    queryset = Resident.objects.all()

class ResidentCreateView(generics.CreateAPIView):
    serializer_class = ResidentCreateSerializer
    permission_classes = [IsAuthenticated]

class ResidentMarkVacatedView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        resident = get_tenant_scoped_object_or_404(Resident, pk, request)

        if resident.status != 'active':
            return Response({"error": "Resident is already vacated"}, status=status.HTTP_400_BAD_REQUEST)

        resident.status = 'vacated'
        resident.save(update_fields=['status', 'updated_at'])

        serializer = ResidentSerializer(resident)
        return Response({"success": True, "data": serializer.data})
