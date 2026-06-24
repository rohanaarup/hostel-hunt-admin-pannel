from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import HostelViewSet

router = DefaultRouter()
router.register(r'', HostelViewSet, basename='hostels')

urlpatterns = [
    path('hostels/', include(router.urls)),
]
