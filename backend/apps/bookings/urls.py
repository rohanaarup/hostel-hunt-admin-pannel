from django.urls import path
from .views import (
    BookingListView,
    BookingDetailView,
    BookingApproveView,
    BookingRejectView,
    BookingVerifyPaymentView,
    BookingMarkPaidView,
)

urlpatterns = [
    path('bookings/', BookingListView.as_view(), name='booking-list'),
    path('bookings/<uuid:pk>/', BookingDetailView.as_view(), name='booking-detail'),
    path('bookings/<uuid:pk>/approve/', BookingApproveView.as_view(), name='booking-approve'),
    path('bookings/<uuid:pk>/reject/', BookingRejectView.as_view(), name='booking-reject'),
    path('bookings/<uuid:pk>/verify/', BookingVerifyPaymentView.as_view(), name='booking-verify'),
    path('bookings/<uuid:pk>/mark-paid/', BookingMarkPaidView.as_view(), name='booking-mark-paid'),
]
