from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .location_views import CityListView, CityLocalityListView
from .views import HostelViewSet

router = DefaultRouter()
router.register(r'', HostelViewSet, basename='hostels')

urlpatterns = [
    path('cities/', CityListView.as_view(), name='city-list'),
    path('cities/<slug:slug>/localities/', CityLocalityListView.as_view(), name='city-locality-list'),
    path('hostels/', include(router.urls)),
]
