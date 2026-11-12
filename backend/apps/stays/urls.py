from django.urls import path

from .admin_views import StaysAdminOverdueView, StaysAdminView
from .billing_views import BillingPreviewView, HostelBillingView
from .read_views import (
    StayAnalyticsView, StayCalendarView, StayDetailView, StayDuesView, StayHomeView, StayListView, StayPaymentsView,
    StayReceiptView,
)
from .views import (
    DueRecordPaymentView, DueSendReminderView, DueVoidPaymentView, StayEndView, StayVacateRequestView,
)

urlpatterns = [
    # Phase 9: the admin panel (billing rule, preview, the owner and admin list)
    path('hostels/<uuid:pk>/billing/', HostelBillingView.as_view(), name='hostel-billing'),
    path('stays/billing/preview/', BillingPreviewView.as_view(), name='billing-preview'),
    path('stays/admin/', StaysAdminView.as_view(), name='stays-admin'),
    path('stays/admin/overdue/', StaysAdminOverdueView.as_view(), name='stays-admin-overdue'),
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
    path('stays/dues/<uuid:pk>/send-reminder/', DueSendReminderView.as_view(), name='due-send-reminder'),
]
