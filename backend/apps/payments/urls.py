"""
apps/payments/urls.py
----------------------
URL patterns for the payments app — all mounted under /api/v1/ in the
main urls.py (path('', include('apps.payments.urls'))).

Full URL table:
  POST  /api/v1/payments/create-order/           → CreateOrderView
  POST  /api/v1/payments/initiate-upi-intent/    → InitiateUpiIntentView
  POST  /api/v1/payments/initiate-card-checkout/ → InitiateCardCheckoutView
  GET   /api/v1/payments/status/<uuid>/          → PaymentStatusPollView
  POST  /api/v1/payments/verify/                 → VerifyPaymentView
  POST  /api/v1/payments/webhook/                → WebhookView  (NO AUTH — intentional)
  GET   /api/v1/payments/list/                   → PaymentListView
  GET   /api/v1/payments/admin-list/             → AdminPaymentListView
  POST  /api/v1/payments/refund/<uuid>/          → RefundView
"""

from django.urls import path
from .views import (
    CreateOrderView,
    InitiateUpiIntentView,
    InitiateCardCheckoutView,
    PaymentStatusPollView,
    VerifyPaymentView,
    WebhookView,
    PaymentListView,
    AdminPaymentListView,
    RefundView,
)

urlpatterns = [
    path('payments/create-order/',           CreateOrderView.as_view(),           name='payment-create-order'),
    path('payments/initiate-upi-intent/',    InitiateUpiIntentView.as_view(),     name='payment-upi-intent'),
    path('payments/initiate-card-checkout/', InitiateCardCheckoutView.as_view(),  name='payment-card-checkout'),
    path('payments/status/<uuid:payment_id>/', PaymentStatusPollView.as_view(),   name='payment-status-poll'),
    path('payments/verify/',                 VerifyPaymentView.as_view(),         name='payment-verify'),
    path('payments/webhook/',                WebhookView.as_view(),               name='payment-webhook'),
    path('payments/list/',                   PaymentListView.as_view(),           name='payment-list'),
    path('payments/admin-list/',             AdminPaymentListView.as_view(),      name='payment-admin-list'),
    path('payments/refund/<uuid:payment_id>/', RefundView.as_view(),             name='payment-refund'),
]
