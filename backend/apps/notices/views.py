from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, BasePermission
from django.db.models import Q
from .models import Notice
from .serializers import NoticeSerializer, NoticeCreateSerializer, NoticeUpdateSerializer
from apps.core.tenancy.utils import is_tenant_owner
from apps.core.tenancy.querysets import tenant_scope_q


class IsNoticeTenantOwner(BasePermission):
    """
    Object-level counterpart to NoticeTenantScopedQuerysetMixin below —
    the generic IsTenantOwner can't express the null-hostel/posted_by
    fallback, so it would (wrongly) reject a global notice its own
    poster is otherwise allowed to see via the queryset. Mirrors the
    exact same two-condition rule instead of just deferring to
    OWNER_LOOKUP.
    """

    def has_object_permission(self, request, view, obj):
        if obj.hostel_id is None:
            return obj.posted_by_id == request.user.id
        return is_tenant_owner(obj, request.user)


class NoticeTenantScopedQuerysetMixin:
    """
    Notice-specific scoping: hostel__owner covers the normal case, plus a
    fallback for legacy/global notices with hostel=NULL, which are scoped
    to whoever posted them instead (see Notice.OWNER_LOOKUP's docstring).
    A plain TenantScopedQuerysetMixin can't express this OR-with-a-second-
    condition shape, so it's written out here rather than forced into the
    generic mixin.
    """

    def get_queryset(self):
        base_qs = super().get_queryset()
        user = self.request.user
        if not user or not user.is_authenticated:
            return base_qs.none()
        return base_qs.filter(
            tenant_scope_q(Notice, user) | Q(hostel__isnull=True, posted_by=user)
        )


class NoticeListView(NoticeTenantScopedQuerysetMixin, generics.ListAPIView):
    serializer_class = NoticeSerializer
    permission_classes = [IsAuthenticated]
    queryset = Notice.objects.all()


class NoticeCreateView(generics.CreateAPIView):
    serializer_class = NoticeCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(posted_by=self.request.user)


class NoticeUpdateView(NoticeTenantScopedQuerysetMixin, generics.UpdateAPIView):
    serializer_class = NoticeUpdateSerializer
    permission_classes = [IsAuthenticated, IsNoticeTenantOwner]
    queryset = Notice.objects.all()


class NoticeDeleteView(NoticeTenantScopedQuerysetMixin, generics.DestroyAPIView):
    permission_classes = [IsAuthenticated, IsNoticeTenantOwner]
    queryset = Notice.objects.all()
