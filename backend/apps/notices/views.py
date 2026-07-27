from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Notice
from .serializers import NoticeSerializer, NoticeCreateSerializer, NoticeUpdateSerializer
from apps.core.querysets import TenantScopedQuerysetMixin

class NoticeListView(TenantScopedQuerysetMixin, generics.ListAPIView):
    serializer_class = NoticeSerializer
    permission_classes = [IsAuthenticated]
    queryset = Notice.objects.all()

class NoticeCreateView(generics.CreateAPIView):
    serializer_class = NoticeCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(posted_by=self.request.user)

class NoticeUpdateView(TenantScopedQuerysetMixin, generics.UpdateAPIView):
    serializer_class = NoticeUpdateSerializer
    permission_classes = [IsAuthenticated]
    queryset = Notice.objects.all()

class NoticeDeleteView(TenantScopedQuerysetMixin, generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Notice.objects.all()
