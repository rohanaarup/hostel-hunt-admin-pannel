from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import BookingViewSet, MyBookingListView, MyBookingDetailView

router = DefaultRouter()
router.register(r'bookings', BookingViewSet, basename='booking')

urlpatterns = [
    # Must come before router.urls: Booking's pk is a UUID but the
    # router's default lookup regex isn't UUID-restricted, so it would
    # otherwise also match the literal "my" segment.
    path('bookings/my/', MyBookingListView.as_view(), name='my-booking-list'),
    path('bookings/my/<uuid:pk>/', MyBookingDetailView.as_view(), name='my-booking-detail'),
] + router.urls
