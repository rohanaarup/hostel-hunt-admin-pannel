from django.urls import path

from .read_views import (
    StayAnalyticsView, StayCalendarView, StayDetailView, StayDuesView, StayHomeView, StayListView, StayPaymentsView,
    StayReceiptView,
)
from .views import DueRecordPaymentView, DueVoidPaymentView, StayEndView, StayVacateRequestView

urlpatterns = [
    # Phase 7: read-only student endpoints (fixed paths first, then the ones with an id)
    path('stays/', StayListView.as_view(), name='stay-list'),
    path('stays/home/', StayHomeView.as_view(), name='stay-home'),
    path('stays/calendar/', StayCalendarView.as_view(), name='stay-calendar'),
    path('stays/<uuid:pk>/', StayDetailView.as_view(), name='stay-detail'),
    path('stays/<uuid:pk>/dues/', StayDuesView.as_view(), name='stay-dues'),
    path('stays/<uuid:pk>/payments/', StayPaymentsView.as_view(), name='stay-payments'),
    path('stays/<uuid:pk>/receipts/<uuid:payment_id>/', StayReceiptView.as_view(), name='stay-receipt'),
    path('stays/<uuid:pk>/analytics/', StayAnalyticsView.as_view(), name='stay-analytics'),
    # Phase 5 and 6: the actions
    path('stays/<uuid:pk>/vacate-request/', StayVacateRequestView.as_view(), name='stay-vacate-request'),
    path('stays/<uuid:pk>/end/', StayEndView.as_view(), name='stay-end'),
    path('stays/dues/<uuid:pk>/record-payment/', DueRecordPaymentView.as_view(), name='due-record-payment'),
    path('stays/dues/<uuid:pk>/void-payment/', DueVoidPaymentView.as_view(), name='due-void-payment'),
]
