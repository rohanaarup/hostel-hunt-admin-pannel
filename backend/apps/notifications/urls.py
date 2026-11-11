from django.urls import path

from .views import (
    NotificationListView, NotificationReadAllView, NotificationReadView, OpsStatusView, PreferencesView, UnreadCountView,
)

urlpatterns = [
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/read-all/', NotificationReadAllView.as_view(), name='notification-read-all'),
    path('notifications/unread-count/', UnreadCountView.as_view(), name='notification-unread-count'),
    path('notifications/preferences/', PreferencesView.as_view(), name='notification-preferences'),
    path('notifications/<uuid:pk>/read/', NotificationReadView.as_view(), name='notification-read'),
    path('ops/status/', OpsStatusView.as_view(), name='ops-status'),
]
