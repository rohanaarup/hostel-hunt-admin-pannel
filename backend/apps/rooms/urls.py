from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RoomViewSet

router = DefaultRouter()
# Handles both /api/v1/hostels/{hostel_id}/rooms/ and /api/v1/rooms/ (if accessed directly, but typically nested)
router.register(r'', RoomViewSet, basename='rooms')

urlpatterns = [
    # Optional nested routing if accessed directly under rooms app, though typically included in a master urls.py
    path('hostels/<uuid:hostel_id>/rooms/', include(router.urls)),
]
