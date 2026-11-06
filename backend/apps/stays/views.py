"""
Stay lifecycle endpoints (Phase 5):

    POST /api/v1/stays/<id>/vacate-request/   the student asks to move out      (IsResourceUser: the stay's own student)
    POST /api/v1/stays/<id>/end/              the owner or an admin ends it      (IsTenantOwner, or staff)

Reading stays (lists, detail, dues) is Phase 7. The object is always fetched through the scoped helpers, so a stay that is
not yours answers 404, exactly like a stay that does not exist.
"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.tenancy.permissions import IsResourceUser, IsTenantOwner
from apps.core.tenancy.utils import get_tenant_scoped_object_or_404, get_user_scoped_object_or_404

from . import services
from .models import Stay
from .serializers import StayErrorSerializer, StayLifecycleSerializer, VacateRequestSerializer


class IsTenantOwnerOrStaff(IsTenantOwner):
    """The hostel's owner, or an admin (is_staff), may end a stay."""

    def has_object_permission(self, request, view, obj):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated and user.is_staff:
            return True
        return super().has_object_permission(request, view, obj)


def _refusal(exc):
    return Response({'code': exc.code, 'message': exc.message, 'error': exc.message}, status=exc.http_status)


class StayVacateRequestView(APIView):
    permission_classes = [IsAuthenticated, IsResourceUser]

    @extend_schema(request=VacateRequestSerializer, responses={200: StayLifecycleSerializer, 400: StayErrorSerializer,
                                                              409: StayErrorSerializer},
                   summary='Ask to vacate (student)')
    def post(self, request, pk):
        stay = get_user_scoped_object_or_404(Stay, pk, request)
        self.check_object_permissions(request, stay)
        data = VacateRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            stay = services.request_vacate(stay, data.validated_data['planned_move_out_date'],
                                           data.validated_data['reason'])
        except services.StayError as exc:
            return _refusal(exc)
        return Response(StayLifecycleSerializer(stay).data, status=status.HTTP_200_OK)


class StayEndView(APIView):
    permission_classes = [IsAuthenticated, IsTenantOwnerOrStaff]

    @extend_schema(request=None, responses={200: StayLifecycleSerializer, 409: StayErrorSerializer},
                   summary='End a stay (owner or admin)')
    def post(self, request, pk):
        if request.user.is_staff:
            stay = get_object_or_404(Stay, pk=pk)
        else:
            stay = get_tenant_scoped_object_or_404(Stay, pk, request)
        self.check_object_permissions(request, stay)
        try:
            stay, _ = services.end_stay(stay)
        except services.StayError as exc:
            return _refusal(exc)
        return Response(StayLifecycleSerializer(stay).data, status=status.HTTP_200_OK)
