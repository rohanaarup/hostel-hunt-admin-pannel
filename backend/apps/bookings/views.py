from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.utils import timezone
from .models import Booking
from .serializers import BookingSerializer, BookingCreateSerializer
from apps.core.querysets import TenantScopedQuerysetMixin
from apps.core.utils import get_tenant_scoped_object_or_404


class BookingListView(TenantScopedQuerysetMixin, generics.ListCreateAPIView):
    """
    GET  /bookings/          — list bookings for the authenticated owner
    POST /bookings/          — create a new booking (public, from Flutter app)

    Query params (GET):
        payment_mode=offline|online
        status=pending|confirmed|paid|cancelled|rejected
    """
    queryset = Booking.objects.select_related('hostel', 'room')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return BookingCreateSerializer
        return BookingSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Booking.objects.none()

        # TenantScopedQuerysetMixin handles hostel__owner scoping via OWNER_LOOKUP.
        qs = super().get_queryset()
        payment_mode = self.request.query_params.get('payment_mode')
        if payment_mode:
            qs = qs.filter(payment_mode=payment_mode)
        booking_status = self.request.query_params.get('status')
        if booking_status:
            qs = qs.filter(status=booking_status)
        return qs


class BookingDetailView(TenantScopedQuerysetMixin, generics.RetrieveAPIView):
    """GET /bookings/<pk>/ — retrieve a single booking."""
    permission_classes = [IsAuthenticated]
    serializer_class = BookingSerializer
    queryset = Booking.objects.select_related('hostel', 'room')


class BookingApproveView(APIView):
    """POST /bookings/<pk>/approve/ — confirm an offline booking."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        booking = get_tenant_scoped_object_or_404(Booking, pk, request)

        if booking.status != 'pending':
            return Response({"error": "Only pending bookings can be confirmed"}, status=status.HTTP_400_BAD_REQUEST)

        booking.status = 'confirmed'
        booking.save(update_fields=['status', 'updated_at'])
        return Response({"success": True, "data": BookingSerializer(booking).data})


class BookingRejectView(APIView):
    """POST /bookings/<pk>/reject/ — reject a booking."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        booking = get_tenant_scoped_object_or_404(Booking, pk, request)

        if booking.status not in ('pending', 'confirmed'):
            return Response({"error": "Cannot reject a booking that is already paid or cancelled"}, status=status.HTTP_400_BAD_REQUEST)

        booking.status = 'rejected'
        booking.save(update_fields=['status', 'updated_at'])
        return Response({"success": True, "data": BookingSerializer(booking).data})


class BookingVerifyPaymentView(APIView):
    """POST /bookings/<pk>/verify/ — verify an online payment and confirm booking."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        booking = get_tenant_scoped_object_or_404(Booking, pk, request)

        if booking.payment_mode != 'online':
            return Response({"error": "Only online bookings can be verified"}, status=status.HTTP_400_BAD_REQUEST)

        booking.status = 'paid'
        booking.marked_paid_by = request.user
        booking.marked_paid_at = timezone.now()
        booking.save(update_fields=['status', 'marked_paid_by', 'marked_paid_at', 'updated_at'])
        return Response({"success": True, "data": BookingSerializer(booking).data})


class BookingMarkPaidView(APIView):
    """PATCH /bookings/<pk>/mark-paid/ — mark an offline booking as paid."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        booking = get_tenant_scoped_object_or_404(Booking, pk, request)

        if booking.status not in ('pending', 'confirmed'):
            return Response({"error": "Can only mark pending or confirmed bookings as paid"}, status=status.HTTP_400_BAD_REQUEST)

        booking.status = 'paid'
        booking.marked_paid_by = request.user
        booking.marked_paid_at = timezone.now()
        booking.save(update_fields=['status', 'marked_paid_by', 'marked_paid_at', 'updated_at'])
        return Response({"success": True, "data": BookingSerializer(booking).data})
