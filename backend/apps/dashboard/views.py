from django.db.models import Count, Case, When, IntegerField, Q
import uuid

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.bookings.models import Booking, Wishlist
from apps.core.tenancy.querysets import user_scope_q
from apps.core.tenancy.utils import get_scoped_object_or_404
from apps.hostels.serializers import HostelListSerializer
from apps.hostels.views import public_hostel_queryset
from utils.pagination import CustomPageNumberPagination


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

        # Only bookings linked to this user. Anonymous bookings carry a typed name that anyone can
        # choose, so matching on the name would show one person's bookings to another.
        booking_filter = Q(student=user)

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

class WishlistPagination(CustomPageNumberPagination):
    """{count, next, previous, wishlist: [...]}: the same flat shape as the other lists, under the
    `wishlist` key the first version of this route already used."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 50

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'wishlist': data,
        })


def _saved_visible(user):
    """The user's saved rows whose hostel is still listed (active, in an active city), newest first."""
    return (
        Wishlist.objects
        .filter(user_scope_q(Wishlist, user), hostel__in=public_hostel_queryset().values('pk'))
        .order_by('-created_at', 'id')
    )


WISHLIST_ROWS = inline_serializer('WishlistRow', {
    'id': serializers.UUIDField(help_text='The saved row id (DELETE /wishlist/{id}/).'),
    'hostel_id': serializers.UUIDField(),
    'name': serializers.CharField(),
    'city': serializers.CharField(),
    'locality': serializers.CharField(),
    'gender_type': serializers.CharField(),
    'amenities': serializers.ListField(child=serializers.CharField()),
    'cover_image': serializers.CharField(allow_null=True),
    'price_from': serializers.FloatField(allow_null=True),
    'saved_at': serializers.DateTimeField(),
}, many=True)


class WishlistView(APIView):
    """
    GET  /api/v1/wishlist/        - the signed-in user's saved hostels that are still listed, newest saved
                                    first, paginated (page, page_size; default 20, max 50)
    POST /api/v1/wishlist/        - save a hostel  { "hostel_id": "<uuid>" }. Saving twice is fine:
                                    201 the first time, 200 after, the same row either way.
    """
    permission_classes = [IsAuthenticated]
    pagination_class = WishlistPagination

    @extend_schema(
        parameters=[OpenApiParameter('page', int), OpenApiParameter('page_size', int)],
        responses=inline_serializer('WishlistPage', {
            'count': serializers.IntegerField(),
            'next': serializers.CharField(allow_null=True),
            'previous': serializers.CharField(allow_null=True),
            'wishlist': WISHLIST_ROWS,
        }),
    )
    def get(self, request):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(_saved_visible(request.user), request)
        hostels = {h.pk: h for h in public_hostel_queryset().filter(pk__in=[item.hostel_id for item in page])}
        rows = []
        for item in page:
            hostel = hostels.get(item.hostel_id)
            if hostel is None:
                continue
            rows.append({
                **HostelListSerializer(hostel).data,  # name, city, locality, amenities, cover_image, price_from...
                'id': str(item.id),
                'saved_at': item.created_at.isoformat(),
                # the first version's keys, kept for older apps
                'hostel_name': hostel.name,
                'hostel_city': hostel.city,
                'hostel_locality': hostel.locality,
            })
        return paginator.get_paginated_response(rows)

    @extend_schema(
        request=inline_serializer('WishlistSave', {'hostel_id': serializers.UUIDField()}),
        responses={
            200: inline_serializer('WishlistSaved', {
                'id': serializers.UUIDField(), 'hostel_id': serializers.UUIDField(),
                'created': serializers.BooleanField(), 'saved': serializers.BooleanField(),
            }),
        },
    )
    def post(self, request):
        raw = request.data.get('hostel_id')
        if not raw:
            raise serializers.ValidationError({'hostel_id': 'This field is required.'})
        try:
            hostel_id = uuid.UUID(str(raw))
        except ValueError:
            raise serializers.ValidationError({'hostel_id': 'Enter a valid hostel id.'})

        hostel = get_object_or_404(public_hostel_queryset(), pk=hostel_id)
        item, created = Wishlist.objects.get_or_create(user=request.user, hostel=hostel)
        return Response(
            {'id': str(item.id), 'hostel_id': str(hostel.id), 'created': created, 'saved': True},
            status=201 if created else 200,
        )


class WishlistIdsView(APIView):
    """GET /api/v1/wishlist/ids/ - just the hostel ids the user has saved, for the hearts in the app."""
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=inline_serializer('WishlistIds', {
        'ids': serializers.ListField(child=serializers.UUIDField()),
        'count': serializers.IntegerField(),
    }))
    def get(self, request):
        ids = [str(pk) for pk in _saved_visible(request.user).values_list('hostel_id', flat=True)[:2000]]
        return Response({'ids': ids, 'count': len(ids)})


class WishlistHostelView(APIView):
    """DELETE /api/v1/wishlist/hostel/<hostel id>/ - un-save a hostel. Safe to repeat: it answers 200
    whether or not the hostel was saved (`deleted` says which)."""
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=inline_serializer('WishlistDeleted', {'deleted': serializers.BooleanField()}))
    def delete(self, request, hostel_id):
        removed, _ = Wishlist.objects.filter(user_scope_q(Wishlist, request.user), hostel_id=hostel_id).delete()
        return Response({'deleted': removed > 0})


class WishlistDetailView(APIView):
    """DELETE /api/v1/wishlist/<saved row id>/ - the first version's way to un-save (404 if already gone)."""
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=inline_serializer('WishlistRowDeleted', {'deleted': serializers.BooleanField()}))
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


OWNER_STATS = inline_serializer('OwnerDashboardStats', {
    'success': serializers.BooleanField(),
    'data': inline_serializer('OwnerDashboardStatsData', {
        'total_hostels': serializers.IntegerField(),
        'total_residents': serializers.IntegerField(),
        'total_beds': serializers.IntegerField(help_text="The beds entered on the owner's hostels; the number the occupancy rate divides by."),
        'occupancy_rate': serializers.IntegerField(),
        'bookings_by_status': serializers.DictField(child=serializers.IntegerField(), help_text='pending, confirmed, paid, cancelled, rejected: counted over ALL bookings.'),
        'bookings_by_payment_mode': serializers.DictField(child=serializers.IntegerField(), help_text='offline, online.'),
        'revenue_collected': serializers.FloatField(),
        'revenue_pending': serializers.FloatField(),
        'pending_bookings': serializers.IntegerField(),
    }),
})


class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=OWNER_STATS, summary="The signed-in owner's dashboard numbers")
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

        # Counts over every booking of the owner's hostels, for the dashboard's donut charts. (The bookings
        # list is paged, so counting what one page happens to hold would give wrong totals.)
        owner_bookings = Booking.objects.filter(hostel__owner=user)
        by_status = dict(owner_bookings.values_list('status').annotate(n=Count('id')))
        by_mode = dict(owner_bookings.values_list('payment_mode').annotate(n=Count('id')))

        return Response({
            "success": True,
            "data": {
                "total_hostels": total_hostels,
                "total_residents": total_residents,
                "total_beds": total_beds,
                "occupancy_rate": occupancy_rate,
                "bookings_by_status": {s: by_status.get(s, 0) for s in ('pending', 'confirmed', 'paid', 'cancelled', 'rejected')},
                "bookings_by_payment_mode": {m: by_mode.get(m, 0) for m in ('offline', 'online')},
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
