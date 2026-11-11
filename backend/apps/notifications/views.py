"""
Notification endpoints (Phase 8). All are for the signed-in user's own notifications (IsResourceUser plus a user-scoped
queryset: another user's notification answers 404 exactly as if it did not exist).

    GET   /api/v1/notifications/?category=rent|stay    newest first, paginated (page size 20, at most 100)
    POST  /api/v1/notifications/<id>/read/             mark one read
    POST  /api/v1/notifications/read-all/              mark all read
    GET   /api/v1/notifications/unread-count/          {"unread": N}, cached 15 s per user
    GET   /api/v1/notifications/preferences/           {"inbox", "push", "email"}
    PATCH /api/v1/notifications/preferences/           change any of them

    GET   /api/v1/ops/status/                          admin only: outbox backlog, last job runs, Redis (no personal data)
"""
from django.core.cache import cache
from django.db.models import Min
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.http_cache import private_json_response
from apps.core.tenancy.permissions import IsResourceUser
from apps.core.tenancy.utils import get_user_scoped_object_or_404
from apps.stays.dates import to_ist
from apps.stays.models import OutboxEvent
from utils.pagination import CustomPageNumberPagination

from . import services
from .models import JobRun, Notification, NotificationPreference

CHANNEL_WORDS = {'push': 'Push', 'in_app': 'in-app', 'email': 'email'}


class NotificationPagination(CustomPageNumberPagination):
    page_size = 20
    max_page_size = 100


def item(notification):
    channels = [c for c in ('push', 'in_app', 'email') if c in (notification.channels_delivered or [])]
    action = None
    payload = notification.payload or {}
    if notification.due_id and notification.kind in ('manual_reminder', 'before_7', 'before_3', 'before_1', 'due_day',
                                                     'overdue_1', 'overdue_3', 'overdue_7'):
        action = {'type': 'pay', 'due_id': str(notification.due_id)}
    elif payload.get('payment_id') and notification.kind in ('payment_received', 'owner_recorded'):
        action = {'type': 'receipt', 'payment_id': payload['payment_id'], 'stay_id': payload.get('stay_id')}
    return {
        'id': str(notification.id), 'kind': notification.kind, 'category': notification.category.lower(),
        'title': notification.title, 'body': notification.body,
        'created_at': to_ist(notification.created_at).isoformat(),
        'read_at': to_ist(notification.read_at).isoformat() if notification.read_at else None,
        'channels': channels,
        'channels_label': ', '.join(CHANNEL_WORDS[c] for c in channels),
        'due_id': str(notification.due_id) if notification.due_id else None,
        'action': action,
    }


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated, IsResourceUser]

    @extend_schema(summary='My notifications', responses={200: dict},
                   parameters=[OpenApiParameter('category', str, description='rent or stay (default: all)')])
    def get(self, request):
        queryset = Notification.objects.filter(user=request.user)
        category = (request.query_params.get('category') or '').strip().lower()
        if category:
            if category not in ('rent', 'stay'):
                return Response({'code': 'INVALID_CATEGORY', 'message': 'category must be rent or stay.'},
                                status=status.HTTP_400_BAD_REQUEST)
            queryset = queryset.filter(category=category.upper())
        paginator = NotificationPagination()
        page = paginator.paginate_queryset(queryset.order_by('-created_at', '-id'), request)
        return private_json_response(request, paginator.get_paginated_response([item(n) for n in page]).data)


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated, IsResourceUser]

    @extend_schema(request=None, summary='Mark one notification read', responses={200: dict})
    def post(self, request, pk):
        notification = get_user_scoped_object_or_404(Notification, pk, request)
        self.check_object_permissions(request, notification)
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=['read_at'])
            services.bump_unread(request.user.id)
        return Response(item(notification))


class NotificationReadAllView(APIView):
    permission_classes = [IsAuthenticated, IsResourceUser]

    @extend_schema(request=None, summary='Mark every notification read', responses={200: dict})
    def post(self, request):
        updated = Notification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=timezone.now())
        if updated:
            services.bump_unread(request.user.id)
        return Response({'updated': updated})


class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated, IsResourceUser]

    @extend_schema(summary='Unread count (cached 15 seconds per user)', responses={200: dict})
    def get(self, request):
        return Response({'unread': services.unread_count(request.user)})


class PreferencesSerializer(serializers.Serializer):
    inbox = serializers.BooleanField(required=False)
    push = serializers.BooleanField(required=False)
    email = serializers.BooleanField(required=False)


class PreferencesView(APIView):
    permission_classes = [IsAuthenticated, IsResourceUser]

    @extend_schema(summary='My notification preferences', responses={200: PreferencesSerializer})
    def get(self, request):
        row = NotificationPreference.objects.filter(user=request.user).first()
        return Response({'inbox': row.inbox if row else True, 'push': row.push if row else True,
                         'email': row.email if row else True})

    @extend_schema(request=PreferencesSerializer, summary='Change my notification preferences',
                   responses={200: PreferencesSerializer})
    def patch(self, request):
        data = PreferencesSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row, _ = NotificationPreference.objects.get_or_create(user=request.user)
        for field, value in data.validated_data.items():
            setattr(row, field, value)
        row.save()
        return Response({'inbox': row.inbox, 'push': row.push, 'email': row.email})


class OpsStatusView(APIView):
    """Admin only. Counts and times: no personal data."""
    permission_classes = [IsAdminUser]

    @extend_schema(summary='Engine status (admin)', responses={200: dict})
    def get(self, request):
        now = timezone.now()
        pending = OutboxEvent.objects.filter(status=OutboxEvent.Status.PENDING)
        oldest = pending.aggregate(oldest=Min('created_at'))['oldest']
        failed = OutboxEvent.objects.filter(status=OutboxEvent.Status.FAILED)
        jobs = {}
        for name in ('stays_daily', 'process_outbox', 'cleanup_expired'):
            last_ok = JobRun.objects.filter(name=name, status=JobRun.Status.OK).order_by('-finished_at').first()
            last = JobRun.objects.filter(name=name).order_by('-started_at').first()
            jobs[name] = {
                'last_success_at': last_ok.finished_at.isoformat() if last_ok and last_ok.finished_at else None,
                'last_run_status': last.status if last else None,
            }
        return Response({
            'outbox': {
                'pending': pending.count(), 'failed': failed.count(),
                'oldest_pending_age_seconds': int((now - oldest).total_seconds()) if oldest else None,
            },
            'jobs': jobs,
            'redis': self.redis_state(),
        })

    @staticmethod
    def redis_state():
        from django.conf import settings
        if not getattr(settings, 'REDIS_URL', ''):
            return 'not_configured'
        try:
            cache.set('hh:ops:probe', 1, 10)
            return 'reachable' if cache.get('hh:ops:probe') == 1 else 'unreachable'
        except Exception:  # noqa: BLE001
            return 'unreachable'
