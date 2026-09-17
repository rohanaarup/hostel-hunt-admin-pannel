from django.db.models import Count, Case, When, IntegerField, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.bookings.models import Booking, Wishlist
from apps.core.tenancy.querysets import user_scope_q
from apps.core.tenancy.utils import get_scoped_object_or_404


# ─────────────────────────────────────────────────────────────────────────────
# Lightweight serialisers — defined here to keep the endpoint self-contained
# and avoid pulling in the full heavy BookingSerializer (which joins more tables).
# ─────────────────────────────────────────────────────────────────────────────

class ActiveBookingSerializer:
    """Hand-rolled serialiser for the single active booking spotlight card."""

    def __init__(self, instance):
        self.instance = instance

    @property
    def data(self):
        b = self.instance
        if b is None:
            return None
        return {
            "id": str(b.id),
            "hostel_name": b.hostel.name if b.hostel_id else None,
            "hostel_city": b.hostel.city if b.hostel_id else None,
            "room_name": b.room_name or (b.room.room_name if b.room_id else None),
            "room_number": b.room_number,
            "bed_number": b.bed_number,
            "status": b.status,
            "check_in_date": b.check_in_date.isoformat() if b.check_in_date else None,
            "check_out_date": b.check_out_date.isoformat() if b.check_out_date else None,
            "amount": str(b.amount) if b.amount is not None else None,
            "created_at": b.created_at.isoformat(),
        }


class RecentBookingSerializer:
    """Hand-rolled serialiser for the recent activity list rows."""

    def __init__(self, queryset):
        self.queryset = queryset

    @property
    def data(self):
        result = []
        for b in self.queryset:
            result.append({
                "id": str(b.id),
                "hostel_name": b.hostel.name if b.hostel_id else None,
                "hostel_city": b.hostel.city if b.hostel_id else None,
                "status": b.status,
                "amount": str(b.amount) if b.amount is not None else None,
                "check_in_date": b.check_in_date.isoformat() if b.check_in_date else None,
                "created_at": b.created_at.isoformat(),
            })
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Student Dashboard Stats — 4 DB queries total, no loops, no per-row queries
# ─────────────────────────────────────────────────────────────────────────────

class StudentDashboardStatsView(APIView):
    """
    GET /api/v1/dashboard/student/stats/

    Returns aggregated stats for the authenticated *student* user.
    Total DB queries: 4 (one aggregate, one count, one first(), one slice).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Build a filter that catches:
        # 1. Bookings where student FK is explicitly set to this user
        # 2. Legacy bookings (student=NULL) where student_name matches the user's name
        user_name = getattr(user, 'display_name', '') or getattr(user, 'username', '')
        booking_filter = Q(student=user)
        if user_name:
            booking_filter |= Q(student__isnull=True, student_name__iexact=user_name)

        # Query 1 — aggregate booking status breakdown in a single pass
        booking_stats = Booking.objects.filter(booking_filter).aggregate(
            total=Count('id'),
            pending=Count(Case(When(status='pending',   then=1), output_field=IntegerField())),
            confirmed=Count(Case(When(status='confirmed', then=1), output_field=IntegerField())),
            paid=Count(Case(When(status='paid',         then=1), output_field=IntegerField())),
            cancelled=Count(Case(When(status='cancelled', then=1), output_field=IntegerField())),
            rejected=Count(Case(When(status='rejected',  then=1), output_field=IntegerField())),
        )

        # Query 2 — wishlist count
        wishlist_count = Wishlist.objects.filter(user=user).count()

        # Query 3 — most recent confirmed booking (the "active" spotlight)
        active_booking = (
            Booking.objects
            .filter(booking_filter, status__in=['confirmed', 'paid'])
            .select_related('hostel', 'room')
            .order_by('-created_at')
            .first()
        )

        # Query 4 — last 5 bookings for the activity list
        recent_bookings = (
            Booking.objects
            .filter(booking_filter)
            .select_related('hostel')
            .order_by('-created_at')[:5]
        )

        return Response({
            "wishlist_count": wishlist_count,
            "booking_stats": booking_stats,
            "active_booking": ActiveBookingSerializer(active_booking).data,
            "recent_activity": RecentBookingSerializer(recent_bookings).data,
        })


# ─────────────────────────────────────────────────────────────────────────────
# Wishlist endpoints
# ─────────────────────────────────────────────────────────────────────────────

class WishlistView(APIView):
    """
    GET  /api/v1/wishlist/        — list the authenticated user's wishlisted hostels
    POST /api/v1/wishlist/        — add a hostel to wishlist  { "hostel_id": "<uuid>" }
    DELETE /api/v1/wishlist/<pk>/ — remove a wishlist entry by wishlist row id
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = (
            Wishlist.objects
            .filter(user_scope_q(Wishlist, request.user))
            .select_related('hostel')
            .order_by('-created_at')
        )
        data = [
            {
                "id": str(item.id),
                "hostel_id": str(item.hostel_id),
                "hostel_name": item.hostel.name,
                "hostel_city": item.hostel.city,
                "hostel_locality": item.hostel.locality,
                "gender_type": item.hostel.gender_type,
                "saved_at": item.created_at.isoformat(),
            }
            for item in items
        ]
        return Response({"wishlist": data, "count": len(data)})

    def post(self, request):
        hostel_id = request.data.get('hostel_id')
        if not hostel_id:
            return Response({"error": "hostel_id is required"}, status=400)

        from apps.hostels.models import Hostel
        from django.shortcuts import get_object_or_404
        hostel = get_object_or_404(Hostel, pk=hostel_id)

        item, created = Wishlist.objects.get_or_create(
            user=request.user, hostel=hostel
        )
        return Response(
            {"id": str(item.id), "hostel_id": str(hostel.id), "created": created},
            status=201 if created else 200,
        )


class WishlistDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        item = get_scoped_object_or_404(Wishlist, pk, request, kind="user")
        item.delete()
        return Response({"deleted": True})


# ─────────────────────────────────────────────────────────────────────────────
# Legacy owner-scoped dashboard views (kept intact, not removed)
# ─────────────────────────────────────────────────────────────────────────────

from rest_framework import viewsets  # noqa: E402 (keep below new views)
from django.db.models import Sum
from apps.hostels.models import Hostel
from apps.residents.models import Resident
from apps.payments.models import Payment


class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        hostels = Hostel.objects.filter(owner=user)
        total_hostels = hostels.count()

        # Total residents (active only)
        total_residents = Resident.objects.filter(hostel__owner=user, status='active').count()

        # Occupancy rate calculation
        total_beds = sum(h.total_beds for h in hostels)
        occupancy_rate = 0
        if total_beds > 0:
            occupancy_rate = int((total_residents / total_beds) * 100)

        # Payment has no direct `hostel` FK (only `booking`) and no
        # amount_due/amount_paid fields — those belonged to an older
        # offline-payment schema that was deliberately removed (see
        # apps/payments/models.py's module docstring). Current schema:
        # online payments are tracked on Payment (amount, status=SUCCESS),
        # offline payments directly on Booking (amount, payment_mode=
        # 'offline', status='paid'). Revenue below combines both.
        online_collected = Payment.objects.filter(
            booking__hostel__owner=user, status=Payment.Status.SUCCESS,
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        offline_collected = Booking.objects.filter(
            hostel__owner=user, payment_mode='offline', status='paid',
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        revenue_collected = online_collected + offline_collected

        revenue_pending = Booking.objects.filter(
            hostel__owner=user, status__in=['pending', 'confirmed'],
        ).aggregate(Sum('amount'))['amount__sum'] or 0

        pending_bookings = Booking.objects.filter(hostel__owner=user, status='pending').count()

        return Response({
            "success": True,
            "data": {
                "total_hostels": total_hostels,
                "total_residents": total_residents,
                "occupancy_rate": occupancy_rate,
                "revenue_collected": float(revenue_collected),
                "revenue_pending": float(revenue_pending),
                "pending_bookings": pending_bookings,
            }
        })


class DashboardActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        activities = []

        recent_bookings = Booking.objects.filter(hostel__owner=user).order_by('-updated_at')[:10]
        for b in recent_bookings:
            activity_type = 'booking_request'
            title = 'New Booking Request'

            if b.status == 'confirmed':
                activity_type = 'booking_confirmed'
                title = 'Booking Confirmed'
            elif b.status == 'cancelled':
                activity_type = 'booking_cancelled'
                title = 'Booking Cancelled'

            activities.append({
                "activity_id": f"b_{b.id}",
                "type": activity_type,
                "title": title,
                "description": f"{b.student_name} requested a booking in {b.hostel.name}.",
                "timestamp": b.updated_at,
                "meta": {"booking_id": str(b.id)}
            })

        recent_payments = (
            Payment.objects.filter(booking__hostel__owner=user, status=Payment.Status.SUCCESS)
            .select_related('booking')
            .order_by('-created_at')[:5]
        )
        for p in recent_payments:
            activities.append({
                "activity_id": f"p_{p.id}",
                "type": "payment_received",
                "title": "Payment Received",
                "description": f"Received {p.amount} from {p.booking.student_name or 'a student'}.",
                "timestamp": p.created_at,
                "meta": {"payment_id": str(p.id)}
            })

        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        activities = activities[:10]

        return Response({
            "success": True,
            "data": activities
        })
