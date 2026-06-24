from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaymentViewSet, PaymentSummaryView

router = DefaultRouter()
router.register(r'', PaymentViewSet, basename='payments')

urlpatterns = [
    path('payments/summary/', PaymentSummaryView.as_view(), name='payment-summary'),
    path('payments/', include(router.urls)),
]
