"""
The owner and admin list of stays and rent (Phase 9, the AdminDues board).

    GET /api/v1/stays/admin/            stays with their rent status, four totals, tab counts and the owner's hostels
    GET /api/v1/stays/admin/overdue/    the same rows, overdue stays only

Query parameters (all optional): hostel=<id>, status=<stay status> (default: UPCOMING, ACTIVE and NOTICE), overdue=true,
due_this_week=true, paid=true, needs_review=true, page, page_size (25 by default, at most 100).

Scope: an owner sees only their own hostels; an admin (is_staff) sees every stay. The classification runs in the database
(admin_queries.py), so the number of queries does not depend on the number of stays. Recording a payment, voiding it, sending a
reminder and ending a stay are the existing endpoints of Phases 5, 6 and 8; this list only says which of them a row may use.
"""
import uuid

from django.db.models import F, Prefetch
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from utils.pagination import CustomPageNumberPagination

from . import admin_queries
from .dates import today_ist
from .models import Due, Stay

TRUE = ('1', 'true', 'yes')


def _flag(request, name):
    return (request.query_params.get(name) or '').strip().lower() in TRUE


class StaysAdminView(APIView):
    permission_classes = [IsAuthenticated]
    overdue_only = False

    @extend_schema(summary='Stays and rent (owner or admin)', responses={200: dict}, parameters=[
        OpenApiParameter('hostel', str), OpenApiParameter('status', str), OpenApiParameter('overdue', bool),
        OpenApiParameter('due_this_week', bool), OpenApiParameter('paid', bool), OpenApiParameter('needs_review', bool)])
    def get(self, request):
        today = today_ist()
        hostel_id = request.query_params.get('hostel')
        if hostel_id:
            try:
                hostel_id = uuid.UUID(hostel_id)
            except ValueError:
                return Response({'code': 'INVALID_HOSTEL', 'message': 'hostel must be a hostel id.'},
                                status=status.HTTP_400_BAD_REQUEST)
        wanted = request.query_params.get('status')
        if wanted and wanted not in Stay.Status.values:
            return Response({'code': 'INVALID_STATUS', 'message': 'status must be one of ' + ', '.join(Stay.Status.values) + '.'},
                            status=status.HTTP_400_BAD_REQUEST)

        base = admin_queries.scoped_stays(request.user, hostel_id or None)
        base = base.filter(status=wanted) if wanted else base.filter(status__in=Stay.CURRENT_STATUSES)
        classified = admin_queries.classify(base, today)
        tabs = admin_queries.tab_counts(classified)

        rows = classified
        if self.overdue_only or _flag(request, 'overdue'):
            rows = rows.filter(admin_queries.TAB_FILTERS['overdue'])
        if _flag(request, 'due_this_week'):
            rows = rows.filter(admin_queries.TAB_FILTERS['due_this_week'])
        if _flag(request, 'paid'):
            rows = rows.filter(admin_queries.TAB_FILTERS['paid'])
        if _flag(request, 'needs_review'):
            rows = rows.filter(needs_review=True)
        rows = (rows.select_related('hostel', 'room', 'student', 'booking')
                .prefetch_related(Prefetch('dues', queryset=Due.objects.select_related('payment')))
                .order_by(F('next_open_date').asc(nulls_last=True), 'pk'))

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(rows, request)
        data = paginator.get_paginated_response([admin_queries.row_for(stay, today) for stay in page]).data
        data['totals'] = admin_queries.totals(request.user, today, hostel_id or None)
        data['tab_counts'] = tabs
        data['hostels'] = admin_queries.hostels_for(request.user)
        return Response(data)


class StaysAdminOverdueView(StaysAdminView):
    overdue_only = True

    @extend_schema(summary='Overdue stays (owner or admin)', responses={200: dict})
    def get(self, request):
        return super().get(request)
