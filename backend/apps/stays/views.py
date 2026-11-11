"""
Stay lifecycle endpoints (Phase 5):

    POST /api/v1/stays/<id>/vacate-request/   the student asks to move out      (IsResourceUser: the stay's own student)
    POST /api/v1/stays/<id>/end/              the owner or an admin ends it      (IsTenantOwner, or staff)
    POST /api/v1/stays/dues/<id>/record-payment/  the owner records rent paid offline (IsTenantOwner, or staff)
    POST /api/v1/stays/dues/<id>/void-payment/    the owner takes that record back    (IsTenantOwner, or staff)

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
from .models import Due, Stay
from .serializers import (
    RecordPaymentSerializer, RentPaymentRecordSerializer, StayErrorSerializer, StayLifecycleSerializer,
    VacateRequestSerializer, VoidPaymentSerializer,
)


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


def _payment_record(payment):
    return {
        'payment_id': payment.id, 'due_id': payment.due_id, 'status': payment.status, 'amount': payment.amount,
        'paid_at': payment.verified_at, 'method': payment.paid_via, 'source': payment.source,
        'receipt_number': payment.receipt_number,
    }


def _owned_due(request, pk):
    """The due, for its hostel's owner or an admin; a due that is not yours answers 404."""
    if request.user.is_staff:
        return get_object_or_404(Due, pk=pk)
    return get_tenant_scoped_object_or_404(Due, pk, request)


class DueRecordPaymentView(APIView):
    permission_classes = [IsAuthenticated, IsTenantOwnerOrStaff]

    @extend_schema(request=RecordPaymentSerializer,
                   responses={201: RentPaymentRecordSerializer, 400: StayErrorSerializer, 409: StayErrorSerializer},
                   summary='Record rent paid offline (owner or admin)')
    def post(self, request, pk):
        due = _owned_due(request, pk)
        self.check_object_permissions(request, due)
        data = RecordPaymentSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            payment = services.record_offline_payment(
                due, request.user, data.validated_data['paid_at'], data.validated_data['method'],
                data.validated_data['reference_note'])
        except services.StayError as exc:
            return _refusal(exc)
        return Response(RentPaymentRecordSerializer(_payment_record(payment)).data, status=status.HTTP_201_CREATED)


class DueSendReminderView(APIView):
    """POST /stays/dues/<id>/send-reminder/ : the Send reminder button on the AdminDues board."""
    permission_classes = [IsAuthenticated, IsTenantOwnerOrStaff]

    @extend_schema(request=None, responses={202: dict, 409: StayErrorSerializer, 429: StayErrorSerializer},
                   summary='Send a rent reminder now (owner or admin; once per due per day)')
    def post(self, request, pk):
        from apps.notifications import services as notification_services
        due = _owned_due(request, pk)
        self.check_object_permissions(request, due)
        due = Due.objects.select_related('stay').get(pk=due.pk)
        try:
            notification_services.request_manual_reminder(due)
        except services.StayError as exc:
            return _refusal(exc)
        return Response({'status': 'queued'}, status=status.HTTP_202_ACCEPTED)


class DueVoidPaymentView(APIView):
    permission_classes = [IsAuthenticated, IsTenantOwnerOrStaff]

    @extend_schema(request=VoidPaymentSerializer,
                   responses={200: RentPaymentRecordSerializer, 400: StayErrorSerializer, 409: StayErrorSerializer},
                   summary='Void an offline rent record (owner or admin)')
    def post(self, request, pk):
        due = _owned_due(request, pk)
        self.check_object_permissions(request, due)
        data = VoidPaymentSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            payment = services.void_offline_payment(due, request.user, data.validated_data['reason'])
        except services.StayError as exc:
            return _refusal(exc)
        return Response(RentPaymentRecordSerializer(_payment_record(payment)).data, status=status.HTTP_200_OK)

