"""
Read-only student endpoints for stays (Phase 7). Every one is GET only, student scoped (the stay's own student; anyone else
gets 404 exactly as if it did not exist), and sends `ETag` with `Cache-Control: private, no-cache` so the app can revalidate
with If-None-Match and get a bodiless 304.

    GET /api/v1/stays/                              the student's stays, current first, then past (paginated)
    GET /api/v1/stays/home/                         the whole Home screen in one call (cached per user for a few seconds)
    GET /api/v1/stays/calendar/?month=YYYY-MM       the payment calendar of the current stay
    GET /api/v1/stays/<id>/                         one stay
    GET /api/v1/stays/<id>/dues/                    its dues (stored, then projected)
    GET /api/v1/stays/<id>/payments/?filter=        the payment history (all, paid, upcoming)
    GET /api/v1/stays/<id>/receipts/<payment_id>/   one receipt
    GET /api/v1/stays/<id>/analytics/?range=        the analytics board

A past stay (ENDED or CANCELLED) is listed with `openable: false`; its own pages answer 403 STAY_NOT_OPENABLE.
Queries are fixed in number whatever the number of dues: the stay with its hostel and room, its dues (with the payment, and
the successful attempt where a payment is shown) fetched once, then plain Python (see schedule.py and readmodels.py).
"""
from django.conf import settings
from django.db.models import Case, IntegerField, Prefetch, Value, When
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import cache as shared_cache
from apps.core.http_cache import private_json_response
from apps.core.tenancy.querysets import user_scope_q
from apps.payments.models import PaymentAttempt
from utils.pagination import CustomPageNumberPagination

from . import readmodels, schedule, services
from .dates import today_ist
from .models import Due, Stay

HOME_TTL_SECONDS = 20


def _dues(with_attempts=False):
    prefetches = [Prefetch('dues', queryset=Due.objects.select_related('payment'))]
    if with_attempts:
        prefetches.append(Prefetch('dues__payment__attempts',
                                   queryset=PaymentAttempt.objects.filter(status=PaymentAttempt.Status.SUCCESS)))
    return prefetches


def _not_openable():
    message = 'Past stays are kept for your records and cannot be opened.'
    return Response({'code': 'STAY_NOT_OPENABLE', 'message': message, 'error': message}, status=status.HTTP_403_FORBIDDEN)


class StayReadView(APIView):
    """Base: signed in, GET only (APIView answers 405 to anything else, because only `get` is defined)."""
    permission_classes = [IsAuthenticated]

    def own_stays(self, request, with_attempts=False):
        return (Stay.objects.filter(user_scope_q(Stay, request.user))
                .select_related('hostel', 'room', 'student').prefetch_related(*_dues(with_attempts)))

    def open_stay(self, request, pk, with_attempts=False):
        """(stay, None) for the student's own open stay; (None, response) for a 404 or the 403 of a past stay."""
        stay = self.own_stays(request, with_attempts).filter(pk=pk).first()
        if stay is None:
            return None, Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not stay.is_current:
            return None, _not_openable()
        return stay, None


class StayListView(StayReadView):
    @extend_schema(summary='My stays: current first, then past', operation_id='stays_list_mine', responses={200: dict})
    def get(self, request):
        today = today_ist()
        rank = Case(When(status__in=Stay.CURRENT_STATUSES, then=Value(0)), default=Value(1), output_field=IntegerField())
        queryset = self.own_stays(request).annotate(rank=rank).order_by('rank', '-join_date', '-created_at')
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        results = [readmodels.stay_summary(stay, today)[0] for stay in page]
        return private_json_response(request, paginator.get_paginated_response(results).data)


class StayDetailView(StayReadView):
    @extend_schema(summary='One stay', responses={200: dict})
    def get(self, request, pk):
        stay, refusal = self.open_stay(request, pk)
        if refusal is not None:
            return refusal
        return private_json_response(request, readmodels.stay_detail(stay, today_ist(), request.user))


class StayDuesView(StayReadView):
    @extend_schema(summary='Dues of a stay: stored, then projected (not yet created)', responses={200: dict})
    def get(self, request, pk):
        stay, refusal = self.open_stay(request, pk)
        if refusal is not None:
            return refusal
        stored, projected = readmodels.dues_payload(stay, today_ist())
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(stored, request)
        data = paginator.get_paginated_response(page).data
        data['projected'] = projected
        return private_json_response(request, data)


class StayPaymentsView(StayReadView):
    FILTERS = ('all', 'paid', 'upcoming')

    @extend_schema(summary='Payment history of a stay', responses={200: dict},
                   parameters=[OpenApiParameter('filter', str, description='paid or upcoming (default: all)')])
    def get(self, request, pk):
        stay, refusal = self.open_stay(request, pk, with_attempts=True)
        if refusal is not None:
            return refusal
        wanted = request.query_params.get('filter', 'all')
        if wanted not in self.FILTERS:
            return Response({'code': 'INVALID_FILTER', 'message': 'filter must be paid or upcoming.'},
                            status=status.HTTP_400_BAD_REQUEST)
        today = today_ist()
        stored, projected = schedule.all_rows(stay, today)
        _, grace = schedule.window_and_grace(stay)
        if wanted == 'paid':
            stored, projected = [r for r in stored if r.status == 'PAID'], []
        elif wanted == 'upcoming':
            stored = [r for r in stored if r.is_open]
        stored = sorted(stored, key=lambda r: (r.due_date, r.period_start), reverse=True)
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset([readmodels.payment_item(r, today, grace) for r in stored], request)
        data = paginator.get_paginated_response(page).data
        data['projected'] = [readmodels.due_item(r, today, grace) for r in projected]
        return private_json_response(request, data)


class StayReceiptView(StayReadView):
    @extend_schema(summary='One receipt', responses={200: dict})
    def get(self, request, pk, payment_id):
        stay, refusal = self.open_stay(request, pk, with_attempts=True)
        if refusal is not None:
            return refusal
        today = today_ist()
        for row in schedule.stored_rows(stay, today):
            payment = row.payment
            if (row.status == 'PAID' and payment is not None and str(payment.id) == str(payment_id)
                    and payment.status == 'SUCCESS'):
                return private_json_response(request, readmodels.receipt_payload(stay, row, payment))
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)


class StayAnalyticsView(StayReadView):
    RANGES = ('stay', '6m', '12m')

    @extend_schema(summary='Stay analytics', responses={200: dict},
                   parameters=[OpenApiParameter('range', str, description='stay (default), 6m or 12m')])
    def get(self, request, pk):
        stay, refusal = self.open_stay(request, pk, with_attempts=True)
        if refusal is not None:
            return refusal
        range_key = request.query_params.get('range', 'stay')
        if range_key not in self.RANGES:
            return Response({'code': 'INVALID_RANGE', 'message': 'range must be stay, 6m or 12m.'},
                            status=status.HTTP_400_BAD_REQUEST)
        return private_json_response(request, readmodels.analytics_payload(stay, today_ist(), range_key))


def _current_stay(user, with_attempts=False):
    return (Stay.objects.filter(user_scope_q(Stay, user), status__in=Stay.CURRENT_STATUSES)
            .select_related('hostel', 'room', 'student').prefetch_related(*_dues(with_attempts))
            .order_by('-created_at').first())


class StayCalendarView(StayReadView):
    @extend_schema(summary='Payment calendar of the current stay', responses={200: dict},
                   parameters=[OpenApiParameter('month', str, description='YYYY-MM', required=True)])
    def get(self, request):
        today = today_ist()
        parsed = readmodels.parse_month(request.query_params.get('month', ''), today)
        if parsed is None:
            return Response({'code': 'INVALID_MONTH', 'message': 'month must look like 2026-10.'},
                            status=status.HTTP_400_BAD_REQUEST)
        stay = _current_stay(request.user)
        if stay is None:
            return Response({'code': 'NO_CURRENT_STAY', 'message': 'You have no current stay.'},
                            status=status.HTTP_404_NOT_FOUND)
        return private_json_response(request, readmodels.calendar_payload(stay, today, *parsed))


class StayHomeView(StayReadView):
    """The Home screen in ONE call. With STAYS_ENABLED off it answers {"enabled": false} and nothing else. The answer is
    cached per user for a few seconds through the shared cache (never a per-process dict); paying, recording or voiding
    rent, creating or ending a stay and a vacate request all bump that user's version, so money is never stale."""

    @extend_schema(summary='Home screen data', responses={200: dict})
    def get(self, request):
        if not getattr(settings, 'STAYS_ENABLED', False):
            return private_json_response(request, {'enabled': False})

        def build():
            return readmodels.home_payload(_current_stay(request.user), request.user, today_ist())

        data = shared_cache.get_or_set(
            services.home_cache_name(request.user.id), HOME_TTL_SECONDS, build,
            user_id=request.user.id, per_user=True)
        return private_json_response(request, data)
