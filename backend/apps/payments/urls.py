from django.urls import path
from .views import PaymentListView, PaymentCreateView, PaymentMarkPaidView

urlpatterns = [
    path('payments/', PaymentListView.as_view(), name='payment-list'),
    path('payments/create/', PaymentCreateView.as_view(), name='payment-create'),
    path('payments/<uuid:pk>/mark-paid/', PaymentMarkPaidView.as_view(), name='payment-mark-paid'),
]
